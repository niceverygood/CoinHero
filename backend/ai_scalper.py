"""
AI 기반 단타 자동매매 시스템
- 선택한 전략을 AI가 이해하고 스스로 판단하여 매매
- OpenRouter API를 통한 실시간 AI 분석
"""
import asyncio
import aiohttp
import ssl
import certifi
import json
import pyupbit
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
from threading import Thread, Event
import time

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from upbit_client import upbit_client
from scalping_strategies import STRATEGIES, StrategyType
from database import db


# AI 모델 설정
AI_MODEL = "anthropic/claude-sonnet-4"  # Claude Sonnet 4


@dataclass
class AITradeDecision:
    """AI 매매 결정"""
    ticker: str
    action: str  # buy, sell, hold
    confidence: int  # 0-100
    amount_percent: int  # 투자금 비율 (10-100%)
    reason: str
    target_price: Optional[float]
    stop_loss: Optional[float]
    timestamp: str


@dataclass
class TradeExecution:
    """거래 실행 기록"""
    id: str
    ticker: str
    coin_name: str
    action: str
    strategy: str
    price: float
    amount: float
    total_krw: float
    ai_reason: str
    ai_confidence: int
    timestamp: str
    profit: Optional[float] = None
    profit_rate: Optional[float] = None


class AIScalper:
    """AI 기반 단타 자동매매"""
    
    # 전략별 AI 프롬프트
    STRATEGY_PROMPTS = {
        "volatility_breakout": """
당신은 '변동성 돌파' 전략 전문가입니다.
래리 윌리엄스의 변동성 돌파 전략을 기반으로 매매합니다.

핵심 원리:
- 전일 고가-저가 범위(변동폭)의 K배(보통 0.5)를 당일 시가에 더한 가격이 목표가
- 현재가가 목표가를 돌파하면 상승 모멘텀으로 판단하여 매수
- 다음날 시가에 매도 (또는 목표 수익률 달성 시)

매수 조건:
1. 현재가 > 시가 + (전일 고가 - 전일 저가) × K
2. 거래량이 평균 대비 증가
3. 시장 전체가 급락하지 않음

매도 조건:
1. 목표 수익률(3-5%) 달성
2. 손절선(-2%) 도달
3. 다음날 09:00 (시간 기반 청산)
""",
        "rsi_reversal": """
당신은 'RSI 반등' 전략 전문가입니다.
RSI(상대강도지수) 기반 평균회귀 전략으로 매매합니다.

핵심 원리:
- RSI 30 이하는 과매도, 70 이상은 과매수
- 과매도 구간에서 반등 시작 시 매수
- 과매수 구간 진입 또는 중간선(50) 도달 시 매도

매수 조건:
1. RSI < 35이고 상승 전환 (이전 RSI보다 높음)
2. 가격이 최근 저점 대비 반등 시작
3. 거래량 증가 동반

매도 조건:
1. RSI > 65 (과매수 근접)
2. 목표 수익률(5-8%) 달성
3. RSI가 하락 전환
""",
        "bollinger_bounce": """
당신은 '볼린저 밴드 반등' 전략 전문가입니다.
볼린저 밴드를 활용한 평균회귀 전략으로 매매합니다.

핵심 원리:
- 볼린저 밴드: 20일 이동평균 ± 2×표준편차
- 가격이 하단 밴드 터치 후 반등 시 매수 (평균으로 회귀 기대)
- 중간선 또는 상단 밴드 도달 시 매도

매수 조건:
1. 가격이 하단 밴드 터치 또는 이탈
2. 반등 캔들 확인 (양봉 또는 아래꼬리)
3. RSI가 과매도 근접 (보조 확인)

매도 조건:
1. 중간선(20일 MA) 도달 - 1차 익절
2. 상단 밴드 도달 - 2차 익절
3. 손절선(-3%) 도달
""",
        "volume_surge": """
당신은 '거래량 급증' 전략 전문가입니다.
거래량 폭발을 동반한 추세 추종 전략으로 매매합니다.

핵심 원리:
- 거래량은 가격에 선행한다
- 평균 거래량 3배 이상 급증 + 양봉 = 강한 매수 신호
- 급등 초기에 진입, 거래량 감소 시 청산

매수 조건:
1. 거래량 > 평균 × 3 (급증)
2. 양봉 (종가 > 시가)
3. 가격 상승률 2% 이상

매도 조건:
1. 거래량 감소 (평균 이하로 하락)
2. 음봉 출현
3. 목표 수익률(5%) 또는 손절(-2%)
""",
        "momentum_breakout": """
당신은 '모멘텀 돌파' 전략 전문가입니다.
신고가 돌파를 활용한 추세 추종 전략으로 매매합니다.

핵심 원리:
- 20일 신고가 돌파 = 강한 상승 모멘텀
- 돌파 직후 매수하여 모멘텀 추종
- 모멘텀 약화 시 청산

매수 조건:
1. 현재가 > 20일 최고가
2. 거래량 증가 동반
3. 돌파 폭 1% 이상

매도 조건:
1. 5일 이동평균 하회
2. 신고가 대비 -5% 하락
3. 목표 수익률(8-10%) 달성
""",
        "scalping_5min": """
당신은 '5분봉 스캘핑' 전략 전문가입니다.
5분봉 기준 RSI + MACD 복합 신호로 초단기 매매합니다.

핵심 원리:
- 5분봉에서 RSI 과매도 + MACD 상향 전환 = 매수
- 빠른 진입, 빠른 청산 (1-2% 목표)
- 손절은 타이트하게 (-1%)

매수 조건:
1. 5분봉 RSI < 40
2. MACD 히스토그램 상향 전환
3. 거래량 증가

매도 조건:
1. 목표 수익률(1.5-2%) 달성
2. RSI > 60
3. MACD 하향 전환
4. 손절(-1%)
""",
        # ========== 래리 윌리엄스 전략들 ==========
        "larry_williams_r": """
당신은 '래리 윌리엄스 %R' 전략 전문가입니다.
래리 윌리엄스가 직접 개발한 Williams %R 지표를 활용합니다.

핵심 원리:
- Williams %R = (최고가 - 현재가) / (최고가 - 최저가) × -100
- 범위: -100 ~ 0
- -80 ~ -100: 과매도 (매수 기회)
- -20 ~ 0: 과매수 (매도 기회)

매수 조건:
1. Williams %R <= -80 (과매도 구간)
2. %R이 상승 전환 (반등 시작)
3. 거래량 증가 동반

매도 조건:
1. Williams %R >= -20 (과매수 구간)
2. 목표 수익률(5%) 달성
3. %R이 하락 전환
4. 손절(-3%)
""",
        "larry_oops": """
당신은 '래리 윌리엄스 OOPS!' 전략 전문가입니다.
갭 하락 후 반등을 노리는 역발상 전략입니다.

핵심 원리:
- 갭 하락(당일 시가 < 전일 저가) 후 공포 매도 발생
- 전일 저가를 다시 상향 돌파하면 반등 신호
- 공포에 매수하는 역발상 전략

매수 조건:
1. 당일 시가 < 전일 저가 (갭 하락)
2. 현재가 > 전일 저가 (상향 돌파)
3. 양봉 (현재가 > 시가)

매도 조건:
1. 전일 고가 도달 (갭 메우기 완료)
2. 목표 수익률(6%) 달성
3. 손절 - 당일 시가 -2%
""",
        "larry_smash_day": """
당신은 '래리 윌리엄스 Smash Day' 전략 전문가입니다.
급락일 다음날 반등을 노리는 전략입니다.

핵심 원리:
- Smash Day: 일중 -3% 이상 또는 전일대비 -5% 이상 급락
- 급락 다음날 시가 대비 상승 시 반등 진입
- 과매도 반등 + 추세 전환 포착

매수 조건:
1. 전일이 Smash Day (급락일)
2. 당일 시가 대비 상승 중
3. 전일 종가 상회

매도 조건:
1. 전일 시가 도달 (반등 목표)
2. 목표 수익률(6%) 달성
3. 손절 - 전일 저가 -2%
""",
        "larry_combo": """
당신은 '래리 윌리엄스 종합' 전략 전문가입니다.
변동성 돌파 + Williams %R + 자금관리를 결합한 종합 전략입니다.

핵심 원리:
- 변동성 돌파로 추세 확인
- Williams %R로 과매도/과매수 확인
- 거래량으로 신뢰도 검증
- 래리 윌리엄스의 자금관리 원칙 적용 (6% 익절, 3% 손절)

매수 조건 (3개 이상 충족):
1. 변동성 돌파 목표가 달성
2. Williams %R -80~-50 (과매도 탈출 중)
3. 거래량 > 평균 × 1.5
4. 양봉

매도 조건:
1. 목표 수익률(6%) 달성 - 래리 윌리엄스 추천
2. Williams %R > -20 (과매수)
3. 손절(-3%) - 래리 윌리엄스 원칙
"""
    }
    
    def __init__(self):
        self.client = upbit_client
        self.is_running = False
        self.selected_strategies: List[str] = []  # 복수 전략 지원
        self.selected_strategy: Optional[str] = None  # 기존 호환성
        self.trade_amount: float = 10000
        self.max_positions: int = 3
        self.check_interval: int = 60
        
        # 포지션 관리
        self.positions: Dict[str, Dict] = {}
        self.trade_logs: List[TradeExecution] = []
        self.ai_decisions: List[AITradeDecision] = []
        
        # 스레드 관리
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 조회"""
        strategy_infos = []
        for s in self.selected_strategies:
            try:
                strategy_infos.append(asdict(STRATEGIES[StrategyType(s)]))
            except:
                pass
        
        return {
            "is_running": self.is_running,
            "strategy": self.selected_strategy,
            "strategies": self.selected_strategies,  # 복수 전략
            "strategy_info": strategy_infos[0] if strategy_infos else None,
            "strategy_infos": strategy_infos,
            "trade_amount": self.trade_amount,
            "max_positions": self.max_positions,
            "check_interval": self.check_interval,
            "current_positions": len(self.positions),
            "positions": list(self.positions.values()),
            "recent_decisions": [asdict(d) for d in self.ai_decisions[-5:]],
            "ai_model": AI_MODEL
        }
    
    def configure(
        self,
        strategy: str = None,
        strategies: List[str] = None,
        trade_amount: float = 10000,
        max_positions: int = 3,
        check_interval: int = 60
    ) -> Dict[str, Any]:
        """설정 (복수 전략 지원)"""
        # 복수 전략 처리
        if strategies and len(strategies) > 0:
            valid_strategies = [s for s in strategies if s in self.STRATEGY_PROMPTS]
            if not valid_strategies:
                raise ValueError("유효한 전략이 없습니다")
            self.selected_strategies = valid_strategies
            self.selected_strategy = valid_strategies[0]  # 기존 호환성
        elif strategy:
            if strategy not in self.STRATEGY_PROMPTS:
                raise ValueError(f"지원하지 않는 전략: {strategy}")
            self.selected_strategies = [strategy]
            self.selected_strategy = strategy
        else:
            raise ValueError("전략을 선택하세요")
        
        self.trade_amount = max(5000, trade_amount)
        self.max_positions = max(1, min(5, max_positions))
        self.check_interval = max(30, check_interval)
        
        return self.get_status()
    
    def start(self) -> Dict[str, Any]:
        """AI 자동매매 시작"""
        if self.is_running:
            return {"status": "already_running"}
        
        if not self.selected_strategies:
            raise ValueError("전략을 먼저 선택하세요")
        
        # 기존 보유 코인을 포지션으로 등록 (재시작 시)
        self._sync_existing_positions()
        
        self.is_running = True
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        strategy_names = [STRATEGIES[StrategyType(s)].name_kr for s in self.selected_strategies]
        return {
            "status": "started",
            "strategy": self.selected_strategy,
            "strategies": self.selected_strategies,
            "message": f"🤖 AI 복합 전략 ({', '.join(strategy_names)}) 자동매매 시작",
            "synced_positions": len(self.positions)
        }
    
    def _sync_existing_positions(self):
        """DB에서 활성 포지션 복구 + 업비트 잔고 확인"""
        
        # 1. DB에서 활성 포지션 복구
        db_positions = db.get_active_positions()
        if db_positions:
            for pos in db_positions:
                ticker = pos.get("ticker")
                # 업비트 잔고 확인
                currency = ticker.replace("KRW-", "") if ticker else ""
                upbit_balance = self.client.get_balance(currency)
                
                if upbit_balance and upbit_balance > 0:
                    self.positions[ticker] = {
                        'ticker': ticker,
                        'coin_name': pos.get("coin_name", currency),
                        'entry_price': float(pos.get("entry_price", 0)),
                        'amount': upbit_balance,
                        'target_price': float(pos.get("target_price", 0)) if pos.get("target_price") else None,
                        'stop_loss': float(pos.get("stop_loss", 0)) if pos.get("stop_loss") else None,
                        'strategy': pos.get("strategy", ""),
                        'entry_time': pos.get("created_at", datetime.now().isoformat()),
                        'ai_reason': pos.get("ai_reason", ""),
                        'max_profit': float(pos.get("max_profit", 0)) if pos.get("max_profit") else None,
                        'trailing_stop': float(pos.get("trailing_stop", 0)) if pos.get("trailing_stop") else None
                    }
                    print(f"[{datetime.now()}] 🔄 포지션 복구: {currency} @ ₩{pos.get('entry_price'):,.0f}")
                else:
                    # 잔고 없으면 DB에서도 청산 처리
                    db.close_position(ticker)
            
            print(f"[{datetime.now()}] ✅ DB에서 {len(self.positions)}개 포지션 복구 완료")
        else:
            print(f"[{datetime.now()}] ℹ️ 복구할 포지션 없음 (새 매수만 관리)")
    
    def stop(self) -> Dict[str, Any]:
        """자동매매 중지"""
        if not self.is_running:
            return {"status": "not_running"}
        
        self.is_running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=5)
        
        return {"status": "stopped", "message": "AI 자동매매 중지됨"}
    
    def _run_loop(self):
        """메인 루프 - 적극적 포지션 모니터링 + 주기적 스캔"""
        strategy_names = [STRATEGIES[StrategyType(s)].name_kr for s in self.selected_strategies]
        print(f"[{datetime.now()}] 🤖 AI 복합 전략 시작 - {', '.join(strategy_names)}")
        
        last_scan_time = 0
        last_ai_check_time = 0
        
        while not self._stop_event.is_set():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    current_time = time.time()
                    
                    # 포지션이 있으면 매우 적극적으로 모니터링
                    if self.positions:
                        # 10초마다 가격 체크 및 기본 청산 조건 확인
                        loop.run_until_complete(self._check_exit_positions())
                        
                        # 30초마다 AI에게 매도 타이밍 판단 요청
                        if current_time - last_ai_check_time >= 30:
                            loop.run_until_complete(self._ai_monitor_positions())
                            last_ai_check_time = current_time
                    
                    # 전체 스캔은 check_interval 마다 (새 매수 기회 탐색)
                    if current_time - last_scan_time >= self.check_interval:
                        loop.run_until_complete(self._analyze_and_trade())
                        last_scan_time = current_time
                        
                finally:
                    loop.close()
                    
            except Exception as e:
                print(f"[{datetime.now()}] ❌ AI 분석 오류: {e}")
            
            # 포지션 있으면 10초, 없으면 30초 대기 (더 빠른 모니터링)
            wait_time = 10 if self.positions else 30
            self._stop_event.wait(wait_time)
        
        print(f"[{datetime.now()}] 🛑 AI 단타 종료")
    
    async def _analyze_and_trade(self):
        """AI 분석 및 거래"""
        # 1. 전체 코인 스캔하여 후보 선정
        candidates = await self._scan_candidates()
        
        if not candidates:
            print(f"[{datetime.now()}] 📊 스캔 완료: 후보 코인 없음")
            return
        
        print(f"[{datetime.now()}] 📊 스캔 완료: {len(candidates)}개 후보")
        
        # 2. 기존 포지션 청산 체크
        await self._check_exit_positions()
        
        # 3. 새 진입 (최대 포지션 미만일 때)
        if len(self.positions) < self.max_positions:
            for ticker, data in candidates[:3]:  # 상위 3개만 AI 분석
                if ticker in self.positions:
                    continue
                
                # AI 분석 (신뢰도 80% 이상에서만 매수)
                decision = await self._ai_analyze(ticker, data, "entry")
                
                if decision and decision.action == "buy" and decision.confidence >= 80:
                    await self._execute_buy(ticker, decision)
                    print(f"[{datetime.now()}] 🎯 매수 결정: {ticker} (신뢰도 {decision.confidence}%)")
                    
                    if len(self.positions) >= self.max_positions:
                        break
    
    async def _scan_candidates(self) -> List[tuple]:
        """전체 KRW 마켓 코인 스캔 - 선택한 전략에 맞는 코인 탐색"""
        candidates = []
        scanned_count = 0
        
        # 전체 KRW 마켓 코인 가져오기
        try:
            all_tickers = pyupbit.get_tickers(fiat="KRW")
            strategy_names = [STRATEGIES[StrategyType(s)].name_kr for s in self.selected_strategies]
            print(f"[{datetime.now()}] 🔍 전체 {len(all_tickers)}개 코인 스캔 시작 (복합 전략: {', '.join(strategy_names)})")
        except Exception as e:
            print(f"[{datetime.now()}] ❌ 마켓 목록 조회 실패: {e}")
            return []
        
        # 거래대금 기준 필터링 (최소 1억원 이상)
        MIN_TRADE_VALUE = 100_000_000  # 1억원
        
        for ticker in all_tickers:
            try:
                # OHLCV 데이터 조회
                df = self.client.get_ohlcv(ticker, interval="day", count=25)
                if df is None or len(df) < 21:
                    continue
                
                scanned_count += 1
                
                # 기본 데이터 수집
                current_price = float(df['close'].iloc[-1])
                prev_close = float(df['close'].iloc[-2])
                volume = float(df['volume'].iloc[-1])
                avg_volume = float(df['volume'].iloc[:-1].mean())
                trade_value = current_price * volume  # 당일 거래대금
                
                # 거래대금 필터링
                if trade_value < MIN_TRADE_VALUE:
                    continue
                
                # RSI 계산
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = float((100 - (100 / (1 + rs))).iloc[-1])
                prev_rsi = float((100 - (100 / (1 + rs))).iloc[-2]) if len(rs) > 1 else rsi
                
                # 볼린저 밴드
                ma20 = float(df['close'].rolling(20).mean().iloc[-1])
                std20 = float(df['close'].rolling(20).std().iloc[-1])
                bb_lower = ma20 - 2 * std20
                bb_upper = ma20 + 2 * std20
                bb_percent = (current_price - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper != bb_lower else 50
                
                # 변동성 돌파 목표가
                yesterday = df.iloc[-2]
                today_open = float(df['open'].iloc[-1])
                volatility_range = float(yesterday['high']) - float(yesterday['low'])
                volatility_target = today_open + volatility_range * 0.5
                
                # 20일 고가
                high_20d = float(df['high'].iloc[:-1].tail(20).max())
                
                # 변화율
                price_change = (current_price - prev_close) / prev_close * 100
                volume_ratio = volume / avg_volume if avg_volume > 0 else 1
                
                # 복수 전략 점수 계산 (모든 선택된 전략 평가)
                scores = []
                reasons = []
                
                # Williams %R 미리 계산 (여러 전략에서 사용)
                period = 14
                highest_high = float(df['high'].rolling(window=period).max().iloc[-1])
                lowest_low = float(df['low'].rolling(window=period).min().iloc[-1])
                williams_r = ((highest_high - current_price) / (highest_high - lowest_low)) * -100 if highest_high != lowest_low else -50
                prev_highest = float(df['high'].rolling(window=period).max().iloc[-2])
                prev_lowest = float(df['low'].rolling(window=period).min().iloc[-2])
                prev_wr = ((prev_highest - prev_close) / (prev_highest - prev_lowest)) * -100 if prev_highest != prev_lowest else -50
                
                for strategy in self.selected_strategies:
                    strategy_score = 0
                    strategy_reason = ""
                    
                    if strategy == "volatility_breakout":
                        # 변동성 돌파: 목표가 돌파 + 거래량 증가
                        if current_price > volatility_target and volume_ratio > 1.2:
                            breakout_percent = (current_price - volatility_target) / volatility_target * 100
                            strategy_score = 65 + min(35, breakout_percent * 10 + volume_ratio * 5)
                            strategy_reason = f"⚡변동성돌파 {breakout_percent:.1f}%"
                            
                    elif strategy == "rsi_reversal":
                        # RSI 반등: RSI 35 이하에서 상승 전환
                        if rsi < 38 and rsi > prev_rsi and price_change > 0:
                            strategy_score = 85 - rsi + (prev_rsi - rsi) * 2
                            strategy_reason = f"📊RSI {rsi:.1f} 반등"
                            
                    elif strategy == "bollinger_bounce":
                        # 볼린저 반등: 하단 터치 후 반등
                        if bb_percent < 15 and price_change > 0:
                            strategy_score = 75 + (15 - bb_percent) * 2
                            strategy_reason = f"📈BB하단 {bb_percent:.0f}%"
                        elif bb_percent < 5:
                            strategy_score = 80 + (5 - bb_percent) * 3
                            strategy_reason = f"📈BB이탈 {bb_percent:.0f}%"
                            
                    elif strategy == "volume_surge":
                        # 거래량 급증: 평균 대비 2배 이상 + 양봉
                        if volume_ratio > 2.0 and price_change > 1:
                            strategy_score = 60 + min(40, (volume_ratio - 2) * 15 + price_change * 3)
                            strategy_reason = f"🔥거래량 {volume_ratio:.1f}배"
                            
                    elif strategy == "momentum_breakout":
                        # 모멘텀 돌파: 20일 신고가 + 거래량 증가
                        if current_price > high_20d and volume_ratio > 1.3:
                            breakout_percent = (current_price - high_20d) / high_20d * 100
                            strategy_score = 68 + min(32, breakout_percent * 8 + volume_ratio * 4)
                            strategy_reason = f"🚀신고가 +{breakout_percent:.1f}%"
                            
                    elif strategy == "scalping_5min":
                        # 5분봉 스캘핑
                        if rsi < 40 and volume_ratio > 1.5 and price_change > 0:
                            strategy_score = 60 + (40 - rsi) + volume_ratio * 5
                            strategy_reason = f"⏱️RSI {rsi:.1f}"
                    
                    # ========== 래리 윌리엄스 전략들 ==========
                    elif strategy == "larry_williams_r":
                        if williams_r <= -80 and williams_r > prev_wr:
                            strategy_score = 70 + abs(williams_r + 80) + (williams_r - prev_wr) * 2
                            strategy_reason = f"📉%R {williams_r:.1f}"
                            
                    elif strategy == "larry_oops":
                        yesterday_data = df.iloc[-2]
                        today_open_val = float(df['open'].iloc[-1])
                        yesterday_low = float(yesterday_data['low'])
                        
                        gap_down = today_open_val < yesterday_low
                        breakout_oops = current_price > yesterday_low
                        is_bullish_oops = current_price > today_open_val
                        
                        if gap_down and breakout_oops and is_bullish_oops:
                            gap_size = (yesterday_low - today_open_val) / yesterday_low * 100
                            recovery = (current_price - today_open_val) / today_open_val * 100
                            strategy_score = 65 + gap_size * 5 + recovery * 3
                            strategy_reason = f"😱OOPS! +{recovery:.1f}%"
                            
                    elif strategy == "larry_smash_day":
                        yesterday_data = df.iloc[-2]
                        day_before = df.iloc[-3]
                        
                        yesterday_open_val = float(yesterday_data['open'])
                        yesterday_close_val = float(yesterday_data['close'])
                        day_before_close = float(day_before['close'])
                        today_open_val = float(df['open'].iloc[-1])
                        
                        daily_drop = (yesterday_close_val - yesterday_open_val) / yesterday_open_val * 100
                        vs_prev_drop = (yesterday_close_val - day_before_close) / day_before_close * 100
                        
                        is_smash_day = daily_drop < -3 or vs_prev_drop < -5
                        is_recovering = current_price > today_open_val
                        above_smash = current_price > yesterday_close_val
                        
                        if is_smash_day and is_recovering and above_smash:
                            recovery_pct = (current_price - yesterday_close_val) / yesterday_close_val * 100
                            strategy_score = 60 + abs(daily_drop) * 3 + recovery_pct * 5
                            strategy_reason = f"💥Smash +{recovery_pct:.1f}%"
                            
                    elif strategy == "larry_combo":
                        volatility_check = current_price > volatility_target
                        wr_signal = -80 <= williams_r <= -50 and williams_r > prev_wr
                        volume_check = volume_ratio > 1.5
                        is_bullish_lc = current_price > float(df['open'].iloc[-1])
                        
                        conditions_met = sum([volatility_check, wr_signal, volume_check, is_bullish_lc])
                        
                        if conditions_met >= 3:
                            strategy_score = 50 + conditions_met * 12
                            if volatility_check:
                                strategy_score += 5
                            if wr_signal:
                                strategy_score += abs(williams_r + 65)
                            if volume_check:
                                strategy_score += min(20, (volume_ratio - 1) * 10)
                            
                            strategy_reason = f"🏆래리종합 {conditions_met}조건"
                    
                    # 점수가 있으면 추가
                    if strategy_score > 0:
                        scores.append(strategy_score)
                        reasons.append(strategy_reason)
                
                # 복수 전략 점수 합산 (가장 높은 점수 + 중복 가산점)
                if scores:
                    score = max(scores) + len(scores) * 5  # 여러 전략 일치 시 가산점
                    reason = " | ".join(reasons)
                else:
                    score = 0
                    reason = ""
                
                # 점수 70 이상인 코인만 후보로 (더 엄격한 기준)
                if score >= 70:
                    coin_name = ticker.replace("KRW-", "")
                    candidates.append((ticker, {
                        'coin_name': coin_name,
                        'score': round(score, 1),
                        'reason': reason,
                        'price': current_price,
                        'price_change': round(price_change, 2),
                        'rsi': round(rsi, 1),
                        'volume_ratio': round(volume_ratio, 2),
                        'trade_value': trade_value,
                        'bb_lower': bb_lower,
                        'bb_upper': bb_upper,
                        'bb_percent': round(bb_percent, 1),
                        'ma20': ma20,
                        'volatility_target': volatility_target,
                        'high_20d': high_20d
                    }))
                    print(f"  ✅ {coin_name}: {score:.0f}점 - {reason}")
                    
            except Exception as e:
                continue
        
        # 점수 기준 정렬
        candidates.sort(key=lambda x: x[1]['score'], reverse=True)
        
        print(f"[{datetime.now()}] 📊 스캔 완료: {scanned_count}개 분석, {len(candidates)}개 후보 발견")
        
        return candidates
    
    async def _ai_analyze(self, ticker: str, data: Dict, context: str) -> Optional[AITradeDecision]:
        """AI 분석"""
        if not OPENROUTER_API_KEY:
            print(f"[{datetime.now()}] ⚠️ OpenRouter API 키 없음")
            return None
        
        coin_name = ticker.replace("KRW-", "")
        # 복수 전략 프롬프트 생성
        strategy_prompts = []
        for s in self.selected_strategies:
            prompt = self.STRATEGY_PROMPTS.get(s, "")
            if prompt:
                strategy_name = STRATEGIES.get(StrategyType(s), {})
                if hasattr(strategy_name, 'name_kr'):
                    strategy_prompts.append(f"=== {strategy_name.name_kr} ===\n{prompt}")
                else:
                    strategy_prompts.append(prompt)
        
        strategy_prompt = "\n\n".join(strategy_prompts) if strategy_prompts else self.STRATEGY_PROMPTS.get(self.selected_strategy, "")
        
        # 시장 데이터 준비
        market_data = f"""
현재 분석 대상: {coin_name} ({ticker})
현재가: ₩{data['price']:,.0f}
RSI(14): {data['rsi']:.1f}
거래량 비율: {data['volume_ratio']:.2f}x (평균 대비)
볼린저 밴드:
  - 하단: ₩{data['bb_lower']:,.0f}
  - 중간(MA20): ₩{data['ma20']:,.0f}
  - 상단: ₩{data['bb_upper']:,.0f}
변동성 돌파 목표가: ₩{data['volatility_target']:,.0f}
전략 점수: {data['score']:.1f}점
"""
        
        prompt = f"""
{strategy_prompt}

===== 현재 시장 데이터 =====
{market_data}

===== 분석 요청 =====
위 전략과 데이터를 바탕으로 {context} 결정을 내려주세요.

응답 형식 (JSON):
{{
    "action": "buy" | "sell" | "hold",
    "confidence": 0-100,
    "amount_percent": 10-100,
    "reason": "판단 근거 (한국어, 2-3문장)",
    "target_price": 목표가 (숫자),
    "stop_loss": 손절가 (숫자)
}}

주의: 반드시 위 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요.
"""
        
        try:
            # SSL 컨텍스트 설정 (인증서 검증 비활성화 - 개발환경)
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": AI_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 500
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        print(f"[{datetime.now()}] ❌ AI API 오류: {response.status}")
                        return None
                    
                    result = await response.json()
                    content = result['choices'][0]['message']['content'].strip()
                    
                    # JSON 파싱
                    if content.startswith("```"):
                        content = content.split("```")[1]
                        if content.startswith("json"):
                            content = content[4:]
                    
                    ai_response = json.loads(content)
                    
                    decision = AITradeDecision(
                        ticker=ticker,
                        action=ai_response.get('action', 'hold'),
                        confidence=ai_response.get('confidence', 50),
                        amount_percent=ai_response.get('amount_percent', 50),
                        reason=ai_response.get('reason', ''),
                        target_price=ai_response.get('target_price'),
                        stop_loss=ai_response.get('stop_loss'),
                        timestamp=datetime.now().isoformat()
                    )
                    
                    self.ai_decisions.append(decision)
                    
                    emoji = "🟢" if decision.action == "buy" else "🔴" if decision.action == "sell" else "⚪"
                    print(f"[{datetime.now()}] {emoji} AI 결정 ({coin_name}): {decision.action.upper()} "
                          f"(신뢰도: {decision.confidence}%) - {decision.reason[:50]}...")
                    
                    return decision
                    
        except json.JSONDecodeError as e:
            print(f"[{datetime.now()}] ❌ AI 응답 파싱 오류: {e}")
            return None
        except Exception as e:
            print(f"[{datetime.now()}] ❌ AI 분석 오류: {e}")
            return None
    
    async def _ai_monitor_positions(self):
        """AI가 적극적으로 포지션을 모니터링하고 최적의 매도 타이밍 판단"""
        if not self.positions:
            return
        
        print(f"[{datetime.now()}] 🔍 AI 포지션 모니터링 중... ({len(self.positions)}개)")
        
        for ticker, pos in list(self.positions.items()):
            try:
                # 현재가 조회
                current_price = self.client.get_current_price(ticker)
                if not current_price:
                    continue
                
                entry_price = pos['entry_price']
                profit_rate = (current_price - entry_price) / entry_price * 100
                holding_minutes = (datetime.now() - datetime.fromisoformat(pos.get('entry_time', datetime.now().isoformat()))).total_seconds() / 60
                
                # 최근 1분봉 데이터로 시장 상황 분석
                df = self.client.get_ohlcv(ticker, interval="minute1", count=30)
                if df is None or len(df) < 20:
                    continue
                
                # RSI 계산
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = float((100 - (100 / (1 + rs))).iloc[-1])
                
                # 최근 가격 추세 (5분간)
                price_5min_ago = float(df['close'].iloc[-6]) if len(df) >= 6 else current_price
                recent_trend = (current_price - price_5min_ago) / price_5min_ago * 100
                
                # 거래량 추세
                recent_volume = float(df['volume'].iloc[-5:].mean())
                prev_volume = float(df['volume'].iloc[-10:-5].mean())
                volume_trend = recent_volume / prev_volume if prev_volume > 0 else 1
                
                # AI 분석 프롬프트 생성
                analysis_data = {
                    'ticker': ticker,
                    'coin_name': pos['coin_name'],
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'profit_rate': profit_rate,
                    'holding_minutes': holding_minutes,
                    'rsi': rsi,
                    'recent_trend': recent_trend,
                    'volume_trend': volume_trend,
                    'max_profit': pos.get('max_profit', profit_rate),
                    'entry_reason': pos.get('ai_reason', ''),
                }
                
                # AI에게 매도 타이밍 판단 요청
                decision = await self._ai_analyze_sell_timing(analysis_data)
                
                if decision and decision.action == "sell" and decision.confidence >= 75:
                    print(f"[{datetime.now()}] 🤖 AI 매도 결정: {pos['coin_name']} (신뢰도 {decision.confidence}%)")
                    await self._execute_sell(ticker, f"🤖 AI 최적 타이밍: {decision.reason}", profit_rate, current_price)
                elif decision and decision.action == "hold":
                    # 최고 수익 갱신
                    if profit_rate > pos.get('max_profit', 0):
                        pos['max_profit'] = profit_rate
                        print(f"[{datetime.now()}] 📈 {pos['coin_name']}: 최고 수익 갱신 {profit_rate:.2f}%")
                        
            except Exception as e:
                print(f"[{datetime.now()}] ⚠️ AI 모니터링 오류 ({ticker}): {e}")
    
    async def _ai_analyze_sell_timing(self, data: Dict) -> Optional[AITradeDecision]:
        """AI가 최적의 매도 타이밍 분석"""
        if not OPENROUTER_API_KEY:
            return None
        
        prompt = f"""당신은 암호화폐 단기 트레이딩 전문가입니다. 
현재 보유 중인 포지션의 매도 타이밍을 판단해주세요.

=== 포지션 정보 ===
코인: {data['coin_name']}
매수가: ₩{data['entry_price']:,.0f}
현재가: ₩{data['current_price']:,.0f}
수익률: {data['profit_rate']:+.2f}%
보유 시간: {data['holding_minutes']:.0f}분
최고 수익률: {data['max_profit']:.2f}%
매수 이유: {data['entry_reason']}

=== 현재 시장 상황 ===
RSI(14): {data['rsi']:.1f}
최근 5분 추세: {data['recent_trend']:+.2f}%
거래량 추세: {data['volume_trend']:.2f}x

=== 판단 기준 ===
1. 수익 중이면: 추가 상승 가능성 vs 이익 실현 시점
2. 손실 중이면: 반등 가능성 vs 손절 필요성
3. RSI 과매수(70+)이면 매도 고려
4. 거래량 감소 + 수익 중이면 익절 고려
5. 최고 수익 대비 크게 하락하면 익절 고려

=== 응답 형식 (JSON) ===
{{
    "action": "sell" 또는 "hold",
    "confidence": 0-100 (확신도),
    "reason": "판단 근거 (한국어, 1-2문장)",
    "target_price": 목표가 (hold인 경우),
    "stop_loss": 손절가 (hold인 경우)
}}

지금이 최적의 매도 타이밍인지 판단해주세요."""

        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": AI_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 300
                    },
                    ssl=ssl_context
                ) as response:
                    if response.status != 200:
                        return None
                    
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    
                    # JSON 파싱
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    
                    decision_data = json.loads(content.strip())
                    
                    return AITradeDecision(
                        ticker=data['ticker'],
                        action=decision_data.get('action', 'hold'),
                        confidence=int(decision_data.get('confidence', 50)),
                        reason=decision_data.get('reason', ''),
                        target_price=decision_data.get('target_price'),
                        stop_loss=decision_data.get('stop_loss'),
                        amount_percent=100,
                        timestamp=datetime.now().isoformat()
                    )
                    
        except Exception as e:
            print(f"[{datetime.now()}] ⚠️ AI 매도 타이밍 분석 실패: {e}")
            return None
    
    async def _check_exit_positions(self):
        """포지션 청산 체크 - 수익 중심 보수적 청산"""
        positions_to_close = []
        
        # 수수료 고려 최소 수익률 (매수 0.05% + 매도 0.05% = 0.1%)
        MIN_PROFIT_FOR_EXIT = 1.5  # 최소 1.5% 수익이어야 익절
        MIN_HOLDING_SECONDS = 300  # 최소 5분 보유
        
        for ticker, pos in list(self.positions.items()):
            try:
                current_price = self.client.get_current_price(ticker)
                if not current_price:
                    continue
                
                entry_price = pos['entry_price']
                profit_rate = (current_price - entry_price) / entry_price * 100
                
                # 보유 시간 계산
                entry_time = datetime.fromisoformat(pos.get('entry_time', datetime.now().isoformat()))
                holding_seconds = (datetime.now() - entry_time).total_seconds()
                
                # 최소 보유 시간 체크 (손절 제외)
                is_min_holding_passed = holding_seconds >= MIN_HOLDING_SECONDS
                
                # ===== 동적 트레일링 스탑 시스템 =====
                max_profit = pos.get('max_profit', profit_rate)
                
                # 1. 수익 기록 갱신
                if profit_rate > max_profit:
                    pos['max_profit'] = profit_rate
                    max_profit = profit_rate
                
                # 2. 트레일링 스탑 - 3% 이상 수익 시 활성화 (목표 3~10%)
                if profit_rate >= 3 and 'trailing_stop' not in pos:
                    pos['trailing_stop'] = entry_price * 1.02  # 2% 수익 보장 시작
                    print(f"[{datetime.now()}] 📊 {pos['coin_name']}: 트레일링 스탑 활성화 (수익 {profit_rate:.1f}%)")
                
                # 3. 수익 구간별 동적 트레일링 스탑 조정 (목표 3~10% 기준)
                if max_profit >= 3:
                    # 수익률에 따라 보장 비율 증가
                    if max_profit >= 10:
                        protect_ratio = 0.80  # 10% 이상: 80% 보존 (8% 확보)
                    elif max_profit >= 7:
                        protect_ratio = 0.75  # 7% 이상: 75% 보존 (5.25% 확보)
                    elif max_profit >= 5:
                        protect_ratio = 0.70  # 5% 이상: 70% 보존 (3.5% 확보)
                    else:
                        protect_ratio = 0.60  # 3% 이상: 60% 보존 (1.8% 확보)
                    
                    new_stop = entry_price * (1 + (max_profit * protect_ratio) / 100)
                    if new_stop > pos.get('trailing_stop', 0):
                        pos['trailing_stop'] = new_stop
                        # DB 업데이트
                        db.update_position(ticker, {
                            "max_profit": max_profit,
                            "trailing_stop": new_stop
                        })
                        if profit_rate < max_profit - 0.5:  # 최고점 대비 0.5% 이상 하락 시에만 로그
                            print(f"[{datetime.now()}] 📈 {pos['coin_name']}: 트레일링 스탑 @ ₩{new_stop:,.0f} (최고 {max_profit:.1f}% → 현재 {profit_rate:.1f}%)")
                
                # 4. 급격한 수익 감소 감지 (최고점 대비 40% 이상 하락)
                profit_drawdown = max_profit - profit_rate
                if max_profit >= 3 and profit_drawdown >= max_profit * 0.4 and profit_rate >= MIN_PROFIT_FOR_EXIT:
                    positions_to_close.append((ticker, f"📉 수익 급감 익절 ({profit_rate:+.2f}%, 최고 {max_profit:.1f}%에서 하락)", profit_rate, current_price))
                    continue
                
                # 청산 조건 체크
                should_exit = False
                exit_reason = ""
                
                # 1. 목표 수익률 도달 (최소 보유 시간 후)
                target_profit = self._get_take_profit_target()
                if profit_rate >= target_profit and is_min_holding_passed:
                    should_exit = True
                    exit_reason = f"🎯 목표 수익 도달 ({profit_rate:+.2f}%)"
                
                # 2. 트레일링 스탑 (수익 보존)
                elif pos.get('trailing_stop') and current_price <= pos['trailing_stop'] and profit_rate >= MIN_PROFIT_FOR_EXIT:
                    should_exit = True
                    exit_reason = f"📉 트레일링 스탑 ({profit_rate:+.2f}%, 최고 {pos.get('max_profit', 0):.1f}%)"
                
                # 3. 큰 손실 손절 (-5% 이상, 즉시)
                elif profit_rate <= -5:
                    should_exit = True
                    exit_reason = f"⛔ 손절 ({profit_rate:+.2f}%)"
                
                # 4. 장시간 보유 후 소폭 수익이면 청산 (30분 이상, 1.5% 이상)
                elif holding_seconds >= 1800 and profit_rate >= MIN_PROFIT_FOR_EXIT:
                    should_exit = True
                    exit_reason = f"⏰ 시간 기반 익절 ({profit_rate:+.2f}%, {holding_seconds/60:.0f}분 보유)"
                
                # 5. AI 분석 (10분 이상 보유 & 3% 이상 수익/손실)
                if not should_exit and holding_seconds >= 600 and abs(profit_rate) >= 3:
                    df = self.client.get_ohlcv(ticker, interval="day", count=25)
                    if df is not None and len(df) >= 21:
                        # RSI 계산
                        delta = df['close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        rsi = float((100 - (100 / (1 + rs))).iloc[-1])
                        
                        # 수익 중이고 RSI 과매수면 익절
                        if profit_rate >= MIN_PROFIT_FOR_EXIT and rsi >= 75:
                            should_exit = True
                            exit_reason = f"📊 RSI 과매수 익절 (RSI {rsi:.0f}, {profit_rate:+.2f}%)"
                        # 손실 중이고 RSI 과매도면 더 기다림 (반등 기대)
                        elif profit_rate < 0 and rsi <= 25:
                            print(f"[{datetime.now()}] ⏳ {pos['coin_name']}: RSI 과매도 - 반등 대기 (RSI {rsi:.0f})")
                
                if should_exit:
                    positions_to_close.append((ticker, exit_reason, profit_rate, current_price))
                else:
                    # 현재 상태 로그 (5분마다)
                    if int(holding_seconds) % 300 == 0 and holding_seconds > 0:
                        print(f"[{datetime.now()}] 📍 {pos['coin_name']}: {profit_rate:+.2f}% ({holding_seconds/60:.0f}분 보유)")
                    
            except Exception as e:
                print(f"[{datetime.now()}] ⚠️ 포지션 체크 오류 ({ticker}): {e}")
        
        # 청산 실행
        for ticker, reason, profit_rate, price in positions_to_close:
            await self._execute_sell(ticker, reason, profit_rate, price)
    
    def _get_take_profit_target(self) -> float:
        """전략별 익절 목표 (3~10% 범위로 상향)"""
        targets = {
            "volatility_breakout": 6.0,   # 변동성 돌파 6%
            "rsi_reversal": 8.0,          # RSI 반등 8%
            "bollinger_bounce": 7.0,      # 볼린저 반등 7%
            "volume_surge": 8.0,          # 거래량 급증 8%
            "momentum_breakout": 10.0,    # 모멘텀 돌파 10%
            "scalping_5min": 3.0,         # 5분 스캘핑 3% (단기)
            # 래리 윌리엄스 전략들 (상향)
            "larry_williams_r": 7.0,      # %R 반등 7%
            "larry_oops": 8.0,            # OOPS! 패턴 8%
            "larry_smash_day": 8.0,       # Smash Day 8%
            "larry_combo": 10.0           # 래리 종합 10% (복합 전략)
        }
        return targets.get(self.selected_strategy, 7.0)
    
    def _should_auto_exit(self, rsi: float, prev_rsi: float, bb_percent: float, 
                          volume_ratio: float, profit_rate: float, pos: Dict) -> bool:
        """전략별 자동 청산 조건 (목표 3~10% 기준)"""
        strategy = self.selected_strategy
        
        # 최소 수익률 (수수료 고려, 상향)
        MIN_PROFIT = 3.0
        
        if strategy == "rsi_reversal":
            # RSI 과매수 + 충분한 수익 (8% 목표)
            return rsi > 75 and profit_rate >= 5
        
        elif strategy == "bollinger_bounce":
            # 볼린저 상단 도달 + 충분한 수익 (7% 목표)
            return bb_percent > 95 and profit_rate >= 4
        
        elif strategy == "volume_surge":
            # 거래량 급감 + 충분한 수익 (8% 목표)
            return volume_ratio < 0.5 and profit_rate >= 5
        
        elif strategy == "momentum_breakout":
            # 모멘텀 약화 + 충분한 수익 (10% 목표)
            return (rsi < prev_rsi - 10 and bb_percent < 50) and profit_rate >= 6
        
        elif strategy == "scalping_5min":
            # 스캘핑은 빠른 청산 유지 (3% 목표)
            return profit_rate >= 3 or profit_rate <= -3 or (rsi > 70 and profit_rate >= 2)
        
        elif strategy == "volatility_breakout":
            # 상승 모멘텀 약화 + 충분한 수익 (6% 목표)
            return rsi > 75 and profit_rate >= 5
        
        # 래리 윌리엄스 전략들 (목표 7~10%)
        elif strategy == "larry_williams_r":
            # %R이 과매수(-20 이상)로 전환 + 충분한 수익 (7% 목표)
            return profit_rate >= 6 or (rsi > 75 and profit_rate >= 4)
        
        elif strategy == "larry_oops":
            # OOPS 패턴 - 갭 메우기 완료 또는 충분한 수익 (8% 목표)
            return profit_rate >= 7 or (rsi > 75 and profit_rate >= 5)
        
        elif strategy == "larry_smash_day":
            # Smash Day 반등 - RSI 회복 + 수익 (8% 목표)
            return (rsi > 65 and profit_rate >= 6) or profit_rate >= 8
        
        elif strategy == "larry_combo":
            # 종합 전략 - 10% 목표
            return profit_rate >= 8 or (rsi > 75 and profit_rate >= 5)
        
        return False
    
    def _get_auto_exit_reason(self, rsi: float, bb_percent: float, 
                               volume_ratio: float, profit_rate: float) -> str:
        """자동 청산 이유"""
        strategy = self.selected_strategy
        
        if strategy == "rsi_reversal" and rsi > 65:
            return f"📊 RSI 과매수 도달 ({rsi:.0f}, {profit_rate:+.1f}%)"
        elif strategy == "bollinger_bounce" and bb_percent > 90:
            return f"📊 볼린저 상단 도달 ({bb_percent:.0f}%, {profit_rate:+.1f}%)"
        elif strategy == "volume_surge" and volume_ratio < 1.0:
            return f"📉 거래량 감소 ({volume_ratio:.1f}x, {profit_rate:+.1f}%)"
        elif strategy == "momentum_breakout":
            return f"📉 모멘텀 약화 (RSI {rsi:.0f}, {profit_rate:+.1f}%)"
        elif strategy == "scalping_5min":
            return f"⚡ 스캘핑 청산 ({profit_rate:+.1f}%)"
        # 래리 윌리엄스 전략들
        elif strategy == "larry_williams_r":
            return f"📉 Williams %R 과매수 전환 (RSI {rsi:.0f}, {profit_rate:+.1f}%)"
        elif strategy == "larry_oops":
            return f"😱 OOPS! 갭 메우기 완료 ({profit_rate:+.1f}%)"
        elif strategy == "larry_smash_day":
            return f"💥 Smash Day 반등 완료 (RSI {rsi:.0f}, {profit_rate:+.1f}%)"
        elif strategy == "larry_combo":
            return f"🏆 래리 종합 목표 달성 ({profit_rate:+.1f}%)"
        else:
            return f"📊 전략 청산 조건 충족 ({profit_rate:+.1f}%)"
    
    async def _ai_analyze_exit(self, ticker: str, data: Dict, pos: Dict) -> Optional[AITradeDecision]:
        """AI 청산 분석 - 수익 극대화 판단"""
        if not OPENROUTER_API_KEY:
            return None
        
        coin_name = ticker.replace("KRW-", "")
        # 복수 전략 프롬프트 생성
        strategy_prompts = []
        for s in self.selected_strategies:
            prompt = self.STRATEGY_PROMPTS.get(s, "")
            if prompt:
                strategy_name = STRATEGIES.get(StrategyType(s), {})
                if hasattr(strategy_name, 'name_kr'):
                    strategy_prompts.append(f"=== {strategy_name.name_kr} ===\n{prompt}")
                else:
                    strategy_prompts.append(prompt)
        
        strategy_prompt = "\n\n".join(strategy_prompts) if strategy_prompts else self.STRATEGY_PROMPTS.get(self.selected_strategy, "")
        
        prompt = f"""
{strategy_prompt}

===== 현재 포지션 =====
코인: {coin_name}
진입가: ₩{pos['entry_price']:,.0f}
현재가: ₩{data['price']:,.0f}
수익률: {data['profit_rate']:+.2f}%
보유 시간: {pos.get('entry_time', 'N/A')}
진입 이유: {pos.get('ai_reason', 'N/A')}

===== 현재 시장 상황 =====
RSI(14): {data['rsi']:.1f}
거래량 비율: {data['volume_ratio']:.2f}x
볼린저 밴드 위치: {data['bb_percent']:.1f}% (0=하단, 100=상단)
가격 변화율: {data['price_change']:.2f}%

===== 분석 요청 =====
수익을 극대화하기 위해 지금 청산해야 할까요?
- 추가 상승 가능성 vs 하락 리스크를 분석
- 전략의 청산 조건과 비교
- 명확한 매도/보유 결정 제시

응답 형식 (JSON):
{{
    "action": "sell" | "hold",
    "confidence": 0-100,
    "amount_percent": 100,
    "reason": "판단 근거 (한국어, 2-3문장)",
    "target_price": 새목표가 (보유시),
    "stop_loss": 새손절가 (보유시)
}}

주의: 반드시 위 JSON 형식으로만 응답하세요.
"""
        
        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": AI_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "max_tokens": 400
                    },
                    timeout=aiohttp.ClientTimeout(total=25)
                ) as response:
                    if response.status != 200:
                        return None
                    
                    result = await response.json()
                    content = result['choices'][0]['message']['content'].strip()
                    
                    if content.startswith("```"):
                        content = content.split("```")[1]
                        if content.startswith("json"):
                            content = content[4:]
                    
                    ai_response = json.loads(content)
                    
                    decision = AITradeDecision(
                        ticker=ticker,
                        action=ai_response.get('action', 'hold'),
                        confidence=ai_response.get('confidence', 50),
                        amount_percent=100,
                        reason=ai_response.get('reason', ''),
                        target_price=ai_response.get('target_price'),
                        stop_loss=ai_response.get('stop_loss'),
                        timestamp=datetime.now().isoformat()
                    )
                    
                    self.ai_decisions.append(decision)
                    
                    emoji = "🔴" if decision.action == "sell" else "🟡"
                    print(f"[{datetime.now()}] {emoji} AI 청산 분석 ({coin_name}): {decision.action.upper()} "
                          f"(신뢰도: {decision.confidence}%) - {decision.reason[:50]}...")
                    
                    return decision
                    
        except Exception as e:
            print(f"[{datetime.now()}] ⚠️ AI 청산 분석 오류: {e}")
            return None
    
    async def _execute_buy(self, ticker: str, decision: AITradeDecision):
        """매수 실행"""
        try:
            coin_name = ticker.replace("KRW-", "")
            
            # 투자금 계산
            krw_balance = self.client.get_balance("KRW") or 0
            invest_amount = min(
                self.trade_amount * (decision.amount_percent / 100),
                krw_balance * 0.95
            )
            
            if invest_amount < 5000:
                print(f"[{datetime.now()}] ⚠️ 투자금 부족: ₩{invest_amount:,.0f}")
                return
            
            # 시장가 매수
            current_price = self.client.get_current_price(ticker) or decision.target_price or 0
            result = self.client.buy_market_order(ticker, invest_amount)
            
            if result:
                self.positions[ticker] = {
                    'ticker': ticker,
                    'coin_name': coin_name,
                    'entry_price': current_price,
                    'amount': invest_amount / current_price if current_price > 0 else 0,
                    'target_price': decision.target_price,
                    'stop_loss': decision.stop_loss,
                    'strategy': self.selected_strategy,
                    'entry_time': datetime.now().isoformat(),
                    'ai_reason': decision.reason
                }
                
                trade_log = TradeExecution(
                    id=f"buy_{ticker}_{datetime.now().strftime('%H%M%S')}",
                    ticker=ticker,
                    coin_name=coin_name,
                    action="buy",
                    strategy=self.selected_strategy,
                    price=current_price,
                    amount=invest_amount / current_price if current_price > 0 else 0,
                    total_krw=invest_amount,
                    ai_reason=decision.reason,
                    ai_confidence=decision.confidence,
                    timestamp=datetime.now().isoformat()
                )
                self.trade_logs.append(trade_log)
                
                # DB 저장
                db.save_trade(asdict(trade_log))
                db.save_position(self.positions[ticker])
                
                print(f"[{datetime.now()}] ✅ 매수 완료: {coin_name} @ ₩{current_price:,.0f} "
                      f"(₩{invest_amount:,.0f}, 신뢰도: {decision.confidence}%)")
            else:
                print(f"[{datetime.now()}] ❌ 매수 실패: {coin_name}")
                
        except Exception as e:
            print(f"[{datetime.now()}] ❌ 매수 오류: {e}")
    
    async def _execute_sell(self, ticker: str, reason: str, profit_rate: float, price: float):
        """매도 실행 - 실제 체결 금액 계산"""
        try:
            if ticker not in self.positions:
                return
            
            pos = self.positions[ticker]
            coin_name = pos['coin_name']
            entry_price = pos['entry_price']
            
            # 매도 전 보유량 확인
            balance = self.client.get_balance(coin_name) or 0
            if balance <= 0:
                del self.positions[ticker]
                return
            
            # 매도 전 KRW 잔고
            krw_before = self.client.get_balance("KRW") or 0
            
            # 시장가 매도
            result = self.client.sell_market_order(ticker, balance)
            
            if result and 'error' not in result:
                # 잠시 대기 후 실제 체결 금액 확인
                await asyncio.sleep(1)
                
                # 매도 후 KRW 잔고
                krw_after = self.client.get_balance("KRW") or 0
                
                # 실제 체결 금액 = 매도 후 KRW - 매도 전 KRW
                actual_sell_amount = krw_after - krw_before
                
                # 실제 체결 금액이 0 이하면 예상 금액 사용
                if actual_sell_amount <= 0:
                    actual_sell_amount = price * balance
                
                # 실제 체결 가격
                actual_price = actual_sell_amount / balance if balance > 0 else price
                
                # 실제 수익 계산
                # 매수 총액 = 진입가 × 수량
                buy_total = entry_price * balance
                # 실제 수익 = 매도 금액 - 매수 금액
                actual_profit = actual_sell_amount - buy_total
                # 실제 수익률
                actual_profit_rate = (actual_profit / buy_total * 100) if buy_total > 0 else 0
                
                trade_log = TradeExecution(
                    id=f"sell_{ticker}_{datetime.now().strftime('%H%M%S')}",
                    ticker=ticker,
                    coin_name=coin_name,
                    action="sell",
                    strategy=self.selected_strategy,
                    price=actual_price,
                    amount=balance,
                    total_krw=actual_sell_amount,
                    ai_reason=reason,
                    ai_confidence=0,
                    timestamp=datetime.now().isoformat(),
                    profit=actual_profit,
                    profit_rate=actual_profit_rate
                )
                self.trade_logs.append(trade_log)
                
                # DB 저장 및 포지션 청산
                db.save_trade(asdict(trade_log))
                db.close_position(ticker)
                db.update_daily_stats()
                
                emoji = "📈" if actual_profit >= 0 else "📉"
                print(f"[{datetime.now()}] {emoji} 매도 완료: {coin_name}")
                print(f"    매수: {balance:.4f}개 × ₩{entry_price:,.0f} = ₩{buy_total:,.0f}")
                print(f"    매도: {balance:.4f}개 × ₩{actual_price:,.0f} = ₩{actual_sell_amount:,.0f}")
                print(f"    손익: ₩{actual_profit:+,.0f} ({actual_profit_rate:+.2f}%)")
                print(f"    사유: {reason}")
                
                del self.positions[ticker]
            else:
                error_msg = result.get('error', '알 수 없는 오류') if result else '주문 실패'
                print(f"[{datetime.now()}] ❌ 매도 실패: {coin_name} - {error_msg}")
                
        except Exception as e:
            print(f"[{datetime.now()}] ❌ 매도 오류: {e}")
    
    def get_trade_logs(self, limit: int = 20) -> List[Dict]:
        """거래 기록"""
        return [asdict(log) for log in reversed(self.trade_logs[-limit:])]
    
    def get_ai_decisions(self, limit: int = 10) -> List[Dict]:
        """AI 결정 기록"""
        return [asdict(d) for d in reversed(self.ai_decisions[-limit:])]


# 싱글톤 인스턴스
ai_scalper = AIScalper()

