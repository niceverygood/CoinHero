"""
AI 기반 단타 자동매매 트레이더
- 선택한 전략을 바탕으로 AI가 시장을 분석하고 최적의 매매 실행
"""
import asyncio
import aiohttp
import json
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

# OpenRouter API 설정
OPENROUTER_API_KEY = "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# AI 모델
AI_MODEL = "anthropic/claude-sonnet-4"


@dataclass
class AITradeDecision:
    """AI 매매 결정"""
    ticker: str
    coin_name: str
    action: str  # buy, sell, hold
    confidence: int  # 0-100
    reason: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    position_size: Optional[float] = None  # 투자 비중 (0.0-1.0)


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
    ai_reason: str


@dataclass
class TradeRecord:
    """거래 기록"""
    id: str
    ticker: str
    coin_name: str
    action: str
    strategy: str
    price: float
    amount: float
    total: float
    reason: str
    ai_analysis: str
    timestamp: str
    profit: Optional[float] = None
    profit_rate: Optional[float] = None


class AIScalpingTrader:
    """AI 기반 단타 자동매매 트레이더"""
    
    def __init__(self):
        self.client = upbit_client
        self.scanner = scalping_scanner
        self.api_key = OPENROUTER_API_KEY
        
        # 상태
        self.is_running = False
        self.selected_strategy: Optional[StrategyType] = None
        self.trade_amount: float = 10000
        self.max_positions: int = 3
        self.scan_interval: int = 60
        
        # 기록
        self.positions: Dict[str, Position] = {}
        self.trade_logs: List[TradeRecord] = []
        self.ai_logs: List[Dict] = []
        self.last_scan_time: Optional[str] = None
        self.last_ai_analysis: Optional[Dict] = None
        
        # 스레드 관리
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 조회"""
        strategy_info = None
        if self.selected_strategy:
            info = STRATEGIES[self.selected_strategy]
            strategy_info = {
                "id": info.id,
                "name": info.name,
                "name_kr": info.name_kr,
                "emoji": info.emoji
            }
        
        return {
            "is_running": self.is_running,
            "selected_strategy": self.selected_strategy.value if self.selected_strategy else None,
            "strategy_info": strategy_info,
            "trade_amount": self.trade_amount,
            "max_positions": self.max_positions,
            "scan_interval": self.scan_interval,
            "current_positions": len(self.positions),
            "positions": [asdict(p) for p in self.positions.values()],
            "last_scan_time": self.last_scan_time,
            "last_ai_analysis": self.last_ai_analysis
        }
    
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
        
        self.trade_amount = max(5000, trade_amount)
        self.max_positions = max(1, min(10, max_positions))
        self.scan_interval = max(30, scan_interval)
        
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
        
        strategy_info = STRATEGIES[self.selected_strategy]
        return {
            "status": "started",
            "strategy": self.selected_strategy.value,
            "message": f"🤖 AI + {strategy_info.name_kr} 전략 자동매매 시작"
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
        strategy_info = STRATEGIES[self.selected_strategy]
        print(f"[{datetime.now()}] 🤖 AI 단타 트레이더 시작 - 전략: {strategy_info.name_kr}")
        
        while not self._stop_event.is_set():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # AI 분석 및 매매 실행
                    loop.run_until_complete(self._ai_analyze_and_trade())
                finally:
                    loop.close()
                
            except Exception as e:
                print(f"[{datetime.now()}] ❌ AI 트레이딩 오류: {e}")
            
            self._stop_event.wait(self.scan_interval)
        
        print(f"[{datetime.now()}] 🛑 AI 단타 트레이더 종료")
    
    async def _ai_analyze_and_trade(self):
        """AI 분석 및 매매 실행"""
        strategy_info = STRATEGIES[self.selected_strategy]
        
        # 1. 전체 코인 스캔
        print(f"[{datetime.now()}] 📊 전체 코인 스캔 중...")
        scan_results = await self.scanner.scan_all_strategies(self.selected_strategy)
        self.last_scan_time = datetime.now().isoformat()
        
        # 선택된 전략의 시그널
        signals = scan_results.get(self.selected_strategy.value, [])
        top_signals = signals[:10]  # 상위 10개
        
        # 2. 현재 보유 포지션 정보
        current_positions_info = []
        for ticker, pos in self.positions.items():
            current_price = self.client.get_current_price(ticker) or pos.entry_price
            profit_rate = (current_price - pos.entry_price) / pos.entry_price * 100
            current_positions_info.append({
                "ticker": ticker,
                "coin": pos.coin_name,
                "entry_price": pos.entry_price,
                "current_price": current_price,
                "profit_rate": round(profit_rate, 2),
                "target_price": pos.target_price,
                "stop_loss": pos.stop_loss
            })
        
        # 3. 잔고 정보
        krw_balance = self.client.get_balance("KRW") or 0
        
        # 4. AI에게 분석 요청
        ai_decisions = await self._call_ai_for_decisions(
            strategy_info=strategy_info,
            signals=top_signals,
            positions=current_positions_info,
            krw_balance=krw_balance
        )
        
        if ai_decisions:
            self.last_ai_analysis = {
                "timestamp": datetime.now().isoformat(),
                "strategy": strategy_info.name_kr,
                "decisions": ai_decisions,
                "signal_count": len(signals)
            }
            
            # 5. AI 결정에 따라 매매 실행
            await self._execute_ai_decisions(ai_decisions)
    
    async def _call_ai_for_decisions(
        self,
        strategy_info,
        signals: List[TradeSignal],
        positions: List[Dict],
        krw_balance: float
    ) -> List[Dict]:
        """AI에게 매매 결정 요청"""
        
        # 시그널 데이터 정리
        signals_text = ""
        for i, sig in enumerate(signals, 1):
            target_str = f"₩{sig.target_price:,.0f}" if sig.target_price else "N/A"
            stop_str = f"₩{sig.stop_loss:,.0f}" if sig.stop_loss else "N/A"
            signals_text += f"""
{i}. {sig.coin_name} ({sig.ticker})
   - 현재가: ₩{sig.current_price:,.0f}
   - 점수: {sig.score:.0f}점
   - 신호: {sig.reason}
   - 목표가: {target_str}
   - 손절가: {stop_str}
"""
        
        # 포지션 데이터 정리
        positions_text = "없음"
        if positions:
            positions_text = ""
            for pos in positions:
                emoji = "📈" if pos['profit_rate'] >= 0 else "📉"
                positions_text += f"""
- {pos['coin']}: 진입가 ₩{pos['entry_price']:,.0f} → 현재가 ₩{pos['current_price']:,.0f} ({emoji} {pos['profit_rate']:+.2f}%)
  목표가: ₩{pos['target_price']:,.0f}, 손절가: ₩{pos['stop_loss']:,.0f}
"""
        
        prompt = f"""당신은 암호화폐 단타 매매 전문 AI 트레이더입니다.
현재 "{strategy_info.name_kr}" 전략을 사용 중입니다.

## 전략 설명
{strategy_info.description}
- 리스크: {strategy_info.risk_level}
- 평균 보유 시간: {strategy_info.holding_time}
- 예상 승률: {strategy_info.win_rate}

## 현재 시장 스캔 결과 (상위 매수 후보)
{signals_text if signals_text else "현재 조건에 맞는 코인 없음"}

## 현재 보유 포지션
{positions_text}

## 가용 자금
₩{krw_balance:,.0f}

## 설정
- 1회 거래 금액: ₩{self.trade_amount:,.0f}
- 최대 동시 보유: {self.max_positions}개
- 현재 보유: {len(positions)}개

## 요청
위 정보를 바탕으로 최적의 매매 결정을 내려주세요.
{strategy_info.name_kr} 전략의 원칙을 준수하되, 시장 상황을 종합적으로 판단하여 수익을 극대화하세요.

다음 JSON 형식으로 응답해주세요:
```json
{{
  "decisions": [
    {{
      "action": "buy" | "sell" | "hold",
      "ticker": "KRW-XXX",
      "coin_name": "XXX",
      "confidence": 0-100,
      "reason": "매매 이유 (한국어, 구체적으로)",
      "target_price": 목표가(숫자),
      "stop_loss": 손절가(숫자),
      "position_size": 0.0-1.0 (투자 비중, buy일 때만)
    }}
  ],
  "market_summary": "현재 시장 상황 요약 (한국어)",
  "strategy_note": "전략 적용 관련 코멘트 (한국어)"
}}
```

중요:
- 확신이 낮으면 hold로 응답
- 보유 중인 코인의 익절/손절 판단도 포함
- confidence 70 이상일 때만 매수 권장
- 손절 라인 도달 시 반드시 매도 권장
"""

        try:
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://coinhero.app",
                    "X-Title": "CoinHero AI Scalping Trader"
                }
                
                payload = {
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are an expert cryptocurrency scalping trader AI. Always respond in valid JSON format."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                }
                
                async with session.post(
                    OPENROUTER_BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']
                        
                        # JSON 파싱
                        try:
                            # JSON 블록 추출
                            if "```json" in content:
                                json_str = content.split("```json")[1].split("```")[0]
                            elif "```" in content:
                                json_str = content.split("```")[1].split("```")[0]
                            else:
                                json_str = content
                            
                            result = json.loads(json_str.strip())
                            
                            # AI 로그 저장
                            self.ai_logs.append({
                                "timestamp": datetime.now().isoformat(),
                                "strategy": strategy_info.name_kr,
                                "market_summary": result.get("market_summary", ""),
                                "strategy_note": result.get("strategy_note", ""),
                                "decisions": result.get("decisions", [])
                            })
                            
                            print(f"[{datetime.now()}] 🧠 AI 분석 완료: {result.get('market_summary', '')[:50]}...")
                            
                            return result.get("decisions", [])
                            
                        except json.JSONDecodeError as e:
                            print(f"[{datetime.now()}] ⚠️ AI 응답 파싱 실패: {e}")
                            return []
                    else:
                        error = await response.text()
                        print(f"[{datetime.now()}] ❌ AI API 오류: {response.status} - {error[:100]}")
                        return []
                        
        except Exception as e:
            print(f"[{datetime.now()}] ❌ AI 호출 실패: {e}")
            return []
    
    async def _execute_ai_decisions(self, decisions: List[Dict]):
        """AI 결정에 따라 매매 실행"""
        for decision in decisions:
            action = decision.get("action", "hold")
            ticker = decision.get("ticker")
            confidence = decision.get("confidence", 0)
            reason = decision.get("reason", "")
            
            if action == "hold" or not ticker:
                continue
            
            if action == "buy" and confidence >= 70:
                # 매수 조건 확인
                if len(self.positions) >= self.max_positions:
                    print(f"[{datetime.now()}] ⚠️ 최대 포지션 도달, 매수 스킵: {ticker}")
                    continue
                
                if ticker in self.positions:
                    print(f"[{datetime.now()}] ⚠️ 이미 보유 중: {ticker}")
                    continue
                
                # 매수 실행
                await self._execute_buy(
                    ticker=ticker,
                    coin_name=decision.get("coin_name", ticker.replace("KRW-", "")),
                    reason=reason,
                    target_price=decision.get("target_price"),
                    stop_loss=decision.get("stop_loss"),
                    position_size=decision.get("position_size", 1.0)
                )
                
            elif action == "sell" and ticker in self.positions:
                # 매도 실행
                await self._execute_sell(
                    ticker=ticker,
                    reason=reason
                )
    
    async def _execute_buy(
        self,
        ticker: str,
        coin_name: str,
        reason: str,
        target_price: Optional[float],
        stop_loss: Optional[float],
        position_size: float
    ):
        """매수 실행"""
        try:
            krw_balance = self.client.get_balance("KRW") or 0
            trade_amount = min(self.trade_amount * position_size, krw_balance * 0.95)
            
            if trade_amount < 5000:
                print(f"[{datetime.now()}] ⚠️ 잔고 부족: {krw_balance:,.0f}원")
                return
            
            current_price = self.client.get_current_price(ticker)
            if not current_price:
                print(f"[{datetime.now()}] ⚠️ 현재가 조회 실패: {ticker}")
                return
            
            # 시장가 매수
            result = self.client.buy_market(ticker, trade_amount)
            
            if result:
                # 기본 목표가/손절가 설정
                if not target_price:
                    target_price = current_price * 1.03
                if not stop_loss:
                    stop_loss = current_price * 0.98
                
                # 포지션 기록
                self.positions[ticker] = Position(
                    ticker=ticker,
                    coin_name=coin_name,
                    strategy=self.selected_strategy.value,
                    entry_price=current_price,
                    amount=trade_amount / current_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    entry_time=datetime.now().isoformat(),
                    ai_reason=reason
                )
                
                # 거래 기록
                self.trade_logs.append(TradeRecord(
                    id=f"buy_{ticker}_{datetime.now().strftime('%H%M%S')}",
                    ticker=ticker,
                    coin_name=coin_name,
                    action="buy",
                    strategy=self.selected_strategy.value,
                    price=current_price,
                    amount=trade_amount / current_price,
                    total=trade_amount,
                    reason=f"AI 매수 신호",
                    ai_analysis=reason,
                    timestamp=datetime.now().isoformat()
                ))
                
                print(f"[{datetime.now()}] ✅ AI 매수 완료: {coin_name} @ ₩{current_price:,.0f}")
                print(f"   📝 이유: {reason[:50]}...")
            else:
                print(f"[{datetime.now()}] ❌ 매수 실패: {coin_name}")
                
        except Exception as e:
            print(f"[{datetime.now()}] ❌ 매수 오류: {e}")
    
    async def _execute_sell(self, ticker: str, reason: str):
        """매도 실행"""
        try:
            if ticker not in self.positions:
                return
            
            pos = self.positions[ticker]
            coin = ticker.replace("KRW-", "")
            
            balance = self.client.get_balance(coin) or 0
            if balance <= 0:
                del self.positions[ticker]
                return
            
            current_price = self.client.get_current_price(ticker)
            if not current_price:
                return
            
            # 시장가 매도
            result = self.client.sell_market(ticker, balance)
            
            if result:
                profit_rate = (current_price - pos.entry_price) / pos.entry_price * 100
                profit = (current_price - pos.entry_price) * balance
                
                # 거래 기록
                self.trade_logs.append(TradeRecord(
                    id=f"sell_{ticker}_{datetime.now().strftime('%H%M%S')}",
                    ticker=ticker,
                    coin_name=pos.coin_name,
                    action="sell",
                    strategy=pos.strategy,
                    price=current_price,
                    amount=balance,
                    total=current_price * balance,
                    reason=f"AI 매도 신호",
                    ai_analysis=reason,
                    timestamp=datetime.now().isoformat(),
                    profit=profit,
                    profit_rate=profit_rate
                ))
                
                emoji = "📈" if profit_rate >= 0 else "📉"
                print(f"[{datetime.now()}] {emoji} AI 매도 완료: {pos.coin_name} @ ₩{current_price:,.0f} ({profit_rate:+.2f}%)")
                print(f"   📝 이유: {reason[:50]}...")
                
                del self.positions[ticker]
            else:
                print(f"[{datetime.now()}] ❌ 매도 실패: {pos.coin_name}")
                
        except Exception as e:
            print(f"[{datetime.now()}] ❌ 매도 오류: {e}")
    
    def get_trade_logs(self, limit: int = 20) -> List[Dict]:
        """거래 기록 조회"""
        return [asdict(log) for log in reversed(self.trade_logs[-limit:])]
    
    def get_ai_logs(self, limit: int = 10) -> List[Dict]:
        """AI 분석 로그 조회"""
        return list(reversed(self.ai_logs[-limit:]))
    
    async def manual_analysis(self) -> Dict:
        """수동 AI 분석"""
        if not self.selected_strategy:
            return {"error": "전략을 먼저 선택하세요"}
        
        strategy_info = STRATEGIES[self.selected_strategy]
        
        # 스캔
        scan_results = await self.scanner.scan_all_strategies(self.selected_strategy)
        signals = scan_results.get(self.selected_strategy.value, [])[:10]
        
        # 포지션 정보
        positions = []
        for ticker, pos in self.positions.items():
            current_price = self.client.get_current_price(ticker) or pos.entry_price
            profit_rate = (current_price - pos.entry_price) / pos.entry_price * 100
            positions.append({
                "ticker": ticker,
                "coin": pos.coin_name,
                "entry_price": pos.entry_price,
                "current_price": current_price,
                "profit_rate": round(profit_rate, 2),
                "target_price": pos.target_price,
                "stop_loss": pos.stop_loss
            })
        
        krw_balance = self.client.get_balance("KRW") or 0
        
        # AI 분석
        decisions = await self._call_ai_for_decisions(
            strategy_info=strategy_info,
            signals=signals,
            positions=positions,
            krw_balance=krw_balance
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "strategy": strategy_info.name_kr,
            "signal_count": len(signals),
            "decisions": decisions,
            "top_signals": [asdict(s) for s in signals[:5]]
        }


# 싱글톤 인스턴스
ai_scalping_trader = AIScalpingTrader()

