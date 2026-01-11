"""
CoinHero - 업비트 자동거래 시스템 설정
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Upbit API Keys (직접 연결 - 24시간 자동매매용)
UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY") or "juh1vWFSlwJz8zlCQWCFM5NQ15THFn2vDdDWs7Pi"
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY") or "7JFe4CifeOzrL9g6aJMHMoGO8A4Ik33FhDcQ0kkx"

# Server Settings
BACKEND_PORT = int(os.getenv("BACKEND_PORT", 8000))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", 8080))

# Trading Settings
DEFAULT_TRADE_AMOUNT = int(os.getenv("DEFAULT_TRADE_AMOUNT", 10000))  # 기본 거래금액 (KRW)
MAX_COINS = int(os.getenv("MAX_COINS", 5))  # 최대 보유 코인 수

# Strategy Settings
VOLATILITY_K = 0.5  # 변동성 돌파 K값
RSI_OVERSOLD = 30   # RSI 과매도 기준
RSI_OVERBOUGHT = 70 # RSI 과매수 기준

# OpenRouter API (AI 분석용 - 직접 연결)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Supabase (DB) - 빈 문자열인 경우에도 기본값 사용
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://lbnvztnbsbqisemvkvwe.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxibnZ6dG5ic2JxaXNlbXZrdndlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzc2Nzk0MCwiZXhwIjoyMDgzMzQzOTQwfQ.e7CiDAtFnGNRu65XAVA_z9njXhL-bnCWQ2kKWR9tm1k"  # service_role key

