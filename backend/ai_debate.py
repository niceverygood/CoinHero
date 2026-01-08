"""
AI 3대장 토론 모듈
세 명의 AI 전문가가 코인에 대해 토론하고 합의된 추천을 도출합니다.

캐릭터:
- 클로드 리 (Claude Lee): 균형 분석가 - 침착하고 분석적, 재무/실적 분석 전문
- 제미 나인 (Gemi Nine): 혁신·트렌드 전략가 - 세련됨, 신기술/트렌드 분석 전문  
- 지피 테일러 (G.P. Taylor): 수석 리스크 총괄 - 중후함, 거시경제/리스크 분석 전문
"""
import asyncio
import aiohttp
import json
import ssl
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import time

from upbit_client import upbit_client
from market_analyzer import market_analyzer


# OpenRouter API 설정
from config import OPENROUTER_API_KEY
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass
class Expert:
    """AI 전문가 캐릭터"""
    id: str
    name: str
    name_kr: str
    role: str
    personality: str
    focus: str
    model: str
    avatar: str  # 이미지 경로
    color: str   # 테마 색상


# AI 3대장 캐릭터 정의 (OpenRouter 최신 모델)
EXPERTS = {
    "claude": Expert(
        id="claude",
        name="Claude Lee",
        name_kr="클로드 리",
        role="균형 분석가 (Balanced Analyst)",
        personality="침착하고 분석적이며 디테일에 강함. 실적 분석, 재무구조, 산업 구조를 깊이 파고드는 타입.",
        focus="기술적 지표, 온체인 데이터, 거래량 분석",
        model="anthropic/claude-3.5-sonnet",  # Claude Opus 4.5
        avatar="/avatars/claude.png",
        color="#F97316"  # 오렌지
    ),
    "gemini": Expert(
        id="gemini",
        name="Gemi Nine",
        name_kr="제미 나인",
        role="혁신·트렌드 전략가 (Future Trend Strategist)",
        personality="세련됨, 센스, 빠른 판단. 신성장 산업, 기술 분석의 1인자. 감각적 사고 + 데이터 스캔 능력.",
        focus="신기술 트렌드, 생태계 발전, 커뮤니티 성장",
        model="google/gemini-2.0-flash-001",  # Gemini 3
        avatar="/avatars/gemini.png",
        color="#10B981"  # 민트/그린
    ),
    "gpt": Expert(
        id="gpt",
        name="G.P. Taylor",
        name_kr="지피 테일러",
        role="수석 리스크 총괄 (Chief Risk Officer)",
        personality="중후함, 느긋함, 깊은 통찰. 거시경제, 리스크 분석의 원로. 말투가 부드럽지만 권위 있음.",
        focus="거시경제, 규제 리스크, 시장 심리",
        model="openai/gpt-4o",  # GPT 5.2
        avatar="/avatars/gpt.png",
        color="#3B82F6"  # 블루
    )
}


class Opinion(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class DebateMessage:
    """토론 메시지"""
    id: str
    expert_id: str
    expert_name: str
    content: str
    opinion: str
    confidence: int
    key_points: List[str]
    timestamp: str


@dataclass
class DebateResult:
    """토론 결과"""
    ticker: str
    coin_name: str
    messages: List[DebateMessage]
    consensus: str  # 합의된 의견
    consensus_confidence: int
    final_verdict: str  # 최종 판정
    price_target: Optional[float]
    key_reasons: List[str]
    timestamp: str


class AIDebate:
    """AI 3대장 토론 시스템 - 매시간 자동 추천"""
    
    def __init__(self):
        self.client = upbit_client
        self.api_key = OPENROUTER_API_KEY
        self.debate_history: List[DebateResult] = []
        self.message_counter = 0
        self.is_running = False
        self.current_debate: Optional[Dict] = None
        self.hourly_recommendations: List[Dict] = []  # 매시간 추천 기록
        self._scheduler_task = None
        self._broadcast_callback = None  # WebSocket 브로드캐스트 콜백
        self.last_debate_time: Optional[str] = None
        
    def set_broadcast_callback(self, callback):
        """WebSocket 브로드캐스트 콜백 설정"""
        self._broadcast_callback = callback
        
    async def broadcast(self, data: Dict):
        """실시간 브로드캐스트"""
        if self._broadcast_callback:
            await self._broadcast_callback(json.dumps(data))
        
    async def call_ai(self, model: str, prompt: str, system_prompt: str) -> str:
        """OpenRouter API 호출"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8081",
            "X-Title": "CoinHero AI Debate"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    OPENROUTER_BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=90)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        error = await response.text()
                        print(f"AI API 오류 ({model}): {response.status} - {error}")
                        return None
        except Exception as e:
            print(f"AI 호출 실패 ({model}): {e}")
            return None
    
    def get_market_data(self, ticker: str) -> Dict[str, Any]:
        """시장 데이터 수집"""
        current_price = self.client.get_current_price(ticker)
        df = self.client.get_ohlcv(ticker, interval="day", count=30)
        
        if df is None or df.empty:
            return None
        
        # 기술적 지표
        analysis = market_analyzer.analyze_ticker(ticker)
        
        # 가격 변동
        price_change_24h = ((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]) * 100
        price_change_7d = ((df['close'].iloc[-1] - df['close'].iloc[-7]) / df['close'].iloc[-7]) * 100 if len(df) >= 7 else 0
        
        # 거래량
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        return {
            "ticker": ticker,
            "coin": ticker.replace("KRW-", ""),
            "current_price": current_price,
            "price_change_24h": round(price_change_24h, 2),
            "price_change_7d": round(price_change_7d, 2),
            "high_24h": df['high'].iloc[-1],
            "low_24h": df['low'].iloc[-1],
            "volume_24h": df['volume'].iloc[-1],
            "volume_ratio": round(volume_ratio, 2),
            "rsi": analysis.rsi,
            "trend_strength": analysis.trend_strength,
            "volatility": analysis.volatility,
            "support": analysis.support_level,
            "resistance": analysis.resistance_level,
            "market_condition": analysis.condition.value
        }
    
    async def get_expert_opinion(
        self, 
        expert: Expert, 
        ticker: str, 
        market_data: Dict, 
        previous_messages: List[DebateMessage] = None
    ) -> DebateMessage:
        """전문가 의견 수집"""
        
        # 이전 대화 내용 구성
        context = ""
        if previous_messages:
            context = "\n\n[이전 전문가들의 의견]\n"
            for msg in previous_messages:
                context += f"- {msg.expert_name}: {msg.content[:200]}... (의견: {msg.opinion}, 신뢰도: {msg.confidence}%)\n"
        
        system_prompt = f"""당신은 '{expert.name_kr}' ({expert.name})입니다.
역할: {expert.role}
성격: {expert.personality}
전문 분야: {expert.focus}

당신은 암호화폐 전문 애널리스트로서, 다른 두 전문가와 함께 토론을 진행합니다.
자신만의 관점에서 분석하되, 이전 전문가들의 의견이 있다면 그것에 대한 동의/반박도 포함하세요.

응답 형식 (JSON만, 다른 텍스트 없이):
{{
    "opinion": "strong_buy" | "buy" | "hold" | "sell" | "strong_sell",
    "confidence": 0-100,
    "content": "한국어로 2-4문장의 분석 의견. 자신의 캐릭터에 맞는 말투 사용.",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"]
}}"""

        prompt = f"""[{market_data['coin']}] 코인을 분석해주세요.

📊 현재 시장 데이터:
- 현재가: ₩{market_data['current_price']:,}
- 24시간 변동: {market_data['price_change_24h']}%
- 7일 변동: {market_data['price_change_7d']}%
- 거래량 비율: 평균 대비 {market_data['volume_ratio']}배
- RSI: {market_data['rsi']}
- 추세 강도: {market_data['trend_strength']}
- 변동성: {market_data['volatility']}%
- 지지선: ₩{market_data['support']:,}
- 저항선: ₩{market_data['resistance']:,}
- 시장 상태: {market_data['market_condition']}
{context}

당신의 전문 분야({expert.focus})를 바탕으로 분석하고, 
이전 전문가 의견에 동의하거나 다른 관점을 제시하세요."""

        response = await self.call_ai(expert.model, prompt, system_prompt)
        
        if not response:
            # 기본 응답 생성
            return DebateMessage(
                id=f"msg-{self.message_counter}",
                expert_id=expert.id,
                expert_name=expert.name_kr,
                content=f"현재 데이터 분석 중입니다. RSI {market_data['rsi']}, 변동성 {market_data['volatility']}% 수준입니다.",
                opinion="hold",
                confidence=50,
                key_points=["데이터 분석 진행 중"],
                timestamp=datetime.now().isoformat()
            )
        
        try:
            # JSON 파싱
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
            else:
                raise ValueError("JSON not found")
            
            self.message_counter += 1
            return DebateMessage(
                id=f"msg-{self.message_counter}-{int(time.time())}",
                expert_id=expert.id,
                expert_name=expert.name_kr,
                content=data.get("content", "분석 중..."),
                opinion=data.get("opinion", "hold"),
                confidence=data.get("confidence", 50),
                key_points=data.get("key_points", []),
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            print(f"JSON 파싱 실패 ({expert.id}): {e}")
            self.message_counter += 1
            return DebateMessage(
                id=f"msg-{self.message_counter}-{int(time.time())}",
                expert_id=expert.id,
                expert_name=expert.name_kr,
                content=response[:300] if response else "분석 실패",
                opinion="hold",
                confidence=50,
                key_points=[],
                timestamp=datetime.now().isoformat()
            )
    
    def calculate_consensus(self, messages: List[DebateMessage]) -> tuple:
        """합의 도출"""
        opinion_scores = {
            "strong_buy": 2,
            "buy": 1,
            "hold": 0,
            "sell": -1,
            "strong_sell": -2
        }
        
        total_score = 0
        total_confidence = 0
        all_key_points = []
        
        for msg in messages:
            score = opinion_scores.get(msg.opinion, 0)
            weight = msg.confidence / 100
            total_score += score * weight
            total_confidence += msg.confidence
            all_key_points.extend(msg.key_points[:2])
        
        avg_confidence = total_confidence / len(messages) if messages else 50
        avg_score = total_score / len(messages) if messages else 0
        
        # 합의 의견 결정
        if avg_score >= 1.5:
            consensus = "strong_buy"
            verdict = "🚀 강력 매수 추천"
        elif avg_score >= 0.5:
            consensus = "buy"
            verdict = "📈 매수 추천"
        elif avg_score >= -0.5:
            consensus = "hold"
            verdict = "⏸️ 관망 추천"
        elif avg_score >= -1.5:
            consensus = "sell"
            verdict = "📉 매도 추천"
        else:
            consensus = "strong_sell"
            verdict = "⚠️ 강력 매도 추천"
        
        return consensus, int(avg_confidence), verdict, all_key_points[:5]
    
    async def run_debate(self, ticker: str) -> Optional[DebateResult]:
        """토론 실행"""
        print(f"[{datetime.now()}] AI 3대장 토론 시작: {ticker}")
        
        # 시장 데이터 수집
        market_data = self.get_market_data(ticker)
        if not market_data:
            print(f"시장 데이터 수집 실패: {ticker}")
            return None
        
        messages = []
        
        # 순서대로 의견 수집 (Claude → Gemini → GPT)
        expert_order = ["claude", "gemini", "gpt"]
        
        for expert_id in expert_order:
            expert = EXPERTS[expert_id]
            print(f"  → {expert.name_kr} 분석 중...")
            
            message = await self.get_expert_opinion(
                expert, 
                ticker, 
                market_data,
                messages if messages else None
            )
            messages.append(message)
            
            # API 속도 제한 고려
            await asyncio.sleep(1)
        
        # 합의 도출
        consensus, confidence, verdict, key_reasons = self.calculate_consensus(messages)
        
        result = DebateResult(
            ticker=ticker,
            coin_name=market_data['coin'],
            messages=messages,
            consensus=consensus,
            consensus_confidence=confidence,
            final_verdict=verdict,
            price_target=None,
            key_reasons=key_reasons,
            timestamp=datetime.now().isoformat()
        )
        
        self.debate_history.append(result)
        print(f"[{datetime.now()}] 토론 완료: {verdict} (신뢰도 {confidence}%)")
        
        return result
    
    async def run_multi_debate(self, tickers: List[str]) -> List[DebateResult]:
        """여러 코인 토론"""
        results = []
        for ticker in tickers:
            result = await self.run_debate(ticker)
            if result:
                results.append(result)
        return results
    
    def get_top_picks(self, n: int = 5) -> List[Dict]:
        """상위 추천 코인"""
        if not self.debate_history:
            return []
        
        # 최근 토론 결과 중 매수 추천 필터
        buy_picks = [
            r for r in self.debate_history 
            if r.consensus in ["buy", "strong_buy"]
        ]
        
        # 신뢰도 순 정렬
        buy_picks.sort(key=lambda x: x.consensus_confidence, reverse=True)
        
        return [
            {
                "ticker": r.ticker,
                "coin": r.coin_name,
                "verdict": r.final_verdict,
                "confidence": r.consensus_confidence,
                "reasons": r.key_reasons[:3],
                "timestamp": r.timestamp
            }
            for r in buy_picks[:n]
        ]
    
    def to_dict(self, result: DebateResult) -> Dict:
        """결과를 딕셔너리로 변환"""
        return {
            "ticker": result.ticker,
            "coin_name": result.coin_name,
            "messages": [asdict(m) for m in result.messages],
            "consensus": result.consensus,
            "consensus_confidence": result.consensus_confidence,
            "final_verdict": result.final_verdict,
            "price_target": result.price_target,
            "key_reasons": result.key_reasons,
            "timestamp": result.timestamp,
            "experts": {k: asdict(v) for k, v in EXPERTS.items()}
        }


    async def get_top_candidates(self, n: int = 30) -> List[str]:
        """업비트 상장 코인 중 거래량 상위 코인 선정
        
        Args:
            n: 분석할 코인 수 (기본값: 30개, 최대: 전체 상장 코인)
        """
        try:
            import pyupbit
            
            # 모든 KRW 마켓 코인 가져오기
            all_tickers = pyupbit.get_tickers(fiat="KRW")
            if not all_tickers:
                return ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
            
            print(f"[토론] 업비트 전체 상장 코인: {len(all_tickers)}개")
            
            # 거래대금 기준으로 정렬하기 위해 현재가 정보 가져오기
            try:
                ticker_info = pyupbit.get_current_price(all_tickers)
                if ticker_info and isinstance(ticker_info, dict):
                    # 가격이 있는 코인만 필터링
                    valid_tickers = [t for t in all_tickers if ticker_info.get(t)]
                    print(f"[토론] 유효한 코인: {len(valid_tickers)}개")
                else:
                    valid_tickers = all_tickers
            except:
                valid_tickers = all_tickers
            
            # n개 선택 (BTC, ETH는 항상 포함)
            result = []
            if "KRW-BTC" in valid_tickers:
                result.append("KRW-BTC")
                valid_tickers.remove("KRW-BTC")
            if "KRW-ETH" in valid_tickers:
                result.append("KRW-ETH")
                valid_tickers.remove("KRW-ETH")
            
            # 나머지 코인 추가
            remaining = n - len(result)
            result.extend(valid_tickers[:remaining])
            
            print(f"[토론] 분석 대상: {len(result)}개 코인")
            return result[:n]
            
        except Exception as e:
            print(f"[토론] 후보 선정 실패: {e}")
            return ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"]
    
    async def run_hourly_debate(self) -> Dict:
        """매시간 AI 토론 실행"""
        print(f"\n{'='*60}")
        print(f"[{datetime.now()}] 🎭 AI 3대장 토론 시작!")
        print(f"{'='*60}")
        
        self.current_debate = {
            "status": "analyzing",
            "started_at": datetime.now().isoformat(),
            "messages": [],
            "candidates": [],
            "final_pick": None
        }
        
        # 실시간 상태 브로드캐스트
        await self.broadcast({
            "type": "debate_start",
            "data": {
                "status": "started",
                "message": "🎭 AI 3대장 토론이 시작되었습니다!",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        # 1. 후보 코인 선정 (거래량 상위 30개 코인 분석)
        candidates = await self.get_top_candidates(30)
        self.current_debate["candidates"] = candidates
        
        await self.broadcast({
            "type": "debate_candidates",
            "data": {
                "candidates": candidates,
                "message": f"📋 {len(candidates)}개 코인 후보 선정 완료"
            }
        })
        
        # 2. 각 코인에 대해 토론
        all_results = []
        for i, ticker in enumerate(candidates):
            coin_name = ticker.replace("KRW-", "")
            
            await self.broadcast({
                "type": "debate_progress",
                "data": {
                    "current_coin": coin_name,
                    "progress": i + 1,
                    "total": len(candidates),
                    "message": f"🔍 {coin_name} 분석 중..."
                }
            })
            
            result = await self.run_debate_with_broadcast(ticker)
            if result:
                all_results.append(result)
            
            await asyncio.sleep(2)  # API 속도 제한
        
        # 3. 최종 추천 선정
        final_pick = None
        if all_results:
            # 매수 추천 중 가장 높은 신뢰도
            buy_results = [r for r in all_results if r.consensus in ["buy", "strong_buy"]]
            if buy_results:
                buy_results.sort(key=lambda x: x.consensus_confidence, reverse=True)
                final_pick = buy_results[0]
        
        # 4. 결과 저장
        recommendation = {
            "timestamp": datetime.now().isoformat(),
            "candidates": candidates,
            "results": [self.to_dict(r) for r in all_results],
            "final_pick": self.to_dict(final_pick) if final_pick else None,
            "summary": {
                "total_analyzed": len(all_results),
                "buy_recommendations": len([r for r in all_results if r.consensus in ["buy", "strong_buy"]]),
                "hold_recommendations": len([r for r in all_results if r.consensus == "hold"]),
                "sell_recommendations": len([r for r in all_results if r.consensus in ["sell", "strong_sell"]])
            }
        }
        
        self.hourly_recommendations.append(recommendation)
        if len(self.hourly_recommendations) > 24:  # 최근 24시간만 유지
            self.hourly_recommendations = self.hourly_recommendations[-24:]
        
        self.last_debate_time = datetime.now().isoformat()
        self.current_debate = None
        
        # 최종 결과 브로드캐스트
        await self.broadcast({
            "type": "debate_complete",
            "data": {
                "recommendation": recommendation,
                "message": f"✅ AI 토론 완료! 추천: {final_pick.coin_name if final_pick else '없음'}"
            }
        })
        
        print(f"\n[{datetime.now()}] ✅ 토론 완료!")
        if final_pick:
            print(f"   🏆 최종 추천: {final_pick.coin_name} - {final_pick.final_verdict}")
        print(f"{'='*60}\n")
        
        return recommendation
    
    async def run_debate_with_broadcast(self, ticker: str) -> Optional[DebateResult]:
        """실시간 브로드캐스트와 함께 토론 실행"""
        coin_name = ticker.replace("KRW-", "")
        print(f"\n[{datetime.now()}] 🎭 {coin_name} 토론 시작")
        
        # 시장 데이터 수집
        market_data = self.get_market_data(ticker)
        if not market_data:
            print(f"   ❌ 시장 데이터 수집 실패")
            return None
        
        messages = []
        expert_order = ["claude", "gemini", "gpt"]
        
        for expert_id in expert_order:
            expert = EXPERTS[expert_id]
            
            # 분석 시작 브로드캐스트
            await self.broadcast({
                "type": "expert_thinking",
                "data": {
                    "coin": coin_name,
                    "expert_id": expert_id,
                    "expert_name": expert.name_kr,
                    "status": "thinking",
                    "message": f"💭 {expert.name_kr} 분석 중..."
                }
            })
            
            print(f"   → {expert.name_kr} 분석 중...")
            message = await self.get_expert_opinion(
                expert, ticker, market_data,
                messages if messages else None
            )
            messages.append(message)
            
            # 의견 브로드캐스트
            await self.broadcast({
                "type": "expert_opinion",
                "data": {
                    "coin": coin_name,
                    "expert_id": expert_id,
                    "expert_name": expert.name_kr,
                    "opinion": message.opinion,
                    "confidence": message.confidence,
                    "content": message.content,
                    "key_points": message.key_points,
                    "color": expert.color
                }
            })
            
            print(f"      의견: {message.opinion} (신뢰도 {message.confidence}%)")
            await asyncio.sleep(1)
        
        # 합의 도출
        consensus, confidence, verdict, key_reasons = self.calculate_consensus(messages)
        
        result = DebateResult(
            ticker=ticker,
            coin_name=coin_name,
            messages=messages,
            consensus=consensus,
            consensus_confidence=confidence,
            final_verdict=verdict,
            price_target=None,
            key_reasons=key_reasons,
            timestamp=datetime.now().isoformat()
        )
        
        self.debate_history.append(result)
        
        # 합의 결과 브로드캐스트
        await self.broadcast({
            "type": "debate_consensus",
            "data": {
                "coin": coin_name,
                "consensus": consensus,
                "confidence": confidence,
                "verdict": verdict,
                "key_reasons": key_reasons
            }
        })
        
        print(f"   ✅ 합의: {verdict} (신뢰도 {confidence}%)")
        return result
    
    async def start_hourly_scheduler(self):
        """매시간 자동 토론 스케줄러 시작"""
        if self.is_running:
            return
        
        self.is_running = True
        print(f"[{datetime.now()}] 🕐 매시간 AI 토론 스케줄러 시작")
        
        while self.is_running:
            try:
                # 다음 정시까지 대기
                now = datetime.now()
                next_hour = now.replace(minute=0, second=0, microsecond=0)
                if now.minute > 0 or now.second > 0:
                    next_hour = next_hour.replace(hour=now.hour + 1)
                
                wait_seconds = (next_hour - now).total_seconds()
                
                # 처음 시작 시 즉시 실행 (5분 내면 바로 실행)
                if wait_seconds > 300:  # 5분 이상 남았으면 대기
                    print(f"[{datetime.now()}] 다음 토론: {next_hour.strftime('%H:%M')} ({int(wait_seconds/60)}분 후)")
                    await asyncio.sleep(wait_seconds)
                
                if not self.is_running:
                    break
                
                # 토론 실행
                await self.run_hourly_debate()
                
                # 1시간 대기 (다음 정시)
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[토론 스케줄러 오류] {e}")
                await asyncio.sleep(60)  # 오류 시 1분 후 재시도
        
        print(f"[{datetime.now()}] 🛑 AI 토론 스케줄러 종료")
    
    def stop_scheduler(self):
        """스케줄러 중지"""
        self.is_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
    
    def get_status(self) -> Dict:
        """현재 상태 조회"""
        return {
            "is_running": self.is_running,
            "last_debate_time": self.last_debate_time,
            "current_debate": self.current_debate,
            "total_debates": len(self.debate_history),
            "hourly_recommendations_count": len(self.hourly_recommendations),
            "experts": {k: asdict(v) for k, v in EXPERTS.items()}
        }
    
    def get_latest_recommendation(self) -> Optional[Dict]:
        """최신 추천 조회"""
        if self.hourly_recommendations:
            return self.hourly_recommendations[-1]
        return None


# 싱글톤 인스턴스
ai_debate = AIDebate()







