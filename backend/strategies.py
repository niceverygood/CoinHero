"""
자동매매 전략 모듈
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from upbit_client import upbit_client
from config import VOLATILITY_K, RSI_OVERSOLD, RSI_OVERBOUGHT


class TradingStrategy:
    """트레이딩 전략 기본 클래스"""
    
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.client = upbit_client
        
    def should_buy(self) -> Tuple[bool, str]:
        """매수 신호 확인 - 서브클래스에서 구현"""
        raise NotImplementedError
        
    def should_sell(self) -> Tuple[bool, str]:
        """매도 신호 확인 - 서브클래스에서 구현"""
        raise NotImplementedError


class VolatilityBreakout(TradingStrategy):
    """변동성 돌파 전략
    
    전날 고가-저가 범위의 K배를 당일 시가에 더한 값을 
    돌파하면 매수하는 전략
    """
    
    def __init__(self, ticker: str, k: float = VOLATILITY_K):
        super().__init__(ticker)
        self.k = k
        
    def get_target_price(self) -> Optional[float]:
        """목표가 계산"""
        df = self.client.get_ohlcv(self.ticker, interval="day", count=2)
        if df is None or len(df) < 2:
            return None
            
        # 전일 고가 - 전일 저가
        yesterday = df.iloc[-2]
        today_open = df.iloc[-1]['open']
        
        range_val = yesterday['high'] - yesterday['low']
        target = today_open + range_val * self.k
        
        return target
    
    def should_buy(self) -> Tuple[bool, str]:
        """매수 신호 확인"""
        target = self.get_target_price()
        if target is None:
            return False, "목표가 계산 실패"
            
        current = self.client.get_current_price(self.ticker)
        if current is None:
            return False, "현재가 조회 실패"
            
        if current > target:
            return True, f"변동성 돌파! 현재가({current:,.0f}) > 목표가({target:,.0f})"
        return False, f"대기 중... 현재가({current:,.0f}) < 목표가({target:,.0f})"
    
    def should_sell(self) -> Tuple[bool, str]:
        """매도 신호 - 다음날 시가에 매도 (09:00)"""
        now = datetime.now()
        if now.hour == 9 and now.minute < 5:
            return True, "다음날 09:00 - 익절/손절"
        return False, "보유 중..."


class MovingAverageCross(TradingStrategy):
    """이동평균선 교차 전략
    
    단기 이동평균이 장기 이동평균을 상향 돌파하면 매수,
    하향 돌파하면 매도
    """
    
    def __init__(self, ticker: str, short_window: int = 5, long_window: int = 20):
        super().__init__(ticker)
        self.short_window = short_window
        self.long_window = long_window
        
    def get_moving_averages(self) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
        """이동평균 계산"""
        df = self.client.get_ohlcv(self.ticker, interval="day", count=self.long_window + 5)
        if df is None or len(df) < self.long_window:
            return None, None
            
        short_ma = df['close'].rolling(window=self.short_window).mean()
        long_ma = df['close'].rolling(window=self.long_window).mean()
        
        return short_ma, long_ma
    
    def should_buy(self) -> Tuple[bool, str]:
        """골든크로스 감지"""
        short_ma, long_ma = self.get_moving_averages()
        if short_ma is None or long_ma is None:
            return False, "이동평균 계산 실패"
            
        # 현재와 이전 값 비교
        if (short_ma.iloc[-1] > long_ma.iloc[-1] and 
            short_ma.iloc[-2] <= long_ma.iloc[-2]):
            return True, f"골든크로스! MA{self.short_window}({short_ma.iloc[-1]:,.0f}) > MA{self.long_window}({long_ma.iloc[-1]:,.0f})"
        
        return False, f"대기 중... MA{self.short_window}({short_ma.iloc[-1]:,.0f}) vs MA{self.long_window}({long_ma.iloc[-1]:,.0f})"
    
    def should_sell(self) -> Tuple[bool, str]:
        """데드크로스 감지"""
        short_ma, long_ma = self.get_moving_averages()
        if short_ma is None or long_ma is None:
            return False, "이동평균 계산 실패"
            
        if (short_ma.iloc[-1] < long_ma.iloc[-1] and 
            short_ma.iloc[-2] >= long_ma.iloc[-2]):
            return True, f"데드크로스! MA{self.short_window}({short_ma.iloc[-1]:,.0f}) < MA{self.long_window}({long_ma.iloc[-1]:,.0f})"
        
        return False, f"보유 중... MA{self.short_window}({short_ma.iloc[-1]:,.0f}) vs MA{self.long_window}({long_ma.iloc[-1]:,.0f})"


class RSIStrategy(TradingStrategy):
    """RSI 전략
    
    RSI가 과매도 구간에서 매수, 과매수 구간에서 매도
    """
    
    def __init__(self, ticker: str, period: int = 14, 
                 oversold: int = RSI_OVERSOLD, overbought: int = RSI_OVERBOUGHT):
        super().__init__(ticker)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        
    def calculate_rsi(self) -> Optional[float]:
        """RSI 계산"""
        df = self.client.get_ohlcv(self.ticker, interval="day", count=self.period + 10)
        if df is None or len(df) < self.period + 1:
            return None
            
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]
    
    def should_buy(self) -> Tuple[bool, str]:
        """과매도 구간 매수"""
        rsi = self.calculate_rsi()
        if rsi is None:
            return False, "RSI 계산 실패"
            
        if rsi < self.oversold:
            return True, f"과매도! RSI({rsi:.1f}) < {self.oversold}"
        return False, f"대기 중... RSI({rsi:.1f})"
    
    def should_sell(self) -> Tuple[bool, str]:
        """과매수 구간 매도"""
        rsi = self.calculate_rsi()
        if rsi is None:
            return False, "RSI 계산 실패"
            
        if rsi > self.overbought:
            return True, f"과매수! RSI({rsi:.1f}) > {self.overbought}"
        return False, f"보유 중... RSI({rsi:.1f})"


class CombinedStrategy(TradingStrategy):
    """복합 전략
    
    여러 전략의 신호를 종합하여 판단
    """
    
    def __init__(self, ticker: str):
        super().__init__(ticker)
        self.strategies = [
            VolatilityBreakout(ticker),
            MovingAverageCross(ticker),
            RSIStrategy(ticker)
        ]
        
    def should_buy(self) -> Tuple[bool, str]:
        """매수 신호 - 2개 이상 전략 동의 시"""
        signals = []
        reasons = []
        
        for strategy in self.strategies:
            signal, reason = strategy.should_buy()
            signals.append(signal)
            if signal:
                reasons.append(reason)
                
        buy_count = sum(signals)
        if buy_count >= 2:
            return True, f"복합 매수 신호 ({buy_count}/3): " + " | ".join(reasons)
        return False, f"매수 신호 부족 ({buy_count}/3)"
    
    def should_sell(self) -> Tuple[bool, str]:
        """매도 신호 - 2개 이상 전략 동의 시"""
        signals = []
        reasons = []
        
        for strategy in self.strategies:
            signal, reason = strategy.should_sell()
            signals.append(signal)
            if signal:
                reasons.append(reason)
                
        sell_count = sum(signals)
        if sell_count >= 2:
            return True, f"복합 매도 신호 ({sell_count}/3): " + " | ".join(reasons)
        return False, f"매도 신호 부족 ({sell_count}/3)"


# 기술적 지표 유틸리티 함수들
def calculate_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: float = 2) -> Dict[str, pd.Series]:
    """볼린저 밴드 계산"""
    middle = df['close'].rolling(window=window).mean()
    std = df['close'].rolling(window=window).std()
    
    return {
        'upper': middle + (std * num_std),
        'middle': middle,
        'lower': middle - (std * num_std)
    }


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """MACD 계산"""
    exp_fast = df['close'].ewm(span=fast, adjust=False).mean()
    exp_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    macd_line = exp_fast - exp_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
    """스토캐스틱 계산"""
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    
    k = 100 * ((df['close'] - low_min) / (high_max - low_min))
    d = k.rolling(window=d_period).mean()
    
    return {'k': k, 'd': d}







