"""
CoinHero - 업비트 자동거래 시스템 설정
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Upbit API Keys (환경변수에서 로드)
UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY", "")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY", "")

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

# OpenRouter API (AI 분석용)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Supabase (DB)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lbnvztnbsbqisemvkvwe.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxibnZ6dG5ic2JxaXNlbXZrdndlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzc2Nzk0MCwiZXhwIjoyMDgzMzQzOTQwfQ.e7CiDAtFnGNRu65XAVA_z9njXhL-bnCWQ2kKWR9tm1k")  # service_role key

