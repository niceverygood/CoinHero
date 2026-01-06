"""
백테스트 모듈 - 다양한 매매 전략 테스트 (확장 버전)
"""
import pyupbit
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import json
import os

class BacktestEngine:
    """백테스트 엔진"""
    
    def __init__(self, initial_capital: float = 1_000_000, log_file: str = "backtest_results.log"):
        self.initial_capital = initial_capital
        self.log_file = log_file
        self.results = {}
        
    def log(self, message: str):
        """로그 기록"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    
    def get_historical_data(self, ticker: str, days: int = 7) -> pd.DataFrame:
        """과거 데이터 조회 (분봉)"""
        try:
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=24 * days)
            if df is None or len(df) < 10:
                return None
            return df
        except Exception as e:
            self.log(f"데이터 조회 실패 ({ticker}): {e}")
            return None
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 볼린저 밴드
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
        
        # 이동평균
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=14).mean()
        
        # 거래량 이동평균
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        
        # 스토캐스틱
        low_14 = df['low'].rolling(window=14).min()
        high_14 = df['high'].rolling(window=14).max()
        df['stoch_k'] = ((df['close'] - low_14) / (high_14 - low_14)) * 100
        df['stoch_d'] = df['stoch_k'].rolling(window=3).mean()
        
        # Williams %R
        df['williams_r'] = ((high_14 - df['close']) / (high_14 - low_14)) * -100
        
        # CCI
        tp = (df['high'] + df['low'] + df['close']) / 3
        df['cci'] = (tp - tp.rolling(window=20).mean()) / (0.015 * tp.rolling(window=20).std())
        
        # ADX
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        
        tr14 = tr.rolling(window=14).sum()
        plus_di = 100 * (plus_dm.rolling(window=14).sum() / tr14)
        minus_di = 100 * (abs(minus_dm).rolling(window=14).sum() / tr14)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.rolling(window=14).mean()
        df['plus_di'] = plus_di
        df['minus_di'] = minus_di
        
        # OBV
        obv = [0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.append(obv[-1] + df['volume'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.append(obv[-1] - df['volume'].iloc[i])
            else:
                obv.append(obv[-1])
        df['obv'] = obv
        df['obv_ma'] = pd.Series(obv).rolling(window=20).mean().values
        
        # 일목균형표
        df['tenkan'] = (df['high'].rolling(window=9).max() + df['low'].rolling(window=9).min()) / 2
        df['kijun'] = (df['high'].rolling(window=26).max() + df['low'].rolling(window=26).min()) / 2
        
        # 피보나치
        recent_high = df['high'].rolling(window=50).max()
        recent_low = df['low'].rolling(window=50).min()
        diff = recent_high - recent_low
        df['fib_382'] = recent_high - diff * 0.382
        df['fib_618'] = recent_high - diff * 0.618
        
        return df
    
    # ===== 기본 전략들 =====
    def strategy_rsi_reversal(self, df, row_idx, position):
        """RSI 반전 전략"""
        if row_idx < 20: return "hold", ""
        rsi = df['rsi'].iloc[row_idx]
        prev_rsi = df['rsi'].iloc[row_idx - 1]
        close = df['close'].iloc[row_idx]
        
        if not position['holding']:
            if prev_rsi < 30 and rsi > prev_rsi:
                return "buy", f"RSI 과매도 반등 ({rsi:.1f})"
        else:
            if rsi > 70: return "sell", f"RSI 과매수 ({rsi:.1f})"
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
        return "hold", ""
    
    def strategy_bollinger_bounce(self, df, row_idx, position):
        """볼린저 밴드 반등 전략"""
        if row_idx < 25: return "hold", ""
        close = df['close'].iloc[row_idx]
        bb_lower = df['bb_lower'].iloc[row_idx]
        bb_upper = df['bb_upper'].iloc[row_idx]
        bb_middle = df['bb_middle'].iloc[row_idx]
        
        if not position['holding']:
            if close <= bb_lower * 1.01:
                return "buy", f"볼린저 하단 터치"
        else:
            if close >= bb_upper * 0.99: return "sell", f"볼린저 상단 도달"
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if close >= bb_middle and profit_rate >= 2:
                return "sell", f"중심선 + 익절 ({profit_rate:.1f}%)"
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
        return "hold", ""
    
    def strategy_golden_cross(self, df, row_idx, position):
        """골든크로스 전략 (MA5 > MA20)"""
        if row_idx < 25: return "hold", ""
        ma5, ma20 = df['ma5'].iloc[row_idx], df['ma20'].iloc[row_idx]
        prev_ma5, prev_ma20 = df['ma5'].iloc[row_idx-1], df['ma20'].iloc[row_idx-1]
        close = df['close'].iloc[row_idx]
        
        if not position['holding']:
            if prev_ma5 <= prev_ma20 and ma5 > ma20:
                return "buy", f"골든크로스"
        else:
            if prev_ma5 >= prev_ma20 and ma5 < ma20: return "sell", f"데드크로스"
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 7: return "sell", f"익절 ({profit_rate:.1f}%)"
        return "hold", ""
    
    def strategy_macd_cross(self, df, row_idx, position):
        """MACD 크로스 전략"""
        if row_idx < 30: return "hold", ""
        macd, signal = df['macd'].iloc[row_idx], df['macd_signal'].iloc[row_idx]
        prev_macd, prev_signal = df['macd'].iloc[row_idx-1], df['macd_signal'].iloc[row_idx-1]
        close = df['close'].iloc[row_idx]
        
        if not position['holding']:
            if prev_macd <= prev_signal and macd > signal:
                return "buy", f"MACD 골든크로스"
        else:
            if prev_macd >= prev_signal and macd < signal: return "sell", f"MACD 데드크로스"
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
        return "hold", ""
    
    def strategy_volume_breakout(self, df, row_idx, position):
        """거래량 돌파 전략"""
        if row_idx < 25: return "hold", ""
        volume, volume_ma = df['volume'].iloc[row_idx], df['volume_ma'].iloc[row_idx]
        close, prev_close = df['close'].iloc[row_idx], df['close'].iloc[row_idx-1]
        
        if not position['holding']:
            if volume > volume_ma * 2 and close > prev_close:
                return "buy", f"거래량 급증 (x{volume/volume_ma:.1f})"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -2: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 3: return "sell", f"익절 ({profit_rate:.1f}%)"
            if volume < volume_ma * 0.5: return "sell", f"거래량 감소"
        return "hold", ""
    
    def strategy_momentum(self, df, row_idx, position):
        """모멘텀 전략"""
        if row_idx < 10: return "hold", ""
        close = df['close'].iloc[row_idx]
        up_count = sum(1 for i in range(1, 4) if df['close'].iloc[row_idx-i+1] > df['close'].iloc[row_idx-i])
        
        if not position['holding']:
            if up_count >= 3: return "buy", f"3연속 상승"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -2: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if df['close'].iloc[row_idx] < df['close'].iloc[row_idx-1] < df['close'].iloc[row_idx-2]:
                return "sell", f"모멘텀 약화"
        return "hold", ""
    
    def strategy_combined(self, df, row_idx, position):
        """복합 전략 (RSI + 볼린저 + MA)"""
        if row_idx < 30: return "hold", ""
        rsi, close = df['rsi'].iloc[row_idx], df['close'].iloc[row_idx]
        bb_lower, ma20 = df['bb_lower'].iloc[row_idx], df['ma20'].iloc[row_idx]
        
        if not position['holding']:
            score, reasons = 0, []
            if rsi < 40: score += 1; reasons.append(f"RSI {rsi:.0f}")
            if close <= bb_lower * 1.02: score += 1; reasons.append("BB 하단")
            if close > ma20: score += 1; reasons.append("MA20 위")
            if score >= 2: return "buy", f"복합신호 ({', '.join(reasons)})"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if rsi > 70: return "sell", f"RSI 과매수 ({rsi:.0f})"
        return "hold", ""
    
    # ===== 추가 전략들 =====
    def strategy_stochastic(self, df, row_idx, position):
        """스토캐스틱 전략"""
        if row_idx < 20: return "hold", ""
        stoch_k, stoch_d = df['stoch_k'].iloc[row_idx], df['stoch_d'].iloc[row_idx]
        prev_k, prev_d = df['stoch_k'].iloc[row_idx-1], df['stoch_d'].iloc[row_idx-1]
        close = df['close'].iloc[row_idx]
        
        if pd.isna(stoch_k): return "hold", ""
        
        if not position['holding']:
            if prev_k <= prev_d and stoch_k > stoch_d and stoch_k < 30:
                return "buy", f"스토캐스틱 골든 (K:{stoch_k:.0f})"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if prev_k >= prev_d and stoch_k < stoch_d and stoch_k > 70:
                return "sell", f"스토캐스틱 데드 (K:{stoch_k:.0f})"
        return "hold", ""
    
    def strategy_williams_r(self, df, row_idx, position):
        """Williams %R 전략"""
        if row_idx < 20: return "hold", ""
        wr, prev_wr = df['williams_r'].iloc[row_idx], df['williams_r'].iloc[row_idx-1]
        close = df['close'].iloc[row_idx]
        
        if pd.isna(wr): return "hold", ""
        
        if not position['holding']:
            if prev_wr < -80 and wr > prev_wr:
                return "buy", f"Williams %R 반등 ({wr:.0f})"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if wr > -20: return "sell", f"Williams %R 과매수 ({wr:.0f})"
        return "hold", ""
    
    def strategy_cci(self, df, row_idx, position):
        """CCI 전략"""
        if row_idx < 25: return "hold", ""
        cci, prev_cci = df['cci'].iloc[row_idx], df['cci'].iloc[row_idx-1]
        close = df['close'].iloc[row_idx]
        
        if pd.isna(cci): return "hold", ""
        
        if not position['holding']:
            if prev_cci < -100 and cci > -100:
                return "buy", f"CCI 과매도 탈출 ({cci:.0f})"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if prev_cci > 100 and cci < 100: return "sell", f"CCI 과매수 탈출 ({cci:.0f})"
        return "hold", ""
    
    def strategy_adx_trend(self, df, row_idx, position):
        """ADX 추세 강도 전략"""
        if row_idx < 30: return "hold", ""
        adx = df['adx'].iloc[row_idx]
        plus_di, minus_di = df['plus_di'].iloc[row_idx], df['minus_di'].iloc[row_idx]
        prev_plus_di, prev_minus_di = df['plus_di'].iloc[row_idx-1], df['minus_di'].iloc[row_idx-1]
        close = df['close'].iloc[row_idx]
        
        if pd.isna(adx): return "hold", ""
        
        if not position['holding']:
            if adx > 25 and prev_plus_di <= prev_minus_di and plus_di > minus_di:
                return "buy", f"ADX 상승추세 ({adx:.0f})"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if prev_minus_di <= prev_plus_di and minus_di > plus_di:
                return "sell", f"ADX 하락전환"
        return "hold", ""
    
    def strategy_ichimoku(self, df, row_idx, position):
        """일목균형표 전략"""
        if row_idx < 30: return "hold", ""
        close = df['close'].iloc[row_idx]
        tenkan, kijun = df['tenkan'].iloc[row_idx], df['kijun'].iloc[row_idx]
        prev_tenkan, prev_kijun = df['tenkan'].iloc[row_idx-1], df['kijun'].iloc[row_idx-1]
        
        if pd.isna(tenkan): return "hold", ""
        
        if not position['holding']:
            if prev_tenkan <= prev_kijun and tenkan > kijun and close > tenkan:
                return "buy", f"일목 골든크로스"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if prev_tenkan >= prev_kijun and tenkan < kijun:
                return "sell", f"일목 데드크로스"
        return "hold", ""
    
    def strategy_obv(self, df, row_idx, position):
        """OBV 전략"""
        if row_idx < 25: return "hold", ""
        obv, obv_ma = df['obv'].iloc[row_idx], df['obv_ma'].iloc[row_idx]
        prev_obv, prev_obv_ma = df['obv'].iloc[row_idx-1], df['obv_ma'].iloc[row_idx-1]
        close = df['close'].iloc[row_idx]
        
        if pd.isna(obv_ma): return "hold", ""
        
        if not position['holding']:
            if prev_obv <= prev_obv_ma and obv > obv_ma:
                return "buy", f"OBV 상향돌파"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if prev_obv >= prev_obv_ma and obv < obv_ma:
                return "sell", f"OBV 하향돌파"
        return "hold", ""
    
    def strategy_fibonacci(self, df, row_idx, position):
        """피보나치 되돌림 전략"""
        if row_idx < 55: return "hold", ""
        close = df['close'].iloc[row_idx]
        fib_618, fib_382 = df['fib_618'].iloc[row_idx], df['fib_382'].iloc[row_idx]
        rsi = df['rsi'].iloc[row_idx]
        
        if pd.isna(fib_618): return "hold", ""
        
        if not position['holding']:
            if close <= fib_618 * 1.01 and rsi < 40:
                return "buy", f"피보 61.8% + RSI({rsi:.0f})"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if close >= fib_382: return "sell", f"피보 38.2% 도달"
        return "hold", ""
    
    def strategy_atr_breakout(self, df, row_idx, position):
        """ATR 변동성 돌파 전략"""
        if row_idx < 20: return "hold", ""
        close, atr = df['close'].iloc[row_idx], df['atr'].iloc[row_idx]
        prev_high = df['high'].iloc[row_idx-1]
        
        if pd.isna(atr): return "hold", ""
        
        if not position['holding']:
            breakout_level = prev_high + atr * 0.5
            if close > breakout_level:
                return "buy", f"ATR 상단돌파"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -2: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 3: return "sell", f"익절 ({profit_rate:.1f}%)"
        return "hold", ""
    
    def strategy_mean_reversion(self, df, row_idx, position):
        """평균 회귀 전략"""
        if row_idx < 25: return "hold", ""
        close, ma20 = df['close'].iloc[row_idx], df['ma20'].iloc[row_idx]
        bb_lower = df['bb_lower'].iloc[row_idx]
        deviation = (close - ma20) / ma20 * 100
        
        if not position['holding']:
            if deviation <= -3 and close <= bb_lower * 1.01:
                return "buy", f"평균회귀 (편차:{deviation:.1f}%)"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -4: return "sell", f"손절 ({profit_rate:.1f}%)"
            if abs(deviation) < 0.5: return "sell", f"평균 도달 ({profit_rate:.1f}%)"
            if profit_rate >= 4: return "sell", f"익절 ({profit_rate:.1f}%)"
        return "hold", ""
    
    def strategy_double_ma(self, df, row_idx, position):
        """이중 이평선 전략 (10/20)"""
        if row_idx < 25: return "hold", ""
        ma10, ma20 = df['ma10'].iloc[row_idx], df['ma20'].iloc[row_idx]
        prev_ma10, prev_ma20 = df['ma10'].iloc[row_idx-1], df['ma20'].iloc[row_idx-1]
        close = df['close'].iloc[row_idx]
        
        if not position['holding']:
            if prev_ma10 <= prev_ma20 and ma10 > ma20 and close > ma10:
                return "buy", f"이중MA 골든크로스"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if prev_ma10 >= prev_ma20 and ma10 < ma20: return "sell", f"이중MA 데드크로스"
        return "hold", ""
    
    def strategy_macd_histogram(self, df, row_idx, position):
        """MACD 히스토그램 전략"""
        if row_idx < 30: return "hold", ""
        macd_hist = df['macd_hist'].iloc[row_idx]
        prev_hist, prev_prev_hist = df['macd_hist'].iloc[row_idx-1], df['macd_hist'].iloc[row_idx-2]
        close = df['close'].iloc[row_idx]
        
        if not position['holding']:
            if prev_prev_hist < 0 and prev_hist < 0 and macd_hist > 0:
                return "buy", f"MACD 히스토그램 양전환"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if prev_prev_hist > 0 and prev_hist > 0 and macd_hist < 0:
                return "sell", f"MACD 히스토그램 음전환"
        return "hold", ""
    
    def strategy_triple_screen(self, df, row_idx, position):
        """삼중창 전략"""
        if row_idx < 30: return "hold", ""
        ma20, close = df['ma20'].iloc[row_idx], df['close'].iloc[row_idx]
        rsi, prev_rsi = df['rsi'].iloc[row_idx], df['rsi'].iloc[row_idx-1]
        bb_lower = df['bb_lower'].iloc[row_idx]
        trend_up = close > ma20
        
        if not position['holding']:
            if trend_up and rsi > prev_rsi and rsi < 40 and close <= bb_lower * 1.02:
                return "buy", f"삼중창 매수신호"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if rsi > 70: return "sell", f"삼중창 과매수"
        return "hold", ""
    
    def strategy_scalping(self, df, row_idx, position):
        """빠른 스캘핑 전략"""
        if row_idx < 15: return "hold", ""
        close, rsi = df['close'].iloc[row_idx], df['rsi'].iloc[row_idx]
        stoch_k = df['stoch_k'].iloc[row_idx]
        volume, volume_ma = df['volume'].iloc[row_idx], df['volume_ma'].iloc[row_idx]
        
        if pd.isna(stoch_k) or pd.isna(volume_ma): return "hold", ""
        
        if not position['holding']:
            if rsi < 35 and stoch_k < 25 and volume > volume_ma:
                return "buy", f"스캘핑 진입 (RSI:{rsi:.0f})"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -1.5: return "sell", f"스캘핑 손절 ({profit_rate:.1f}%)"
            if profit_rate >= 1.5: return "sell", f"스캘핑 익절 ({profit_rate:.1f}%)"
        return "hold", ""
    
    def strategy_breakout(self, df, row_idx, position):
        """박스권 돌파 전략"""
        if row_idx < 30: return "hold", ""
        close = df['close'].iloc[row_idx]
        recent_high = df['high'].iloc[row_idx-20:row_idx].max()
        recent_low = df['low'].iloc[row_idx-20:row_idx].min()
        range_pct = (recent_high - recent_low) / recent_low * 100
        volume, volume_ma = df['volume'].iloc[row_idx], df['volume_ma'].iloc[row_idx]
        
        if not position['holding']:
            if range_pct < 5 and close > recent_high and volume > volume_ma * 1.5:
                return "buy", f"박스권 상단돌파"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -2: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 4: return "sell", f"익절 ({profit_rate:.1f}%)"
        return "hold", ""
    
    def strategy_rsi_divergence(self, df, row_idx, position):
        """RSI 다이버전스 전략"""
        if row_idx < 30: return "hold", ""
        close = df['close'].iloc[row_idx]
        rsi = df['rsi'].iloc[row_idx]
        prev_close = df['close'].iloc[row_idx-10]
        prev_rsi = df['rsi'].iloc[row_idx-10]
        
        if not position['holding']:
            # 상승 다이버전스: 가격 저점 갱신, RSI 저점 상승
            if close < prev_close and rsi > prev_rsi and rsi < 35:
                return "buy", f"RSI 상승 다이버전스"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            # 하락 다이버전스
            if close > prev_close and rsi < prev_rsi and rsi > 65:
                return "sell", f"RSI 하락 다이버전스"
        return "hold", ""
    
    def strategy_vwap(self, df, row_idx, position):
        """VWAP 기반 전략"""
        if row_idx < 20: return "hold", ""
        close = df['close'].iloc[row_idx]
        # 간단한 VWAP 계산
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).rolling(20).sum() / df['volume'].rolling(20).sum()
        current_vwap = vwap.iloc[row_idx]
        rsi = df['rsi'].iloc[row_idx]
        
        if pd.isna(current_vwap): return "hold", ""
        
        if not position['holding']:
            if close < current_vwap * 0.99 and rsi < 40:
                return "buy", f"VWAP 하회 + RSI({rsi:.0f})"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if close > current_vwap * 1.02: return "sell", f"VWAP 상회 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
        return "hold", ""
    
    def strategy_supertrend(self, df, row_idx, position):
        """슈퍼트렌드 기반 전략"""
        if row_idx < 20: return "hold", ""
        close = df['close'].iloc[row_idx]
        atr = df['atr'].iloc[row_idx]
        hl2 = (df['high'].iloc[row_idx] + df['low'].iloc[row_idx]) / 2
        
        if pd.isna(atr): return "hold", ""
        
        upper_band = hl2 + atr * 2
        lower_band = hl2 - atr * 2
        prev_close = df['close'].iloc[row_idx-1]
        
        if not position['holding']:
            if prev_close < lower_band and close > lower_band:
                return "buy", f"슈퍼트렌드 상향돌파"
        else:
            profit_rate = (close - position['entry_price']) / position['entry_price'] * 100
            if profit_rate <= -3: return "sell", f"손절 ({profit_rate:.1f}%)"
            if profit_rate >= 5: return "sell", f"익절 ({profit_rate:.1f}%)"
            if close < lower_band: return "sell", f"슈퍼트렌드 하향이탈"
        return "hold", ""
    
    def run_backtest(self, ticker: str, strategy_func, strategy_name: str) -> Dict[str, Any]:
        """단일 전략 백테스트 실행"""
        self.log(f"\n{'='*60}")
        self.log(f"📊 [{strategy_name}] 백테스트 시작 - {ticker}")
        self.log(f"{'='*60}")
        
        df = self.get_historical_data(ticker, days=7)
        if df is None: return None
        
        df = self.calculate_indicators(df)
        
        capital = self.initial_capital
        position = {'holding': False, 'entry_price': 0, 'quantity': 0, 'entry_time': None}
        trades = []
        max_capital = capital
        min_capital = capital
        
        for i in range(len(df)):
            action, reason = strategy_func(df, i, position)
            current_price = df['close'].iloc[i]
            current_time = df.index[i]
            
            if action == "buy" and not position['holding']:
                invest_amount = capital * 0.9
                fee = invest_amount * 0.0005
                quantity = (invest_amount - fee) / current_price
                
                position = {'holding': True, 'entry_price': current_price, 
                           'quantity': quantity, 'entry_time': current_time}
                capital -= invest_amount
                
                trades.append({'time': str(current_time), 'action': 'BUY', 
                              'price': current_price, 'quantity': quantity,
                              'amount': invest_amount, 'reason': reason})
                self.log(f"  🟢 매수 | {current_time} | ₩{current_price:,.0f} | {reason}")
                
            elif action == "sell" and position['holding']:
                sell_amount = position['quantity'] * current_price
                fee = sell_amount * 0.0005
                profit = sell_amount - fee - (position['entry_price'] * position['quantity'])
                profit_rate = (current_price - position['entry_price']) / position['entry_price'] * 100
                
                capital += sell_amount - fee
                
                trades.append({'time': str(current_time), 'action': 'SELL',
                              'price': current_price, 'profit': profit,
                              'profit_rate': profit_rate, 'reason': reason})
                self.log(f"  🔴 매도 | {current_time} | ₩{current_price:,.0f} | {profit_rate:+.2f}% | {reason}")
                
                position = {'holding': False, 'entry_price': 0, 'quantity': 0, 'entry_time': None}
            
            total_value = capital + (position['quantity'] * current_price if position['holding'] else 0)
            max_capital = max(max_capital, total_value)
            min_capital = min(min_capital, total_value)
        
        final_value = capital + (position['quantity'] * df['close'].iloc[-1] if position['holding'] else 0)
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        mdd = (max_capital - min_capital) / max_capital * 100 if max_capital > 0 else 0
        
        sell_trades = [t for t in trades if t['action'] == 'SELL']
        win_trades = [t for t in sell_trades if t.get('profit', 0) > 0]
        win_rate = len(win_trades) / len(sell_trades) * 100 if sell_trades else 0
        
        result = {
            'strategy': strategy_name, 'ticker': ticker,
            'initial_capital': self.initial_capital, 'final_value': final_value,
            'total_return': total_return, 'total_trades': len([t for t in trades if t['action'] == 'BUY']),
            'win_trades': len(win_trades), 'lose_trades': len(sell_trades) - len(win_trades),
            'win_rate': win_rate, 'max_drawdown': mdd, 'trades': trades
        }
        
        self.log(f"\n  📈 결과: 수익률 {total_return:+.2f}% | 거래 {result['total_trades']}회 | 승률 {win_rate:.1f}%")
        self.log(f"  💰 최종자산: ₩{final_value:,.0f} (시작: ₩{self.initial_capital:,.0f})")
        
        return result
    
    def run_all_strategies(self, tickers: List[str] = None):
        """모든 전략 백테스트 실행"""
        if tickers is None:
            tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"]
        
        strategies = [
            # 기본 전략
            (self.strategy_rsi_reversal, "RSI 반전"),
            (self.strategy_bollinger_bounce, "볼린저 반등"),
            (self.strategy_golden_cross, "골든크로스"),
            (self.strategy_macd_cross, "MACD 크로스"),
            (self.strategy_volume_breakout, "거래량 돌파"),
            (self.strategy_momentum, "모멘텀"),
            (self.strategy_combined, "복합전략"),
            # 추가 전략
            (self.strategy_stochastic, "스토캐스틱"),
            (self.strategy_williams_r, "Williams %R"),
            (self.strategy_cci, "CCI"),
            (self.strategy_adx_trend, "ADX 추세"),
            (self.strategy_ichimoku, "일목균형표"),
            (self.strategy_obv, "OBV"),
            (self.strategy_fibonacci, "피보나치"),
            (self.strategy_atr_breakout, "ATR 돌파"),
            (self.strategy_mean_reversion, "평균회귀"),
            (self.strategy_double_ma, "이중이평선"),
            (self.strategy_macd_histogram, "MACD히스토그램"),
            (self.strategy_triple_screen, "삼중창"),
            (self.strategy_scalping, "스캘핑"),
            (self.strategy_breakout, "박스돌파"),
            (self.strategy_rsi_divergence, "RSI다이버전스"),
            (self.strategy_vwap, "VWAP"),
            (self.strategy_supertrend, "슈퍼트렌드"),
        ]
        
        # 로그 파일 초기화
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(f"{'='*80}\n")
            f.write(f"📊 CoinHero 백테스트 리포트 (확장판)\n")
            f.write(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"초기 자본: ₩{self.initial_capital:,.0f}\n")
            f.write(f"테스트 기간: 최근 7일\n")
            f.write(f"테스트 전략: {len(strategies)}개\n")
            f.write(f"테스트 코인: {len(tickers)}개\n")
            f.write(f"{'='*80}\n\n")
        
        all_results = []
        
        for ticker in tickers:
            self.log(f"\n\n{'#'*80}")
            self.log(f"# 코인: {ticker}")
            self.log(f"{'#'*80}")
            
            for strategy_func, strategy_name in strategies:
                result = self.run_backtest(ticker, strategy_func, strategy_name)
                if result:
                    all_results.append(result)
        
        # 결과 정렬
        all_results.sort(key=lambda x: x['total_return'], reverse=True)
        
        # 최종 결과 출력
        self.log(f"\n\n{'='*80}")
        self.log(f"📊 최종 결과 순위 (수익률 기준)")
        self.log(f"{'='*80}")
        
        self.log(f"\n{'순위':^4} | {'전략':^14} | {'코인':^10} | {'수익률':^10} | {'거래수':^6} | {'승률':^8} | {'MDD':^8}")
        self.log("-" * 80)
        
        for i, r in enumerate(all_results[:30], 1):
            emoji = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "  "))
            self.log(f"{emoji}{i:2} | {r['strategy']:^14} | {r['ticker']:^10} | {r['total_return']:+8.2f}% | {r['total_trades']:^6} | {r['win_rate']:6.1f}% | {r['max_drawdown']:6.2f}%")
        
        # 전략별 평균
        self.log(f"\n\n{'='*80}")
        self.log(f"📈 전략별 평균 수익률")
        self.log(f"{'='*80}")
        
        strategy_avg = {}
        for r in all_results:
            if r['strategy'] not in strategy_avg:
                strategy_avg[r['strategy']] = []
            strategy_avg[r['strategy']].append(r['total_return'])
        
        avg_results = [(s, sum(v)/len(v)) for s, v in strategy_avg.items()]
        avg_results.sort(key=lambda x: x[1], reverse=True)
        
        for i, (strategy, avg_return) in enumerate(avg_results, 1):
            emoji = "🏆" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "  "))
            self.log(f"{emoji} {i:2}. {strategy}: {avg_return:+.2f}%")
        
        # 최고 성과
        if all_results:
            best = all_results[0]
            self.log(f"\n\n{'='*80}")
            self.log(f"🏆 최고 추천 전략")
            self.log(f"{'='*80}")
            self.log(f"전략: {best['strategy']}")
            self.log(f"코인: {best['ticker']}")
            self.log(f"수익률: {best['total_return']:+.2f}%")
            self.log(f"최종 자산: ₩{best['final_value']:,.0f}")
            self.log(f"거래 횟수: {best['total_trades']}회")
            self.log(f"승률: {best['win_rate']:.1f}%")
        
        # JSON 저장
        with open("backtest_results.json", "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
        
        self.log(f"\n\n✅ 백테스트 완료!")
        self.log(f"📁 상세 로그: {self.log_file}")
        self.log(f"📁 JSON 결과: backtest_results.json")
        
        return all_results


if __name__ == "__main__":
    engine = BacktestEngine(initial_capital=1_000_000)
    
    test_tickers = [
        "KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE",
        "KRW-ADA", "KRW-AVAX", "KRW-LINK", "KRW-DOT", "KRW-MATIC"
    ]
    
    results = engine.run_all_strategies(test_tickers)
