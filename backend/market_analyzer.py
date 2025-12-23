"""
시장 상태 분석 모듈
현재 시장 상황을 분석하여 최적의 매매 전략을 추천합니다.
"""
import pyupbit
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class MarketCondition(Enum):
    """시장 상태"""
    STRONG_UPTREND = "strong_uptrend"      # 강한 상승세
    UPTREND = "uptrend"                     # 상승세
    SIDEWAYS = "sideways"                   # 횡보
    DOWNTREND = "downtrend"                 # 하락세
    STRONG_DOWNTREND = "strong_downtrend"  # 강한 하락세
    HIGH_VOLATILITY = "high_volatility"    # 고변동성
    LOW_VOLATILITY = "low_volatility"      # 저변동성


class RecommendedStrategy(Enum):
    """추천 전략"""
    VOLATILITY_BREAKOUT = "volatility"     # 변동성 돌파
    MOVING_AVERAGE = "moving_average"      # 이동평균 교차
    RSI = "rsi"                            # RSI 과매수/과매도
    COMBINED = "combined"                  # 복합 전략
    HOLD = "hold"                          # 관망


@dataclass
class MarketAnalysis:
    """시장 분석 결과"""
    ticker: str
    condition: MarketCondition
    recommended_strategy: RecommendedStrategy
    confidence: float  # 0-100
    
    # 지표들
    trend_strength: float  # -100 ~ 100 (음수: 하락, 양수: 상승)
    volatility: float      # 변동성 (%)
    rsi: float
    volume_ratio: float    # 평균 대비 거래량 비율
    
    # 추가 분석
    support_level: float   # 지지선
    resistance_level: float  # 저항선
    
    reasons: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticker': self.ticker,
            'condition': self.condition.value,
            'recommended_strategy': self.recommended_strategy.value,
            'confidence': self.confidence,
            'trend_strength': self.trend_strength,
            'volatility': self.volatility,
            'rsi': self.rsi,
            'volume_ratio': self.volume_ratio,
            'support_level': self.support_level,
            'resistance_level': self.resistance_level,
            'reasons': self.reasons
        }


class MarketAnalyzer:
    """시장 분석기"""
    
    def __init__(self):
        self.cache: Dict[str, MarketAnalysis] = {}
        self.last_analysis: Optional[str] = None
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """RSI 계산"""
        try:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
        except:
            return 50
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """ATR (Average True Range) 계산 - 변동성 지표"""
        try:
            high = df['high']
            low = df['low']
            close = df['close'].shift(1)
            
            tr1 = high - low
            tr2 = abs(high - close)
            tr3 = abs(low - close)
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            
            return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0
        except:
            return 0
    
    def calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """
        추세 강도 계산 (-100 ~ 100)
        ADX와 이동평균 기울기를 결합
        """
        try:
            # 이동평균 기울기
            ma20 = df['close'].rolling(20).mean()
            ma_slope = (ma20.iloc[-1] - ma20.iloc[-5]) / ma20.iloc[-5] * 100
            
            # 단기 vs 장기 이동평균
            ma5 = df['close'].rolling(5).mean()
            ma_diff = (ma5.iloc[-1] - ma20.iloc[-1]) / ma20.iloc[-1] * 100
            
            # 최근 가격 변화
            price_change = (df['close'].iloc[-1] - df['close'].iloc[-10]) / df['close'].iloc[-10] * 100
            
            # 종합 점수 (가중 평균)
            trend_score = (ma_slope * 0.4) + (ma_diff * 0.3) + (price_change * 0.3)
            
            # -100 ~ 100 범위로 제한
            return max(-100, min(100, trend_score * 5))
        except:
            return 0
    
    def find_support_resistance(self, df: pd.DataFrame) -> Tuple[float, float]:
        """지지선/저항선 계산"""
        try:
            recent = df.tail(20)
            
            # 피봇 포인트 기반
            pivot = (recent['high'].max() + recent['low'].min() + recent['close'].iloc[-1]) / 3
            support = 2 * pivot - recent['high'].max()
            resistance = 2 * pivot - recent['low'].min()
            
            return float(support), float(resistance)
        except:
            return 0, 0
    
    def analyze_ticker(self, ticker: str) -> MarketAnalysis:
        """개별 코인 시장 분석"""
        try:
            # OHLCV 데이터 조회
            df = pyupbit.get_ohlcv(ticker, interval="day", count=60)
            if df is None or len(df) < 30:
                return self._default_analysis(ticker)
            
            current_price = float(df['close'].iloc[-1])
            
            # 기술적 지표 계산
            rsi = self.calculate_rsi(df)
            atr = self.calculate_atr(df)
            volatility = (atr / current_price) * 100  # % 변동성
            trend_strength = self.calculate_trend_strength(df)
            support, resistance = self.find_support_resistance(df)
            
            # 거래량 분석
            avg_volume = df['volume'].rolling(20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            volume_ratio = float(current_volume / avg_volume) if avg_volume > 0 else 1
            
            # 시장 상태 결정
            condition = self._determine_condition(trend_strength, volatility, rsi)
            
            # 최적 전략 추천
            strategy, confidence, reasons = self._recommend_strategy(
                condition, trend_strength, volatility, rsi, volume_ratio,
                current_price, support, resistance
            )
            
            analysis = MarketAnalysis(
                ticker=ticker,
                condition=condition,
                recommended_strategy=strategy,
                confidence=confidence,
                trend_strength=round(trend_strength, 2),
                volatility=round(volatility, 2),
                rsi=round(rsi, 2),
                volume_ratio=round(volume_ratio, 2),
                support_level=round(support, 0),
                resistance_level=round(resistance, 0),
                reasons=reasons
            )
            
            self.cache[ticker] = analysis
            self.last_analysis = datetime.now().isoformat()
            
            return analysis
            
        except Exception as e:
            print(f"시장 분석 실패 ({ticker}): {e}")
            return self._default_analysis(ticker)
    
    def _determine_condition(self, trend: float, volatility: float, rsi: float) -> MarketCondition:
        """시장 상태 결정"""
        # 변동성 체크
        if volatility > 8:
            return MarketCondition.HIGH_VOLATILITY
        if volatility < 2:
            return MarketCondition.LOW_VOLATILITY
        
        # 추세 체크
        if trend > 30:
            return MarketCondition.STRONG_UPTREND
        elif trend > 10:
            return MarketCondition.UPTREND
        elif trend < -30:
            return MarketCondition.STRONG_DOWNTREND
        elif trend < -10:
            return MarketCondition.DOWNTREND
        else:
            return MarketCondition.SIDEWAYS
    
    def _recommend_strategy(
        self, condition: MarketCondition, trend: float, 
        volatility: float, rsi: float, volume_ratio: float,
        price: float, support: float, resistance: float
    ) -> Tuple[RecommendedStrategy, float, List[str]]:
        """최적 전략 추천"""
        reasons = []
        scores = {
            RecommendedStrategy.VOLATILITY_BREAKOUT: 0,
            RecommendedStrategy.MOVING_AVERAGE: 0,
            RecommendedStrategy.RSI: 0,
            RecommendedStrategy.COMBINED: 0,
            RecommendedStrategy.HOLD: 0,
        }
        
        # 1. 변동성 돌파 전략 점수
        if condition == MarketCondition.HIGH_VOLATILITY:
            scores[RecommendedStrategy.VOLATILITY_BREAKOUT] += 30
            reasons.append("🔥 고변동성 시장 - 변동성 돌파 유리")
        if 3 <= volatility <= 8:
            scores[RecommendedStrategy.VOLATILITY_BREAKOUT] += 20
            reasons.append(f"⚡ 적정 변동성 ({volatility:.1f}%)")
        if volume_ratio > 1.5:
            scores[RecommendedStrategy.VOLATILITY_BREAKOUT] += 15
            reasons.append(f"📊 거래량 급증 (평균 {volume_ratio:.1f}배)")
        
        # 2. 이동평균 교차 전략 점수
        if condition in [MarketCondition.UPTREND, MarketCondition.STRONG_UPTREND]:
            scores[RecommendedStrategy.MOVING_AVERAGE] += 30
            reasons.append("📈 상승 추세 - 이평선 매매 유리")
        if condition in [MarketCondition.DOWNTREND, MarketCondition.STRONG_DOWNTREND]:
            scores[RecommendedStrategy.MOVING_AVERAGE] += 20
            reasons.append("📉 하락 추세 - 이평선 매매 (숏/관망)")
        if abs(trend) > 20:
            scores[RecommendedStrategy.MOVING_AVERAGE] += 15
            reasons.append(f"🎯 추세 강도 {abs(trend):.0f}")
        
        # 3. RSI 전략 점수
        if rsi < 30:
            scores[RecommendedStrategy.RSI] += 40
            reasons.append(f"💎 RSI 과매도 ({rsi:.0f}) - 반등 기대")
        elif rsi > 70:
            scores[RecommendedStrategy.RSI] += 35
            reasons.append(f"⚠️ RSI 과매수 ({rsi:.0f}) - 조정 주의")
        elif condition == MarketCondition.SIDEWAYS and 40 <= rsi <= 60:
            scores[RecommendedStrategy.RSI] += 25
            reasons.append("📊 횡보장 RSI 전략 유효")
        
        # 4. 복합 전략 점수
        if condition == MarketCondition.SIDEWAYS:
            scores[RecommendedStrategy.COMBINED] += 25
            reasons.append("🔄 횡보장 - 복합 전략 추천")
        if condition == MarketCondition.LOW_VOLATILITY:
            scores[RecommendedStrategy.COMBINED] += 20
        
        # 불확실한 상황에서 관망
        max_score = max(scores.values())
        if max_score < 30:
            scores[RecommendedStrategy.HOLD] += 40
            reasons.append("⏸️ 명확한 시그널 없음 - 관망 추천")
        
        # 지지/저항 근처 체크
        if support > 0 and price < support * 1.02:
            scores[RecommendedStrategy.RSI] += 10
            reasons.append(f"🛡️ 지지선 근접 ({support:,.0f})")
        if resistance > 0 and price > resistance * 0.98:
            reasons.append(f"🚧 저항선 근접 ({resistance:,.0f})")
        
        # 최고 점수 전략 선택
        best_strategy = max(scores, key=scores.get)
        confidence = min(100, scores[best_strategy] + 20)
        
        return best_strategy, confidence, reasons
    
    def _default_analysis(self, ticker: str) -> MarketAnalysis:
        """기본 분석 결과"""
        return MarketAnalysis(
            ticker=ticker,
            condition=MarketCondition.SIDEWAYS,
            recommended_strategy=RecommendedStrategy.HOLD,
            confidence=30,
            trend_strength=0,
            volatility=0,
            rsi=50,
            volume_ratio=1,
            support_level=0,
            resistance_level=0,
            reasons=["⚠️ 데이터 부족 - 관망 추천"]
        )
    
    def get_best_strategy_for_market(self, tickers: List[str] = None) -> Dict[str, Any]:
        """
        여러 코인을 분석하여 전체 시장에 최적인 전략 추천
        """
        if tickers is None:
            tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
        
        analyses = [self.analyze_ticker(t) for t in tickers]
        
        # 전략별 추천 횟수 집계
        strategy_counts = {}
        total_confidence = {}
        all_reasons = []
        
        for analysis in analyses:
            strategy = analysis.recommended_strategy
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
            total_confidence[strategy] = total_confidence.get(strategy, 0) + analysis.confidence
            all_reasons.extend([f"[{analysis.ticker.replace('KRW-', '')}] {r}" for r in analysis.reasons[:2]])
        
        # 가장 많이 추천된 전략
        best_strategy = max(strategy_counts, key=strategy_counts.get)
        avg_confidence = total_confidence[best_strategy] / strategy_counts[best_strategy]
        
        # 시장 전체 상태 요약
        avg_volatility = sum(a.volatility for a in analyses) / len(analyses)
        avg_trend = sum(a.trend_strength for a in analyses) / len(analyses)
        avg_rsi = sum(a.rsi for a in analyses) / len(analyses)
        
        return {
            'best_strategy': best_strategy.value,
            'confidence': round(avg_confidence, 1),
            'strategy_votes': {k.value: v for k, v in strategy_counts.items()},
            'market_summary': {
                'avg_volatility': round(avg_volatility, 2),
                'avg_trend': round(avg_trend, 2),
                'avg_rsi': round(avg_rsi, 2),
            },
            'reasons': all_reasons[:6],
            'individual_analyses': [a.to_dict() for a in analyses],
            'analyzed_at': datetime.now().isoformat()
        }


# 싱글톤 인스턴스
market_analyzer = MarketAnalyzer()



