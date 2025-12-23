"""
Supabase 데이터베이스 클라이언트
"""
from supabase import create_client, Client
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import json

from config import SUPABASE_URL, SUPABASE_KEY


class Database:
    """Supabase 데이터베이스 래퍼"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self._init_client()
    
    def _init_client(self):
        """Supabase 클라이언트 초기화"""
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
                print(f"[DB] Supabase 연결 성공")
            except Exception as e:
                print(f"[DB] Supabase 연결 실패: {e}")
                self.client = None
        else:
            print("[DB] Supabase 설정 없음 - 메모리 모드로 동작")
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.client is not None
    
    # ========== 거래 기록 ==========
    
    def save_trade(self, trade: Dict[str, Any]) -> bool:
        """거래 기록 저장"""
        if not self.client:
            return False
        
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
            print(f"[DB] 거래 저장 실패: {e}")
            return False
    
    def get_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """거래 기록 조회"""
        if not self.client:
            return []
        
        try:
            result = self.client.table("trades") \
                .select("*") \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            return result.data
        except Exception as e:
            print(f"[DB] 거래 조회 실패: {e}")
            return []
    
    def get_today_trades(self) -> List[Dict[str, Any]]:
        """오늘 거래 기록"""
        if not self.client:
            return []
        
        try:
            today = date.today().isoformat()
            result = self.client.table("trades") \
                .select("*") \
                .gte("created_at", today) \
                .order("created_at", desc=True) \
                .execute()
            return result.data
        except Exception as e:
            print(f"[DB] 오늘 거래 조회 실패: {e}")
            return []
    
    def get_total_profit(self) -> float:
        """총 수익 계산"""
        if not self.client:
            return 0.0
        
        try:
            result = self.client.table("trades") \
                .select("profit") \
                .eq("action", "sell") \
                .execute()
            
            total = sum(t.get("profit", 0) or 0 for t in result.data)
            return total
        except Exception as e:
            print(f"[DB] 총 수익 조회 실패: {e}")
            return 0.0
    
    # ========== 포지션 ==========
    
    def save_position(self, position: Dict[str, Any]) -> bool:
        """포지션 저장"""
        if not self.client:
            return False
        
        try:
            data = {
                "ticker": position.get("ticker", ""),
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
                .eq("ticker", position.get("ticker", "")) \
                .eq("is_active", True) \
                .execute()
            
            if existing.data:
                result = self.client.table("positions") \
                    .update(data) \
                    .eq("id", existing.data[0]["id"]) \
                    .execute()
            else:
                result = self.client.table("positions").insert(data).execute()
            
            return len(result.data) > 0
        except Exception as e:
            print(f"[DB] 포지션 저장 실패: {e}")
            return False
    
    def close_position(self, ticker: str) -> bool:
        """포지션 청산 (비활성화)"""
        if not self.client:
            return False
        
        try:
            result = self.client.table("positions") \
                .update({"is_active": False, "closed_at": datetime.now().isoformat()}) \
                .eq("ticker", ticker) \
                .eq("is_active", True) \
                .execute()
            return True
        except Exception as e:
            print(f"[DB] 포지션 청산 실패: {e}")
            return False
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """활성 포지션 조회"""
        if not self.client:
            return []
        
        try:
            result = self.client.table("positions") \
                .select("*") \
                .eq("is_active", True) \
                .execute()
            return result.data
        except Exception as e:
            print(f"[DB] 활성 포지션 조회 실패: {e}")
            return []
    
    def update_position(self, ticker: str, updates: Dict[str, Any]) -> bool:
        """포지션 업데이트 (트레일링 스탑 등)"""
        if not self.client:
            return False
        
        try:
            result = self.client.table("positions") \
                .update(updates) \
                .eq("ticker", ticker) \
                .eq("is_active", True) \
                .execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"[DB] 포지션 업데이트 실패: {e}")
            return False
    
    # ========== 일별 통계 ==========
    
    def update_daily_stats(self) -> bool:
        """일별 통계 업데이트"""
        if not self.client:
            return False
        
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
            
            # Upsert (있으면 업데이트, 없으면 삽입)
            result = self.client.table("daily_stats").upsert(data).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"[DB] 일별 통계 업데이트 실패: {e}")
            return False
    
    def get_daily_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """일별 통계 조회"""
        if not self.client:
            return []
        
        try:
            result = self.client.table("daily_stats") \
                .select("*") \
                .order("date", desc=True) \
                .limit(days) \
                .execute()
            return result.data
        except Exception as e:
            print(f"[DB] 일별 통계 조회 실패: {e}")
            return []


# 싱글톤 인스턴스
db = Database()

