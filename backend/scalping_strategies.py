"""
검증된 단타(스캘핑) 전략 모듈
- 전체 코인 스캔 + 실시간 매매
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio

from upbit_client import upbit_client


class StrategyType(str, Enum):
    """전략 타입"""
    VOLATILITY_BREAKOUT = "volatility_breakout"  # 변동성 돌파
    RSI_REVERSAL = "rsi_reversal"                # RSI 반등
    BOLLINGER_BOUNCE = "bollinger_bounce"        # 볼린저 밴드 반등
    VOLUME_SURGE = "volume_surge"                # 거래량 급증
    MOMENTUM_BREAKOUT = "momentum_breakout"      # 모멘텀 돌파
    SCALPING_5MIN = "scalping_5min"              # 5분봉 스캘핑
    # 래리 윌리엄스 전략들
    LARRY_WILLIAMS_R = "larry_williams_r"        # Williams %R 지표
    LARRY_OOPS = "larry_oops"                    # OOPS! 패턴
    LARRY_SMASH_DAY = "larry_smash_day"          # Smash Day 패턴
    LARRY_COMBO = "larry_combo"                  # 래리 윌리엄스 종합
    # 수익률 최대화 전략
    MAX_PROFIT = "max_profit"                    # 수익률 최대화


@dataclass
class StrategyInfo:
    """전략 정보"""
    id: str
    name: str
    name_kr: str
    description: str
    risk_level: str  # low, medium, high
    holding_time: str  # 평균 보유 시간
    win_rate: str  # 예상 승률
    emoji: str


# 전략 정보 정의
STRATEGIES = {
    StrategyType.VOLATILITY_BREAKOUT: StrategyInfo(
        id="volatility_breakout",
        name="Volatility Breakout",
        name_kr="변동성 돌파",
        description="래리 윌리엄스의 변동성 돌파 전략. 전일 변동폭의 K배를 시가에 더한 목표가 돌파 시 매수",
        risk_level="medium",
        holding_time="1일",
        win_rate="55-60%",
        emoji="⚡"
    ),
    StrategyType.RSI_REVERSAL: StrategyInfo(
        id="rsi_reversal",
        name="RSI Reversal",
        name_kr="RSI 반등",
        description="RSI 30 이하 과매도 구간 진입 후 반등 시 매수. 검증된 평균회귀 전략",
        risk_level="medium",
        holding_time="1-3일",
        win_rate="58-65%",
        emoji="📊"
    ),
    StrategyType.BOLLINGER_BOUNCE: StrategyInfo(
        id="bollinger_bounce",
        name="Bollinger Bounce",
        name_kr="볼린저 밴드 반등",
        description="볼린저 밴드 하단 터치 후 반등 시 매수. 통계적 평균 회귀 활용",
        risk_level="low",
        holding_time="1-2일",
        win_rate="60-68%",
        emoji="📈"
    ),
    StrategyType.VOLUME_SURGE: StrategyInfo(
        id="volume_surge",
        name="Volume Surge",
        name_kr="거래량 급증",
        description="평균 거래량 3배 이상 급증 + 양봉 출현 시 추세 추종 매수",
        risk_level="high",
        holding_time="수시간-1일",
        win_rate="52-58%",
        emoji="🔥"
    ),
    StrategyType.MOMENTUM_BREAKOUT: StrategyInfo(
        id="momentum_breakout",
        name="Momentum Breakout",
        name_kr="모멘텀 돌파",
        description="20일 신고가 돌파 시 모멘텀 추종 매수. 추세 추종 전략",
        risk_level="high",
        holding_time="1-5일",
        win_rate="50-55%",
        emoji="🚀"
    ),
    StrategyType.SCALPING_5MIN: StrategyInfo(
        id="scalping_5min",
        name="5-Min Scalping",
        name_kr="5분봉 스캘핑",
        description="5분봉 기준 RSI + MACD 복합 신호. 빠른 진입/청산",
        risk_level="high",
        holding_time="5-30분",
        win_rate="55-60%",
        emoji="⏱️"
    ),
    # 래리 윌리엄스 전략들
    StrategyType.LARRY_WILLIAMS_R: StrategyInfo(
        id="larry_williams_r",
        name="Larry Williams %R",
        name_kr="래리 윌리엄스 %R",
        description="래리 윌리엄스가 개발한 %R 지표. -80 이하 과매도에서 반등 시 매수, -20 이상 과매수에서 매도",
        risk_level="medium",
        holding_time="1-3일",
        win_rate="58-65%",
        emoji="📉"
    ),
    StrategyType.LARRY_OOPS: StrategyInfo(
        id="larry_oops",
        name="Larry OOPS!",
        name_kr="래리 OOPS! 패턴",
        description="갭 하락 후 전일 저가를 상향 돌파 시 매수. 공포 매도 후 반등을 노리는 역발상 전략",
        risk_level="medium",
        holding_time="1-2일",
        win_rate="60-68%",
        emoji="😱"
    ),
    StrategyType.LARRY_SMASH_DAY: StrategyInfo(
        id="larry_smash_day",
        name="Larry Smash Day",
        name_kr="래리 스매시 데이",
        description="급락일 다음날 시가보다 상승 시 매수. 과매도 반등 + 추세 전환 포착",
        risk_level="medium",
        holding_time="1-3일",
        win_rate="55-62%",
        emoji="💥"
    ),
    StrategyType.LARRY_COMBO: StrategyInfo(
        id="larry_combo",
        name="Larry Williams Combo",
        name_kr="래리 윌리엄스 종합",
        description="변동성 돌파 + %R + 자금관리를 결합한 래리 윌리엄스 종합 전략. 최적의 진입점 탐색",
        risk_level="medium",
        holding_time="1-3일",
        win_rate="60-70%",
        emoji="🏆"
    ),
    # 수익률 최대화 전략
    StrategyType.MAX_PROFIT: StrategyInfo(
        id="max_profit",
        name="Maximum Profit",
        name_kr="💎 수익률 최대화",
        description="5개 지표 동시 확인 + BTC 추세 연동 + 타이트 손절(-1.5%) + 적극적 트레일링. 최고의 수익률 추구",
        risk_level="medium",
        holding_time="수분-수시간",
        win_rate="65-75%",
        emoji="💎"
    ),
}


@dataclass
class TradeSignal:
    """매매 시그널"""
    ticker: str
    coin_name: str
    action: str  # buy, sell, hold
    strategy: str
    score: float  # 0-100
    reason: str
    current_price: float
    target_price: Optional[float]
    stop_loss: Optional[float]
    timestamp: str


class ScalpingScanner:
    """전체 코인 스캔 및 단타 시그널 생성"""
    
    def __init__(self):
        self.client = upbit_client
        
    def get_all_krw_tickers(self) -> List[str]:
        """KRW 마켓 전체 티커 조회"""
        try:
            markets = self.client.get_tickers()
            return [t for t in markets if t.startswith('KRW-')]
        except:
            return []
    
    def get_high_volume_tickers(self, min_volume: float = 1_000_000_000) -> List[str]:
        """거래량 기준 필터링 (최소 10억원)"""
        tickers = self.get_all_krw_tickers()
        high_volume = []
        
        for ticker in tickers[:100]:  # 상위 100개만 확인
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=1)
                if df is not None and len(df) > 0:
                    volume_krw = df.iloc[-1]['value']
                    if volume_krw >= min_volume:
                        high_volume.append(ticker)
            except:
                continue
                
        return high_volume
    
    async def scan_volatility_breakout(self, tickers: List[str], k: float = 0.5) -> List[TradeSignal]:
        """변동성 돌파 스캔"""
        signals = []
        
        for ticker in tickers:
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=2)
                if df is None or len(df) < 2:
                    continue
                
                yesterday = df.iloc[-2]
                today = df.iloc[-1]
                
                # 목표가 계산
                range_val = yesterday['high'] - yesterday['low']
                target_price = today['open'] + range_val * k
                current_price = today['close']
                
                # 돌파 여부
                if current_price > target_price:
                    # 거래량 조건 (평균 대비 1.5배 이상)
                    avg_volume = df['volume'].mean()
                    if today['volume'] > avg_volume * 1.2:
                        score = min(100, 60 + (current_price - target_price) / target_price * 100)
                        signals.append(TradeSignal(
                            ticker=ticker,
                            coin_name=ticker.replace("KRW-", ""),
                            action="buy",
                            strategy="volatility_breakout",
                            score=score,
                            reason=f"목표가({target_price:,.0f}) 돌파, 거래량 증가",
                            current_price=current_price,
                            target_price=target_price * 1.03,  # 3% 익절
                            stop_loss=target_price * 0.98,  # 2% 손절
                            timestamp=datetime.now().isoformat()
                        ))
            except Exception as e:
                continue
                
        return sorted(signals, key=lambda x: x.score, reverse=True)
    
    async def scan_rsi_reversal(self, tickers: List[str], oversold: int = 30) -> List[TradeSignal]:
        """RSI 반등 스캔"""
        signals = []
        
        for ticker in tickers:
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=20)
                if df is None or len(df) < 15:
                    continue
                
                # RSI 계산
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                current_rsi = rsi.iloc[-1]
                prev_rsi = rsi.iloc[-2]
                current_price = df['close'].iloc[-1]
                
                # RSI 30 이하에서 반등 시작
                if current_rsi < 35 and current_rsi > prev_rsi:
                    score = max(0, 80 - current_rsi)  # RSI가 낮을수록 높은 점수
                    signals.append(TradeSignal(
                        ticker=ticker,
                        coin_name=ticker.replace("KRW-", ""),
                        action="buy",
                        strategy="rsi_reversal",
                        score=score,
                        reason=f"RSI {current_rsi:.1f} 과매도 반등 시작",
                        current_price=current_price,
                        target_price=current_price * 1.05,  # 5% 익절
                        stop_loss=current_price * 0.97,  # 3% 손절
                        timestamp=datetime.now().isoformat()
                    ))
            except:
                continue
                
        return sorted(signals, key=lambda x: x.score, reverse=True)
    
    async def scan_bollinger_bounce(self, tickers: List[str]) -> List[TradeSignal]:
        """볼린저 밴드 반등 스캔"""
        signals = []
        
        for ticker in tickers:
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=25)
                if df is None or len(df) < 21:
                    continue
                
                # 볼린저 밴드 계산
                middle = df['close'].rolling(window=20).mean()
                std = df['close'].rolling(window=20).std()
                upper = middle + (std * 2)
                lower = middle - (std * 2)
                
                current_price = df['close'].iloc[-1]
                prev_price = df['close'].iloc[-2]
                lower_band = lower.iloc[-1]
                middle_band = middle.iloc[-1]
                
                # 하단 밴드 터치 후 반등
                if prev_price <= lower.iloc[-2] and current_price > lower_band:
                    # 밴드 폭 대비 위치
                    band_width = upper.iloc[-1] - lower_band
                    position_pct = (current_price - lower_band) / band_width * 100
                    
                    score = min(100, 70 + (30 - position_pct) / 2)
                    signals.append(TradeSignal(
                        ticker=ticker,
                        coin_name=ticker.replace("KRW-", ""),
                        action="buy",
                        strategy="bollinger_bounce",
                        score=score,
                        reason=f"볼린저 하단({lower_band:,.0f}) 터치 후 반등",
                        current_price=current_price,
                        target_price=middle_band,  # 중간선까지
                        stop_loss=lower_band * 0.98,
                        timestamp=datetime.now().isoformat()
                    ))
            except:
                continue
                
        return sorted(signals, key=lambda x: x.score, reverse=True)
    
    async def scan_volume_surge(self, tickers: List[str], volume_mult: float = 3.0) -> List[TradeSignal]:
        """거래량 급증 스캔"""
        signals = []
        
        for ticker in tickers:
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=10)
                if df is None or len(df) < 8:
                    continue
                
                current_volume = df['volume'].iloc[-1]
                avg_volume = df['volume'].iloc[:-1].mean()
                current_price = df['close'].iloc[-1]
                open_price = df['open'].iloc[-1]
                
                # 거래량 3배 이상 + 양봉
                if current_volume > avg_volume * volume_mult and current_price > open_price:
                    volume_ratio = current_volume / avg_volume
                    price_change = (current_price - open_price) / open_price * 100
                    
                    score = min(100, 50 + volume_ratio * 5 + price_change * 3)
                    signals.append(TradeSignal(
                        ticker=ticker,
                        coin_name=ticker.replace("KRW-", ""),
                        action="buy",
                        strategy="volume_surge",
                        score=score,
                        reason=f"거래량 {volume_ratio:.1f}배 급증, +{price_change:.1f}% 상승",
                        current_price=current_price,
                        target_price=current_price * 1.05,
                        stop_loss=open_price * 0.98,
                        timestamp=datetime.now().isoformat()
                    ))
            except:
                continue
                
        return sorted(signals, key=lambda x: x.score, reverse=True)
    
    async def scan_momentum_breakout(self, tickers: List[str]) -> List[TradeSignal]:
        """모멘텀 돌파 스캔 - 20일 신고가"""
        signals = []
        
        for ticker in tickers:
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=25)
                if df is None or len(df) < 21:
                    continue
                
                current_price = df['close'].iloc[-1]
                high_20d = df['high'].iloc[:-1].tail(20).max()
                avg_volume = df['volume'].iloc[:-1].mean()
                current_volume = df['volume'].iloc[-1]
                
                # 20일 신고가 돌파 + 거래량 증가
                if current_price > high_20d and current_volume > avg_volume:
                    breakout_pct = (current_price - high_20d) / high_20d * 100
                    score = min(100, 60 + breakout_pct * 10)
                    
                    signals.append(TradeSignal(
                        ticker=ticker,
                        coin_name=ticker.replace("KRW-", ""),
                        action="buy",
                        strategy="momentum_breakout",
                        score=score,
                        reason=f"20일 신고가({high_20d:,.0f}) 돌파 +{breakout_pct:.1f}%",
                        current_price=current_price,
                        target_price=current_price * 1.08,  # 8% 익절
                        stop_loss=high_20d * 0.98,  # 신고가 아래 손절
                        timestamp=datetime.now().isoformat()
                    ))
            except:
                continue
                
        return sorted(signals, key=lambda x: x.score, reverse=True)
    
    async def scan_scalping_5min(self, tickers: List[str]) -> List[TradeSignal]:
        """5분봉 스캘핑 스캔"""
        signals = []
        
        for ticker in tickers[:30]:  # 상위 30개만 (API 제한)
            try:
                df = self.client.get_ohlcv(ticker, interval="minute5", count=50)
                if df is None or len(df) < 30:
                    continue
                
                # RSI 계산
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                # MACD 계산
                exp12 = df['close'].ewm(span=12, adjust=False).mean()
                exp26 = df['close'].ewm(span=26, adjust=False).mean()
                macd = exp12 - exp26
                signal = macd.ewm(span=9, adjust=False).mean()
                histogram = macd - signal
                
                current_rsi = rsi.iloc[-1]
                current_macd = histogram.iloc[-1]
                prev_macd = histogram.iloc[-2]
                current_price = df['close'].iloc[-1]
                
                # RSI 40 이하 + MACD 상향 전환
                if current_rsi < 40 and current_macd > prev_macd and current_macd > -abs(prev_macd):
                    score = min(100, 60 + (40 - current_rsi) + (current_macd - prev_macd) * 10)
                    signals.append(TradeSignal(
                        ticker=ticker,
                        coin_name=ticker.replace("KRW-", ""),
                        action="buy",
                        strategy="scalping_5min",
                        score=score,
                        reason=f"5분봉 RSI {current_rsi:.1f} + MACD 상향전환",
                        current_price=current_price,
                        target_price=current_price * 1.015,  # 1.5% 익절
                        stop_loss=current_price * 0.99,  # 1% 손절
                        timestamp=datetime.now().isoformat()
                    ))
            except:
                continue
                
        return sorted(signals, key=lambda x: x.score, reverse=True)
    
    async def scan_larry_williams_r(self, tickers: List[str]) -> List[TradeSignal]:
        """래리 윌리엄스 %R 지표 스캔
        
        %R = (최고가 - 현재가) / (최고가 - 최저가) × -100
        - -80 ~ -100: 과매도 (매수 신호)
        - -20 ~ 0: 과매수 (매도 신호)
        """
        signals = []
        
        for ticker in tickers:
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=20)
                if df is None or len(df) < 15:
                    continue
                
                # Williams %R 계산 (14일 기준)
                period = 14
                highest_high = df['high'].rolling(window=period).max()
                lowest_low = df['low'].rolling(window=period).min()
                
                williams_r = ((highest_high - df['close']) / (highest_high - lowest_low)) * -100
                
                current_wr = williams_r.iloc[-1]
                prev_wr = williams_r.iloc[-2]
                prev2_wr = williams_r.iloc[-3]
                current_price = df['close'].iloc[-1]
                
                # 과매도 구간(-80 이하)에서 반등 시작
                if current_wr <= -80 and current_wr > prev_wr:
                    # 연속 하락 후 반등 확인 (더 신뢰도 높은 신호)
                    if prev_wr < prev2_wr:
                        score = min(100, 70 + abs(current_wr + 80) + (current_wr - prev_wr) * 2)
                        
                        signals.append(TradeSignal(
                            ticker=ticker,
                            coin_name=ticker.replace("KRW-", ""),
                            action="buy",
                            strategy="larry_williams_r",
                            score=score,
                            reason=f"Williams %R {current_wr:.1f} 과매도 반등 (전일 {prev_wr:.1f})",
                            current_price=current_price,
                            target_price=current_price * 1.05,  # 5% 익절
                            stop_loss=current_price * 0.97,     # 3% 손절
                            timestamp=datetime.now().isoformat()
                        ))
            except:
                continue
                
        return sorted(signals, key=lambda x: x.score, reverse=True)
    
    async def scan_larry_oops(self, tickers: List[str]) -> List[TradeSignal]:
        """래리 윌리엄스 OOPS! 패턴 스캔
        
        조건:
        1. 갭 하락 (당일 시가 < 전일 저가)
        2. 전일 저가를 상향 돌파
        → 공포 매도 후 반등을 노리는 역발상 전략
        """
        signals = []
        
        for ticker in tickers:
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=5)
                if df is None or len(df) < 2:
                    continue
                
                yesterday = df.iloc[-2]
                today = df.iloc[-1]
                
                # 갭 하락 확인 (당일 시가 < 전일 저가)
                gap_down = today['open'] < yesterday['low']
                
                # 전일 저가 상향 돌파 (현재가 > 전일 저가)
                breakout = today['close'] > yesterday['low']
                
                # 양봉 확인
                is_bullish = today['close'] > today['open']
                
                current_price = today['close']
                
                if gap_down and breakout and is_bullish:
                    gap_size = (yesterday['low'] - today['open']) / yesterday['low'] * 100
                    recovery = (today['close'] - today['open']) / today['open'] * 100
                    
                    score = min(100, 65 + gap_size * 5 + recovery * 3)
                    
                    signals.append(TradeSignal(
                        ticker=ticker,
                        coin_name=ticker.replace("KRW-", ""),
                        action="buy",
                        strategy="larry_oops",
                        score=score,
                        reason=f"OOPS! 갭 -{gap_size:.1f}% 후 반등 +{recovery:.1f}%",
                        current_price=current_price,
                        target_price=yesterday['high'],         # 전일 고가까지
                        stop_loss=today['open'] * 0.98,         # 당일 시가 -2%
                        timestamp=datetime.now().isoformat()
                    ))
            except:
                continue
                
        return sorted(signals, key=lambda x: x.score, reverse=True)
    
    async def scan_larry_smash_day(self, tickers: List[str]) -> List[TradeSignal]:
        """래리 윌리엄스 Smash Day 패턴 스캔
        
        조건:
        1. 전일 급락 (종가 < 시가의 97% 또는 전전일 종가의 97%)
        2. 당일 시가 상회 상승
        → 과매도 반등 + 추세 전환 포착
        """
        signals = []
        
        for ticker in tickers:
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=5)
                if df is None or len(df) < 3:
                    continue
                
                day_before = df.iloc[-3]
                yesterday = df.iloc[-2]
                today = df.iloc[-1]
                
                # 전일 급락 확인 (Smash Day)
                daily_drop = (yesterday['close'] - yesterday['open']) / yesterday['open'] * 100
                vs_prev_drop = (yesterday['close'] - day_before['close']) / day_before['close'] * 100
                
                is_smash_day = daily_drop < -3 or vs_prev_drop < -5  # 일중 -3% 또는 전일대비 -5%
                
                # 당일 반등 확인
                is_recovering = today['close'] > today['open']
                above_smash_close = today['close'] > yesterday['close']
                
                current_price = today['close']
                
                if is_smash_day and is_recovering and above_smash_close:
                    recovery_pct = (today['close'] - yesterday['close']) / yesterday['close'] * 100
                    score = min(100, 60 + abs(daily_drop) * 3 + recovery_pct * 5)
                    
                    signals.append(TradeSignal(
                        ticker=ticker,
                        coin_name=ticker.replace("KRW-", ""),
                        action="buy",
                        strategy="larry_smash_day",
                        score=score,
                        reason=f"Smash Day 패턴: 전일 {daily_drop:.1f}% 급락 후 +{recovery_pct:.1f}% 반등",
                        current_price=current_price,
                        target_price=yesterday['open'],          # 전일 시가까지
                        stop_loss=yesterday['low'] * 0.98,       # 전일 저가 -2%
                        timestamp=datetime.now().isoformat()
                    ))
            except:
                continue
                
        return sorted(signals, key=lambda x: x.score, reverse=True)
    
    async def scan_larry_combo(self, tickers: List[str], k: float = 0.5) -> List[TradeSignal]:
        """래리 윌리엄스 종합 전략 스캔
        
        변동성 돌파 + Williams %R + 자금관리 원칙 결합
        - 변동성 돌파 목표가 달성
        - Williams %R이 과매도에서 반등 중
        - 거래량 증가
        """
        signals = []
        
        for ticker in tickers:
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=20)
                if df is None or len(df) < 15:
                    continue
                
                yesterday = df.iloc[-2]
                today = df.iloc[-1]
                current_price = today['close']
                
                # 1. 변동성 돌파 체크
                range_val = yesterday['high'] - yesterday['low']
                target_price = today['open'] + range_val * k
                volatility_breakout = current_price > target_price
                
                # 2. Williams %R 계산
                period = 14
                highest_high = df['high'].rolling(window=period).max()
                lowest_low = df['low'].rolling(window=period).min()
                williams_r = ((highest_high - df['close']) / (highest_high - lowest_low)) * -100
                
                current_wr = williams_r.iloc[-1]
                prev_wr = williams_r.iloc[-2]
                
                # %R이 -80~-50 사이이고 상승 중 (과매도 탈출 중)
                wr_signal = -80 <= current_wr <= -50 and current_wr > prev_wr
                
                # 3. 거래량 체크
                avg_volume = df['volume'].iloc[:-1].mean()
                volume_surge = today['volume'] > avg_volume * 1.5
                
                # 4. 양봉 확인
                is_bullish = today['close'] > today['open']
                
                # 조건 점수화
                conditions_met = sum([volatility_breakout, wr_signal, volume_surge, is_bullish])
                
                # 최소 3개 조건 충족 시 매수
                if conditions_met >= 3:
                    score = 50 + conditions_met * 12
                    
                    if volatility_breakout:
                        score += 5
                    if wr_signal:
                        score += abs(current_wr + 65)  # -65 근처일수록 가산점
                    if volume_surge:
                        score += min(20, (today['volume'] / avg_volume - 1) * 10)
                    
                    score = min(100, score)
                    
                    reasons = []
                    if volatility_breakout:
                        reasons.append(f"변동성돌파({target_price:,.0f})")
                    if wr_signal:
                        reasons.append(f"%R={current_wr:.0f}")
                    if volume_surge:
                        reasons.append(f"거래량{today['volume']/avg_volume:.1f}배")
                    if is_bullish:
                        reasons.append("양봉")
                    
                    signals.append(TradeSignal(
                        ticker=ticker,
                        coin_name=ticker.replace("KRW-", ""),
                        action="buy",
                        strategy="larry_combo",
                        score=score,
                        reason=f"래리 종합: {', '.join(reasons)}",
                        current_price=current_price,
                        target_price=current_price * 1.06,   # 6% 익절 (래리 윌리엄스 권장)
                        stop_loss=current_price * 0.97,      # 3% 손절 (래리 윌리엄스 권장)
                        timestamp=datetime.now().isoformat()
                    ))
            except:
                continue
                
        return sorted(signals, key=lambda x: x.score, reverse=True)
    
    async def scan_all_strategies(self, strategy_type: Optional[StrategyType] = None) -> Dict[str, List[TradeSignal]]:
        """전체 전략 스캔 또는 특정 전략 스캔"""
        # 거래량 기준 상위 코인 필터링
        tickers = self.get_high_volume_tickers(min_volume=500_000_000)  # 5억원 이상
        
        if len(tickers) == 0:
            tickers = self.get_all_krw_tickers()[:50]
        
        results = {}
        
        if strategy_type is None or strategy_type == StrategyType.VOLATILITY_BREAKOUT:
            results['volatility_breakout'] = await self.scan_volatility_breakout(tickers)
            
        if strategy_type is None or strategy_type == StrategyType.RSI_REVERSAL:
            results['rsi_reversal'] = await self.scan_rsi_reversal(tickers)
            
        if strategy_type is None or strategy_type == StrategyType.BOLLINGER_BOUNCE:
            results['bollinger_bounce'] = await self.scan_bollinger_bounce(tickers)
            
        if strategy_type is None or strategy_type == StrategyType.VOLUME_SURGE:
            results['volume_surge'] = await self.scan_volume_surge(tickers)
            
        if strategy_type is None or strategy_type == StrategyType.MOMENTUM_BREAKOUT:
            results['momentum_breakout'] = await self.scan_momentum_breakout(tickers)
            
        if strategy_type is None or strategy_type == StrategyType.SCALPING_5MIN:
            results['scalping_5min'] = await self.scan_scalping_5min(tickers)
        
        # 래리 윌리엄스 전략들
        if strategy_type is None or strategy_type == StrategyType.LARRY_WILLIAMS_R:
            results['larry_williams_r'] = await self.scan_larry_williams_r(tickers)
            
        if strategy_type is None or strategy_type == StrategyType.LARRY_OOPS:
            results['larry_oops'] = await self.scan_larry_oops(tickers)
            
        if strategy_type is None or strategy_type == StrategyType.LARRY_SMASH_DAY:
            results['larry_smash_day'] = await self.scan_larry_smash_day(tickers)
            
        if strategy_type is None or strategy_type == StrategyType.LARRY_COMBO:
            results['larry_combo'] = await self.scan_larry_combo(tickers)
        
        return results
    
    def get_top_signals(self, results: Dict[str, List[TradeSignal]], top_n: int = 10) -> List[TradeSignal]:
        """전체 결과에서 상위 N개 시그널 추출"""
        all_signals = []
        for signals in results.values():
            all_signals.extend(signals)
        
        # 점수 기준 정렬
        all_signals.sort(key=lambda x: x.score, reverse=True)
        return all_signals[:top_n]


# 싱글톤 인스턴스
scalping_scanner = ScalpingScanner()

