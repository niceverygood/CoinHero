"""
업비트 API 클라이언트 모듈
"""
import pyupbit
import pandas as pd
import requests
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
from config import UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY


class UpbitClient:
    """업비트 API 래퍼 클래스"""
    
    def __init__(self):
        self.upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
        
    # ========== 시세 조회 ==========
    
    def get_current_price(self, ticker: str, max_retries: int = 3) -> Optional[float]:
        """현재가 조회 (재시도 및 직접 API 폴백 포함)"""
        for attempt in range(max_retries):
            try:
                price = pyupbit.get_current_price(ticker)
                if price and price > 0:
                    return price
            except Exception:
                pass
            
            # 직접 API 호출 폴백
            try:
                response = requests.get(
                    f"https://api.upbit.com/v1/ticker?markets={ticker}",
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        return float(data[0].get('trade_price', 0))
            except Exception:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(0.2)
        
        return None
    
    def get_current_prices(self, tickers: List[str]) -> Dict[str, float]:
        """여러 코인 현재가 조회"""
        try:
            result = pyupbit.get_current_price(tickers)
            if isinstance(result, dict):
                return result
            # 단일 티커인 경우 dict로 변환
            if len(tickers) == 1 and result:
                return {tickers[0]: result}
        except Exception:
            pass
        
        # 폴백: 직접 API 호출
        try:
            markets = ",".join(tickers[:100])  # 최대 100개
            response = requests.get(
                f"https://api.upbit.com/v1/ticker?markets={markets}",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {item['market']: float(item['trade_price']) for item in data}
        except Exception:
            pass
        
        return {}
    
    def get_ohlcv(self, ticker: str, interval: str = "day", count: int = 200) -> pd.DataFrame:
        """OHLCV 데이터 조회
        
        Args:
            ticker: 마켓 코드 (예: KRW-BTC)
            interval: minute1, minute3, minute5, minute10, minute15, minute30, 
                     minute60, minute240, day, week, month
            count: 조회할 캔들 수
        """
        try:
            df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            print(f"OHLCV 조회 실패: {e}")
            return pd.DataFrame()
    
    def get_orderbook(self, ticker: str) -> Dict[str, Any]:
        """호가 정보 조회"""
        try:
            orderbook = pyupbit.get_orderbook(ticker)
            if orderbook:
                return orderbook[0] if isinstance(orderbook, list) else orderbook
            return {}
        except Exception as e:
            print(f"호가 조회 실패: {e}")
            return {}
    
    # ========== 잔고 조회 ==========
    
    def get_balance(self, ticker: str = "KRW") -> float:
        """잔고 조회"""
        try:
            return self.upbit.get_balance(ticker)
        except Exception as e:
            print(f"잔고 조회 실패: {e}")
            return 0.0
    
    def get_balances(self) -> List[Dict[str, Any]]:
        """전체 잔고 조회"""
        try:
            balances = self.upbit.get_balances()
            
            # 에러 발생 시 처리
            if isinstance(balances, dict) and 'error' in balances:
                error_msg = balances.get('error', {}).get('message', '알 수 없는 오류')
                print(f"업비트 API 에러: {error_msg}")
                return []
                
            if not isinstance(balances, list):
                print(f"잔고 조회 실패: 예상치 못한 응답 형식 {type(balances)}")
                return []
                
            result = []
            for b in balances:
                if not isinstance(b, dict):
                    continue
                    
                if float(b.get('balance', 0)) > 0 or float(b.get('locked', 0)) > 0:
                    currency = b.get('currency', '')
                    balance = float(b.get('balance', 0))
                    locked = float(b.get('locked', 0))
                    avg_buy_price = float(b.get('avg_buy_price', 0))
                    
                    # 현재가 조회 (KRW 제외)
                    current_price = 1 if currency == 'KRW' else self.get_current_price(f"KRW-{currency}")
                    current_price = current_price or avg_buy_price
                    
                    # 평가금액 및 수익률 계산
                    total_balance = balance + locked
                    eval_amount = total_balance * current_price
                    buy_total = total_balance * avg_buy_price  # 매수 총액
                    profit = eval_amount - buy_total  # 실현 손익 (원화)
                    profit_rate = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
                    
                    result.append({
                        'currency': currency,
                        'balance': balance,
                        'locked': locked,
                        'avg_buy_price': avg_buy_price,
                        'current_price': current_price,
                        'eval_amount': eval_amount,
                        'buy_total': round(buy_total, 2),
                        'profit': round(profit, 2),
                        'profit_rate': round(profit_rate, 2)
                    })
            return result
        except Exception as e:
            print(f"전체 잔고 조회 예외 발생: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_avg_buy_price(self, ticker: str) -> float:
        """평균 매수가 조회"""
        try:
            return self.upbit.get_avg_buy_price(ticker)
        except Exception as e:
            print(f"평균 매수가 조회 실패: {e}")
            return 0.0
    
    # ========== 주문 ==========
    
    def buy_market_order(self, ticker: str, amount: float) -> Dict[str, Any]:
        """시장가 매수
        
        Args:
            ticker: 마켓 코드 (예: KRW-BTC)
            amount: 매수 금액 (KRW)
        """
        try:
            result = self.upbit.buy_market_order(ticker, amount)
            return result if result else {'error': '주문 실패'}
        except Exception as e:
            print(f"시장가 매수 실패: {e}")
            return {'error': str(e)}
    
    def sell_market_order(self, ticker: str, volume: float) -> Dict[str, Any]:
        """시장가 매도
        
        Args:
            ticker: 마켓 코드 (예: KRW-BTC)
            volume: 매도 수량
        """
        try:
            result = self.upbit.sell_market_order(ticker, volume)
            return result if result else {'error': '주문 실패'}
        except Exception as e:
            print(f"시장가 매도 실패: {e}")
            return {'error': str(e)}
    
    def buy_limit_order(self, ticker: str, price: float, volume: float) -> Dict[str, Any]:
        """지정가 매수"""
        try:
            result = self.upbit.buy_limit_order(ticker, price, volume)
            return result if result else {'error': '주문 실패'}
        except Exception as e:
            print(f"지정가 매수 실패: {e}")
            return {'error': str(e)}
    
    def sell_limit_order(self, ticker: str, price: float, volume: float) -> Dict[str, Any]:
        """지정가 매도"""
        try:
            result = self.upbit.sell_limit_order(ticker, price, volume)
            return result if result else {'error': '주문 실패'}
        except Exception as e:
            print(f"지정가 매도 실패: {e}")
            return {'error': str(e)}
    
    def cancel_order(self, uuid: str) -> Dict[str, Any]:
        """주문 취소"""
        try:
            result = self.upbit.cancel_order(uuid)
            return result if result else {'error': '취소 실패'}
        except Exception as e:
            print(f"주문 취소 실패: {e}")
            return {'error': str(e)}
    
    def get_order(self, uuid: str) -> Dict[str, Any]:
        """주문 조회"""
        try:
            return self.upbit.get_order(uuid) or {}
        except Exception as e:
            print(f"주문 조회 실패: {e}")
            return {}
    
    # ========== 마켓 정보 ==========
    
    @staticmethod
    def get_tickers(fiat: str = "KRW") -> List[str]:
        """마켓 코드 목록 조회"""
        try:
            return pyupbit.get_tickers(fiat=fiat)
        except Exception as e:
            print(f"마켓 목록 조회 실패: {e}")
            return []
    
    @staticmethod
    def get_ticker_info() -> List[Dict[str, Any]]:
        """전체 코인 정보 조회"""
        try:
            tickers = pyupbit.get_tickers(fiat="KRW")
            prices = pyupbit.get_current_price(tickers)
            
            result = []
            for ticker in tickers:
                price = prices.get(ticker, 0) if isinstance(prices, dict) else prices
                coin_name = ticker.replace("KRW-", "")
                result.append({
                    'ticker': ticker,
                    'coin': coin_name,
                    'price': price
                })
            return result
        except Exception as e:
            print(f"코인 정보 조회 실패: {e}")
            return []


# 싱글톤 인스턴스
upbit_client = UpbitClient()



