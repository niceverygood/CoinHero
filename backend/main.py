"""
CoinHero - 업비트 자동거래 시스템 API 서버
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import json
from datetime import datetime

from config import BACKEND_PORT
from upbit_client import upbit_client
from trading_engine import trading_engine
from ai_trader import ai_trader, AI_MODELS
from coin_scanner import coin_scanner
from market_analyzer import market_analyzer
from ai_debate import ai_debate, EXPERTS
from scalping_strategies import STRATEGIES, StrategyType
from scalping_trader import scalping_trader
from ai_scalper import ai_scalper
from database import db
from dataclasses import asdict

app = FastAPI(
    title="CoinHero API",
    description="업비트 코인 자동거래 시스템",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Pydantic Models ==========

class ConfigureRequest(BaseModel):
    strategy: Optional[str] = None
    coins: Optional[List[str]] = None
    amount: Optional[int] = None
    interval: Optional[int] = None


class TradeRequest(BaseModel):
    ticker: str
    amount: Optional[float] = None


# ========== WebSocket 관리 ==========

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass


manager = ConnectionManager()

# AI Scalper에 WebSocket 브로드캐스트 콜백 설정
ai_scalper.set_broadcast_callback(manager.broadcast)


# ========== API 엔드포인트 ==========

@app.get("/")
async def root():
    return {
        "name": "CoinHero API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


# 시세 조회
@app.get("/api/price/{ticker}")
async def get_price(ticker: str):
    """현재가 조회"""
    price = upbit_client.get_current_price(ticker)
    if price is None:
        raise HTTPException(status_code=404, detail="가격 조회 실패")
    return {"ticker": ticker, "price": price}


@app.get("/api/prices")
async def get_prices(tickers: str = "KRW-BTC,KRW-ETH"):
    """여러 코인 현재가 조회"""
    ticker_list = tickers.split(",")
    prices = upbit_client.get_current_prices(ticker_list)
    return {"prices": prices}


@app.get("/api/ohlcv/{ticker}")
async def get_ohlcv(ticker: str, interval: str = "day", count: int = 100):
    """OHLCV 데이터 조회"""
    df = upbit_client.get_ohlcv(ticker, interval=interval, count=count)
    if df.empty:
        raise HTTPException(status_code=404, detail="데이터 조회 실패")
    return {"ticker": ticker, "data": df.reset_index().to_dict(orient='records')}


@app.get("/api/orderbook/{ticker}")
async def get_orderbook(ticker: str):
    """호가 정보 조회"""
    orderbook = upbit_client.get_orderbook(ticker)
    if not orderbook:
        raise HTTPException(status_code=404, detail="호가 조회 실패")
    return orderbook


# API 연결 상태 확인
@app.get("/api/auth/status")
async def check_auth_status():
    """API 키 인증 상태 확인"""
    from config import UPBIT_ACCESS_KEY
    api_key_preview = UPBIT_ACCESS_KEY[:8] + "..." if UPBIT_ACCESS_KEY else None
    
    try:
        # 잔고 조회로 API 키 유효성 확인
        balances = upbit_client.upbit.get_balances()
        if balances is None:
            return {
                "authenticated": False,
                "status": "error",
                "message": "잔고 조회 실패",
                "api_key_preview": api_key_preview
            }
        
        # 에러 메시지 확인
        if isinstance(balances, dict) and 'error' in balances:
            error_msg = balances.get('error', {}).get('message', '알 수 없는 오류')
            return {
                "authenticated": False,
                "status": "invalid_key",
                "message": error_msg,
                "api_key_preview": api_key_preview
            }
            
        return {
            "authenticated": True,
            "status": "connected",
            "message": "업비트 API 연결됨",
            "api_key_preview": api_key_preview,
            "account_count": len(balances)
        }
    except Exception as e:
        error_str = str(e)
        status = "expired" if "만료" in error_str or "Expired" in error_str else "error"
        return {
            "authenticated": False,
            "status": status,
            "message": error_str,
            "api_key_preview": api_key_preview
        }


# 잔고 조회
@app.get("/api/balance")
async def get_balance():
    """전체 잔고 조회 (매수일 정보 포함)"""
    try:
        balances = upbit_client.get_balances()
        total_krw = sum(b['eval_amount'] for b in balances) if balances else 0
        
        # 인증 상태 확인
        auth_status = "connected" if balances else "disconnected"
        
        # 각 코인별 매수일 정보 추가
        if balances:
            # DB와 메모리에서 매수 기록 조회
            all_trades = db.get_trades(500)  # 최근 500개 거래
            memory_trades = trading_engine.get_trade_logs(100)
            ai_trades = ai_scalper.get_trade_logs(100)
            
            # 코인별 최초 매수일 찾기
            coin_buy_dates = {}
            
            # DB 거래에서 매수 기록 찾기
            for trade in all_trades:
                action = trade.get("action", trade.get("side", ""))
                if action == "buy":
                    ticker = trade.get("ticker", "")
                    currency = ticker.replace("KRW-", "") if ticker else trade.get("coin_name", "")
                    timestamp = trade.get("created_at", trade.get("timestamp", ""))
                    if currency and timestamp:
                        if currency not in coin_buy_dates:
                            coin_buy_dates[currency] = timestamp
                        elif timestamp < coin_buy_dates[currency]:
                            coin_buy_dates[currency] = timestamp
            
            # 메모리 거래에서 매수 기록 찾기
            for trade in memory_trades + ai_trades:
                action = trade.get("action", trade.get("side", ""))
                if action == "buy":
                    ticker = trade.get("ticker", "")
                    currency = ticker.replace("KRW-", "") if ticker else trade.get("coin_name", "")
                    timestamp = trade.get("timestamp", "")
                    if currency and timestamp:
                        if currency not in coin_buy_dates:
                            coin_buy_dates[currency] = timestamp
                        elif timestamp < coin_buy_dates[currency]:
                            coin_buy_dates[currency] = timestamp
            
            # AI 스캘퍼 포지션에서 entry_time 조회
            for ticker, pos in ai_scalper.positions.items():
                currency = ticker.replace("KRW-", "")
                entry_time = pos.get("entry_time", "")
                if entry_time:
                    if currency not in coin_buy_dates:
                        coin_buy_dates[currency] = entry_time
                    elif entry_time < coin_buy_dates[currency]:
                        coin_buy_dates[currency] = entry_time
            
            # 잔고 데이터에 매수일 정보 추가
            now = datetime.now()
            for b in balances:
                currency = b.get("currency", "")
                if currency in coin_buy_dates:
                    buy_date_str = coin_buy_dates[currency]
                    try:
                        # ISO 형식 파싱
                        if 'T' in buy_date_str:
                            buy_date = datetime.fromisoformat(buy_date_str.replace('Z', '+00:00').split('+')[0])
                        else:
                            buy_date = datetime.strptime(buy_date_str[:10], "%Y-%m-%d")
                        
                        days_held = (now - buy_date).days
                        b["buy_date"] = buy_date.strftime("%Y-%m-%d")
                        b["days_held"] = days_held
                    except:
                        b["buy_date"] = None
                        b["days_held"] = None
                else:
                    b["buy_date"] = None
                    b["days_held"] = None
        
        return {
            "balances": balances,
            "total_krw": total_krw,
            "timestamp": datetime.now().isoformat(),
            "auth_status": auth_status
        }
    except Exception as e:
        return {
            "balances": [],
            "total_krw": 0,
            "timestamp": datetime.now().isoformat(),
            "auth_status": "error",
            "error": str(e)
        }


@app.get("/api/balance/{currency}")
async def get_currency_balance(currency: str):
    """특정 통화 잔고 조회"""
    balance = upbit_client.get_balance(currency)
    return {"currency": currency, "balance": balance}


# 마켓 정보
@app.get("/api/tickers")
async def get_tickers():
    """마켓 코드 목록"""
    tickers = upbit_client.get_tickers()
    return {"tickers": tickers, "count": len(tickers)}


@app.get("/api/coins")
async def get_coins():
    """코인 정보 목록"""
    coins = upbit_client.get_ticker_info()
    return {"coins": coins, "count": len(coins)}


# 자동매매 봇
@app.get("/api/bot/status")
async def get_bot_status():
    """봇 상태 조회"""
    status = trading_engine.get_status()
    return asdict(status)


@app.post("/api/bot/configure")
async def configure_bot(config: ConfigureRequest):
    """봇 설정 변경"""
    trading_engine.configure(
        strategy=config.strategy,
        coins=config.coins,
        amount=config.amount,
        interval=config.interval
    )
    return {"status": "configured", "config": asdict(trading_engine.get_status())}


@app.post("/api/bot/start")
async def start_bot():
    """자동매매 시작"""
    result = trading_engine.start()
    await manager.broadcast(json.dumps({"type": "bot_started", "data": result}))
    return result


@app.post("/api/bot/stop")
async def stop_bot():
    """자동매매 중지"""
    result = trading_engine.stop()
    await manager.broadcast(json.dumps({"type": "bot_stopped", "data": result}))
    return result


# 수동 거래
@app.post("/api/trade/buy")
async def manual_buy(request: TradeRequest):
    """수동 매수"""
    result = trading_engine.manual_buy(request.ticker, request.amount)
    await manager.broadcast(json.dumps({"type": "trade", "data": result}))
    return result


@app.post("/api/trade/sell")
async def manual_sell(request: TradeRequest):
    """수동 매도"""
    result = trading_engine.manual_sell(request.ticker, request.amount)
    await manager.broadcast(json.dumps({"type": "trade", "data": result}))
    return result


# 거래 기록
@app.get("/api/trades")
async def get_trades(limit: int = 50):
    """거래 기록 조회 (DB + 메모리 통합 및 정규화)"""
    # 1. DB에서 최신 거래 내역 조회 (persistent)
    db_trades = db.get_trades(limit)
    
    # 2. 엔진별 메모리 로그 수집 (최신 세션)
    rule_logs_raw = trading_engine.get_trade_logs(limit)
    ai_logs_raw = ai_scalper.get_trade_logs(limit)
    
    # 정규화된 결과 리스트
    normalized_trades = []
    
    # DB 로그 추가 (이미 정규화된 형식일 확률이 높음)
    for t in db_trades:
        # DB 필드명을 API 형식으로 변환
        normalized_trades.append({
            "action": t.get("action", t.get("side", "buy")),
            "ticker": t.get("ticker", ""),
            "coin_name": t.get("coin_name", t.get("ticker", "").replace("KRW-", "")),
            "price": t.get("price", 0),
            "total_krw": t.get("total_krw", t.get("amount", 0)),
            "amount": t.get("amount", t.get("volume", 0)),
            "strategy": t.get("strategy", ""),
            "ai_reason": t.get("ai_reason", t.get("reason", "")),
            "timestamp": t.get("created_at", t.get("timestamp", "")),
            "success": t.get("success", True),
            "profit": t.get("profit"),
            "profit_rate": t.get("profit_rate")
        })
        
    # 메모리 룰 로그 추가
    for log in rule_logs_raw:
        ticker = log.get("ticker", "")
        normalized_trades.append({
            "action": log.get("side", "buy"),
            "ticker": ticker,
            "coin_name": ticker.replace("KRW-", ""),
            "price": log.get("price", 0),
            "total_krw": log.get("amount", 0),
            "amount": log.get("volume", 0),
            "strategy": log.get("strategy", "manual"),
            "ai_reason": log.get("reason", ""),
            "timestamp": log.get("timestamp", ""),
            "success": log.get("success", True),
            "profit": None,
            "profit_rate": None
        })
        
    # 메모리 AI 로그 추가
    for log in ai_logs_raw:
        normalized_trades.append({
            "action": log.get("action", "buy"),
            "ticker": log.get("ticker", ""),
            "coin_name": log.get("coin_name", ""),
            "price": log.get("price", 0),
            "total_krw": log.get("total_krw", 0),
            "amount": log.get("amount", 0),
            "strategy": f"AI-{log.get('strategy', 'unknown')}",
            "ai_reason": log.get("ai_reason", ""),
            "timestamp": log.get("timestamp", ""),
            "success": True,
            "profit": log.get("profit"),
            "profit_rate": log.get("profit_rate")
        })
        
    # 중복 제거 (timestamp + ticker 기준)
    seen = set()
    unique_trades = []
    for t in normalized_trades:
        key = (t["timestamp"], t["ticker"], t["action"])
        if key not in seen:
            seen.add(key)
            unique_trades.append(t)
            
    # 시간순 정렬
    unique_trades.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return {"trades": unique_trades[:limit], "count": len(unique_trades)}


# 분석
@app.get("/api/analysis/{ticker}")
async def get_analysis(ticker: str):
    """코인 분석 정보"""
    analysis = trading_engine.get_analysis(ticker)
    if "error" in analysis:
        raise HTTPException(status_code=404, detail=analysis["error"])
    return analysis


# ========== AI 트레이더 ==========

@app.get("/api/ai/status")
async def get_ai_status():
    """AI 트레이더 상태 조회"""
    return ai_trader.get_status()


@app.get("/api/ai/models")
async def get_ai_models():
    """사용 가능한 AI 모델 목록"""
    return {"models": list(AI_MODELS.keys()), "current": ai_trader.get_model_name()}


@app.post("/api/ai/configure")
async def configure_ai(config: ConfigureRequest):
    """AI 트레이더 설정"""
    if config.strategy:  # model로 사용
        ai_trader.set_model(config.strategy)
    if config.coins:
        ai_trader.target_coins = config.coins
    if config.amount:
        ai_trader.trade_amount = config.amount
    if config.interval:
        ai_trader.check_interval = config.interval
    return ai_trader.get_status()


@app.post("/api/ai/start")
async def start_ai():
    """AI 트레이딩 시작"""
    result = ai_trader.start()
    await manager.broadcast(json.dumps({"type": "ai_started", "data": result}))
    return result


@app.post("/api/ai/stop")
async def stop_ai():
    """AI 트레이딩 중지"""
    result = ai_trader.stop()
    await manager.broadcast(json.dumps({"type": "ai_stopped", "data": result}))
    return result


@app.get("/api/ai/logs")
async def get_ai_logs(limit: int = 50):
    """AI 활동 로그 조회"""
    logs = ai_trader.get_logs(limit)
    return {"logs": logs, "count": len(logs)}


@app.post("/api/ai/analyze/{ticker}")
async def analyze_ticker(ticker: str):
    """특정 코인 AI 분석 (수동)"""
    result = await ai_trader.analyze_once(ticker)
    if result:
        await manager.broadcast(json.dumps({"type": "ai_analysis", "data": result}))
        return result
    raise HTTPException(status_code=500, detail="AI 분석 실패")


# ========== 코인 스캐너 ==========

@app.post("/api/scan")
async def scan_all_coins(min_volume: float = 1_000_000_000):
    """
    전체 코인 스캔
    
    Args:
        min_volume: 최소 거래대금 (기본 10억원)
    """
    results = coin_scanner.scan_all_coins(min_volume=min_volume)
    return {
        "success": True,
        "count": len(results),
        "last_scan": coin_scanner.last_scan,
        "coins": coin_scanner.to_dict_list(results[:50])  # 상위 50개만 반환
    }


@app.get("/api/scan/results")
async def get_scan_results(limit: int = 20):
    """스캔 결과 조회"""
    return {
        "count": len(coin_scanner.scan_results),
        "last_scan": coin_scanner.last_scan,
        "coins": coin_scanner.to_dict_list(coin_scanner.scan_results[:limit])
    }


@app.get("/api/scan/top")
async def get_top_coins(n: int = 10):
    """상위 N개 코인"""
    coins = coin_scanner.get_top_coins(n)
    return {
        "count": len(coins),
        "last_scan": coin_scanner.last_scan,
        "coins": coin_scanner.to_dict_list(coins)
    }


@app.get("/api/scan/buy-candidates")
async def get_buy_candidates(min_score: float = 60):
    """매수 후보 코인"""
    coins = coin_scanner.get_buy_candidates(min_score)
    return {
        "count": len(coins),
        "min_score": min_score,
        "coins": coin_scanner.to_dict_list(coins)
    }


@app.get("/api/scan/volatility-breakout")
async def get_volatility_breakout():
    """변동성 돌파 조건 충족 코인"""
    coins = coin_scanner.get_volatility_breakout_coins()
    return {
        "count": len(coins),
        "coins": coin_scanner.to_dict_list(coins)
    }


@app.get("/api/scan/rsi-oversold")
async def get_rsi_oversold():
    """RSI 과매도 코인"""
    coins = coin_scanner.get_rsi_oversold_coins()
    return {
        "count": len(coins),
        "coins": coin_scanner.to_dict_list(coins)
    }


@app.get("/api/scan/golden-cross")
async def get_golden_cross():
    """골든크로스 발생 코인"""
    coins = coin_scanner.get_golden_cross_coins()
    return {
        "count": len(coins),
        "coins": coin_scanner.to_dict_list(coins)
    }


# ========== 시장 분석 & 전략 추천 ==========

@app.get("/api/market/analyze/{ticker}")
async def analyze_market(ticker: str):
    """개별 코인 시장 분석"""
    analysis = market_analyzer.analyze_ticker(ticker)
    return analysis.to_dict()


@app.get("/api/market/best-strategy")
async def get_best_strategy(tickers: str = "KRW-BTC,KRW-ETH,KRW-XRP"):
    """
    여러 코인을 분석하여 최적의 전략 추천
    
    Args:
        tickers: 쉼표로 구분된 코인 목록
    """
    ticker_list = [t.strip() for t in tickers.split(",")]
    result = market_analyzer.get_best_strategy_for_market(ticker_list)
    return result


@app.post("/api/ai/auto-strategy")
async def toggle_auto_strategy(enabled: bool = True):
    """AI 자동 전략 선택 모드 설정"""
    ai_trader.auto_strategy_mode = enabled
    return {
        "auto_strategy_mode": ai_trader.auto_strategy_mode,
        "current_strategy": ai_trader.current_recommended_strategy,
        "last_analysis": ai_trader.last_strategy_analysis
    }


@app.get("/api/ai/strategy-status")
async def get_strategy_status():
    """현재 AI 전략 상태 조회"""
    return {
        "auto_strategy_mode": ai_trader.auto_strategy_mode,
        "current_recommended_strategy": ai_trader.current_recommended_strategy,
        "last_strategy_analysis": ai_trader.last_strategy_analysis,
        "model": ai_trader.get_model_name()
    }


# ========== AI 3대장 토론 ==========

@app.get("/api/debate/experts")
async def get_experts():
    """AI 전문가 정보 조회"""
    return {
        "experts": {k: {
            "id": v.id,
            "name": v.name,
            "name_kr": v.name_kr,
            "role": v.role,
            "personality": v.personality,
            "focus": v.focus,
            "avatar": v.avatar,
            "color": v.color
        } for k, v in EXPERTS.items()}
    }


@app.post("/api/debate/{ticker}")
async def run_debate(ticker: str):
    """특정 코인에 대한 AI 토론 실행"""
    result = await ai_debate.run_debate(ticker)
    if result:
        return ai_debate.to_dict(result)
    raise HTTPException(status_code=500, detail="토론 실행 실패")


@app.post("/api/debate/multi")
async def run_multi_debate(tickers: str = "KRW-BTC,KRW-ETH,KRW-XRP"):
    """여러 코인 토론 실행"""
    ticker_list = [t.strip() for t in tickers.split(",")]
    results = await ai_debate.run_multi_debate(ticker_list)
    return {
        "count": len(results),
        "debates": [ai_debate.to_dict(r) for r in results]
    }


@app.get("/api/debate/history")
async def get_debate_history(limit: int = 10):
    """토론 기록 조회"""
    history = ai_debate.debate_history[-limit:]
    return {
        "count": len(history),
        "debates": [ai_debate.to_dict(r) for r in history]
    }


@app.get("/api/debate/top-picks")
async def get_top_picks(n: int = 5):
    """AI 3대장 만장일치 추천 코인"""
    picks = ai_debate.get_top_picks(n)
    return {
        "count": len(picks),
        "picks": picks
    }


# ========== WebSocket ==========

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 데이터 스트림"""
    await manager.connect(websocket)
    
    async def send_updates():
        while True:
            try:
                # 봇 상태
                status = asdict(trading_engine.get_status())
                await websocket.send_json({"type": "status", "data": status})
                
                # 주요 코인 가격
                main_tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
                prices = upbit_client.get_current_prices(main_tickers)
                await websocket.send_json({"type": "prices", "data": prices})
                
                # 잔고 정보
                balances = upbit_client.get_balances()
                await websocket.send_json({"type": "balances", "data": balances})
                
                await asyncio.sleep(5)  # 5초마다 업데이트
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket 오류: {e}")
                break
    
    try:
        # 업데이트 태스크 시작
        update_task = asyncio.create_task(send_updates())
        
        # 클라이언트 메시지 수신
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "subscribe":
                # 구독 처리
                pass
            elif message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        update_task.cancel()


# ========== 단타 전략 API ==========

class ScalpingConfigRequest(BaseModel):
    strategy: Optional[str] = None
    strategies: Optional[List[str]] = None  # 복수 전략 지원
    trade_amount: Optional[float] = 10000
    max_positions: Optional[int] = 3
    scan_interval: Optional[int] = 60


@app.get("/api/scalping/strategies")
async def get_scalping_strategies():
    """사용 가능한 단타 전략 목록"""
    strategies = []
    for strategy_type, info in STRATEGIES.items():
        strategies.append({
            "id": info.id,
            "name": info.name,
            "name_kr": info.name_kr,
            "description": info.description,
            "risk_level": info.risk_level,
            "holding_time": info.holding_time,
            "win_rate": info.win_rate,
            "emoji": info.emoji
        })
    return {"strategies": strategies}


@app.get("/api/scalping/status")
async def get_scalping_status():
    """단타 트레이더 상태 조회"""
    return scalping_trader.get_status()


@app.post("/api/scalping/configure")
async def configure_scalping(config: ScalpingConfigRequest):
    """단타 트레이더 설정"""
    try:
        result = scalping_trader.configure(
            strategy=config.strategy,
            trade_amount=config.trade_amount or 10000,
            max_positions=config.max_positions or 3,
            scan_interval=config.scan_interval or 60
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/scalping/start")
async def start_scalping():
    """단타 자동매매 시작"""
    try:
        result = scalping_trader.start()
        await manager.broadcast(json.dumps({
            "type": "scalping_started",
            "data": result
        }))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/scalping/stop")
async def stop_scalping():
    """단타 자동매매 중지"""
    result = scalping_trader.stop()
    await manager.broadcast(json.dumps({
        "type": "scalping_stopped",
        "data": result
    }))
    return result


@app.get("/api/scalping/logs")
async def get_scalping_logs(limit: int = 20):
    """단타 거래 기록"""
    return {
        "logs": scalping_trader.get_trade_logs(limit),
        "count": len(scalping_trader.trade_logs)
    }


@app.post("/api/scalping/scan")
async def manual_scan(strategy: Optional[str] = None):
    """수동 전체 코인 스캔"""
    result = await scalping_trader.manual_scan(strategy)
    await manager.broadcast(json.dumps({
        "type": "scan_result",
        "data": result
    }))
    return result


# ========== AI 단타 전략 API ==========

@app.get("/api/ai-scalping/status")
async def get_ai_scalping_status():
    """AI 단타 트레이더 상태 조회"""
    return ai_scalper.get_status()


@app.get("/api/ai-scalping/positions")
async def get_ai_positions_detail():
    """보유 포지션 상세 정보 및 매도 전략 조회 (모든 보유 종목 포함)"""
    ai_positions = ai_scalper.positions  # AI가 관리하는 포지션
    detailed_positions = []
    processed_tickers = set()
    
    # 매도 전략 설정값
    sell_strategy_config = {
        "min_profit_for_ai_analysis": 5.0,
        "min_profit_for_trailing": 5.0,
        "stop_loss_pct": -3.0,
        "target_profit": 10.0,
        "min_holding_seconds": 300
    }
    
    # 1. 먼저 AI 포지션 처리
    for ticker, pos in ai_positions.items():
        processed_tickers.add(ticker)
        position_info = _get_position_detail(ticker, pos, sell_strategy_config, is_ai_managed=True)
        detailed_positions.append(position_info)
    
    # 2. 업비트 잔고에서 모든 보유 종목 가져오기 (AI 포지션이 아닌 것도 포함)
    try:
        balances = upbit_client.get_balances()
        if isinstance(balances, list):
            for coin in balances:
                currency = coin.get('currency', '')
                if currency == 'KRW':
                    continue
                    
                ticker = f"KRW-{currency}"
                
                # AI 포지션에서 이미 처리한 것은 스킵
                if ticker in processed_tickers:
                    continue
                
                balance = float(coin.get('balance', 0) or 0)
                avg_buy_price = float(coin.get('avg_buy_price', 0) or 0)
                
                # 너무 작은 잔고는 스킵
                if balance * avg_buy_price < 1000:
                    continue
                
                # 수동 보유 종목 정보 구성
                manual_pos = {
                    'entry_price': avg_buy_price,
                    'coin_name': currency,
                    'entry_time': coin.get('buy_date') or datetime.now().isoformat(),
                    'invest_amount': balance * avg_buy_price,
                    'strategy': '수동 보유',
                    'volume': balance
                }
                
                position_info = _get_position_detail(ticker, manual_pos, sell_strategy_config, is_ai_managed=False)
                detailed_positions.append(position_info)
                processed_tickers.add(ticker)
    except Exception as e:
        logger.error(f"잔고 조회 오류: {e}")
    
    # 수익률 순으로 정렬 (높은 것이 먼저)
    detailed_positions.sort(key=lambda x: x['profit_rate'], reverse=True)
    
    # 최근 AI 모니터링 로그 가져오기
    recent_activities = ai_scalper.get_activities(20)
    monitoring_logs = [a for a in recent_activities if a.get('type') in ['exit_scan', 'new_high', 'trailing_active', 'exit_decision', 'ai_sell_analysis', 'position_status']]
    
    return {
        "positions": detailed_positions,
        "count": len(detailed_positions),
        "ai_count": len(ai_positions),
        "manual_count": len(detailed_positions) - len(ai_positions),
        "sell_strategy_config": sell_strategy_config,
        "monitoring_logs": monitoring_logs[:10],
        "is_monitoring": ai_scalper.is_running
    }


def _get_position_detail(ticker: str, pos: dict, sell_strategy_config: dict, is_ai_managed: bool = True) -> dict:
    """포지션 상세 정보 생성"""
    current_price = upbit_client.get_current_price(ticker)
    entry_price = pos.get('entry_price', 0)
    
    if current_price and entry_price:
        profit_rate = (current_price - entry_price) / entry_price * 100
    else:
        profit_rate = 0
    
    # 보유 시간 계산
    entry_time_str = pos.get('entry_time', datetime.now().isoformat())
    try:
        entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
        holding_seconds = (datetime.now() - entry_time.replace(tzinfo=None)).total_seconds()
    except:
        holding_seconds = 0
    
    holding_minutes = int(holding_seconds // 60)
    holding_hours = holding_minutes // 60
    holding_mins_remainder = holding_minutes % 60
    
    # 매도 전략 상태 분석
    max_profit = pos.get('max_profit') or profit_rate
    trailing_stop = pos.get('trailing_stop')
    
    # None 체크
    if max_profit is None:
        max_profit = profit_rate
    
    # 현재 상태 판단
    if not is_ai_managed:
        status = "👤 수동 보유"
        status_color = "gray"
    elif profit_rate <= sell_strategy_config["stop_loss_pct"]:
        status = "🔴 손절 임박"
        status_color = "red"
    elif profit_rate >= sell_strategy_config["target_profit"]:
        status = "🎯 목표 달성"
        status_color = "gold"
    elif profit_rate >= sell_strategy_config["min_profit_for_ai_analysis"]:
        if trailing_stop:
            trailing_pct = (trailing_stop - entry_price) / entry_price * 100
            status = f"📊 트레일링 ({trailing_pct:+.1f}%)"
            status_color = "green"
        else:
            status = "🤖 AI 분석 중"
            status_color = "cyan"
    elif profit_rate > 0:
        status = "📈 수익 중"
        status_color = "green"
    else:
        status = "📉 손실 중"
        status_color = "orange"
    
    return {
        "ticker": ticker,
        "coin_name": pos.get('coin_name', ticker.replace('KRW-', '')),
        "entry_price": entry_price,
        "current_price": current_price,
        "profit_rate": round(profit_rate, 2),
        "max_profit": round(max_profit, 2),
        "trailing_stop": trailing_stop,
        "trailing_stop_pct": round((trailing_stop - entry_price) / entry_price * 100, 2) if trailing_stop and entry_price else None,
        "entry_time": entry_time_str,
        "holding_time": f"{holding_hours}h {holding_mins_remainder}m" if holding_hours > 0 else f"{holding_minutes}m",
        "holding_seconds": holding_seconds,
        "invest_amount": pos.get('invest_amount', 0),
        "strategy": pos.get('strategy', ''),
        "status": status,
        "status_color": status_color,
        "is_ai_managed": is_ai_managed,
        "sell_strategy": {
            "stop_loss": sell_strategy_config["stop_loss_pct"],
            "target_profit": sell_strategy_config["target_profit"],
            "ai_analysis_threshold": sell_strategy_config["min_profit_for_ai_analysis"],
            "trailing_threshold": sell_strategy_config["min_profit_for_trailing"],
            "min_holding_time": f"{sell_strategy_config['min_holding_seconds'] // 60}분"
        }
    }


@app.post("/api/ai-scalping/configure")
async def configure_ai_scalping(config: ScalpingConfigRequest):
    """AI 단타 트레이더 설정 (복수 전략 지원)"""
    try:
        result = ai_scalper.configure(
            strategy=config.strategy,
            strategies=config.strategies,  # 복수 전략
            trade_amount=config.trade_amount or 10000,
            max_positions=config.max_positions or 3,
            check_interval=config.scan_interval or 60
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/ai-scalping/start")
async def start_ai_scalping():
    """AI 단타 자동매매 시작"""
    try:
        result = ai_scalper.start()
        await manager.broadcast(json.dumps({
            "type": "ai_scalping_started",
            "data": result
        }))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/ai-scalping/stop")
async def stop_ai_scalping():
    """AI 단타 자동매매 중지"""
    result = ai_scalper.stop()
    await manager.broadcast(json.dumps({
        "type": "ai_scalping_stopped",
        "data": result
    }))
    return result


@app.get("/api/ai-scalping/models")
async def get_ai_models():
    """사용 가능한 AI 모델 목록 조회"""
    return ai_scalper.get_ai_models()


@app.get("/api/ai-scalping/activities")
async def get_ai_activities(limit: int = 20):
    """실시간 AI 활동 로그 조회"""
    return {
        "activities": ai_scalper.get_activities(limit),
        "count": len(ai_scalper.activity_logs)
    }


@app.get("/api/ai-scalping/signals")
async def get_ai_signals(limit: int = 20):
    """발견된 신호 조회"""
    return {
        "signals": ai_scalper.get_signals(limit),
        "count": len(ai_scalper.discovered_signals)
    }


@app.post("/api/ai-scalping/models/{model_key}")
async def set_ai_model(model_key: str):
    """AI 모델 변경"""
    if ai_scalper.set_ai_model(model_key):
        return {
            "status": "success",
            "model": model_key,
            "info": ai_scalper.get_ai_models()
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_key}")


@app.get("/api/ai-scalping/logs")
async def get_ai_scalping_logs(limit: int = 20):
    """AI 단타 거래 기록"""
    return {
        "logs": ai_scalper.get_trade_logs(limit),
        "ai_decisions": ai_scalper.get_ai_decisions(limit // 2),
        "count": len(ai_scalper.trade_logs)
    }


@app.get("/api/ai-scalping/decisions")
async def get_ai_decisions(limit: int = 10):
    """AI 결정 기록"""
    return {
        "decisions": ai_scalper.get_ai_decisions(limit),
        "count": len(ai_scalper.ai_decisions)
    }


# ========== DB 통계 ==========

@app.get("/api/db/status")
async def get_db_status():
    """DB 연결 상태"""
    return {
        "connected": db.is_connected(),
        "type": "supabase" if db.is_connected() else "memory"
    }


@app.get("/api/db/stats")
async def get_db_stats():
    """거래 통계"""
    if not db.is_connected():
        return {"error": "DB 연결 안됨"}
    
    return {
        "total_profit": db.get_total_profit(),
        "today_trades": db.get_today_trades(),
        "daily_stats": db.get_daily_stats(7),
        "active_positions": db.get_active_positions()
    }


@app.get("/api/db/trades")
async def get_db_trades(limit: int = 50, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """DB에서 거래 기록 조회"""
    if not db.is_connected():
        return {"trades": db.get_trades(limit, start_date, end_date), "error": "DB 연결 안됨"}
    
    return {
        "trades": db.get_trades(limit, start_date, end_date),
        "total_profit": db.get_total_profit()
    }


@app.get("/api/stats/summary")
async def get_stats_summary(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """일/주/월별 또는 특정 기간 수익 요약 조회"""
    stats = db.get_period_stats(start_date, end_date)
    return stats


# ========== 서버 실행 ==========

if __name__ == "__main__":
    import uvicorn
    print(f"""
╔═══════════════════════════════════════════╗
║                                           ║
║     🚀 CoinHero 자동거래 시스템 🚀        ║
║                                           ║
║     API Server: http://localhost:{BACKEND_PORT}      ║
║     Docs: http://localhost:{BACKEND_PORT}/docs       ║
║                                           ║
╚═══════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=BACKEND_PORT)

