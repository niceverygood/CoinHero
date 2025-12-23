"""
자동매매 엔진 모듈
"""
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import time

from upbit_client import upbit_client
from strategies import (
    VolatilityBreakout, 
    MovingAverageCross, 
    RSIStrategy, 
    CombinedStrategy
)
from config import DEFAULT_TRADE_AMOUNT, MAX_COINS
from coin_scanner import coin_scanner


class StrategyType(str, Enum):
    VOLATILITY = "volatility"
    MA_CROSS = "ma_cross"
    RSI = "rsi"
    COMBINED = "combined"


@dataclass
class TradeLog:
    """거래 기록"""
    timestamp: str
    ticker: str
    side: str  # buy or sell
    price: float
    volume: float
    amount: float
    strategy: str
    reason: str
    success: bool
    error: Optional[str] = None


@dataclass
class BotStatus:
    """봇 상태"""
    is_running: bool
    strategy: str
    target_coins: List[str]
    trade_amount: int
    last_check: Optional[str]
    total_trades: int
    successful_trades: int
    scan_mode: bool = False
    min_score: float = 65
    min_volume: float = 1_000_000_000


class TradingEngine:
    """자동매매 엔진"""
    
    def __init__(self):
        self.client = upbit_client
        self.is_running = False
        self.strategy_type = StrategyType.VOLATILITY
        self.target_coins = ["KRW-BTC", "KRW-ETH"]
        self.trade_amount = DEFAULT_TRADE_AMOUNT
        self.trade_logs: List[TradeLog] = []
        self.positions: Dict[str, Dict[str, Any]] = {}  # 보유 포지션
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.check_interval = 60  # 체크 주기 (초)
        self.last_check: Optional[str] = None
        self.callbacks: List[callable] = []  # WebSocket 콜백
        
        # 전체 코인 스캔 모드
        self.scan_mode = False  # True면 전체 코인 스캔
        self.min_volume = 1_000_000_000  # 최소 거래대금 10억
        self.min_score = 65  # 최소 점수
        self.scan_interval = 300  # 스캔 주기 (초, 5분)
        
    def add_callback(self, callback: callable):
        """콜백 추가"""
        self.callbacks.append(callback)
        
    def remove_callback(self, callback: callable):
        """콜백 제거"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    async def notify(self, event_type: str, data: Any):
        """이벤트 알림"""
        message = {"type": event_type, "data": data, "timestamp": datetime.now().isoformat()}
        for callback in self.callbacks:
            try:
                await callback(json.dumps(message))
            except Exception as e:
                print(f"콜백 실행 실패: {e}")
    
    def get_strategy(self, ticker: str):
        """전략 인스턴스 반환"""
        if self.strategy_type == StrategyType.VOLATILITY:
            return VolatilityBreakout(ticker)
        elif self.strategy_type == StrategyType.MA_CROSS:
            return MovingAverageCross(ticker)
        elif self.strategy_type == StrategyType.RSI:
            return RSIStrategy(ticker)
        else:
            return CombinedStrategy(ticker)
    
    def get_status(self) -> BotStatus:
        """봇 상태 조회"""
        return BotStatus(
            is_running=self.is_running,
            strategy=self.strategy_type.value,
            target_coins=self.target_coins,
            trade_amount=self.trade_amount,
            last_check=self.last_check,
            total_trades=len(self.trade_logs),
            successful_trades=sum(1 for log in self.trade_logs if log.success),
            scan_mode=self.scan_mode,
            min_score=self.min_score,
            min_volume=self.min_volume
        )
    
    def configure(self, strategy: str = None, coins: List[str] = None, 
                  amount: int = None, interval: int = None,
                  scan_mode: bool = None, min_score: float = None,
                  min_volume: float = None):
        """설정 변경"""
        if strategy:
            self.strategy_type = StrategyType(strategy)
        if coins is not None:
            # coins가 빈 리스트면 전체 스캔 모드로 전환
            if len(coins) == 0:
                self.scan_mode = True
            else:
                self.target_coins = coins
                self.scan_mode = False
        if amount:
            self.trade_amount = amount
        if interval:
            self.check_interval = interval
        if scan_mode is not None:
            self.scan_mode = scan_mode
        if min_score is not None:
            self.min_score = min_score
        if min_volume is not None:
            self.min_volume = min_volume
            
    def start(self):
        """자동매매 시작"""
        if self.is_running:
            return {"status": "already_running"}
            
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        return {"status": "started", "config": asdict(self.get_status())}
    
    def stop(self):
        """자동매매 중지"""
        if not self.is_running:
            return {"status": "not_running"}
            
        self.is_running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
            
        return {"status": "stopped"}
    
    def _run_loop(self):
        """메인 루프"""
        print(f"[{datetime.now()}] 자동매매 시작 - 전략: {self.strategy_type.value}")
        
        while not self._stop_event.is_set():
            try:
                self._check_and_trade()
                self.last_check = datetime.now().isoformat()
            except Exception as e:
                print(f"[{datetime.now()}] 체크 오류: {e}")
                
            self._stop_event.wait(self.check_interval)
            
        print(f"[{datetime.now()}] 자동매매 종료")
    
    def _check_and_trade(self):
        """시그널 체크 및 거래 실행"""
        
        # 전체 코인 스캔 모드
        if self.scan_mode:
            self._scan_and_trade()
            return
        
        # 기존 특정 코인 모드
        for ticker in self.target_coins:
            strategy = self.get_strategy(ticker)
            coin = ticker.replace("KRW-", "")
            
            # 현재 보유량 확인
            balance = self.client.get_balance(coin)
            has_position = balance > 0
            
            if has_position:
                # 매도 시그널 체크
                should_sell, reason = strategy.should_sell()
                if should_sell:
                    self._execute_sell(ticker, balance, reason)
            else:
                # 매수 시그널 체크
                should_buy, reason = strategy.should_buy()
                if should_buy:
                    self._execute_buy(ticker, reason)
                    
            print(f"[{datetime.now()}] {ticker} 체크 완료 - 보유: {has_position}")
    
    def _scan_and_trade(self):
        """전체 코인 스캔 및 자동 거래"""
        print(f"[{datetime.now()}] 전체 코인 스캔 모드 실행...")
        
        # 전체 코인 스캔
        results = coin_scanner.scan_all_coins(min_volume=self.min_volume)
        
        # 보유 코인 매도 체크
        balances = self.client.get_balances()
        for b in balances:
            if b['currency'] == 'KRW':
                continue
            ticker = f"KRW-{b['currency']}"
            balance = b['balance']
            if balance > 0:
                # 해당 코인의 스캔 결과 확인
                coin_result = next((c for c in results if c.ticker == ticker), None)
                if coin_result:
                    # 매도 조건: 점수가 낮거나 과매수 상태
                    if coin_result.score < 40 or coin_result.signals.get('rsi_overbought', False):
                        reason = f"스캔 결과: 점수 {coin_result.score}, 추천 {coin_result.recommendation}"
                        self._execute_sell(ticker, balance, reason)
        
        # 매수 후보 선정
        buy_candidates = coin_scanner.get_buy_candidates(self.min_score)
        
        if buy_candidates:
            # 현재 보유 코인 수 확인
            current_positions = len([b for b in balances if b['currency'] != 'KRW' and b['balance'] > 0])
            
            # 최대 보유 코인 수 체크
            if current_positions < MAX_COINS:
                # KRW 잔고 확인
                krw_balance = self.client.get_balance("KRW")
                
                for candidate in buy_candidates[:3]:  # 상위 3개만 검토
                    if krw_balance < self.trade_amount:
                        break
                    
                    # 이미 보유 중인지 확인
                    coin = candidate.ticker.replace("KRW-", "")
                    if self.client.get_balance(coin) > 0:
                        continue
                    
                    # 매수 실행
                    reason = f"스캔 점수 {candidate.score}: " + ", ".join(candidate.reasons[:3])
                    self._execute_buy(candidate.ticker, reason)
                    krw_balance -= self.trade_amount
                    
                    print(f"[{datetime.now()}] 스캔 매수: {candidate.ticker} (점수: {candidate.score})")
        
        print(f"[{datetime.now()}] 전체 코인 스캔 완료 - 후보: {len(buy_candidates)}개")
    
    def _execute_buy(self, ticker: str, reason: str):
        """매수 실행"""
        # 최대 코인 수 체크
        current_positions = len([c for c in self.target_coins 
                                if self.client.get_balance(c.replace("KRW-", "")) > 0])
        if current_positions >= MAX_COINS:
            print(f"[{datetime.now()}] 최대 보유 코인 수 도달")
            return
            
        # KRW 잔고 체크
        krw_balance = self.client.get_balance("KRW")
        if krw_balance < self.trade_amount:
            print(f"[{datetime.now()}] KRW 잔고 부족: {krw_balance:,.0f}")
            return
            
        # 매수 실행
        current_price = self.client.get_current_price(ticker)
        result = self.client.buy_market_order(ticker, self.trade_amount)
        
        success = 'error' not in result
        log = TradeLog(
            timestamp=datetime.now().isoformat(),
            ticker=ticker,
            side="buy",
            price=current_price or 0,
            volume=self.trade_amount / (current_price or 1),
            amount=self.trade_amount,
            strategy=self.strategy_type.value,
            reason=reason,
            success=success,
            error=result.get('error') if not success else None
        )
        self.trade_logs.append(log)
        
        if success:
            print(f"[{datetime.now()}] 매수 성공: {ticker} {self.trade_amount:,}원")
        else:
            print(f"[{datetime.now()}] 매수 실패: {ticker} - {result.get('error')}")
    
    def _execute_sell(self, ticker: str, volume: float, reason: str):
        """매도 실행"""
        current_price = self.client.get_current_price(ticker)
        result = self.client.sell_market_order(ticker, volume)
        
        success = 'error' not in result
        log = TradeLog(
            timestamp=datetime.now().isoformat(),
            ticker=ticker,
            side="sell",
            price=current_price or 0,
            volume=volume,
            amount=volume * (current_price or 0),
            strategy=self.strategy_type.value,
            reason=reason,
            success=success,
            error=result.get('error') if not success else None
        )
        self.trade_logs.append(log)
        
        if success:
            print(f"[{datetime.now()}] 매도 성공: {ticker} {volume}개")
        else:
            print(f"[{datetime.now()}] 매도 실패: {ticker} - {result.get('error')}")
    
    def manual_buy(self, ticker: str, amount: int = None) -> Dict[str, Any]:
        """수동 매수"""
        amount = amount or self.trade_amount
        current_price = self.client.get_current_price(ticker)
        result = self.client.buy_market_order(ticker, amount)
        
        success = 'error' not in result
        log = TradeLog(
            timestamp=datetime.now().isoformat(),
            ticker=ticker,
            side="buy",
            price=current_price or 0,
            volume=amount / (current_price or 1),
            amount=amount,
            strategy="manual",
            reason="수동 매수",
            success=success,
            error=result.get('error') if not success else None
        )
        self.trade_logs.append(log)
        
        return {
            "success": success,
            "result": result,
            "log": asdict(log)
        }
    
    def manual_sell(self, ticker: str, volume: float = None) -> Dict[str, Any]:
        """수동 매도"""
        coin = ticker.replace("KRW-", "")
        if volume is None:
            volume = self.client.get_balance(coin)
            
        if volume <= 0:
            return {"success": False, "error": "보유량 없음"}
            
        current_price = self.client.get_current_price(ticker)
        result = self.client.sell_market_order(ticker, volume)
        
        success = 'error' not in result
        log = TradeLog(
            timestamp=datetime.now().isoformat(),
            ticker=ticker,
            side="sell",
            price=current_price or 0,
            volume=volume,
            amount=volume * (current_price or 0),
            strategy="manual",
            reason="수동 매도",
            success=success,
            error=result.get('error') if not success else None
        )
        self.trade_logs.append(log)
        
        return {
            "success": success,
            "result": result,
            "log": asdict(log)
        }
    
    def get_trade_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """거래 기록 조회"""
        logs = self.trade_logs[-limit:]
        return [asdict(log) for log in reversed(logs)]
    
    def get_analysis(self, ticker: str) -> Dict[str, Any]:
        """코인 분석 정보"""
        from strategies import calculate_bollinger_bands, calculate_macd, calculate_stochastic
        
        df = self.client.get_ohlcv(ticker, interval="day", count=100)
        if df is None or df.empty:
            return {"error": "데이터 조회 실패"}
            
        current_price = self.client.get_current_price(ticker)
        
        # 각 전략 시그널
        vol_strategy = VolatilityBreakout(ticker)
        ma_strategy = MovingAverageCross(ticker)
        rsi_strategy = RSIStrategy(ticker)
        
        vol_buy, vol_reason = vol_strategy.should_buy()
        ma_buy, ma_reason = ma_strategy.should_buy()
        rsi_buy, rsi_reason = rsi_strategy.should_buy()
        
        # 기술적 지표
        bb = calculate_bollinger_bands(df)
        macd = calculate_macd(df)
        stoch = calculate_stochastic(df)
        
        return {
            "ticker": ticker,
            "current_price": current_price,
            "signals": {
                "volatility": {"buy": vol_buy, "reason": vol_reason},
                "ma_cross": {"buy": ma_buy, "reason": ma_reason},
                "rsi": {"buy": rsi_buy, "reason": rsi_reason}
            },
            "indicators": {
                "bollinger": {
                    "upper": bb['upper'].iloc[-1],
                    "middle": bb['middle'].iloc[-1],
                    "lower": bb['lower'].iloc[-1]
                },
                "macd": {
                    "macd": macd['macd'].iloc[-1],
                    "signal": macd['signal'].iloc[-1],
                    "histogram": macd['histogram'].iloc[-1]
                },
                "stochastic": {
                    "k": stoch['k'].iloc[-1],
                    "d": stoch['d'].iloc[-1]
                }
            },
            "ohlcv": df.tail(30).reset_index().to_dict(orient='records')
        }


# 싱글톤 인스턴스
trading_engine = TradingEngine()

