"""
CoinHero - 사용자 관리 및 인증 모듈
Supabase를 통한 사용자별 API 키 관리
"""
import os
import base64
import json
from typing import Optional, Dict, Any
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
import pyupbit
from functools import lru_cache
import time


class UserManager:
    def __init__(self):
        self.supabase: Optional[Client] = None
        self._user_clients: Dict[str, Any] = {}  # 사용자별 업비트 클라이언트 캐시
        self._client_timestamps: Dict[str, float] = {}  # 클라이언트 생성 시간
        self._cache_ttl = 300  # 5분 캐시
        self._init_supabase()
    
    def _init_supabase(self):
        """Supabase 클라이언트 초기화"""
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
                print("[UserManager] Supabase 연결 성공")
            except Exception as e:
                print(f"[UserManager] Supabase 연결 실패: {e}")
                self.supabase = None
        else:
            print("[UserManager] Supabase 설정 없음")
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Supabase JWT 토큰 검증 및 사용자 정보 반환
        JWT를 직접 디코딩하여 user_id 추출
        
        Args:
            token: Bearer 토큰 (access_token)
            
        Returns:
            사용자 정보 또는 None
        """
        if not token:
            print("[UserManager] 토큰 없음")
            return None
        
        try:
            # JWT 토큰 직접 디코딩 (base64)
            # JWT는 header.payload.signature 형식
            parts = token.split('.')
            if len(parts) != 3:
                print("[UserManager] 잘못된 JWT 형식")
                return None
            
            # payload (두 번째 부분) 디코딩
            payload = parts[1]
            # base64 패딩 추가
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            
            decoded_bytes = base64.urlsafe_b64decode(payload)
            decoded = json.loads(decoded_bytes.decode('utf-8'))
            
            user_id = decoded.get("sub")
            email = decoded.get("email")
            exp = decoded.get("exp", 0)
            
            # 만료 확인
            if exp and exp < time.time():
                print("[UserManager] 토큰 만료됨")
                return None
            
            if user_id:
                print(f"[UserManager] 토큰 디코딩 성공: {email}")
                return {
                    "id": user_id,
                    "email": email,
                    "created_at": None
                }
        except Exception as e:
            print(f"[UserManager] 토큰 검증 실패: {e}")
        
        return None
    
    def get_user_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        사용자 설정 조회 (업비트 API 키 포함)
        
        Args:
            user_id: Supabase 사용자 ID
            
        Returns:
            사용자 설정 딕셔너리
        """
        if not self.supabase:
            print(f"[UserManager] Supabase 클라이언트 없음")
            return None
        
        try:
            print(f"[UserManager] 사용자 설정 조회 중: user_id={user_id}")
            result = self.supabase.table("user_settings") \
                .select("*") \
                .eq("user_id", user_id) \
                .single() \
                .execute()
            
            if result.data:
                print(f"[UserManager] 설정 조회 성공: {result.data.keys()}")
                # access_key가 있는지 확인
                has_access = bool(result.data.get("upbit_access_key"))
                has_secret = bool(result.data.get("upbit_secret_key"))
                print(f"[UserManager] API 키 존재: access={has_access}, secret={has_secret}")
                return result.data
            else:
                print(f"[UserManager] 설정 없음 (빈 결과)")
        except Exception as e:
            print(f"[UserManager] 설정 조회 실패: {e}")
        
        return None
    
    def save_user_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """
        사용자 설정 저장/업데이트
        
        Args:
            user_id: Supabase 사용자 ID
            settings: 저장할 설정
            
        Returns:
            성공 여부
        """
        if not self.supabase:
            return False
        
        try:
            # upsert (있으면 업데이트, 없으면 생성)
            settings["user_id"] = user_id
            result = self.supabase.table("user_settings") \
                .upsert(settings, on_conflict="user_id") \
                .execute()
            
            # 캐시 무효화
            if user_id in self._user_clients:
                del self._user_clients[user_id]
            
            return True
        except Exception as e:
            print(f"[UserManager] 설정 저장 실패: {e}")
            return False
    
    def get_user_upbit_client(self, user_id: str) -> Optional[pyupbit.Upbit]:
        """
        사용자별 업비트 클라이언트 반환 (캐시 사용)
        
        Args:
            user_id: Supabase 사용자 ID
            
        Returns:
            pyupbit.Upbit 클라이언트 또는 None
        """
        # 캐시 확인
        now = time.time()
        if user_id in self._user_clients:
            if now - self._client_timestamps.get(user_id, 0) < self._cache_ttl:
                return self._user_clients[user_id]
        
        # Supabase에서 사용자 설정 조회
        settings = self.get_user_settings(user_id)
        if not settings:
            print(f"[UserManager] 사용자 {user_id}의 설정을 찾을 수 없습니다")
            return None
        
        access_key = settings.get("upbit_access_key")
        secret_key = settings.get("upbit_secret_key")
        
        if not access_key or not secret_key:
            print(f"[UserManager] 사용자 {user_id}의 API 키가 설정되지 않았습니다")
            return None
        
        try:
            client = pyupbit.Upbit(access_key, secret_key)
            
            # 캐시 저장
            self._user_clients[user_id] = client
            self._client_timestamps[user_id] = now
            
            print(f"[UserManager] 사용자 {user_id}의 업비트 클라이언트 생성 성공")
            return client
        except Exception as e:
            print(f"[UserManager] 업비트 클라이언트 생성 실패: {e}")
            return None
    
    def validate_upbit_keys(self, access_key: str, secret_key: str) -> Dict[str, Any]:
        """
        업비트 API 키 유효성 검증
        
        Args:
            access_key: 업비트 Access Key
            secret_key: 업비트 Secret Key
            
        Returns:
            검증 결과
        """
        try:
            client = pyupbit.Upbit(access_key, secret_key)
            balances = client.get_balances()
            
            if balances is None:
                return {"valid": False, "error": "잔고 조회 실패"}
            
            if isinstance(balances, dict) and "error" in balances:
                return {"valid": False, "error": balances.get("error", {}).get("message", "알 수 없는 오류")}
            
            return {"valid": True, "account_count": len(balances)}
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def get_user_balances(self, user_id: str) -> Optional[list]:
        """
        사용자별 잔고 조회
        
        Args:
            user_id: Supabase 사용자 ID
            
        Returns:
            잔고 리스트 또는 None
        """
        client = self.get_user_upbit_client(user_id)
        if not client:
            return None
        
        try:
            return client.get_balances()
        except Exception as e:
            print(f"[UserManager] 잔고 조회 실패: {e}")
            return None
    
    def execute_buy(self, user_id: str, ticker: str, amount: float) -> Dict[str, Any]:
        """
        사용자별 매수 실행
        
        Args:
            user_id: Supabase 사용자 ID
            ticker: 코인 티커 (예: KRW-BTC)
            amount: 매수 금액 (KRW)
            
        Returns:
            거래 결과
        """
        client = self.get_user_upbit_client(user_id)
        if not client:
            return {"success": False, "error": "업비트 연결 실패"}
        
        try:
            result = client.buy_market_order(ticker, amount)
            if result and "uuid" in result:
                return {
                    "success": True,
                    "uuid": result["uuid"],
                    "ticker": ticker,
                    "amount": amount,
                    "side": "bid"
                }
            else:
                error_msg = result.get("error", {}).get("message", "매수 실패") if isinstance(result, dict) else "매수 실패"
                return {"success": False, "error": error_msg}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def execute_sell(self, user_id: str, ticker: str, volume: Optional[float] = None) -> Dict[str, Any]:
        """
        사용자별 매도 실행
        
        Args:
            user_id: Supabase 사용자 ID
            ticker: 코인 티커 (예: KRW-BTC)
            volume: 매도 수량 (None이면 전량 매도)
            
        Returns:
            거래 결과
        """
        client = self.get_user_upbit_client(user_id)
        if not client:
            return {"success": False, "error": "업비트 연결 실패"}
        
        try:
            # 전량 매도인 경우 잔고 조회
            if volume is None:
                currency = ticker.replace("KRW-", "")
                balance = client.get_balance(currency)
                if balance is None or balance <= 0:
                    return {"success": False, "error": "매도할 코인이 없습니다"}
                volume = balance
            
            result = client.sell_market_order(ticker, volume)
            if result and "uuid" in result:
                return {
                    "success": True,
                    "uuid": result["uuid"],
                    "ticker": ticker,
                    "volume": volume,
                    "side": "ask"
                }
            else:
                error_msg = result.get("error", {}).get("message", "매도 실패") if isinstance(result, dict) else "매도 실패"
                return {"success": False, "error": error_msg}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def save_user_trade(self, user_id: str, trade_data: Dict[str, Any]) -> bool:
        """
        사용자별 거래 기록 저장
        
        Args:
            user_id: Supabase 사용자 ID
            trade_data: 거래 정보
            
        Returns:
            성공 여부
        """
        if not self.supabase:
            return False
        
        try:
            trade_data["user_id"] = user_id
            self.supabase.table("user_trades").insert(trade_data).execute()
            return True
        except Exception as e:
            print(f"[UserManager] 거래 저장 실패: {e}")
            return False
    
    def get_user_trades(self, user_id: str, limit: int = 50) -> list:
        """
        사용자별 거래 기록 조회
        
        Args:
            user_id: Supabase 사용자 ID
            limit: 조회 개수
            
        Returns:
            거래 기록 리스트
        """
        if not self.supabase:
            return []
        
        try:
            result = self.supabase.table("user_trades") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("executed_at", desc=True) \
                .limit(limit) \
                .execute()
            
            return result.data if result.data else []
        except Exception as e:
            print(f"[UserManager] 거래 조회 실패: {e}")
            return []


# 싱글톤 인스턴스
user_manager = UserManager()

