"""
전체 코인 스캐너 모듈
업비트의 모든 KRW 마켓 코인을 스캔하여 조건에 맞는 코인을 찾습니다.
"""
import pyupbit
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from upbit_client import upbit_client
from config import VOLATILITY_K, RSI_OVERSOLD, RSI_OVERBOUGHT


@dataclass
class CoinScore:
    """코인 점수 데이터"""
    ticker: str
    name: str
    price: float
    score: float  # 종합 점수 (0-100)
    signals: Dict[str, bool]
    indicators: Dict[str, float]
    volume_24h: float
    change_rate: float
    volatility: float
    recommendation: str  # 'strong_buy', 'buy', 'hold', 'sell', 'strong_sell'
    reasons: List[str]


class CoinScanner:
    """전체 코인 스캐너"""
    
    def __init__(self):
        self.client = upbit_client
        self.scan_results: List[CoinScore] = []
        self.last_scan: Optional[str] = None
        self.excluded_coins = ['KRW-USDT', 'KRW-USDC']  # 스테이블코인 제외
        
    def get_all_krw_tickers(self) -> List[str]:
        """모든 KRW 마켓 코인 목록 조회"""
        try:
            tickers = pyupbit.get_tickers(fiat="KRW")
            # 스테이블코인 제외
            return [t for t in tickers if t not in self.excluded_coins]
        except Exception as e:
            print(f"마켓 목록 조회 실패: {e}")
            return []
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """RSI 계산"""
        try:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
        except:
            return 50
    
    def calculate_macd(self, df: pd.DataFrame) -> Tuple[float, float, float]:
        """MACD 계산"""
        try:
            exp12 = df['close'].ewm(span=12, adjust=False).mean()
            exp26 = df['close'].ewm(span=26, adjust=False).mean()
            macd = exp12 - exp26
            signal = macd.ewm(span=9, adjust=False).mean()
            histogram = macd - signal
            return macd.iloc[-1], signal.iloc[-1], histogram.iloc[-1]
        except:
            return 0, 0, 0
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20) -> Tuple[float, float, float]:
        """볼린저 밴드 계산"""
        try:
            middle = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            upper = middle + (std * 2)
            lower = middle - (std * 2)
            return upper.iloc[-1], middle.iloc[-1], lower.iloc[-1]
        except:
            return 0, 0, 0
    
    def calculate_volatility_breakout_target(self, df: pd.DataFrame, k: float = VOLATILITY_K) -> float:
        """변동성 돌파 목표가 계산"""
        try:
            if len(df) < 2:
                return 0
            yesterday = df.iloc[-2]
            today_open = df.iloc[-1]['open']
            range_val = yesterday['high'] - yesterday['low']
            return today_open + range_val * k
        except:
            return 0
    
    def calculate_moving_averages(self, df: pd.DataFrame) -> Dict[str, float]:
        """이동평균 계산"""
        try:
            ma5 = df['close'].rolling(5).mean().iloc[-1]
            ma10 = df['close'].rolling(10).mean().iloc[-1]
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            ma60 = df['close'].rolling(60).mean().iloc[-1] if len(df) >= 60 else ma20
            return {'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60}
        except:
            return {'ma5': 0, 'ma10': 0, 'ma20': 0, 'ma60': 0}
    
    def analyze_coin(self, ticker: str) -> Optional[CoinScore]:
        """개별 코인 분석"""
        try:
            # OHLCV 데이터 조회
            df = pyupbit.get_ohlcv(ticker, interval="day", count=100)
            if df is None or len(df) < 20:
                return None
            
            current_price = df['close'].iloc[-1]
            
            # 거래량 및 변동률
            volume_24h = df['volume'].iloc[-1] * current_price
            change_rate = ((current_price - df['close'].iloc[-2]) / df['close'].iloc[-2]) * 100
            
            # 변동성 계산
            volatility = (df['high'].iloc[-1] - df['low'].iloc[-1]) / df['close'].iloc[-2] * 100
            
            # 기술적 지표 계산
            rsi = self.calculate_rsi(df)
            macd, macd_signal, macd_hist = self.calculate_macd(df)
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df)
            target_price = self.calculate_volatility_breakout_target(df)
            mas = self.calculate_moving_averages(df)
            
            # 시그널 생성
            signals = {
                'volatility_breakout': current_price > target_price if target_price > 0 else False,
                'rsi_oversold': rsi < RSI_OVERSOLD,
                'rsi_overbought': rsi > RSI_OVERBOUGHT,
                'macd_bullish': macd_hist > 0 and macd > macd_signal,
                'macd_bearish': macd_hist < 0 and macd < macd_signal,
                'golden_cross': mas['ma5'] > mas['ma20'] and df['close'].iloc[-2] <= df['close'].rolling(20).mean().iloc[-2],
                'above_ma20': current_price > mas['ma20'],
                'bollinger_lower': current_price < bb_lower,
                'bollinger_upper': current_price > bb_upper,
                'volume_surge': df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1] * 1.5,
            }
            
            # 점수 계산 (0-100)
            score = 50  # 기본 점수
            reasons = []
            
            # 변동성 돌파
            if signals['volatility_breakout']:
                score += 15
                reasons.append("🔥 변동성 돌파 시그널")
            
            # RSI
            if signals['rsi_oversold']:
                score += 15
                reasons.append(f"📉 RSI 과매도 ({rsi:.1f})")
            elif signals['rsi_overbought']:
                score -= 15
                reasons.append(f"📈 RSI 과매수 ({rsi:.1f})")
            elif 40 <= rsi <= 60:
                score += 5
                reasons.append(f"✅ RSI 중립 ({rsi:.1f})")
            
            # MACD
            if signals['macd_bullish']:
                score += 10
                reasons.append("📊 MACD 상승 신호")
            elif signals['macd_bearish']:
                score -= 10
            
            # 이동평균
            if signals['golden_cross']:
                score += 15
                reasons.append("⭐ 골든크로스 발생")
            if signals['above_ma20']:
                score += 5
            
            # 볼린저 밴드
            if signals['bollinger_lower']:
                score += 10
                reasons.append("💎 볼린저 하단 터치")
            elif signals['bollinger_upper']:
                score -= 10
            
            # 거래량
            if signals['volume_surge']:
                score += 5
                reasons.append("📈 거래량 급증")
            
            # 변동성 보너스/페널티
            if 2 <= volatility <= 8:
                score += 5
                reasons.append(f"⚡ 적정 변동성 ({volatility:.1f}%)")
            elif volatility > 15:
                score -= 5
            
            # 점수 범위 제한
            score = max(0, min(100, score))
            
            # 추천 결정
            if score >= 75:
                recommendation = 'strong_buy'
            elif score >= 60:
                recommendation = 'buy'
            elif score >= 40:
                recommendation = 'hold'
            elif score >= 25:
                recommendation = 'sell'
            else:
                recommendation = 'strong_sell'
            
            # 지표 저장
            indicators = {
                'rsi': round(rsi, 2),
                'macd': round(macd, 2),
                'macd_signal': round(macd_signal, 2),
                'macd_hist': round(macd_hist, 2),
                'bb_upper': round(bb_upper, 0),
                'bb_middle': round(bb_middle, 0),
                'bb_lower': round(bb_lower, 0),
                'target_price': round(target_price, 0),
                **{k: round(v, 0) for k, v in mas.items()}
            }
            
            return CoinScore(
                ticker=ticker,
                name=ticker.replace('KRW-', ''),
                price=current_price,
                score=round(score, 1),
                signals=signals,
                indicators=indicators,
                volume_24h=volume_24h,
                change_rate=round(change_rate, 2),
                volatility=round(volatility, 2),
                recommendation=recommendation,
                reasons=reasons
            )
            
        except Exception as e:
            print(f"{ticker} 분석 실패: {e}")
            return None
    
    def scan_all_coins(self, min_volume: float = 1_000_000_000, max_workers: int = 10) -> List[CoinScore]:
        """
        전체 코인 스캔
        
        Args:
            min_volume: 최소 거래대금 (기본 10억원)
            max_workers: 병렬 처리 스레드 수
        """
        print(f"[{datetime.now()}] 전체 코인 스캔 시작...")
        
        tickers = self.get_all_krw_tickers()
        print(f"총 {len(tickers)}개 코인 분석 중...")
        
        results = []
        
        # 병렬 처리
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.analyze_coin, ticker): ticker for ticker in tickers}
            
            for future in as_completed(futures):
                result = future.result()
                if result and result.volume_24h >= min_volume:
                    results.append(result)
        
        # 점수순 정렬
        results.sort(key=lambda x: x.score, reverse=True)
        
        self.scan_results = results
        self.last_scan = datetime.now().isoformat()
        
        print(f"[{datetime.now()}] 스캔 완료: {len(results)}개 코인 (거래대금 {min_volume/1e8:.0f}억 이상)")
        
        return results
    
    def get_top_coins(self, n: int = 10) -> List[CoinScore]:
        """상위 N개 코인 반환"""
        return self.scan_results[:n]
    
    def get_buy_candidates(self, min_score: float = 60) -> List[CoinScore]:
        """매수 후보 코인 반환"""
        return [c for c in self.scan_results if c.score >= min_score and c.recommendation in ['buy', 'strong_buy']]
    
    def get_volatility_breakout_coins(self) -> List[CoinScore]:
        """변동성 돌파 조건 충족 코인"""
        return [c for c in self.scan_results if c.signals.get('volatility_breakout', False)]
    
    def get_rsi_oversold_coins(self) -> List[CoinScore]:
        """RSI 과매도 코인"""
        return [c for c in self.scan_results if c.signals.get('rsi_oversold', False)]
    
    def get_golden_cross_coins(self) -> List[CoinScore]:
        """골든크로스 발생 코인"""
        return [c for c in self.scan_results if c.signals.get('golden_cross', False)]
    
    def to_dict_list(self, coins: List[CoinScore] = None) -> List[Dict[str, Any]]:
        """결과를 딕셔너리 리스트로 변환"""
        coins = coins or self.scan_results
        result = []
        for c in coins:
            # numpy 타입을 Python 네이티브 타입으로 변환
            signals = {k: bool(v) for k, v in c.signals.items()}
            indicators = {k: float(v) if not pd.isna(v) else 0 for k, v in c.indicators.items()}
            
            result.append({
                'ticker': c.ticker,
                'name': c.name,
                'price': float(c.price) if not pd.isna(c.price) else 0,
                'score': float(c.score),
                'signals': signals,
                'indicators': indicators,
                'volume_24h': float(c.volume_24h) if not pd.isna(c.volume_24h) else 0,
                'change_rate': float(c.change_rate) if not pd.isna(c.change_rate) else 0,
                'volatility': float(c.volatility) if not pd.isna(c.volatility) else 0,
                'recommendation': c.recommendation,
                'reasons': c.reasons
            })
        return result


# 싱글톤 인스턴스
coin_scanner = CoinScanner()

