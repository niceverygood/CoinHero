"""
단타 자동매매 트레이더
- 선택한 전략으로 전체 코인 스캔 후 자동 매매
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
from threading import Thread, Event
import time

from upbit_client import upbit_client
from scalping_strategies import (
    scalping_scanner, 
    StrategyType, 
    STRATEGIES, 
    TradeSignal
)


@dataclass
class TradeRecord:
    """거래 기록"""
    id: str
    ticker: str
    coin_name: str
    action: str  # buy, sell
    strategy: str
    price: float
    amount: float
    total: float
    reason: str
    timestamp: str
    profit: Optional[float] = None
    profit_rate: Optional[float] = None


@dataclass 
class Position:
    """보유 포지션"""
    ticker: str
    coin_name: str
    strategy: str
    entry_price: float
    amount: float
    target_price: float
    stop_loss: float
    entry_time: str
    

class ScalpingTrader:
    """단타 자동매매 트레이더"""
    
    def __init__(self):
        self.client = upbit_client
        self.scanner = scalping_scanner
        
        # 상태
        self.is_running = False
        self.selected_strategy: Optional[StrategyType] = None
        self.trade_amount: float = 10000  # 기본 1만원
        self.max_positions: int = 3  # 최대 동시 보유 수
        self.scan_interval: int = 60  # 스캔 간격 (초)
        
        # 기록
        self.positions: Dict[str, Position] = {}
        self.trade_logs: List[TradeRecord] = []
        self.scan_results: Dict[str, List[TradeSignal]] = {}
        self.last_scan_time: Optional[str] = None
        
        # 스레드 관리
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 조회"""
        return {
            "is_running": self.is_running,
            "selected_strategy": self.selected_strategy.value if self.selected_strategy else None,
            "strategy_info": asdict(STRATEGIES[self.selected_strategy]) if self.selected_strategy else None,
            "trade_amount": self.trade_amount,
            "max_positions": self.max_positions,
            "scan_interval": self.scan_interval,
            "current_positions": len(self.positions),
            "positions": [asdict(p) for p in self.positions.values()],
            "last_scan_time": self.last_scan_time,
            "recent_signals": self._get_recent_signals()
        }
    
    def _get_recent_signals(self) -> List[Dict]:
        """최근 스캔 결과"""
        if not self.scan_results:
            return []
        
        strategy_key = self.selected_strategy.value if self.selected_strategy else None
        if strategy_key and strategy_key in self.scan_results:
            return [asdict(s) for s in self.scan_results[strategy_key][:5]]
        
        # 전체 상위 시그널
        all_signals = self.scanner.get_top_signals(self.scan_results, 5)
        return [asdict(s) for s in all_signals]
    
    def configure(
        self,
        strategy: str,
        trade_amount: float = 10000,
        max_positions: int = 3,
        scan_interval: int = 60
    ):
        """설정 변경"""
        try:
            self.selected_strategy = StrategyType(strategy)
        except ValueError:
            raise ValueError(f"알 수 없는 전략: {strategy}")
        
        self.trade_amount = max(5000, trade_amount)  # 최소 5천원
        self.max_positions = max(1, min(10, max_positions))  # 1~10개
        self.scan_interval = max(30, scan_interval)  # 최소 30초
        
        return self.get_status()
    
    def start(self):
        """자동매매 시작"""
        if self.is_running:
            return {"status": "already_running"}
        
        if not self.selected_strategy:
            raise ValueError("전략을 먼저 선택하세요")
        
        self.is_running = True
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        return {
            "status": "started",
            "strategy": self.selected_strategy.value,
            "message": f"{STRATEGIES[self.selected_strategy].name_kr} 전략 시작"
        }
    
    def stop(self):
        """자동매매 중지"""
        if not self.is_running:
            return {"status": "not_running"}
        
        self.is_running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=5)
        
        return {
            "status": "stopped",
            "message": "자동매매 중지됨"
        }
    
    def _run_loop(self):
        """자동매매 루프"""
        print(f"[{datetime.now()}] 🚀 단타 트레이더 시작 - 전략: {self.selected_strategy.value}")
        
        while not self._stop_event.is_set():
            try:
                # 비동기 스캔 실행
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # 스캔
                    self.scan_results = loop.run_until_complete(
                        self.scanner.scan_all_strategies(self.selected_strategy)
                    )
                    self.last_scan_time = datetime.now().isoformat()
                    
                    # 매매 체크
                    self._check_and_trade()
                    
                finally:
                    loop.close()
                
            except Exception as e:
                print(f"[{datetime.now()}] ❌ 트레이딩 오류: {e}")
            
            # 대기
            self._stop_event.wait(self.scan_interval)
        
        print(f"[{datetime.now()}] 🛑 단타 트레이더 종료")
    
    def _check_and_trade(self):
        """매매 체크 및 실행"""
        if not self.selected_strategy:
            return
        
        strategy_key = self.selected_strategy.value
        signals = self.scan_results.get(strategy_key, [])
        
        print(f"[{datetime.now()}] 📊 스캔 완료: {len(signals)}개 시그널")
        
        # 1. 기존 포지션 청산 체크
        self._check_exit_positions()
        
        # 2. 새 진입 체크
        if len(self.positions) < self.max_positions:
            for signal in signals:
                if signal.ticker in self.positions:
                    continue
                
                if signal.score >= 60:  # 60점 이상만
                    self._execute_buy(signal)
                    
                    if len(self.positions) >= self.max_positions:
                        break
    
    def _check_exit_positions(self):
        """포지션 청산 체크"""
        positions_to_close = []
        
        for ticker, pos in self.positions.items():
            try:
                current_price = self.client.get_current_price(ticker)
                if current_price is None:
                    continue
                
                profit_rate = (current_price - pos.entry_price) / pos.entry_price * 100
                
                # 익절
                if current_price >= pos.target_price:
                    positions_to_close.append((ticker, "익절", profit_rate, current_price))
                    continue
                
                # 손절
                if current_price <= pos.stop_loss:
                    positions_to_close.append((ticker, "손절", profit_rate, current_price))
                    continue
                
                # 시간 초과 (전략별)
                entry_time = datetime.fromisoformat(pos.entry_time)
                holding_hours = (datetime.now() - entry_time).total_seconds() / 3600
                
                # 스캘핑은 1시간, 다른 전략은 24시간
                max_hours = 1 if pos.strategy == "scalping_5min" else 24
                if holding_hours > max_hours:
                    positions_to_close.append((ticker, "시간초과", profit_rate, current_price))
                    
            except Exception as e:
                print(f"[{datetime.now()}] ⚠️ 포지션 체크 오류 ({ticker}): {e}")
        
        # 청산 실행
        for ticker, reason, profit_rate, price in positions_to_close:
            self._execute_sell(ticker, reason, profit_rate, price)
    
    def _execute_buy(self, signal: TradeSignal):
        """매수 실행"""
        try:
            ticker = signal.ticker
            
            # 보유 원화 확인
            krw_balance = self.client.get_balance("KRW") or 0
            if krw_balance < self.trade_amount:
                print(f"[{datetime.now()}] ⚠️ 원화 부족: {krw_balance:,.0f}원")
                return
            
            # 시장가 매수
            result = self.client.buy_market(ticker, self.trade_amount)
            
            if result:
                # 포지션 기록
                self.positions[ticker] = Position(
                    ticker=ticker,
                    coin_name=signal.coin_name,
                    strategy=signal.strategy,
                    entry_price=signal.current_price,
                    amount=self.trade_amount / signal.current_price,
                    target_price=signal.target_price or signal.current_price * 1.03,
                    stop_loss=signal.stop_loss or signal.current_price * 0.98,
                    entry_time=datetime.now().isoformat()
                )
                
                # 거래 기록
                self.trade_logs.append(TradeRecord(
                    id=f"buy_{ticker}_{datetime.now().strftime('%H%M%S')}",
                    ticker=ticker,
                    coin_name=signal.coin_name,
                    action="buy",
                    strategy=signal.strategy,
                    price=signal.current_price,
                    amount=self.trade_amount / signal.current_price,
                    total=self.trade_amount,
                    reason=signal.reason,
                    timestamp=datetime.now().isoformat()
                ))
                
                print(f"[{datetime.now()}] ✅ 매수 완료: {signal.coin_name} @ {signal.current_price:,.0f} ({signal.strategy})")
            else:
                print(f"[{datetime.now()}] ❌ 매수 실패: {signal.coin_name}")
                
        except Exception as e:
            print(f"[{datetime.now()}] ❌ 매수 오류: {e}")
    
    def _execute_sell(self, ticker: str, reason: str, profit_rate: float, price: float):
        """매도 실행"""
        try:
            if ticker not in self.positions:
                return
            
            pos = self.positions[ticker]
            coin = ticker.replace("KRW-", "")
            
            # 보유 수량 확인
            balance = self.client.get_balance(coin) or 0
            if balance <= 0:
                del self.positions[ticker]
                return
            
            # 시장가 매도
            result = self.client.sell_market(ticker, balance)
            
            if result:
                profit = (price - pos.entry_price) * balance
                
                # 거래 기록
                self.trade_logs.append(TradeRecord(
                    id=f"sell_{ticker}_{datetime.now().strftime('%H%M%S')}",
                    ticker=ticker,
                    coin_name=pos.coin_name,
                    action="sell",
                    strategy=pos.strategy,
                    price=price,
                    amount=balance,
                    total=price * balance,
                    reason=reason,
                    timestamp=datetime.now().isoformat(),
                    profit=profit,
                    profit_rate=profit_rate
                ))
                
                emoji = "📈" if profit_rate >= 0 else "📉"
                print(f"[{datetime.now()}] {emoji} 매도 완료: {pos.coin_name} @ {price:,.0f} ({reason}, {profit_rate:+.2f}%)")
                
                del self.positions[ticker]
            else:
                print(f"[{datetime.now()}] ❌ 매도 실패: {pos.coin_name}")
                
        except Exception as e:
            print(f"[{datetime.now()}] ❌ 매도 오류: {e}")
    
    def get_trade_logs(self, limit: int = 20) -> List[Dict]:
        """거래 기록 조회"""
        return [asdict(log) for log in reversed(self.trade_logs[-limit:])]
    
    async def manual_scan(self, strategy: Optional[str] = None) -> Dict[str, Any]:
        """수동 스캔 (비동기)"""
        strategy_type = None
        if strategy:
            try:
                strategy_type = StrategyType(strategy)
            except ValueError:
                pass
        
        results = await self.scanner.scan_all_strategies(strategy_type)
        self.scan_results = results
        self.last_scan_time = datetime.now().isoformat()
        
        # 결과 정리
        summary = {}
        for key, signals in results.items():
            summary[key] = {
                "count": len(signals),
                "top_signals": [asdict(s) for s in signals[:3]]
            }
        
        return {
            "timestamp": self.last_scan_time,
            "strategies": summary,
            "top_picks": [asdict(s) for s in self.scanner.get_top_signals(results, 5)]
        }


# 싱글톤 인스턴스
scalping_trader = ScalpingTrader()

