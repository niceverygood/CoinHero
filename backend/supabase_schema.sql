-- CoinHero Supabase Schema
-- Supabase SQL Editor에서 실행하세요

-- 1. 거래 기록 테이블
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(20) NOT NULL,
    coin_name VARCHAR(20),
    action VARCHAR(10) NOT NULL CHECK (action IN ('buy', 'sell')),
    amount DECIMAL(20,8),
    price DECIMAL(20,2),
    total_krw DECIMAL(20,2),
    profit DECIMAL(20,2),
    profit_rate DECIMAL(10,4),
    strategy VARCHAR(50),
    ai_reason TEXT,
    ai_confidence INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 포지션 테이블
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(20) NOT NULL,
    coin_name VARCHAR(20),
    entry_price DECIMAL(20,2) NOT NULL,
    amount DECIMAL(20,8) NOT NULL,
    target_price DECIMAL(20,2),
    stop_loss DECIMAL(20,2),
    strategy VARCHAR(50),
    ai_reason TEXT,
    max_profit DECIMAL(10,4),
    trailing_stop DECIMAL(20,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

-- 3. 일별 통계 테이블
CREATE TABLE IF NOT EXISTS daily_stats (
    date DATE PRIMARY KEY,
    total_profit DECIMAL(20,2) DEFAULT 0,
    trade_count INTEGER DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_action ON trades(action);
CREATE INDEX IF NOT EXISTS idx_positions_active ON positions(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker);

-- RLS (Row Level Security) 비활성화 (service_role 키 사용 시)
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_stats ENABLE ROW LEVEL SECURITY;

-- service_role은 모든 작업 허용
CREATE POLICY "Service role full access" ON trades FOR ALL USING (true);
CREATE POLICY "Service role full access" ON positions FOR ALL USING (true);
CREATE POLICY "Service role full access" ON daily_stats FOR ALL USING (true);





