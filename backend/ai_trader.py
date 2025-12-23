"""
AI 트레이딩 모듈 - OpenRouter API를 통한 AI 기반 거래 결정
"""
import aiohttp
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import time

from upbit_client import upbit_client
from strategies import calculate_bollinger_bands, calculate_macd, calculate_stochastic
from market_analyzer import market_analyzer, MarketAnalysis, RecommendedStrategy


# OpenRouter API 설정
OPENROUTER_API_KEY = "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# AI 모델 설정 (최신 버전)
AI_MODELS = {
    "claude": "anthropic/claude-sonnet-4",      # Claude Opus 4.5
    "gpt": "openai/gpt-4.1",                    # GPT 5.2
    "gemini": "google/gemini-2.5-pro-preview", # Gemini 3
    "grok": "x-ai/grok-3-mini-beta",                    # Grok 4.1
}


class AIDecision(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class AILog:
    """AI 활동 로그"""
    id: str
    timestamp: str
    model: str
    ticker: str
    decision: str
    confidence: int  # 0-100
    reasoning: str
    market_analysis: str
    indicators: Dict[str, Any]
    executed: bool
    result: Optional[str] = None
    selected_strategy: Optional[str] = None  # AI가 선택한 최적 전략
    market_condition: Optional[str] = None   # 시장 상태


class AITrader:
    """AI 기반 자동매매 트레이더"""
    
    def __init__(self):
        self.client = upbit_client
        self.api_key = OPENROUTER_API_KEY
        self.model = AI_MODELS["claude"]  # 기본 모델: Claude
        self.is_running = False
        self.logs: List[AILog] = []
        self.target_coins = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
        self.trade_amount = 10000
        self.check_interval = 300  # 5분마다 분석
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.log_id_counter = 0
        
        # 자동 전략 선택 모드
        self.auto_strategy_mode = True  # True면 AI가 최적 전략 자동 선택
        self.current_recommended_strategy = None
        self.last_strategy_analysis = None
        
    def set_model(self, model_key: str):
        """AI 모델 변경"""
        if model_key in AI_MODELS:
            self.model = AI_MODELS[model_key]
            
    def get_model_name(self) -> str:
        """현재 모델 이름 반환"""
        for key, value in AI_MODELS.items():
            if value == self.model:
                return key
        return "unknown"
    
    async def call_ai(self, prompt: str, system_prompt: str = None) -> str:
        """OpenRouter API 호출"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8080",
            "X-Title": "CoinHero AI Trader"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2000
        }
        
        try:
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    OPENROUTER_BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        error = await response.text()
                        print(f"AI API 오류: {response.status} - {error}")
                        return None
        except Exception as e:
            print(f"AI 호출 실패: {e}")
            return None
    
    def get_market_data(self, ticker: str) -> Dict[str, Any]:
        """시장 데이터 수집"""
        # 현재가
        current_price = self.client.get_current_price(ticker)
        
        # OHLCV 데이터
        df = self.client.get_ohlcv(ticker, interval="day", count=30)
        if df is None or df.empty:
            return None
            
        # 기술적 지표 계산
        bb = calculate_bollinger_bands(df)
        macd = calculate_macd(df)
        stoch = calculate_stochastic(df)
        
        # RSI 계산
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # 이동평균
        ma5 = df['close'].rolling(5).mean().iloc[-1]
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        
        # 최근 가격 변동
        price_change_24h = ((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]) * 100
        price_change_7d = ((df['close'].iloc[-1] - df['close'].iloc[-7]) / df['close'].iloc[-7]) * 100 if len(df) >= 7 else 0
        
        return {
            "ticker": ticker,
            "current_price": current_price,
            "price_change_24h": round(price_change_24h, 2),
            "price_change_7d": round(price_change_7d, 2),
            "volume_24h": df['volume'].iloc[-1],
            "high_24h": df['high'].iloc[-1],
            "low_24h": df['low'].iloc[-1],
            "indicators": {
                "rsi": round(rsi.iloc[-1], 2) if not rsi.empty else None,
                "macd": round(macd['macd'].iloc[-1], 2),
                "macd_signal": round(macd['signal'].iloc[-1], 2),
                "macd_histogram": round(macd['histogram'].iloc[-1], 2),
                "bollinger_upper": round(bb['upper'].iloc[-1], 0),
                "bollinger_middle": round(bb['middle'].iloc[-1], 0),
                "bollinger_lower": round(bb['lower'].iloc[-1], 0),
                "stochastic_k": round(stoch['k'].iloc[-1], 2),
                "stochastic_d": round(stoch['d'].iloc[-1], 2),
                "ma5": round(ma5, 0),
                "ma20": round(ma20, 0),
            },
            "recent_prices": df['close'].tail(7).tolist()
        }
    
    async def analyze_and_decide(self, ticker: str) -> Optional[AILog]:
        """AI가 시장을 분석하고 거래 결정"""
        market_data = self.get_market_data(ticker)
        if not market_data:
            return None
            
        # 보유량 확인 (API 키 만료 시 0으로 처리)
        coin = ticker.replace("KRW-", "")
        balance = self.client.get_balance(coin) or 0
        krw_balance = self.client.get_balance("KRW") or 0
        has_position = balance > 0
        
        # 🆕 시장 상태 분석 (자동 전략 선택 모드)
        market_analysis_result = None
        strategy_recommendation = ""
        if self.auto_strategy_mode:
            market_analysis_result = market_analyzer.analyze_ticker(ticker)
            self.current_recommended_strategy = market_analysis_result.recommended_strategy.value
            self.last_strategy_analysis = datetime.now().isoformat()
            
            strategy_names = {
                'volatility': '변동성 돌파 전략',
                'moving_average': '이동평균 교차 전략',
                'rsi': 'RSI 과매수/과매도 전략',
                'combined': '복합 전략',
                'hold': '관망'
            }
            strategy_recommendation = f"""
🎯 **AI 추천 전략: {strategy_names.get(market_analysis_result.recommended_strategy.value, '알 수 없음')}** (신뢰도: {market_analysis_result.confidence:.0f}%)

📊 시장 상태 분석:
- 시장 상태: {market_analysis_result.condition.value}
- 추세 강도: {market_analysis_result.trend_strength:.1f} (-100~100)
- 변동성: {market_analysis_result.volatility:.2f}%
- 거래량 비율: {market_analysis_result.volume_ratio:.2f}x
- 지지선: ₩{market_analysis_result.support_level:,.0f}
- 저항선: ₩{market_analysis_result.resistance_level:,.0f}

🔍 분석 이유:
{chr(10).join('- ' + r for r in market_analysis_result.reasons)}

⚠️ 위 추천 전략을 참고하여 거래 결정을 내리세요. 추천 전략이 'hold'인 경우 관망을 우선 고려하세요.
"""
        
        system_prompt = """당신은 세계 최고의 암호화폐 퀀트 트레이더 AI입니다.

당신의 역할:
1. 시장 상태를 정확히 파악하고 최적의 매매 타이밍을 포착
2. 여러 전략(변동성 돌파, 이동평균 교차, RSI, 복합) 중 현재 시장에 가장 적합한 전략 적용
3. 리스크 관리를 최우선으로 하되, 확실한 기회는 놓치지 않음
4. 과매수/과매도, 추세, 변동성을 종합적으로 분석

매매 기준:
- 변동성 돌파: 고변동성 시장에서 전일 고가-저가의 K배 돌파 시 매수
- 이동평균 교차: 골든크로스 매수, 데드크로스 매도
- RSI 전략: RSI 30 이하 과매도 매수, RSI 70 이상 과매수 매도
- 복합 전략: 2개 이상 시그널 일치 시 매매

응답 형식 (JSON만, 다른 텍스트 없이):
{
    "decision": "buy" | "sell" | "hold",
    "confidence": 0-100,
    "selected_strategy": "volatility" | "moving_average" | "rsi" | "combined",
    "reasoning": "결정 이유 (한국어, 구체적으로 2-3문장)",
    "market_analysis": "시장 분석 요약 (한국어, 2-3문장)"
}"""

        prompt = f"""현재 {ticker} 시장 상황을 분석하고 최적의 전략으로 거래 결정을 내려주세요.

📊 시장 데이터:
- 현재가: ₩{market_data['current_price']:,}
- 24시간 변동: {market_data['price_change_24h']}%
- 7일 변동: {market_data['price_change_7d']}%
- 24시간 거래량: {market_data['volume_24h']:,.0f}

📈 기술적 지표:
- RSI(14): {market_data['indicators']['rsi']} (30 이하 과매도, 70 이상 과매수)
- MACD: {market_data['indicators']['macd']} / Signal: {market_data['indicators']['macd_signal']}
- MACD Histogram: {market_data['indicators']['macd_histogram']}
- 볼린저밴드: 상단 ₩{market_data['indicators']['bollinger_upper']:,} / 중간 ₩{market_data['indicators']['bollinger_middle']:,} / 하단 ₩{market_data['indicators']['bollinger_lower']:,}
- 스토캐스틱: K={market_data['indicators']['stochastic_k']}, D={market_data['indicators']['stochastic_d']}
- MA5: ₩{market_data['indicators']['ma5']:,} / MA20: ₩{market_data['indicators']['ma20']:,}

💰 포지션 상태:
- 현재 보유량: {balance} {coin}
- 보유 KRW: ₩{krw_balance:,.0f}
- 포지션: {'보유 중 (매도 검토)' if has_position else '미보유 (매수 검토)'}
{strategy_recommendation}
최근 7일 종가: {market_data['recent_prices']}

위 모든 데이터와 추천 전략을 종합 분석하여 최적의 매매 결정을 JSON 형식으로 응답해주세요.
신뢰도 70% 이상일 때만 매수/매도를 권장하고, 불확실하면 hold를 선택하세요."""

        response = await self.call_ai(prompt, system_prompt)
        if not response:
            return None
            
        try:
            # JSON 파싱
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                ai_response = json.loads(json_str)
            else:
                return None
                
            self.log_id_counter += 1
            log = AILog(
                id=f"ai-{self.log_id_counter}-{int(time.time())}",
                timestamp=datetime.now().isoformat(),
                model=self.get_model_name(),
                ticker=ticker,
                decision=ai_response.get("decision", "hold"),
                confidence=ai_response.get("confidence", 0),
                reasoning=ai_response.get("reasoning", ""),
                market_analysis=ai_response.get("market_analysis", ""),
                indicators=market_data['indicators'],
                executed=False,
                selected_strategy=ai_response.get("selected_strategy", self.current_recommended_strategy),
                market_condition=market_analysis_result.condition.value if market_analysis_result else None
            )
            
            return log
            
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 실패: {e}")
            return None
    
    async def execute_decision(self, log: AILog) -> bool:
        """AI 결정 실행"""
        if log.confidence < 60:
            log.result = f"신뢰도 부족 ({log.confidence}% < 60%)"
            return False
            
        ticker = log.ticker
        coin = ticker.replace("KRW-", "")
        
        if log.decision == AIDecision.BUY:
            krw_balance = self.client.get_balance("KRW") or 0
            if krw_balance < self.trade_amount:
                log.result = f"KRW 잔고 부족 (₩{krw_balance:,.0f})"
                return False
                
            result = self.client.buy_market_order(ticker, self.trade_amount)
            if 'error' not in result:
                log.executed = True
                log.result = f"매수 성공: ₩{self.trade_amount:,}"
                return True
            else:
                log.result = f"매수 실패: {result.get('error')}"
                return False
                
        elif log.decision == AIDecision.SELL:
            balance = self.client.get_balance(coin) or 0
            if balance <= 0:
                log.result = "보유량 없음"
                return False
                
            result = self.client.sell_market_order(ticker, balance)
            if 'error' not in result:
                log.executed = True
                current_price = self.client.get_current_price(ticker)
                log.result = f"매도 성공: {balance} {coin} (≈₩{balance * current_price:,.0f})"
                return True
            else:
                log.result = f"매도 실패: {result.get('error')}"
                return False
                
        else:  # HOLD
            log.result = "홀드 - 거래 없음"
            return True
    
    def start(self):
        """AI 트레이딩 시작"""
        if self.is_running:
            return {"status": "already_running"}
            
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        return {"status": "started", "model": self.get_model_name()}
    
    def stop(self):
        """AI 트레이딩 중지"""
        if not self.is_running:
            return {"status": "not_running"}
            
        self.is_running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
            
        return {"status": "stopped"}
    
    def _run_loop(self):
        """메인 분석 루프"""
        print(f"[{datetime.now()}] AI 트레이딩 시작 - 모델: {self.get_model_name()}")
        
        while not self._stop_event.is_set():
            try:
                # 각 코인에 대해 분석
                for ticker in self.target_coins:
                    if self._stop_event.is_set():
                        break
                        
                    # 비동기 함수 실행
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        log = loop.run_until_complete(self.analyze_and_decide(ticker))
                        if log:
                            # 결정 실행
                            loop.run_until_complete(self.execute_decision(log))
                            self.logs.append(log)
                            print(f"[{datetime.now()}] AI 분석 완료: {ticker} - {log.decision} ({log.confidence}%)")
                    finally:
                        loop.close()
                        
                    time.sleep(2)  # API 호출 간격
                    
            except Exception as e:
                print(f"[{datetime.now()}] AI 분석 오류: {e}")
                
            self._stop_event.wait(self.check_interval)
            
        print(f"[{datetime.now()}] AI 트레이딩 종료")
    
    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """AI 로그 조회"""
        logs = self.logs[-limit:]
        return [asdict(log) for log in reversed(logs)]
    
    def get_status(self) -> Dict[str, Any]:
        """AI 트레이더 상태"""
        return {
            "is_running": self.is_running,
            "model": self.get_model_name(),
            "target_coins": self.target_coins,
            "trade_amount": self.trade_amount,
            "check_interval": self.check_interval,
            "total_analyses": len(self.logs),
            "executed_trades": sum(1 for log in self.logs if log.executed)
        }
    
    async def analyze_once(self, ticker: str) -> Optional[Dict[str, Any]]:
        """단일 분석 (수동 트리거)"""
        log = await self.analyze_and_decide(ticker)
        if log:
            self.logs.append(log)
            return asdict(log)
        return None


# 싱글톤 인스턴스
ai_trader = AITrader()

