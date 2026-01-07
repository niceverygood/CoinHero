-- CoinHero 멀티유저 스키마
-- Supabase SQL Editor에서 실행

-- 1. 사용자 설정 테이블 (업비트 API 키 저장)
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    upbit_access_key TEXT,  -- 암호화하여 저장 권장
    upbit_secret_key TEXT,  -- 암호화하여 저장 권장
    openrouter_api_key TEXT,
    default_trade_amount INTEGER DEFAULT 10000,
    max_positions INTEGER DEFAULT 3,
    ai_model TEXT DEFAULT 'claude-opus-4.5',
    ai_sell_analysis BOOLEAN DEFAULT false,
    budget_limit BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 사용자별 거래 내역 테이블
CREATE TABLE IF NOT EXISTS user_trades (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    price DECIMAL(20, 8) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    total_amount DECIMAL(20, 2) NOT NULL,
    strategy TEXT,
    ai_reason TEXT,
    profit_rate DECIMAL(10, 4),
    profit_amount DECIMAL(20, 2),
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 사용자별 포지션 테이블
CREATE TABLE IF NOT EXISTS user_positions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    avg_price DECIMAL(20, 8) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    strategy TEXT,
    entry_reason TEXT,
    max_profit DECIMAL(10, 4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, ticker)
);

-- 4. AI 스캘핑 세션 테이블
CREATE TABLE IF NOT EXISTS user_scalping_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    is_running BOOLEAN DEFAULT false,
    strategies TEXT[], -- 선택된 전략들
    trade_amount INTEGER DEFAULT 10000,
    ai_model TEXT DEFAULT 'claude-opus-4.5',
    started_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. RLS (Row Level Security) 정책 설정
-- 사용자는 자신의 데이터만 접근 가능

ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_scalping_sessions ENABLE ROW LEVEL SECURITY;

-- user_settings 정책
CREATE POLICY "Users can view own settings" ON user_settings
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own settings" ON user_settings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own settings" ON user_settings
    FOR UPDATE USING (auth.uid() = user_id);

-- user_trades 정책
CREATE POLICY "Users can view own trades" ON user_trades
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own trades" ON user_trades
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- user_positions 정책
CREATE POLICY "Users can view own positions" ON user_positions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own positions" ON user_positions
    FOR ALL USING (auth.uid() = user_id);

-- user_scalping_sessions 정책
CREATE POLICY "Users can manage own sessions" ON user_scalping_sessions
    FOR ALL USING (auth.uid() = user_id);

-- 6. 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_user_trades_user_id ON user_trades(user_id);
CREATE INDEX IF NOT EXISTS idx_user_trades_executed_at ON user_trades(executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_positions_user_id ON user_positions(user_id);

-- 7. updated_at 자동 업데이트 함수
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 트리거 생성
CREATE TRIGGER update_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_positions_updated_at
    BEFORE UPDATE ON user_positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_scalping_sessions_updated_at
    BEFORE UPDATE ON user_scalping_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

