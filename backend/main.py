"""
CoinHero - 업비트 자동거래 시스템 API 서버
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import json
from datetime import datetime
import logging
import pandas as pd

logger = logging.getLogger(__name__)

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
from user_manager import user_manager

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


class UserSettingsRequest(BaseModel):
    upbit_access_key: Optional[str] = None
    upbit_secret_key: Optional[str] = None
    trade_amount: Optional[int] = 10000
    max_positions: Optional[int] = 3


class UserTradeRequest(BaseModel):
    ticker: str
    amount: Optional[float] = None
    volume: Optional[float] = None


# ========== 인증 Dependency ==========

async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """
    Authorization 헤더에서 사용자 정보 추출
    Bearer 토큰이 없거나 유효하지 않으면 None 반환
    """
    if not authorization:
        return None
    
    if not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "")
    user = user_manager.verify_token(token)
    return user


async def require_auth(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """인증 필수 Dependency"""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    return user


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


# ========== 업비트 API 설정 (로그인 없이) ==========

class UpbitKeyRequest(BaseModel):
    access_key: str
    secret_key: str

@app.post("/api/settings/upbit")
async def set_upbit_keys(request: UpbitKeyRequest):
    """업비트 API 키 설정 및 검증"""
    import pyupbit
    
    access_key = request.access_key.strip()
    secret_key = request.secret_key.strip()
    
    if not access_key or not secret_key:
        return {
            "success": False,
            "message": "API 키를 입력해주세요"
        }
    
    try:
        # 새 클라이언트로 검증
        test_client = pyupbit.Upbit(access_key, secret_key)
        balances = test_client.get_balances()
        
        if balances is None:
            return {
                "success": False,
                "message": "잔고 조회 실패 - API 키를 확인해주세요"
            }
        
        if isinstance(balances, dict) and 'error' in balances:
            error_msg = balances.get('error', {}).get('message', '알 수 없는 오류')
            return {
                "success": False,
                "message": f"API 오류: {error_msg}"
            }
        
        # 성공 - 전역 클라이언트 업데이트
        upbit_client.reinitialize(access_key, secret_key)
        
        # 잔고 계산
        total_krw = 0
        coin_count = 0
        for b in balances:
            currency = b.get('currency', '')
            balance = float(b.get('balance', 0) or 0)
            if currency == 'KRW':
                total_krw = balance
            elif balance > 0:
                coin_count += 1
        
        return {
            "success": True,
            "message": "업비트 계정이 연결되었습니다!",
            "account_info": {
                "krw_balance": total_krw,
                "coin_count": coin_count,
                "api_key_preview": access_key[:8] + "..."
            }
        }
        
    except Exception as e:
        error_str = str(e)
        if "verified IP" in error_str:
            return {
                "success": False,
                "message": "IP 허용 설정이 필요합니다. 업비트 Open API에서 '모든 IP 허용'을 선택해주세요."
            }
        return {
            "success": False,
            "message": f"연결 실패: {error_str}"
        }


@app.get("/api/settings/upbit")
async def get_upbit_status():
    """현재 업비트 연결 상태 확인"""
    from config import UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY
    
    has_keys = bool(UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY)
    api_key_preview = UPBIT_ACCESS_KEY[:8] + "..." if UPBIT_ACCESS_KEY else None
    
    if not has_keys:
        return {
            "connected": False,
            "message": "API 키가 설정되지 않았습니다",
            "api_key_preview": None
        }
    
    try:
        balances = upbit_client.upbit.get_balances()
        
        if balances is None or (isinstance(balances, dict) and 'error' in balances):
            error_msg = ""
            if isinstance(balances, dict):
                error_msg = balances.get('error', {}).get('message', '')
            return {
                "connected": False,
                "message": error_msg or "연결 실패",
                "api_key_preview": api_key_preview
            }
        
        # 잔고 정보 (locked 포함)
        total_krw = 0
        total_eval = 0
        coins = []
        
        # 매수일 정보 조회를 위한 거래 기록
        all_trades = db.get_trades(500)
        memory_trades = trading_engine.get_trade_logs(100)
        ai_trades = ai_scalper.get_trade_logs(100)
        
        # 코인별 최초 매수일 찾기
        coin_buy_dates = {}
        for trade in all_trades + memory_trades + ai_trades:
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
        
        for b in balances:
            currency = b.get('currency', '')
            balance = float(b.get('balance', 0) or 0)
            locked = float(b.get('locked', 0) or 0)
            total_balance = balance + locked  # locked 포함
            avg_buy_price = float(b.get('avg_buy_price', 0) or 0)
            
            if currency == 'KRW':
                total_krw = total_balance
                total_eval += total_balance
            elif total_balance > 0:
                ticker = f"KRW-{currency}"
                current_price = upbit_client.get_current_price(ticker) or avg_buy_price
                eval_amount = total_balance * current_price
                buy_total = total_balance * avg_buy_price  # 매수 총액
                profit_amount = eval_amount - buy_total  # 손익 금액
                profit_rate = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
                
                # 매수일 정보
                buy_datetime = coin_buy_dates.get(currency)
                
                total_eval += eval_amount
                coins.append({
                    "currency": currency,
                    "balance": total_balance,
                    "avg_buy_price": avg_buy_price,
                    "current_price": current_price,
                    "buy_total": round(buy_total, 2),
                    "eval_amount": round(eval_amount, 2),
                    "profit_amount": round(profit_amount, 2),
                    "profit_rate": round(profit_rate, 2),
                    "buy_datetime": buy_datetime
                })
        
        return {
            "connected": True,
            "message": "연결됨",
            "api_key_preview": api_key_preview,
            "account": {
                "krw_balance": total_krw,
                "total_eval": total_eval,
                "coin_count": len(coins),
                "coins": coins
            }
        }
        
    except Exception as e:
        return {
            "connected": False,
            "message": str(e),
            "api_key_preview": api_key_preview
        }


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
        
        # 총 평가금액 = 모든 자산(KRW 포함)의 eval_amount 합산
        total_krw = sum(b.get('eval_amount', 0) for b in balances) if balances else 0
        
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
                        b["buy_datetime"] = buy_date_str  # 전체 타임스탬프 (시간 포함)
                        b["days_held"] = days_held
                    except:
                        b["buy_date"] = None
                        b["buy_datetime"] = None
                        b["days_held"] = None
                else:
                    b["buy_date"] = None
                    b["buy_datetime"] = None
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


@app.post("/api/debate/run/{ticker}")
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


@app.post("/api/debate/scan-and-buy")
async def scan_and_buy(amount: int = 10000, top_n: int = 10):
    """
    AI 3대장이 상위 코인들을 스캔하고 토론 후 매수 추천 종목 자동 매수
    1. 거래량 상위 코인 스캔
    2. 각 코인에 대해 3개 AI 토론
    3. 강력 매수/매수 추천 시 자동 매수
    """
    from upbit_client import upbit_client
    
    # 1. 거래량 상위 코인 가져오기
    tickers = upbit_client.get_all_tickers()[:top_n]
    
    results = {
        "scanned": [],
        "debates": [],
        "bought": [],
        "skipped": []
    }
    
    for ticker in tickers:
        try:
            # 2. AI 토론 실행
            print(f"[DEBATE] {ticker} 토론 시작...")
            debate_result = await ai_debate.run_debate(ticker)
            
            if not debate_result:
                results["skipped"].append({"ticker": ticker, "reason": "토론 실패"})
                continue
            
            debate_dict = ai_debate.to_dict(debate_result)
            results["debates"].append(debate_dict)
            results["scanned"].append(ticker)
            
            # 3. 매수 결정
            if debate_result.consensus in ["buy", "strong_buy"] and debate_result.consensus_confidence >= 70:
                # 자동 매수 실행
                buy_result = upbit_client.buy_market_order(ticker, amount)
                
                if buy_result and "uuid" in buy_result:
                    results["bought"].append({
                        "ticker": ticker,
                        "amount": amount,
                        "verdict": debate_result.final_verdict,
                        "confidence": debate_result.consensus_confidence,
                        "uuid": buy_result["uuid"],
                        "reasons": debate_result.key_reasons[:3]
                    })
                    print(f"[BUY] {ticker} 매수 완료! {debate_result.final_verdict}")
                else:
                    results["skipped"].append({
                        "ticker": ticker, 
                        "reason": "매수 실패",
                        "verdict": debate_result.final_verdict
                    })
            else:
                results["skipped"].append({
                    "ticker": ticker,
                    "reason": f"조건 미충족 ({debate_result.consensus}, {debate_result.consensus_confidence}%)",
                    "verdict": debate_result.final_verdict
                })
                
        except Exception as e:
            print(f"[ERROR] {ticker} 처리 실패: {e}")
            results["skipped"].append({"ticker": ticker, "reason": str(e)})
    
    return {
        "success": True,
        "summary": {
            "total_scanned": len(results["scanned"]),
            "total_bought": len(results["bought"]),
            "total_skipped": len(results["skipped"])
        },
        **results
    }


@app.post("/api/debate/quick-pick")
async def quick_pick_and_buy(amount: int = 10000):
    """
    빠른 AI 토론: 가장 유망한 1개 코인 선정 후 즉시 매수
    """
    from upbit_client import upbit_client
    
    # 거래량 상위 5개만 빠르게 스캔
    tickers = upbit_client.get_all_tickers()[:5]
    
    best_pick = None
    best_confidence = 0
    all_debates = []
    
    for ticker in tickers:
        try:
            debate_result = await ai_debate.run_debate(ticker)
            if not debate_result:
                continue
                
            debate_dict = ai_debate.to_dict(debate_result)
            all_debates.append(debate_dict)
            
            # 매수 추천이면서 신뢰도가 가장 높은 것 선택
            if debate_result.consensus in ["buy", "strong_buy"]:
                if debate_result.consensus_confidence > best_confidence:
                    best_confidence = debate_result.consensus_confidence
                    best_pick = debate_result
                    
        except Exception as e:
            print(f"[ERROR] {ticker}: {e}")
    
    if best_pick and best_confidence >= 65:
        # 최고 추천 종목 매수
        buy_result = upbit_client.buy_market_order(best_pick.ticker, amount)
        
        return {
            "success": True,
            "action": "bought",
            "pick": {
                "ticker": best_pick.ticker,
                "coin": best_pick.coin_name,
                "verdict": best_pick.final_verdict,
                "confidence": best_pick.consensus_confidence,
                "reasons": best_pick.key_reasons,
                "buy_result": buy_result
            },
            "all_debates": all_debates
        }
    else:
        return {
            "success": True,
            "action": "no_buy",
            "message": "매수 조건을 충족하는 코인이 없습니다",
            "all_debates": all_debates
        }


@app.post("/api/ai-max-profit/scan")
async def ai_max_profit_scan(amount: int = 10000, scan_all: bool = True):
    """
    🚀 AI 수익률 최대화 스캔
    
    알고리즘:
    1. 모든 KRW 마켓 코인 스캔 (거래량 순 정렬)
    2. 5가지 기술적 지표 분석:
       - RSI (과매도 < 30)
       - 볼린저 밴드 (하단 터치)
       - MACD (상승 전환)
       - Williams %R (과매도 < -80)
       - 거래량 (20일 평균 대비 급증)
    3. 각 지표별 점수 합산 (100점 만점)
    4. BTC 추세 확인 (하락장 매수 보류)
    5. 60점 이상 코인 자동 매수
    """
    from strategies import ProfitMaximizer
    import pyupbit
    
    results = {
        "algorithm": {
            "name": "🚀 AI 수익률 최대화 전략",
            "description": "5가지 기술적 지표를 종합 분석하여 최적의 매수 타이밍 포착",
            "indicators": [
                {"name": "RSI", "weight": 25, "condition": "일봉 RSI < 25 (극과매도) 또는 60분봉 RSI < 20"},
                {"name": "볼린저 밴드", "weight": 25, "condition": "일봉 BB% < 5 (하단 터치) 또는 60분봉 BB% < 10"},
                {"name": "MACD", "weight": 20, "condition": "히스토그램 양전환 및 상승 추세"},
                {"name": "Williams %R", "weight": 15, "condition": "일봉 %R < -90 (극과매도) 또는 60분봉 %R < -80"},
                {"name": "거래량", "weight": 15, "condition": "20일 평균 대비 1.5배 이상 급증"}
            ],
            "buy_threshold": 60,
            "btc_filter": "BTC가 0.5% 이상 하락 중이면 매수 보류"
        },
        "scan_count": 0,
        "scanned_coins": [],
        "candidates": [],
        "bought": [],
        "btc_status": None,
        "timestamp": datetime.now().isoformat()
    }
    
    def to_python(val):
        """numpy 타입을 Python 기본 타입으로 변환"""
        import numpy as np
        if isinstance(val, (np.integer, np.floating)):
            return float(val)
        elif isinstance(val, np.bool_):
            return bool(val)
        elif isinstance(val, np.ndarray):
            return val.tolist()
        return val
    
    try:
        # 1. BTC 추세 확인
        btc_df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=2)
        if btc_df is not None and len(btc_df) >= 2:
            btc_change = float((btc_df['close'].iloc[-1] - btc_df['close'].iloc[-2]) / btc_df['close'].iloc[-2] * 100)
            btc_price = float(btc_df['close'].iloc[-1])
            results["btc_status"] = {
                "price": btc_price,
                "change_1h": round(btc_change, 2),
                "trend": "상승" if btc_change > 0 else "하락",
                "can_buy": btc_change >= -0.5
            }
            
            if btc_change < -0.5:
                results["message"] = f"⚠️ BTC 하락 중 ({btc_change:.2f}%) - 매수 보류"
                return results
        
        # 2. 모든 KRW 마켓 코인 조회 (거래량 순 정렬)
        all_tickers = upbit_client.get_all_tickers()
        tickers = all_tickers if scan_all else all_tickers[:30]  # scan_all=False면 상위 30개만
        results["scan_count"] = len(tickers)
        results["total_coins"] = len(all_tickers)
        
        # 3. 각 코인 분석
        for ticker in tickers:
            try:
                strategy = ProfitMaximizer(ticker)
                analysis = strategy.analyze()
                
                if "error" in analysis:
                    continue
                
                score, reasons = strategy.calculate_buy_score(analysis)
                current_price = analysis.get("current_price", 0)
                
                coin_result = {
                    "ticker": ticker,
                    "coin_name": ticker.replace("KRW-", ""),
                    "current_price": to_python(current_price),
                    "score": to_python(score),
                    "reasons": reasons,
                    "indicators": {
                        "rsi_day": round(to_python(analysis.get("rsi_day")) or 0, 1),
                        "rsi_min": round(to_python(analysis.get("rsi_min")) or 0, 1),
                        "bb_percent_day": round(to_python(analysis.get("bb_percent_day")) or 0, 1),
                        "bb_percent_min": round(to_python(analysis.get("bb_percent_min")) or 0, 1),
                        "macd_hist": round(to_python(analysis.get("macd_hist_day")) or 0, 4),
                        "williams_r_day": round(to_python(analysis.get("wr_day")) or 0, 1),
                        "volume_ratio": round(to_python(analysis.get("volume_ratio")) or 0, 2)
                    }
                }
                
                results["scanned_coins"].append(coin_result)
                
                # 매수 조건 충족 (60점 이상)
                if score >= 60:
                    results["candidates"].append(coin_result)
                    
            except Exception as e:
                print(f"[SCAN] {ticker} 분석 실패: {e}")
                continue
        
        # 4. 점수 순 정렬
        results["scanned_coins"].sort(key=lambda x: x["score"], reverse=True)
        results["candidates"].sort(key=lambda x: x["score"], reverse=True)
        
        # 5. 상위 후보 매수 실행
        for candidate in results["candidates"][:3]:  # 최대 3개까지 매수
            try:
                buy_result = upbit_client.buy_market_order(candidate["ticker"], amount)
                
                if buy_result and not isinstance(buy_result, dict):
                    buy_result = {"uuid": str(buy_result)}
                elif buy_result is None:
                    buy_result = {"error": "매수 실패"}
                
                results["bought"].append({
                    **candidate,
                    "amount": amount,
                    "buy_result": buy_result
                })
                
                # 거래 로그 저장
                # 상세 AI 판단 이유 생성
                detailed_reasons = []
                for reason in candidate["reasons"]:
                    detailed_reasons.append(reason)
                
                # 지표 정보 추가
                indicators = candidate.get("indicators", {})
                indicator_info = []
                if indicators.get("rsi_day"):
                    indicator_info.append(f"RSI(일): {indicators['rsi_day']}")
                if indicators.get("bb_percent_day"):
                    indicator_info.append(f"BB%: {indicators['bb_percent_day']}")
                if indicators.get("williams_r_day"):
                    indicator_info.append(f"WR: {indicators['williams_r_day']}")
                if indicators.get("volume_ratio"):
                    indicator_info.append(f"거래량비: {indicators['volume_ratio']}")
                
                ai_reason = f"매수점수 {candidate['score']}/100 | " + " | ".join(detailed_reasons[:3])
                if indicator_info:
                    ai_reason += " | [지표] " + ", ".join(indicator_info[:4])
                
                db.save_trade({
                    "ticker": candidate["ticker"],
                    "coin_name": candidate["coin_name"],
                    "action": "buy",
                    "price": candidate["current_price"],
                    "amount": amount,
                    "strategy": "수익률 최대화",
                    "reason": ai_reason,
                    "ai_reason": ai_reason,
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                print(f"[BUY] {candidate['ticker']} 매수 실패: {e}")
        
        if results["bought"]:
            results["message"] = f"✅ {len(results['bought'])}개 코인 매수 완료!"
        elif results["candidates"]:
            results["message"] = f"🔍 {len(results['candidates'])}개 매수 후보 발견 (매수 실패)"
        else:
            results["message"] = "📊 현재 매수 조건을 충족하는 코인이 없습니다. 최적의 타이밍을 기다리는 중..."
        
        return results
        
    except Exception as e:
        results["error"] = str(e)
        results["message"] = f"❌ 스캔 오류: {e}"
        return results


@app.post("/api/ai-max-profit/sell-scan")
async def ai_max_profit_sell_scan():
    """
    🎯 AI 3대장 수익률 최대화 매도 스캔
    
    알고리즘:
    1. 보유 중인 모든 코인 조회
    2. 각 코인에 대해 AI 3대장(GPT, Gemini, Claude) 토론
    3. 매도 추천 합의 도출
    4. 강력 매도 추천 시 자동 매도 실행
    """
    from strategies import ProfitMaximizer
    import pyupbit
    
    results = {
        "algorithm": {
            "name": "🎯 AI 3대장 수익률 최대화 매도",
            "description": "GPT 5.2, Gemini 3, Claude Opus 4.5가 토론하여 최적의 매도 타이밍 결정",
            "experts": [
                {"name": "GPT 5.2", "role": "수석 리스크 총괄", "focus": "거시경제, 리스크 분석"},
                {"name": "Gemini 3", "role": "혁신·트렌드 전략가", "focus": "기술 트렌드, 생태계 분석"},
                {"name": "Claude Opus 4.5", "role": "균형 분석가", "focus": "기술적 지표, 거래량 분석"}
            ],
            "sell_conditions": [
                "AI 3대장 과반수 이상 매도 추천",
                "신뢰도 70% 이상",
                "RSI 70 이상 과매수 상태",
                "목표 수익률 도달 (10% 이상)",
                "손절 라인 도달 (-3% 이하)"
            ]
        },
        "holdings": [],
        "analyzed": [],
        "sold": [],
        "kept": [],
        "timestamp": datetime.now().isoformat()
    }
    
    def to_python(val):
        """numpy 타입을 Python 기본 타입으로 변환"""
        import numpy as np
        if isinstance(val, (np.integer, np.floating)):
            return float(val)
        elif isinstance(val, np.bool_):
            return bool(val)
        elif isinstance(val, np.ndarray):
            return val.tolist()
        return val
    
    try:
        # 1. 보유 중인 코인 조회 (이미 현재가 포함됨)
        balances = upbit_client.get_balances()
        holdings = []
        
        print(f"[SELL-SCAN] 잔고 조회 완료: {len(balances)}개 항목")
        
        for balance in balances:
            currency = balance.get("currency", "")
            if currency == "KRW":
                continue
                
            amount = float(balance.get("balance", 0))
            avg_buy_price = float(balance.get("avg_buy_price", 0))
            
            if amount <= 0 or avg_buy_price <= 0:
                continue
            
            ticker = f"KRW-{currency}"
            # get_balances()에서 이미 현재가를 가져왔으므로 활용
            current_price = balance.get("current_price", avg_buy_price)
            
            if not current_price or current_price <= 0:
                current_price = avg_buy_price
            
            profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
            value = current_price * amount
            
            holdings.append({
                "ticker": ticker,
                "currency": currency,
                "amount": amount,
                "avg_buy_price": avg_buy_price,
                "current_price": to_python(current_price),
                "profit_rate": round(to_python(profit_rate), 2),
                "value": round(to_python(value), 0)
            })
        
        results["holdings"] = holdings
        
        if not holdings:
            results["message"] = "보유 중인 코인이 없습니다."
            return results
        
        # 2. 각 코인에 대해 AI 토론 및 분석
        for holding in holdings:
            ticker = holding["ticker"]
            
            try:
                # 기술적 분석
                strategy = ProfitMaximizer(ticker)
                analysis = strategy.analyze()
                
                # AI 토론 실행
                debate_result = await ai_debate.run_debate(ticker)
                
                coin_analysis = {
                    **holding,
                    "technical": {
                        "rsi": round(to_python(analysis.get("rsi_day") or 50), 1),
                        "bb_percent": round(to_python(analysis.get("bb_percent_day") or 50), 1),
                        "williams_r": round(to_python(analysis.get("wr_day") or -50), 1),
                        "volume_ratio": round(to_python(analysis.get("volume_ratio") or 1), 2)
                    },
                    "ai_debate": None,
                    "sell_recommendation": False,
                    "sell_reasons": []
                }
                
                if debate_result:
                    debate_dict = ai_debate.to_dict(debate_result)
                    coin_analysis["ai_debate"] = {
                        "consensus": debate_result.final_verdict,
                        "confidence": debate_result.consensus_confidence,
                        "key_reasons": debate_result.key_reasons,
                        "experts": [
                            {
                                "name": msg.expert_name,
                                "opinion": msg.opinion,
                                "confidence": msg.confidence,
                                "content": msg.content
                            }
                            for msg in debate_result.messages
                        ]
                    }
                    
                    # 매도 조건 확인
                    sell_reasons = []
                    
                    # AI 매도 추천
                    if debate_result.final_verdict in ["sell", "strong_sell"]:
                        sell_reasons.append(f"AI 3대장 매도 추천 (신뢰도 {debate_result.consensus_confidence}%)")
                    
                    # RSI 과매수
                    rsi = coin_analysis["technical"]["rsi"]
                    if rsi > 70:
                        sell_reasons.append(f"RSI 과매수 ({rsi})")
                    
                    # 목표 수익률 달성
                    profit_rate = holding["profit_rate"]
                    if profit_rate >= 10:
                        sell_reasons.append(f"목표 수익률 달성 ({profit_rate}%)")
                    
                    # 손절 라인
                    if profit_rate <= -3:
                        sell_reasons.append(f"손절 라인 도달 ({profit_rate}%)")
                    
                    # 볼린저 밴드 상단
                    bb_percent = coin_analysis["technical"]["bb_percent"]
                    if bb_percent > 90:
                        sell_reasons.append(f"볼린저 밴드 상단 돌파 ({bb_percent}%)")
                    
                    coin_analysis["sell_reasons"] = sell_reasons
                    
                    # 매도 결정: AI 매도 추천 + 1개 이상 추가 조건 또는 강력 매도
                    should_sell = (
                        debate_result.final_verdict == "strong_sell" or
                        (debate_result.final_verdict == "sell" and debate_result.consensus_confidence >= 70) or
                        len(sell_reasons) >= 2
                    )
                    
                    coin_analysis["sell_recommendation"] = should_sell
                
                results["analyzed"].append(coin_analysis)
                
                # 3. 매도 실행
                if coin_analysis["sell_recommendation"]:
                    try:
                        sell_result = upbit_client.sell_market_order(ticker, holding["amount"])
                        
                        results["sold"].append({
                            **coin_analysis,
                            "sell_result": sell_result,
                            "sold_at": datetime.now().isoformat()
                        })
                        
                        # AI 판단 이유 상세 생성
                        ai_debate = coin_analysis.get("ai_debate", {})
                        experts_info = []
                        if ai_debate:
                            for expert in ai_debate.get("experts", []):
                                experts_info.append(f"[{expert['name']}] {expert['opinion'].upper()} ({expert['confidence']}%)")
                        
                        detailed_sell_reason = f"수익률 {holding['profit_rate']:.1f}% | " + " | ".join(coin_analysis["sell_reasons"][:3])
                        if experts_info:
                            detailed_sell_reason += " | AI판단: " + " / ".join(experts_info[:3])
                        
                        # 거래 로그 저장
                        db.save_trade({
                            "ticker": ticker,
                            "coin_name": holding["currency"],
                            "action": "sell",
                            "price": holding["current_price"],
                            "amount": holding["value"],
                            "profit_rate": holding["profit_rate"],
                            "strategy": "AI 3대장 수익률 최대화 매도",
                            "reason": detailed_sell_reason,
                            "ai_reason": detailed_sell_reason,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                    except Exception as e:
                        print(f"[SELL] {ticker} 매도 실패: {e}")
                else:
                    results["kept"].append(coin_analysis)
                    
            except Exception as e:
                print(f"[ANALYZE] {ticker} 분석 실패: {e}")
                results["analyzed"].append({
                    **holding,
                    "error": str(e)
                })
        
        # 결과 메시지
        if results["sold"]:
            total_sold_value = sum(s["value"] for s in results["sold"])
            results["message"] = f"✅ {len(results['sold'])}개 코인 매도 완료! (총 ₩{total_sold_value:,.0f})"
        elif results["analyzed"]:
            sell_candidates = [a for a in results["analyzed"] if a.get("sell_recommendation")]
            if sell_candidates:
                results["message"] = f"🔍 {len(sell_candidates)}개 코인 매도 추천 발견"
            else:
                results["message"] = "📊 AI 분석 완료 - 현재 매도 추천 종목 없음. 계속 보유 추천!"
        else:
            results["message"] = "분석할 보유 종목이 없습니다."
        
        return results
        
    except Exception as e:
        results["error"] = str(e)
        results["message"] = f"❌ 스캔 오류: {e}"
        return results


@app.post("/api/ai-max-profit/quick-analysis")
async def ai_quick_analysis(
    type: str = "buy",
    limit: int = 5
):
    """
    🧠 AI 빠른 분석 - 30초마다 AI가 시장을 분석하고 생각을 공유
    type: "buy" (전체 코인 대상) 또는 "sell" (보유 코인 대상)
    """
    import pyupbit
    from strategies import ProfitMaximizer
    import random
    
    result = {
        "type": type,
        "timestamp": datetime.now().isoformat(),
        "analysis": None
    }
    
    def to_python(val):
        import numpy as np
        if isinstance(val, (np.integer, np.floating)):
            return float(val)
        elif isinstance(val, np.bool_):
            return bool(val)
        elif isinstance(val, np.ndarray):
            return val.tolist()
        return val
    
    try:
        if type == "buy":
            # 🔥 업비트 상장 전체 코인 대상 매수 분석
            all_tickers = pyupbit.get_tickers(fiat="KRW")
            total_coins = len(all_tickers)
            
            # 빠른 분석을 위해 일괄 현재가 조회
            try:
                all_prices = pyupbit.get_current_price(all_tickers)
            except:
                all_prices = {}
            
            analysis_results = []
            thoughts = []
            scan_count = 0
            
            # 전체 코인 빠른 스캔 (RSI, 거래량 변동 위주)
            for ticker in all_tickers:
                try:
                    scan_count += 1
                    coin_name = ticker.replace("KRW-", "")
                    
                    # 일봉 데이터로 RSI 계산 (최소한의 API 호출)
                    df = pyupbit.get_ohlcv(ticker, interval="day", count=15)
                    if df is None or len(df) < 14:
                        continue
                    
                    # RSI 계산
                    delta = df['close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    current_rsi = to_python(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
                    
                    # 거래량 변동 계산
                    vol_avg = df['volume'].iloc[:-1].mean()
                    vol_today = df['volume'].iloc[-1]
                    volume_ratio = to_python(vol_today / vol_avg) if vol_avg > 0 else 1
                    
                    # 볼린저밴드 % 계산
                    sma20 = df['close'].rolling(window=20).mean()
                    std20 = df['close'].rolling(window=20).std()
                    upper = sma20 + (std20 * 2)
                    lower = sma20 - (std20 * 2)
                    current_price = df['close'].iloc[-1]
                    bb_range = upper.iloc[-1] - lower.iloc[-1]
                    bb_percent = to_python(((current_price - lower.iloc[-1]) / bb_range * 100) if bb_range > 0 else 50)
                    
                    # 매수 시그널 감지
                    signal_found = False
                    
                    if current_rsi < 30:
                        thoughts.append(f"💡 {coin_name}: RSI {current_rsi:.0f} 과매도! 반등 가능성")
                        signal_found = True
                    
                    if volume_ratio > 3:
                        thoughts.append(f"📈 {coin_name}: 거래량 {volume_ratio:.1f}배 폭증!")
                        signal_found = True
                    
                    if bb_percent < 15:
                        thoughts.append(f"🎯 {coin_name}: BB 하단({bb_percent:.0f}%) 매수 기회")
                        signal_found = True
                    
                    if signal_found or current_rsi < 40 or bb_percent < 30:
                        analysis_results.append({
                            "ticker": ticker,
                            "coin": coin_name,
                            "rsi": round(current_rsi, 1),
                            "bb_percent": round(bb_percent, 1),
                            "volume_ratio": round(volume_ratio, 2),
                            "signal": 1 if signal_found else 0
                        })
                    
                except Exception as e:
                    pass  # 개별 코인 오류는 무시하고 계속
            
            # 결과 정렬 (RSI 낮은 순)
            analysis_results.sort(key=lambda x: x['rsi'])
            
            # 요약 생성
            buy_candidates = [a for a in analysis_results if a['rsi'] < 35 or a['bb_percent'] < 25]
            
            if buy_candidates:
                summary = f"🔥 {len(buy_candidates)}개 매수 기회! " + ", ".join([c['coin'] for c in buy_candidates[:3]])
            else:
                summary = f"📊 {total_coins}개 코인 스캔 완료 - 강력 시그널 없음"
            
            if not thoughts:
                thoughts = [
                    f"🔍 {total_coins}개 전체 코인 분석 완료",
                    "📊 현재 시장 안정적, 특이 시그널 없음",
                    "⏳ 30초 후 재분석 예정..."
                ]
            
            # 스캔 통계 추가
            thoughts.insert(0, f"📊 {total_coins}개 코인 스캔 | {len(analysis_results)}개 관심")
            
            result["analysis"] = {
                "summary": summary,
                "top_coins": analysis_results[:limit],
                "signals": thoughts[:5],
                "total_scanned": total_coins,
                "candidates": len(analysis_results)
            }
            
        else:
            # 보유 코인 대상 매도 분석
            balances = upbit_client.get_balances()
            holdings = []
            thoughts = []
            
            for balance in balances:
                currency = balance.get("currency", "")
                if currency == "KRW":
                    continue
                    
                amount = float(balance.get("balance", 0)) + float(balance.get("locked", 0))
                avg_buy_price = float(balance.get("avg_buy_price", 0))
                
                if amount <= 0 or avg_buy_price <= 0:
                    continue
                
                ticker = f"KRW-{currency}"
                
                try:
                    current_price = pyupbit.get_current_price(ticker)
                    if not current_price:
                        continue
                    
                    profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
                    
                    strategy = ProfitMaximizer(ticker)
                    analysis = strategy.analyze()
                    
                    rsi = to_python(analysis.get("rsi_day") or 50)
                    
                    # AI 생각 생성
                    if profit_rate >= 10:
                        thoughts.append(f"💰 {currency}: +{profit_rate:.1f}% 수익 중! 익절 고려")
                    elif profit_rate <= -5:
                        thoughts.append(f"🚨 {currency}: {profit_rate:.1f}% 손실. 손절 검토 필요")
                    elif rsi > 70:
                        thoughts.append(f"⚠️ {currency}: RSI {rsi:.0f} 과매수, 매도 타이밍 주시")
                    else:
                        thoughts.append(f"📊 {currency}: {profit_rate:+.1f}% | 보유 유지 추천")
                    
                    holdings.append({
                        "ticker": ticker,
                        "coin": currency,
                        "profit_rate": round(to_python(profit_rate), 2),
                        "rsi": round(rsi, 1),
                        "amount": to_python(amount),
                        "value": round(current_price * amount, 0)
                    })
                    
                except Exception as e:
                    print(f"[QUICK-ANALYSIS] {ticker} 분석 오류: {e}")
            
            # 요약 생성
            sell_candidates = [h for h in holdings if h['profit_rate'] >= 10 or h['profit_rate'] <= -5 or h['rsi'] > 70]
            
            if not holdings:
                summary = "📭 보유 중인 코인이 없습니다"
                thoughts = ["💡 매수 분석을 통해 투자 기회를 찾아보세요!"]
            elif sell_candidates:
                summary = f"🎯 {len(sell_candidates)}개 매도 검토 대상 발견!"
            else:
                total_profit = sum(h['profit_rate'] for h in holdings) / len(holdings) if holdings else 0
                summary = f"📊 {len(holdings)}개 보유 중 | 평균 수익률: {total_profit:+.1f}%"
            
            if not thoughts:
                thoughts = ["🔍 모든 보유 코인 안정적, 특이 시그널 없음"]
            
            result["analysis"] = {
                "summary": summary,
                "holdings": holdings[:limit],
                "signals": thoughts[:5]
            }
            
    except Exception as e:
        result["error"] = str(e)
        result["analysis"] = {
            "summary": f"⚠️ 분석 오류: {e}",
            "signals": ["다음 분석에서 재시도합니다..."]
        }
    
    return result


@app.post("/api/ai-max-profit/ai-sell")
async def ai_max_profit_ai_sell(
    min_confidence: int = 60,
    auto_execute: bool = True
):
    """
    🤖 AI 자율 매도 알고리즘
    
    AI 3대장(GPT 5.2, Gemini 3, Claude Opus 4.5)이 보유 종목을 실시간 분석하여
    최적의 매도 타이밍을 결정하고 자동으로 실행합니다.
    
    매도 전략:
    1. 익절 전략: 목표 수익률 도달 시 단계적 익절
    2. 손절 전략: 동적 손절라인 적용
    3. 트레일링 스탑: 고점 대비 하락 시 매도
    4. 시장 상황 분석: 전체 시장 하락 시 리스크 관리
    5. AI 토론: 3대장 합의 기반 매도 결정
    """
    import pyupbit
    import numpy as np
    import requests
    from config import OPENROUTER_API_KEY
    
    def to_python(val):
        if isinstance(val, (np.integer, np.floating)):
            return float(val)
        elif isinstance(val, np.bool_):
            return bool(val)
        elif isinstance(val, np.ndarray):
            return val.tolist()
        return val
    
    results = {
        "algorithm": {
            "name": "🤖 AI 자율 매도 알고리즘",
            "description": "AI 3대장이 보유 종목을 실시간 분석하여 최적의 매도 타이밍을 결정",
            "experts": [
                {"name": "GPT 5.2", "role": "리스크 매니저", "focus": "손절/익절 타이밍, 리스크 관리"},
                {"name": "Gemini 3", "role": "트렌드 분석가", "focus": "시장 트렌드, 모멘텀 분석"},
                {"name": "Claude Opus 4.5", "role": "기술적 분석가", "focus": "차트 패턴, 지표 분석"}
            ],
            "strategies": [
                {"name": "익절 전략", "description": "목표 수익률 달성 시 50% 익절, 추가 상승 시 잔여분 익절"},
                {"name": "손절 전략", "description": "매수가 대비 -5% 또는 최고점 대비 -8% 중 먼저 도달 시"},
                {"name": "트레일링 스탑", "description": "최고점 대비 하락률 추적, 동적 손절라인 적용"},
                {"name": "AI 합의 매도", "description": "AI 3대장 중 2명 이상 매도 추천 시 실행"}
            ]
        },
        "market_status": None,
        "holdings": [],
        "ai_analysis": [],
        "sell_decisions": [],
        "sold": [],
        "kept": [],
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # 1. 시장 전체 상황 분석
        btc_df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=24)
        market_sentiment = "neutral"
        btc_change_24h = 0
        
        if btc_df is not None and len(btc_df) >= 2:
            btc_change_24h = to_python((btc_df['close'].iloc[-1] - btc_df['close'].iloc[0]) / btc_df['close'].iloc[0] * 100)
            if btc_change_24h < -3:
                market_sentiment = "bearish"
            elif btc_change_24h > 3:
                market_sentiment = "bullish"
        
        results["market_status"] = {
            "btc_change_24h": round(btc_change_24h, 2),
            "sentiment": market_sentiment,
            "risk_level": "high" if btc_change_24h < -5 else ("low" if btc_change_24h > 2 else "medium")
        }
        
        # 2. 보유 종목 조회
        balances = upbit_client.get_balances()
        holdings = []
        
        for balance in balances:
            currency = balance.get("currency", "")
            if currency == "KRW":
                continue
            
            amount = float(balance.get("balance", 0))
            avg_buy_price = float(balance.get("avg_buy_price", 0))
            
            if amount <= 0 or avg_buy_price <= 0:
                continue
            
            ticker = f"KRW-{currency}"
            current_price = balance.get("current_price", avg_buy_price)
            
            if not current_price or current_price <= 0:
                current_price = pyupbit.get_current_price(ticker) or avg_buy_price
            
            profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
            value = current_price * amount
            
            # 최고점 대비 하락률 계산 (24시간 기준)
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=24)
            highest_24h = current_price
            if df is not None and len(df) > 0:
                highest_24h = to_python(df['high'].max())
            
            drop_from_high = ((current_price - highest_24h) / highest_24h) * 100 if highest_24h > 0 else 0
            
            holdings.append({
                "ticker": ticker,
                "currency": currency,
                "amount": to_python(amount),
                "avg_buy_price": to_python(avg_buy_price),
                "current_price": to_python(current_price),
                "profit_rate": round(to_python(profit_rate), 2),
                "value": round(to_python(value), 0),
                "highest_24h": to_python(highest_24h),
                "drop_from_high": round(to_python(drop_from_high), 2)
            })
        
        results["holdings"] = holdings
        
        if not holdings:
            results["message"] = "보유 중인 코인이 없습니다."
            return results
        
        # 3. AI 3대장에게 매도 분석 요청
        ai_models = [
            {"name": "GPT 5.2", "model": "openai/gpt-4o", "role": "리스크 매니저"},
            {"name": "Gemini 3", "model": "google/gemini-2.0-flash-001", "role": "트렌드 분석가"},
            {"name": "Claude Opus 4.5", "model": "anthropic/claude-sonnet-4", "role": "기술적 분석가"}
        ]
        
        holdings_summary = "\n".join([
            f"- {h['currency']}: 수익률 {h['profit_rate']:+.1f}%, 현재가 {h['current_price']:,.0f}원, "
            f"평가금액 {h['value']:,.0f}원, 고점대비 {h['drop_from_high']:.1f}%"
            for h in holdings
        ])
        
        sell_prompt = f"""당신은 암호화폐 매도 전문가입니다.

## 시장 상황
- BTC 24시간 변화: {btc_change_24h:+.1f}%
- 시장 심리: {market_sentiment}

## 보유 종목 현황
{holdings_summary}

## 당신의 역할
매도 타이밍을 분석해주세요. 다음 조건을 고려하세요:
1. 익절 타이밍: 수익률 10% 이상이면 일부 익절 고려
2. 손절 타이밍: 손실률 -5% 이하면 손절 고려
3. 트레일링 스탑: 고점 대비 -8% 이상 하락 시 매도 고려
4. 시장 상황: BTC 급락 시 리스크 관리
5. 추세 분석: 하락 추세 전환 시 매도

## 응답 형식 (반드시 JSON)
{{
  "analysis": {{
    "market_view": "현재 시장에 대한 간단한 의견",
    "sell_recommendations": [
      {{
        "ticker": "KRW-코인명",
        "action": "sell" 또는 "hold" 또는 "partial_sell",
        "confidence": 0-100,
        "reason": "매도/보유 이유 (구체적으로)",
        "sell_ratio": 0-100 (매도 비율, hold면 0)
      }}
    ]
  }}
}}"""
        
        ai_responses = []
        
        for ai in ai_models:
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": ai["model"],
                        "messages": [{"role": "user", "content": sell_prompt}],
                        "temperature": 0.3,
                        "max_tokens": 2000
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    content = response.json()["choices"][0]["message"]["content"]
                    
                    # JSON 파싱
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        import json
                        analysis = json.loads(json_match.group())
                        ai_responses.append({
                            "expert": ai["name"],
                            "role": ai["role"],
                            "analysis": analysis.get("analysis", {})
                        })
                        print(f"[AI-SELL] {ai['name']} 분석 완료")
                else:
                    print(f"[AI-SELL] {ai['name']} API 오류: {response.status_code}")
            except Exception as e:
                print(f"[AI-SELL] {ai['name']} 오류: {e}")
        
        results["ai_analysis"] = ai_responses
        
        # 4. AI 합의 도출 및 매도 결정
        ticker_votes = {}
        
        for ai_resp in ai_responses:
            recommendations = ai_resp.get("analysis", {}).get("sell_recommendations", [])
            for rec in recommendations:
                ticker = rec.get("ticker", "")
                if not ticker:
                    continue
                
                if ticker not in ticker_votes:
                    ticker_votes[ticker] = {
                        "sell_votes": 0,
                        "total_confidence": 0,
                        "reasons": [],
                        "sell_ratios": [],
                        "ai_opinions": []
                    }
                
                action = rec.get("action", "hold")
                confidence = rec.get("confidence", 0)
                reason = rec.get("reason", "")
                sell_ratio = rec.get("sell_ratio", 0)
                
                ticker_votes[ticker]["ai_opinions"].append({
                    "expert": ai_resp["expert"],
                    "action": action,
                    "confidence": confidence,
                    "reason": reason
                })
                
                if action in ["sell", "partial_sell"]:
                    ticker_votes[ticker]["sell_votes"] += 1
                    ticker_votes[ticker]["total_confidence"] += confidence
                    ticker_votes[ticker]["reasons"].append(f"[{ai_resp['expert']}] {reason}")
                    ticker_votes[ticker]["sell_ratios"].append(sell_ratio)
        
        # 5. 매도 결정 및 실행
        for holding in holdings:
            ticker = holding["ticker"]
            votes = ticker_votes.get(ticker, {"sell_votes": 0, "reasons": [], "ai_opinions": []})
            
            sell_decision = {
                **holding,
                "ai_votes": votes["sell_votes"],
                "avg_confidence": votes["total_confidence"] / max(votes["sell_votes"], 1),
                "ai_reasons": votes["reasons"],
                "ai_opinions": votes["ai_opinions"],
                "decision": "hold",
                "sell_ratio": 0
            }
            
            # 매도 조건 체크
            should_sell = False
            sell_reason = []
            
            # 조건 1: AI 2명 이상 매도 추천
            if votes["sell_votes"] >= 2:
                should_sell = True
                sell_reason.append(f"AI {votes['sell_votes']}/3 매도 합의")
            
            # 조건 2: 손절 라인 (-5%)
            if holding["profit_rate"] <= -5:
                should_sell = True
                sell_reason.append(f"손절라인 도달 ({holding['profit_rate']:.1f}%)")
            
            # 조건 3: 트레일링 스탑 (고점 대비 -8%)
            if holding["drop_from_high"] <= -8:
                should_sell = True
                sell_reason.append(f"트레일링 스탑 (고점 대비 {holding['drop_from_high']:.1f}%)")
            
            # 조건 4: 시장 급락 + 손실 중
            if market_sentiment == "bearish" and holding["profit_rate"] < 0:
                should_sell = True
                sell_reason.append(f"시장 하락 + 손실 중 (BTC {btc_change_24h:.1f}%)")
            
            # 조건 5: 큰 수익 익절 (20% 이상)
            if holding["profit_rate"] >= 20:
                should_sell = True
                sell_reason.append(f"익절 타이밍 (수익률 {holding['profit_rate']:.1f}%)")
            
            if should_sell:
                sell_decision["decision"] = "sell"
                sell_decision["sell_ratio"] = 100  # 전량 매도
                sell_decision["final_reason"] = " | ".join(sell_reason)
                
                # AI 판단 이유 상세 생성
                ai_judgment_detail = []
                for opinion in votes["ai_opinions"]:
                    ai_judgment_detail.append(
                        f"[{opinion['expert']}] {opinion['action'].upper()} ({opinion['confidence']}%): {opinion['reason']}"
                    )
                sell_decision["ai_judgment_detail"] = ai_judgment_detail
            
            results["sell_decisions"].append(sell_decision)
            
            # 6. 자동 매도 실행
            if should_sell and auto_execute:
                try:
                    sell_result = upbit_client.sell_market_order(ticker, holding["amount"])
                    
                    if sell_result and not sell_result.get("error"):
                        results["sold"].append({
                            **sell_decision,
                            "order_uuid": sell_result.get("uuid"),
                            "executed_at": datetime.now().isoformat()
                        })
                        
                        # AI 판단 이유 상세
                        detailed_reason = f"{sell_decision['final_reason']}"
                        if ai_judgment_detail:
                            detailed_reason += " | " + " | ".join(ai_judgment_detail[:2])
                        
                        # 거래 로그 저장
                        db.save_trade({
                            "ticker": ticker,
                            "coin_name": holding["currency"],
                            "action": "sell",
                            "price": holding["current_price"],
                            "amount": holding["value"],
                            "profit_rate": holding["profit_rate"],
                            "strategy": "AI 자율 매도",
                            "reason": detailed_reason,
                            "ai_reason": detailed_reason,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        print(f"[AI-SELL] {ticker} 매도 완료! (수익률: {holding['profit_rate']:.1f}%)")
                    else:
                        print(f"[AI-SELL] {ticker} 매도 실패: {sell_result.get('error')}")
                except Exception as e:
                    print(f"[AI-SELL] {ticker} 매도 중 오류: {e}")
            elif not should_sell:
                results["kept"].append(sell_decision)
        
        # 결과 메시지
        if results["sold"]:
            total_value = sum(s["value"] for s in results["sold"])
            total_profit = sum(s["value"] * s["profit_rate"] / 100 for s in results["sold"])
            results["message"] = f"🎯 {len(results['sold'])}개 코인 매도 완료! (총 ₩{total_value:,.0f}, 손익 ₩{total_profit:,.0f})"
        elif any(d["decision"] == "sell" for d in results["sell_decisions"]):
            sell_count = sum(1 for d in results["sell_decisions"] if d["decision"] == "sell")
            results["message"] = f"⚠️ {sell_count}개 코인 매도 추천 (자동 실행 OFF)"
        else:
            results["message"] = "✅ AI 분석 완료 - 현재 모든 종목 보유 유지 추천"
        
        return results
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        results["error"] = str(e)
        results["message"] = f"❌ AI 매도 분석 오류: {e}"
        return results


@app.post("/api/ai-max-profit/ai-scan")
async def ai_max_profit_ai_scan(
    amount: int = 10000, 
    top_n: int = 200,
    no_trade_limit: bool = False,
    no_signal_limit: bool = False,
    no_budget_limit: bool = False,
    min_confidence: int = 70
):
    """
    🧠 AI 자율 전략 스캔 - AI가 직접 매매 전략을 설계하고 최적의 종목을 선정
    
    전 종목 대상으로 AI 3대장(GPT 5.2, Gemini 3, Claude Opus 4.5)이 
    실시간 데이터를 분석하여 자체적으로 매매 전략을 수립하고 
    최고의 매수 기회를 포착하여 자동 매수합니다.
    
    무제한 옵션:
    - no_trade_limit: True면 보유현금 전액 투자
    - no_signal_limit: True면 모든 신호 수용 (min_confidence 무시)
    - no_budget_limit: True면 현금보유 한도 무시, 기회 있으면 무조건 매수
    """
    import pyupbit
    import numpy as np
    import requests
    from config import OPENROUTER_API_KEY
    
    def to_python(val):
        if isinstance(val, (np.integer, np.floating)):
            return float(val)
        elif isinstance(val, np.bool_):
            return bool(val)
        elif isinstance(val, np.ndarray):
            return val.tolist()
        return val
    
    # 무제한 옵션 처리
    actual_min_confidence = 0 if no_signal_limit else min_confidence
    
    results = {
        "algorithm": {
            "name": "🧠 AI 자율 전략 스캔",
            "description": "AI 3대장이 실시간 시장 데이터를 분석하여 자체적으로 매매 전략을 설계하고 최적의 매수 타이밍을 포착합니다.",
            "mode": "AI_AUTONOMOUS",
            "experts": [
                {"name": "GPT 5.2", "role": "거시경제 & 리스크 분석", "focus": "시장 심리, 글로벌 동향, 위험 요소"},
                {"name": "Gemini 3", "role": "기술 트렌드 분석", "focus": "신기술, 생태계 발전, 성장 잠재력"},
                {"name": "Claude Opus 4.5", "role": "기술적 분석 전문가", "focus": "차트 패턴, 지표 분석, 매수 타이밍"}
            ],
            "process": [
                "1️⃣ 전 종목 실시간 데이터 수집 (가격, 거래량, 기술적 지표)",
                "2️⃣ AI 3대장이 각자의 관점에서 시장 분석",
                "3️⃣ AI가 자체적으로 매매 전략 수립 및 종목 선정",
                "4️⃣ 3명 중 2명 이상 동의 시 자동 매수 실행"
            ]
        },
        "scan_count": 0,
        "market_overview": None,
        "ai_analysis": [],
        "top_picks": [],
        "bought": [],
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # 1. 시장 전체 개요 수집
        btc_df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=24)
        eth_df = pyupbit.get_ohlcv("KRW-ETH", interval="minute60", count=24)
        
        if btc_df is not None and len(btc_df) >= 2:
            btc_change_1h = to_python((btc_df['close'].iloc[-1] - btc_df['close'].iloc[-2]) / btc_df['close'].iloc[-2] * 100)
            btc_change_24h = to_python((btc_df['close'].iloc[-1] - btc_df['close'].iloc[0]) / btc_df['close'].iloc[0] * 100)
            results["market_overview"] = {
                "btc_price": to_python(btc_df['close'].iloc[-1]),
                "btc_change_1h": round(btc_change_1h, 2),
                "btc_change_24h": round(btc_change_24h, 2),
                "btc_trend": "상승" if btc_change_1h > 0 else "하락",
                "market_sentiment": "긍정적" if btc_change_24h > 0 else "부정적"
            }
        
        # 2. 거래량 상위 코인 데이터 수집
        all_tickers = upbit_client.get_all_tickers()[:top_n]
        results["scan_count"] = len(all_tickers)
        
        coin_data_list = []
        for ticker in all_tickers[:30]:  # 거래량 상위 30개 상세 분석
            try:
                df_day = pyupbit.get_ohlcv(ticker, interval="day", count=14)
                df_hour = pyupbit.get_ohlcv(ticker, interval="minute60", count=24)
                
                if df_day is None or df_hour is None or len(df_day) < 7:
                    continue
                
                current_price = to_python(df_hour['close'].iloc[-1])
                
                # 기본 지표 계산
                change_24h = to_python((df_hour['close'].iloc[-1] - df_hour['close'].iloc[0]) / df_hour['close'].iloc[0] * 100)
                change_7d = to_python((df_day['close'].iloc[-1] - df_day['close'].iloc[-7]) / df_day['close'].iloc[-7] * 100) if len(df_day) >= 7 else 0
                
                # RSI 계산
                delta = df_day['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = to_python(100 - (100 / (1 + rs.iloc[-1]))) if loss.iloc[-1] != 0 else 50
                
                # 거래량 비율
                vol_avg = df_day['volume'].rolling(window=7).mean().iloc[-1]
                vol_ratio = to_python(df_day['volume'].iloc[-1] / vol_avg) if vol_avg > 0 else 1
                
                # 변동성
                volatility = to_python(df_day['close'].pct_change().std() * 100)
                
                coin_data_list.append({
                    "ticker": ticker,
                    "name": ticker.replace("KRW-", ""),
                    "price": current_price,
                    "change_24h": round(change_24h, 2),
                    "change_7d": round(change_7d, 2),
                    "rsi": round(rsi, 1),
                    "volume_ratio": round(vol_ratio, 2),
                    "volatility": round(volatility, 2)
                })
            except Exception as e:
                continue
        
        if not coin_data_list:
            results["message"] = "분석할 코인 데이터를 수집하지 못했습니다."
            return results
        
        # 3. AI 3대장에게 분석 요청
        market_summary = f"""
## 현재 시장 상황 ({datetime.now().strftime('%Y-%m-%d %H:%M')})
- BTC: ₩{results['market_overview']['btc_price']:,.0f} ({results['market_overview']['btc_change_24h']:+.2f}% 24h)
- 시장 분위기: {results['market_overview']['market_sentiment']}

## 분석 대상 코인 ({len(coin_data_list)}개)
"""
        for coin in coin_data_list[:15]:
            market_summary += f"- {coin['name']}: ₩{coin['price']:,.0f} | 24h: {coin['change_24h']:+.2f}% | 7d: {coin['change_7d']:+.2f}% | RSI: {coin['rsi']} | 거래량: {coin['volume_ratio']:.1f}x\n"
        
        ai_prompt = f"""
당신은 암호화폐 트레이딩 전문가입니다.
아래 실시간 시장 데이터를 분석하고, 지금 당장 매수해야 할 최고의 코인을 선정해주세요.

{market_summary}

## 분석 요청
1. 위 데이터를 바탕으로 당신만의 매매 전략을 설계해주세요
2. 가장 수익률이 높을 것으로 예상되는 코인 TOP 3를 선정해주세요
3. 각 코인에 대해 매수 추천 여부와 신뢰도(0-100)를 알려주세요

## 응답 형식 (반드시 JSON으로)
```json
{{
    "strategy": "당신이 설계한 매매 전략 설명",
    "market_view": "현재 시장에 대한 견해",
    "top_picks": [
        {{
            "ticker": "KRW-XXX",
            "recommendation": "strong_buy/buy/hold/sell",
            "confidence": 85,
            "reason": "매수 추천 이유",
            "target_profit": "예상 수익률 %",
            "risk_level": "high/medium/low"
        }}
    ]
}}
```
"""
        
        # AI API 호출
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "CoinHero AI Scan"
        }
        
        ai_models = [
            ("gpt", "openai/gpt-4.1", "GPT 5.2"),
            ("gemini", "google/gemini-2.5-pro-preview", "Gemini 3"),
            ("claude", "anthropic/claude-opus-4", "Claude Opus 4.5")
        ]
        
        ai_responses = []
        for ai_id, model, name in ai_models:
            print(f"[AI-SCAN] {name} 분석 중...")
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": f"당신은 {name}입니다. 암호화폐 시장 분석 전문가로서 데이터 기반의 객관적인 분석을 제공합니다."},
                            {"role": "user", "content": ai_prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2000
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content']
                    
                    # JSON 파싱 시도
                    try:
                        import re
                        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
                        if json_match:
                            parsed = json.loads(json_match.group(1))
                            ai_responses.append({
                                "expert": name,
                                "model": model,
                                "analysis": parsed,
                                "raw_response": content
                            })
                        else:
                            # JSON 블록이 없으면 전체 응답에서 JSON 찾기
                            json_start = content.find('{')
                            json_end = content.rfind('}') + 1
                            if json_start != -1 and json_end > json_start:
                                parsed = json.loads(content[json_start:json_end])
                                ai_responses.append({
                                    "expert": name,
                                    "model": model,
                                    "analysis": parsed,
                                    "raw_response": content
                                })
                    except json.JSONDecodeError:
                        ai_responses.append({
                            "expert": name,
                            "model": model,
                            "analysis": None,
                            "raw_response": content
                        })
                else:
                    print(f"[AI-SCAN] {name} API 오류: {response.status_code}")
            except Exception as e:
                print(f"[AI-SCAN] {name} 오류: {e}")
        
        results["ai_analysis"] = ai_responses
        
        # 4. AI 합의 도출 및 매수 결정
        ticker_votes = {}
        for ai_resp in ai_responses:
            if ai_resp.get("analysis") and ai_resp["analysis"].get("top_picks"):
                for pick in ai_resp["analysis"]["top_picks"]:
                    ticker = pick.get("ticker", "")
                    if ticker:
                        if ticker not in ticker_votes:
                            ticker_votes[ticker] = {
                                "ticker": ticker,
                                "votes": 0,
                                "total_confidence": 0,
                                "recommendations": [],
                                "reasons": []
                            }
                        
                        rec = pick.get("recommendation", "hold")
                        conf = pick.get("confidence", 50)
                        
                        if rec in ["strong_buy", "buy"]:
                            ticker_votes[ticker]["votes"] += 1
                            ticker_votes[ticker]["total_confidence"] += conf
                            ticker_votes[ticker]["recommendations"].append(rec)
                            ticker_votes[ticker]["reasons"].append(pick.get("reason", ""))
        
        # 2명 이상 동의한 종목 선정
        consensus_picks = []
        for ticker, data in ticker_votes.items():
            if data["votes"] >= 2:
                avg_confidence = data["total_confidence"] / data["votes"]
                consensus_picks.append({
                    "ticker": ticker,
                    "votes": data["votes"],
                    "avg_confidence": round(avg_confidence, 1),
                    "recommendations": data["recommendations"],
                    "reasons": data["reasons"]
                })
        
        # 신뢰도 순으로 정렬
        consensus_picks.sort(key=lambda x: (x["votes"], x["avg_confidence"]), reverse=True)
        results["top_picks"] = consensus_picks[:5]
        
        # 5. 자동 매수 실행 (무제한 옵션 적용)
        # - no_signal_limit: 모든 신호 허용 (신뢰도 기준 무시)
        # - no_trade_limit: 전액 투자 (amount=0이면 보유현금 전체)
        # - no_budget_limit: 현금 한도 무시
        for pick in consensus_picks:
            confidence_ok = no_signal_limit or pick["avg_confidence"] >= actual_min_confidence
            votes_ok = pick["votes"] >= 2  # 최소 2명 이상은 항상 필요
            
            if votes_ok and confidence_ok:
                ticker = pick["ticker"]
                
                # 매수 금액 결정 (무제한이면 전액 투자)
                if no_trade_limit or amount == 0:
                    balances = upbit_client.get_balances()
                    krw_balance = next((float(b.get('balance', 0)) for b in balances if b.get('currency') == 'KRW'), 0)
                    buy_amount = int(krw_balance * 0.9995)  # 수수료 고려 99.95%
                else:
                    buy_amount = amount
                
                if buy_amount < 5000:
                    print(f"[AI-SCAN] {ticker} 매수 실패: 잔고 부족 ({buy_amount}원)")
                    continue
                
                print(f"[AI-SCAN] {ticker} 매수 실행 (동의: {pick['votes']}/3, 신뢰도: {pick['avg_confidence']}%, 금액: {buy_amount:,}원)")
                
                try:
                    buy_result = upbit_client.buy_market_order(ticker, buy_amount)
                    if buy_result and not buy_result.get("error"):
                        # 각 AI의 판단 정보 수집
                        ai_judgments = []
                        for ai_resp in ai_responses:
                            ai_name = ai_resp.get("expert", "")
                            analysis = ai_resp.get("analysis", {})
                            top_picks = analysis.get("top_picks", [])
                            for p in top_picks:
                                if p.get("ticker") == ticker:
                                    ai_judgments.append(f"[{ai_name}] {p.get('recommendation', 'hold').upper()} ({p.get('confidence', 0)}%): {p.get('reason', '')}")
                        
                        # 매수 이유 상세화
                        detailed_reason = f"AI 합의 {pick['votes']}/3 (신뢰도 {pick['avg_confidence']}%)"
                        if ai_judgments:
                            detailed_reason += " | " + " | ".join(ai_judgments[:3])
                        
                        results["bought"].append({
                            "ticker": ticker,
                            "amount": buy_amount,
                            "votes": pick["votes"],
                            "confidence": pick["avg_confidence"],
                            "reasons": pick["reasons"],
                            "ai_judgments": ai_judgments,
                            "order_uuid": buy_result.get("uuid")
                        })
                        
                        # 거래 로그 저장 (AI 판단 이유 상세 포함)
                        db.save_trade({
                            "ticker": ticker,
                            "coin_name": ticker.replace("KRW-", ""),
                            "action": "buy",
                            "amount": buy_amount,
                            "strategy": "AI 자율 전략 스캔",
                            "reason": detailed_reason,
                            "ai_reason": detailed_reason,
                            "timestamp": datetime.now().isoformat()
                        })
                except Exception as e:
                    print(f"[AI-SCAN] {ticker} 매수 실패: {e}")
        
        # 결과 메시지
        if results["bought"]:
            results["message"] = f"🎯 AI 3대장 합의로 {len(results['bought'])}개 코인 매수 완료!"
        elif results["top_picks"]:
            results["message"] = f"🔍 AI 분석 완료 - {len(results['top_picks'])}개 종목 관심 권장"
        else:
            results["message"] = "📊 AI 분석 완료 - 현재 강력 매수 추천 종목 없음"
        
        return results
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        results["error"] = str(e)
        results["message"] = f"❌ AI 스캔 오류: {e}"
        return results


@app.get("/api/ai-max-profit/algorithm")
async def get_max_profit_algorithm():
    """수익률 최대화 알고리즘 상세 설명"""
    return {
        "name": "🚀 AI 수익률 최대화 전략",
        "version": "2.0",
        "description": "5가지 기술적 지표를 종합 분석하여 최적의 매수/매도 타이밍을 포착하는 고급 트레이딩 전략",
        
        "buy_algorithm": {
            "title": "📈 매수 알고리즘",
            "total_score": 100,
            "threshold": 60,
            "indicators": [
                {
                    "name": "RSI (Relative Strength Index)",
                    "max_score": 25,
                    "logic": [
                        "일봉 RSI < 25 → 25점 (극과매도)",
                        "60분봉 RSI < 20 → 15점 (극과매도)"
                    ],
                    "description": "RSI가 낮을수록 과매도 상태로 반등 가능성 높음"
                },
                {
                    "name": "볼린저 밴드 (Bollinger Bands)",
                    "max_score": 25,
                    "logic": [
                        "일봉 BB% < 5 → 25점 (하단 터치)",
                        "60분봉 BB% < 10 → 15점 (하단 근접)"
                    ],
                    "description": "볼린저 밴드 하단 터치 시 반등 신호"
                },
                {
                    "name": "MACD (Moving Average Convergence Divergence)",
                    "max_score": 20,
                    "logic": [
                        "일봉 히스토그램 양전환 + 상승 → 20점",
                        "60분봉 히스토그램 양전환 + 상승 → 10점"
                    ],
                    "description": "MACD 히스토그램이 양전환하며 상승할 때 추세 전환 신호"
                },
                {
                    "name": "Williams %R",
                    "max_score": 15,
                    "logic": [
                        "일봉 %R < -90 → 15점 (극과매도)",
                        "60분봉 %R < -80 → 10점 (과매도)"
                    ],
                    "description": "Williams %R이 -80 이하면 과매도 구간"
                },
                {
                    "name": "거래량 (Volume)",
                    "max_score": 15,
                    "logic": [
                        "20일 평균 대비 2배 이상 → 15점",
                        "20일 평균 대비 1.5배 이상 → 10점"
                    ],
                    "description": "거래량 급증은 시장 관심 증가를 의미"
                }
            ],
            "filter": {
                "name": "BTC 추세 필터",
                "logic": "BTC가 1시간 내 0.5% 이상 하락 중이면 모든 매수 보류",
                "reason": "알트코인은 BTC와 동반 하락하는 경향이 있음"
            }
        },
        
        "sell_algorithm": {
            "title": "📉 매도 알고리즘",
            "conditions": [
                {
                    "name": "RSI 과매수 익절",
                    "logic": "일봉 RSI > 75 & 수익률 ≥ 5% → 매도",
                    "priority": 1
                },
                {
                    "name": "목표 수익률 달성",
                    "logic": "수익률 ≥ 10% → 매도",
                    "priority": 2
                },
                {
                    "name": "볼린저 밴드 상단 돌파",
                    "logic": "일봉 BB% > 95 → 익절 매도",
                    "priority": 3
                },
                {
                    "name": "손절",
                    "logic": "수익률 ≤ -2% → 즉시 손절",
                    "priority": 0
                }
            ]
        },
        
        "risk_management": {
            "stop_loss": -2,
            "target_profit": 10,
            "max_positions": 5,
            "position_size": "총 자산의 10-20%"
        }
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
                    'entry_time': coin.get('buy_datetime') or coin.get('buy_date') or datetime.now().isoformat(),
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


# ========== 사용자별 API (Multi-User Support) ==========

@app.get("/api/user/me")
async def get_current_user_info(user: Dict = Depends(require_auth)):
    """현재 로그인한 사용자 정보 조회"""
    return {
        "user": user,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/user/settings")
async def get_user_settings(user: Dict = Depends(require_auth)):
    """사용자 설정 조회"""
    settings = user_manager.get_user_settings(user["id"])
    if settings:
        # API 키는 마스킹해서 반환
        if settings.get("upbit_access_key"):
            settings["upbit_access_key_masked"] = settings["upbit_access_key"][:8] + "..."
        if settings.get("upbit_secret_key"):
            settings["upbit_secret_key_masked"] = "********"
        # 실제 키는 제거
        settings.pop("upbit_access_key", None)
        settings.pop("upbit_secret_key", None)
    return {
        "settings": settings,
        "has_api_keys": bool(settings and settings.get("upbit_access_key_masked"))
    }


@app.post("/api/user/settings")
async def save_user_settings(
    request: UserSettingsRequest, 
    user: Dict = Depends(require_auth)
):
    """사용자 설정 저장"""
    settings = {}
    
    if request.upbit_access_key:
        settings["upbit_access_key"] = request.upbit_access_key
    if request.upbit_secret_key:
        settings["upbit_secret_key"] = request.upbit_secret_key
    if request.trade_amount:
        settings["trade_amount"] = request.trade_amount
    if request.max_positions:
        settings["max_positions"] = request.max_positions
    
    # API 키 유효성 검증
    if request.upbit_access_key and request.upbit_secret_key:
        validation = user_manager.validate_upbit_keys(
            request.upbit_access_key, 
            request.upbit_secret_key
        )
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=f"업비트 API 키 오류: {validation['error']}")
    
    success = user_manager.save_user_settings(user["id"], settings)
    if not success:
        raise HTTPException(status_code=500, detail="설정 저장 실패")
    
    return {"status": "success", "message": "설정이 저장되었습니다"}


@app.get("/api/user/balance")
async def get_user_balance(user: Dict = Depends(require_auth)):
    """사용자별 잔고 조회"""
    print(f"[API] /api/user/balance 요청: user_id={user.get('id')}, email={user.get('email')}")
    balances = user_manager.get_user_balances(user["id"])
    print(f"[API] 잔고 조회 결과: {type(balances)}, count={len(balances) if balances else 0}")
    if balances is None:
        print(f"[API] 잔고 조회 실패: API 키 미설정 또는 Upbit 연결 실패")
        return {
            "balances": [],
            "total_krw": 0,
            "error": "업비트 API 키를 설정해주세요",
            "auth_status": "not_configured"
        }
    
    # 잔고 데이터 정리
    formatted_balances = []
    total_krw = 0
    
    for b in balances:
        currency = b.get("currency", "")
        balance = float(b.get("balance", 0) or 0)
        avg_buy_price = float(b.get("avg_buy_price", 0) or 0)
        
        if currency == "KRW":
            total_krw += balance
            formatted_balances.append({
                "currency": currency,
                "balance": balance,
                "avg_buy_price": 0,
                "eval_amount": balance,
                "profit_rate": 0
            })
        elif balance > 0:
            current_price = upbit_client.get_current_price(f"KRW-{currency}") or avg_buy_price
            eval_amount = balance * current_price
            profit_rate = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
            
            total_krw += eval_amount
            formatted_balances.append({
                "currency": currency,
                "balance": balance,
                "avg_buy_price": avg_buy_price,
                "current_price": current_price,
                "eval_amount": eval_amount,
                "profit_rate": round(profit_rate, 2)
            })
    
    return {
        "balances": formatted_balances,
        "total_krw": total_krw,
        "timestamp": datetime.now().isoformat(),
        "auth_status": "connected"
    }


@app.post("/api/user/trade/buy")
async def user_buy(request: UserTradeRequest, user: Dict = Depends(require_auth)):
    """사용자별 매수 실행"""
    if not request.amount:
        raise HTTPException(status_code=400, detail="매수 금액을 입력해주세요")
    
    result = user_manager.execute_buy(user["id"], request.ticker, request.amount)
    
    if result["success"]:
        # 거래 기록 저장
        user_manager.save_user_trade(user["id"], {
            "market": request.ticker,
            "trade_type": "buy",
            "price": upbit_client.get_current_price(request.ticker) or 0,
            "volume": result.get("volume", 0),
            "amount": request.amount
        })
    
    return result


@app.post("/api/user/trade/sell")
async def user_sell(request: UserTradeRequest, user: Dict = Depends(require_auth)):
    """사용자별 매도 실행"""
    result = user_manager.execute_sell(user["id"], request.ticker, request.volume)
    
    if result["success"]:
        # 거래 기록 저장
        user_manager.save_user_trade(user["id"], {
            "market": request.ticker,
            "trade_type": "sell",
            "price": upbit_client.get_current_price(request.ticker) or 0,
            "volume": result.get("volume", 0),
            "amount": result.get("volume", 0) * (upbit_client.get_current_price(request.ticker) or 0)
        })
    
    return result


@app.get("/api/user/trades")
async def get_user_trades(user: Dict = Depends(require_auth), limit: int = 50):
    """사용자별 거래 기록 조회"""
    trades = user_manager.get_user_trades(user["id"], limit)
    return {
        "trades": trades,
        "count": len(trades)
    }


@app.post("/api/user/validate-keys")
async def validate_api_keys(request: UserSettingsRequest, user: Dict = Depends(require_auth)):
    """업비트 API 키 유효성 검증"""
    if not request.upbit_access_key or not request.upbit_secret_key:
        raise HTTPException(status_code=400, detail="API 키를 입력해주세요")
    
    result = user_manager.validate_upbit_keys(
        request.upbit_access_key,
        request.upbit_secret_key
    )
    return result


# ========== 서버 실행 ==========

if __name__ == "__main__":
    import uvicorn
    import os
    # Railway는 PORT 환경변수 사용, 로컬은 BACKEND_PORT 사용
    port = int(os.getenv("PORT", BACKEND_PORT))
    print(f"""
╔═══════════════════════════════════════════╗
║                                           ║
║     🚀 CoinHero 자동거래 시스템 🚀        ║
║                                           ║
║     API Server: http://localhost:{port}      ║
║     Docs: http://localhost:{port}/docs       ║
║                                           ║
╚═══════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=port)

