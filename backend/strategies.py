"""
자동매매 전략 모듈
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple, List
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


def calculate_williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Williams %R 계산"""
    high_max = df['high'].rolling(window=period).max()
    low_min = df['low'].rolling(window=period).min()
    wr = -100 * (high_max - df['close']) / (high_max - low_min)
    return wr


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """RSI 계산"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


class ProfitMaximizer(TradingStrategy):
    """🚀 수익률 최대화 전략
    
    5가지 기술적 지표를 종합 분석하여 최적의 매수/매도 타이밍 포착
    - RSI: 과매도/과매수 판단
    - 볼린저 밴드: 가격 밴드 이탈 감지
    - MACD: 추세 전환 감지
    - Williams %R: 과매도 확인
    - 거래량: 돌파 확인
    
    각 지표가 점수를 부여하고 총점이 임계값을 넘으면 매수/매도
    """
    
    def __init__(self, ticker: str):
        super().__init__(ticker)
        self.buy_threshold = 60  # 매수 점수 임계값
        self.sell_threshold = 60  # 매도 점수 임계값
        
    def analyze(self) -> Dict[str, Any]:
        """종합 분석 수행"""
        df = self.client.get_ohlcv(self.ticker, interval="day", count=50)
        if df is None or len(df) < 30:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # 1. RSI 분석 (14일)
        rsi = calculate_rsi(df, 14)
        rsi_value = rsi.iloc[-1]
        rsi_prev = rsi.iloc[-2]
        
        # 2. 볼린저 밴드 분석 (20일, 2σ)
        bb = calculate_bollinger_bands(df, 20, 2)
        bb_upper = bb['upper'].iloc[-1]
        bb_lower = bb['lower'].iloc[-1]
        bb_middle = bb['middle'].iloc[-1]
        bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) * 100  # 0~100
        
        # 3. MACD 분석
        macd = calculate_macd(df)
        macd_line = macd['macd'].iloc[-1]
        macd_signal = macd['signal'].iloc[-1]
        macd_hist = macd['histogram'].iloc[-1]
        macd_hist_prev = macd['histogram'].iloc[-2]
        
        # 4. Williams %R 분석 (14일)
        williams = calculate_williams_r(df, 14)
        williams_r = williams.iloc[-1]
        
        # 5. 거래량 분석
        vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
        vol_current = df['volume'].iloc[-1]
        vol_ratio = vol_current / vol_ma20 if vol_ma20 > 0 else 1
        
        # 6. 가격 변동 분석
        price_change_1d = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100
        price_change_3d = (df['close'].iloc[-1] - df['close'].iloc[-4]) / df['close'].iloc[-4] * 100
        price_change_7d = (df['close'].iloc[-1] - df['close'].iloc[-8]) / df['close'].iloc[-8] * 100 if len(df) >= 8 else 0
        
        # 7. 추세 강도 (ADX 대용: 이동평균 기울기)
        ma5 = df['close'].rolling(5).mean()
        ma20 = df['close'].rolling(20).mean()
        trend_strength = (ma5.iloc[-1] - ma5.iloc[-3]) / ma5.iloc[-3] * 100 if ma5.iloc[-3] > 0 else 0
        
        return {
            'current_price': current_price,
            'rsi': rsi_value,
            'rsi_prev': rsi_prev,
            'bb_position': bb_position,
            'bb_lower': bb_lower,
            'bb_upper': bb_upper,
            'bb_middle': bb_middle,
            'macd_line': macd_line,
            'macd_signal': macd_signal,
            'macd_hist': macd_hist,
            'macd_hist_prev': macd_hist_prev,
            'williams_r': williams_r,
            'vol_ratio': vol_ratio,
            'price_change_1d': price_change_1d,
            'price_change_3d': price_change_3d,
            'price_change_7d': price_change_7d,
            'trend_strength': trend_strength,
            'ma5': ma5.iloc[-1],
            'ma20': ma20.iloc[-1]
        }
    
    def calculate_buy_score(self, analysis: Dict) -> Tuple[int, List[str]]:
        """매수 점수 계산 (0-100)"""
        score = 0
        reasons = []
        
        # 1. RSI 점수 (최대 25점)
        rsi = analysis['rsi']
        if rsi < 25:
            score += 25
            reasons.append(f"🔥 RSI 극과매도({rsi:.1f})")
        elif rsi < 30:
            score += 20
            reasons.append(f"📉 RSI 과매도({rsi:.1f})")
        elif rsi < 40:
            score += 10
            reasons.append(f"RSI 저점 구간({rsi:.1f})")
        elif rsi > 70:
            score -= 10  # 과매수는 감점
        
        # RSI 반등 신호
        if analysis['rsi'] > analysis['rsi_prev'] and rsi < 40:
            score += 5
            reasons.append("RSI 반등 시작")
            
        # 2. 볼린저 밴드 점수 (최대 25점)
        bb_pos = analysis['bb_position']
        if bb_pos < 5:
            score += 25
            reasons.append(f"🎯 볼린저 하단 터치")
        elif bb_pos < 15:
            score += 15
            reasons.append(f"볼린저 하단 근접")
        elif bb_pos < 30:
            score += 5
        elif bb_pos > 90:
            score -= 10  # 상단 돌파는 감점
            
        # 3. MACD 점수 (최대 20점)
        macd_hist = analysis['macd_hist']
        macd_hist_prev = analysis['macd_hist_prev']
        
        # MACD 히스토그램 상승 전환
        if macd_hist > macd_hist_prev and macd_hist_prev < 0:
            score += 15
            reasons.append("📈 MACD 상승 전환")
        elif macd_hist > macd_hist_prev:
            score += 10
            reasons.append("MACD 개선")
            
        # MACD 골든크로스
        if analysis['macd_line'] > analysis['macd_signal'] and macd_hist > 0:
            score += 5
            reasons.append("MACD 골든크로스")
            
        # 4. Williams %R 점수 (최대 15점)
        williams = analysis['williams_r']
        if williams < -90:
            score += 15
            reasons.append(f"⚡ Williams %R 극과매도({williams:.0f})")
        elif williams < -80:
            score += 10
            reasons.append(f"Williams %R 과매도({williams:.0f})")
        elif williams > -20:
            score -= 5  # 과매수는 감점
            
        # 5. 거래량 점수 (최대 15점)
        vol_ratio = analysis['vol_ratio']
        if vol_ratio > 2:
            score += 15
            reasons.append(f"🔊 거래량 급증({vol_ratio:.1f}x)")
        elif vol_ratio > 1.5:
            score += 10
            reasons.append(f"거래량 증가({vol_ratio:.1f}x)")
        elif vol_ratio > 1.2:
            score += 5
            
        # 보너스: 추세 반전 신호
        if analysis['price_change_3d'] < -5 and analysis['price_change_1d'] > 0:
            score += 10
            reasons.append("🔄 급락 후 반등")
            
        return min(100, max(0, score)), reasons
    
    def calculate_sell_score(self, analysis: Dict, entry_price: float = None) -> Tuple[int, List[str]]:
        """매도 점수 계산 (0-100)"""
        score = 0
        reasons = []
        
        current_price = analysis['current_price']
        profit_rate = ((current_price - entry_price) / entry_price * 100) if entry_price else 0
        
        # 1. RSI 점수 (최대 25점)
        rsi = analysis['rsi']
        if rsi > 80:
            score += 25
            reasons.append(f"🔴 RSI 극과매수({rsi:.1f})")
        elif rsi > 70:
            score += 15
            reasons.append(f"RSI 과매수({rsi:.1f})")
        elif rsi > 65:
            score += 5
            
        # 2. 볼린저 밴드 점수 (최대 25점)
        bb_pos = analysis['bb_position']
        if bb_pos > 95:
            score += 25
            reasons.append(f"⚠️ 볼린저 상단 돌파")
        elif bb_pos > 85:
            score += 15
            reasons.append(f"볼린저 상단 근접")
        elif bb_pos > 70:
            score += 5
            
        # 3. MACD 점수 (최대 20점)
        macd_hist = analysis['macd_hist']
        macd_hist_prev = analysis['macd_hist_prev']
        
        if macd_hist < macd_hist_prev and macd_hist_prev > 0:
            score += 15
            reasons.append("📉 MACD 하락 전환")
        elif macd_hist < macd_hist_prev:
            score += 10
            reasons.append("MACD 약화")
            
        # MACD 데드크로스
        if analysis['macd_line'] < analysis['macd_signal'] and macd_hist < 0:
            score += 5
            reasons.append("MACD 데드크로스")
            
        # 4. 수익 실현 점수 (최대 30점)
        if profit_rate >= 5:
            score += 30
            reasons.append(f"💰 목표 수익 달성(+{profit_rate:.1f}%)")
        elif profit_rate >= 3:
            score += 20
            reasons.append(f"수익 실현 고려(+{profit_rate:.1f}%)")
        elif profit_rate >= 2:
            score += 10
            reasons.append(f"소폭 수익(+{profit_rate:.1f}%)")
        elif profit_rate <= -3:
            score += 25
            reasons.append(f"⛔ 손절 고려({profit_rate:.1f}%)")
            
        return min(100, max(0, score)), reasons
    
    def should_buy(self) -> Tuple[bool, str]:
        """매수 신호 확인"""
        analysis = self.analyze()
        if analysis is None:
            return False, "분석 데이터 부족"
        
        score, reasons = self.calculate_buy_score(analysis)
        
        reason_str = f"[점수: {score}/100] " + " | ".join(reasons) if reasons else f"[점수: {score}/100] 신호 대기"
        
        if score >= self.buy_threshold:
            return True, f"🚀 수익률 최대화 매수! {reason_str}"
        return False, reason_str
    
    def should_sell(self, entry_price: float = None) -> Tuple[bool, str]:
        """매도 신호 확인"""
        analysis = self.analyze()
        if analysis is None:
            return False, "분석 데이터 부족"
        
        score, reasons = self.calculate_sell_score(analysis, entry_price)
        
        reason_str = f"[점수: {score}/100] " + " | ".join(reasons) if reasons else f"[점수: {score}/100] 보유 유지"
        
        if score >= self.sell_threshold:
            return True, f"🔔 수익률 최대화 매도! {reason_str}"
        return False, reason_str
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """분석 요약 반환 (UI용)"""
        analysis = self.analyze()
        if analysis is None:
            return None
        
        buy_score, buy_reasons = self.calculate_buy_score(analysis)
        sell_score, sell_reasons = self.calculate_sell_score(analysis)
        
        return {
            'ticker': self.ticker,
            'price': analysis['current_price'],
            'buy_score': buy_score,
            'sell_score': sell_score,
            'buy_reasons': buy_reasons,
            'sell_reasons': sell_reasons,
            'indicators': {
                'RSI': round(analysis['rsi'], 1),
                'BB위치': round(analysis['bb_position'], 1),
                'Williams%R': round(analysis['williams_r'], 1),
                'MACD히스토': round(analysis['macd_hist'], 2),
                '거래량배율': round(analysis['vol_ratio'], 2),
                '1일변동': round(analysis['price_change_1d'], 2),
                '3일변동': round(analysis['price_change_3d'], 2)
            },
            'recommendation': 'buy' if buy_score >= self.buy_threshold else ('sell' if sell_score >= self.sell_threshold else 'hold')
        }







