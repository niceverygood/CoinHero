"""
Supabase 데이터베이스 클라이언트
"""
from supabase import create_client, Client
from datetime import datetime, date
import time
import os
from typing import List, Dict, Any, Optional
import json

from config import SUPABASE_URL, SUPABASE_KEY


class Database:
    """Supabase 데이터베이스 래퍼"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.memory_trades: List[Dict[str, Any]] = []  # 메모리 저장용 (DB 연결 실패 시)
        self.memory_positions: Dict[str, Dict[str, Any]] = {} # 메모리 포지션
        self.local_db_path = "local_trades.json"
        self._load_local_db()
        self._init_client()
    
    def _load_local_db(self):
        """로컬 JSON 파일에서 데이터 로드"""
        try:
            if os.path.exists(self.local_db_path):
                with open(self.local_db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.memory_trades = data.get("trades", [])
                    self.memory_positions = data.get("positions", {})
                print(f"[DB] 로컬 데이터 로드 완료 ({len(self.memory_trades)}개 거래)")
        except Exception as e:
            print(f"[DB] 로컬 데이터 로드 실패: {e}")

    def _save_local_db(self):
        """로컬 JSON 파일에 데이터 저장"""
        try:
            with open(self.local_db_path, "w", encoding="utf-8") as f:
                json.dump({
                    "trades": self.memory_trades,
                    "positions": self.memory_positions
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[DB] 로컬 데이터 저장 실패: {e}")

    def _init_client(self):
        """Supabase 클라이언트 초기화"""
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
                print(f"[DB] Supabase 연결 성공")
            except Exception as e:
                print(f"[DB] Supabase 연결 실패 (메모리 모드 전환): {e}")
                self.client = None
        else:
            print("[DB] Supabase 설정 없음 - 메모리 모드로 동작")
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.client is not None
    
    # ========== 거래 기록 ==========
    
    def save_trade(self, trade: Dict[str, Any]) -> bool:
        """거래 기록 저장"""
        # 메모리에는 항상 저장
        memory_data = {
            "id": trade.get("id", f"trade_{int(time.time())}"),
            "ticker": trade.get("ticker", ""),
            "coin_name": trade.get("coin_name", trade.get("ticker", "").replace("KRW-", "")),
            "action": trade.get("action", trade.get("side", "buy")),
            "amount": float(trade.get("amount", 0)),
            "price": float(trade.get("price", 0)),
            "total_krw": float(trade.get("total_krw", trade.get("amount", 0))),
            "profit": float(trade.get("profit", 0)) if trade.get("profit") else None,
            "profit_rate": float(trade.get("profit_rate", 0)) if trade.get("profit_rate") else None,
            "strategy": trade.get("strategy", ""),
            "ai_reason": trade.get("ai_reason", trade.get("reason", "")),
            "ai_confidence": trade.get("ai_confidence"),
            "created_at": trade.get("timestamp", datetime.now().isoformat())
        }
        self.memory_trades.append(memory_data)
        self._save_local_db()
        
        if not self.client:
            return True
        
        try:
            data = {
                "ticker": trade.get("ticker", ""),
                "coin_name": trade.get("coin_name", ""),
                "action": trade.get("action", ""),
                "amount": float(trade.get("amount", 0)),
                "price": float(trade.get("price", 0)),
                "total_krw": float(trade.get("total_krw", 0)),
                "profit": float(trade.get("profit", 0)) if trade.get("profit") else None,
                "profit_rate": float(trade.get("profit_rate", 0)) if trade.get("profit_rate") else None,
                "strategy": trade.get("strategy", ""),
                "ai_reason": trade.get("ai_reason", ""),
                "ai_confidence": trade.get("ai_confidence"),
            }
            
            result = self.client.table("trades").insert(data).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"[DB] Supabase 저장 실패 (메모리 보존됨): {e}")
            return False
    
    def get_trades(self, limit: int = 50, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """거래 기록 조회"""
        if self.client:
            try:
                query = self.client.table("trades").select("*").order("created_at", desc=True)
                
                if start_date:
                    query = query.gte("created_at", start_date)
                if end_date:
                    query = query.lte("created_at", end_date)
                    
                result = query.limit(limit).execute()
                if result.data:
                    return result.data
            except Exception as e:
                print(f"[DB] Supabase 조회 실패: {e}")
        
        # 메모리 데이터 필터링 및 반환
        trades = self.memory_trades
        if start_date:
            trades = [t for t in trades if t["created_at"] >= start_date]
        if end_date:
            trades = [t for t in trades if t["created_at"] <= end_date]
            
        return sorted(trades, key=lambda x: x["created_at"], reverse=True)[:limit]
    
    def get_today_trades(self) -> List[Dict[str, Any]]:
        """오늘 거래 기록"""
        today_str = date.today().isoformat()
        
        if self.client:
            try:
                result = self.client.table("trades") \
                    .select("*") \
                    .gte("created_at", today_str) \
                    .order("created_at", desc=True) \
                    .execute()
                if result.data:
                    return result.data
            except Exception as e:
                print(f"[DB] Supabase 오늘 거래 조회 실패: {e}")
        
        # 메모리 필터링
        return [t for t in self.memory_trades if t["created_at"].startswith(today_str)]
    
    def get_total_profit(self) -> float:
        """총 수익 계산"""
        if self.client:
            try:
                result = self.client.table("trades") \
                    .select("profit") \
                    .eq("action", "sell") \
                    .execute()
                if result.data:
                    return sum(t.get("profit", 0) or 0 for t in result.data)
            except Exception as e:
                print(f"[DB] Supabase 총 수익 조회 실패: {e}")
        
        return sum(t.get("profit", 0) or 0 for t in self.memory_trades if t.get("action") == "sell")
    
    # ========== 포지션 ==========
    
    def save_position(self, position: Dict[str, Any]) -> bool:
        """포지션 저장"""
        ticker = position.get("ticker", "")
        self.memory_positions[ticker] = {**position, "is_active": True, "created_at": datetime.now().isoformat()}
        self._save_local_db()
        
        if not self.client:
            return True
        
        try:
            data = {
                "ticker": ticker,
                "coin_name": position.get("coin_name", ""),
                "entry_price": float(position.get("entry_price", 0)),
                "amount": float(position.get("amount", 0)),
                "target_price": float(position.get("target_price", 0)) if position.get("target_price") else None,
                "stop_loss": float(position.get("stop_loss", 0)) if position.get("stop_loss") else None,
                "strategy": position.get("strategy", ""),
                "ai_reason": position.get("ai_reason", ""),
                "max_profit": float(position.get("max_profit", 0)) if position.get("max_profit") else None,
                "trailing_stop": float(position.get("trailing_stop", 0)) if position.get("trailing_stop") else None,
                "is_active": True
            }
            
            # 기존 포지션이 있으면 업데이트, 없으면 삽입
            existing = self.client.table("positions") \
                .select("id") \
                .eq("ticker", ticker) \
                .eq("is_active", True) \
                .execute()
            
            if existing.data:
                self.client.table("positions").update(data).eq("id", existing.data[0]["id"]).execute()
            else:
                self.client.table("positions").insert(data).execute()
            return True
        except Exception as e:
            print(f"[DB] Supabase 포지션 저장 실패: {e}")
            return False
    
    def close_position(self, ticker: str) -> bool:
        """포지션 청산 (비활성화)"""
        if ticker in self.memory_positions:
            self.memory_positions[ticker]["is_active"] = False
            self.memory_positions[ticker]["closed_at"] = datetime.now().isoformat()
            self._save_local_db()
            
        if not self.client:
            return True
        
        try:
            self.client.table("positions") \
                .update({"is_active": False, "closed_at": datetime.now().isoformat()}) \
                .eq("ticker", ticker) \
                .eq("is_active", True) \
                .execute()
            return True
        except Exception as e:
            print(f"[DB] Supabase 포지션 청산 실패: {e}")
            return False
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """활성 포지션 조회"""
        if self.client:
            try:
                result = self.client.table("positions").select("*").eq("is_active", True).execute()
                if result.data: return result.data
            except Exception as e:
                print(f"[DB] Supabase 활성 포지션 조회 실패: {e}")
        
        return [p for p in self.memory_positions.values() if p.get("is_active")]
    
    def update_position(self, ticker: str, updates: Dict[str, Any]) -> bool:
        """포지션 업데이트 (트레일링 스탑 등)"""
        if ticker in self.memory_positions:
            self.memory_positions[ticker].update(updates)
            
        if not self.client:
            return True
            
        try:
            self.client.table("positions").update(updates).eq("ticker", ticker).eq("is_active", True).execute()
            return True
        except Exception as e:
            print(f"[DB] Supabase 포지션 업데이트 실패: {e}")
            return False
    
    # ========== 일별 통계 ==========
    
    def update_daily_stats(self) -> bool:
        """일별 통계 업데이트"""
        if not self.client:
            return True
        
        try:
            today = date.today().isoformat()
            trades = self.get_today_trades()
            
            sell_trades = [t for t in trades if t.get("action") == "sell"]
            total_profit = sum(t.get("profit", 0) or 0 for t in sell_trades)
            win_count = len([t for t in sell_trades if (t.get("profit") or 0) > 0])
            
            data = {
                "date": today,
                "total_profit": total_profit,
                "trade_count": len(trades),
                "win_count": win_count,
                "updated_at": datetime.now().isoformat()
            }
            self.client.table("daily_stats").upsert(data).execute()
            return True
        except Exception as e:
            print(f"[DB] Supabase 일별 통계 업데이트 실패: {e}")
            return False
    
    def get_daily_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """일별 통계 조회"""
        if self.client:
            try:
                result = self.client.table("daily_stats").select("*").order("date", desc=True).limit(days).execute()
                if result.data: return result.data
            except Exception as e:
                print(f"[DB] Supabase 일별 통계 조회 실패: {e}")
        return []

    def get_period_stats(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, float]:
        """일/주/월별 또는 특정 기간 수익 통계 계산"""
        trades = []
        if self.client:
            try:
                query = self.client.table("trades").select("profit, created_at").eq("action", "sell")
                
                if start_date:
                    query = query.gte("created_at", start_date)
                if end_date:
                    query = query.lte("created_at", end_date)
                    
                result = query.execute()
                trades = result.data
            except Exception as e:
                print(f"[DB] Supabase 기간별 통계 조회 실패: {e}")
        
        if not trades:
            trades = [t for t in self.memory_trades if t.get("action") == "sell"]
            
        now = datetime.now()
        daily_profit = 0
        weekly_profit = 0
        monthly_profit = 0
        custom_profit = 0
        
        for t in trades:
            profit = t.get("profit", 0) or 0
            created_at_str = t.get("created_at")
            if not created_at_str: continue
            
            try:
                # ISO 형식 처리 (Z 또는 +00:00)
                if created_at_str.endswith('Z'):
                    created_at_str = created_at_str.replace('Z', '+00:00')
                created_at = datetime.fromisoformat(created_at_str)
                created_at = created_at.replace(tzinfo=None)
                
                # 기본 통계
                if created_at.date() == now.date():
                    daily_profit += profit
                if (now - created_at).days < 7:
                    weekly_profit += profit
                if (now - created_at).days < 30:
                    monthly_profit += profit
                
                # 특정 기간 통계 (필터링된 trades면 전체 합산)
                custom_profit += profit
            except:
                continue
                
        return {
            "daily": round(daily_profit, 2),
            "weekly": round(weekly_profit, 2),
            "monthly": round(monthly_profit, 2),
            "custom": round(custom_profit, 2)
        }


# 싱글톤 인스턴스
db = Database()




