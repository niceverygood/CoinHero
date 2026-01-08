import React, { useState, useEffect, useCallback } from 'react';
import { 
  RefreshCw, Zap, Wifi, WifiOff, Clock, Brain, TrendingUp, TrendingDown, 
  DollarSign, Activity, Target, Search, Play, Pause, BarChart3, 
  ChevronDown, X, AlertTriangle, CheckCircle2, Sparkles, LineChart,
  Layers, Shield, Flame, Eye, ArrowUpRight, ArrowDownRight
} from 'lucide-react';
import { supabase, signInWithGoogle, signOut, getUserSettings, saveUserSettings } from './supabase';
import AuthButton from './components/AuthButton';
import SettingsModal from './components/SettingsModal';
import AIDebatePanel from './components/AIDebatePanel';

// 프로덕션: Railway 백엔드, 개발: 로컬 프록시
const API_BASE = import.meta.env.PROD 
  ? 'https://coinhero-production.up.railway.app' 
  : '';

// 전략 정보
const STRATEGIES = [
  { id: 'max_profit', name: '수익률 최대화', emoji: '💎', risk: 'medium', desc: '5개 지표 동시 확인', icon: Sparkles, color: 'cyan' },
  { id: 'momentum_breakout', name: '모멘텀', emoji: '🚀', risk: 'high', desc: '5일 연속 상승 중인 강한 모멘텀', icon: TrendingUp, color: 'green' },
  { id: 'volatility_breakout', name: '골든크로스', emoji: '📈', risk: 'medium', desc: '5일 이동평균선이 20일 이평선 돌파', icon: LineChart, color: 'yellow' },
  { id: 'rsi_reversal', name: 'RSI 과매도', emoji: '📊', risk: 'medium', desc: 'RSI가 30 이하로 과매도 상태', icon: BarChart3, color: 'blue' },
  { id: 'larry_smash_day', name: '급락 반등', emoji: '💥', risk: 'high', desc: '당일 -5% 이상 급락 후 저점 반등', icon: Zap, color: 'red' },
  { id: 'volume_surge', name: '거래량 급증', emoji: '🔥', risk: 'high', desc: '20일 평균 거래량 대비 급증', icon: Flame, color: 'orange' },
  { id: 'larry_williams_r', name: 'Williams %R', emoji: '📉', risk: 'medium', desc: '%R -80 이하 과매도 반등', icon: Activity, color: 'purple' },
  { id: 'bollinger_bounce', name: '볼린저 반등', emoji: '📈', risk: 'low', desc: '볼린저 밴드 하단 터치 후 반등', icon: Layers, color: 'teal' },
  { id: 'larry_combo', name: '래리 종합', emoji: '🏆', risk: 'medium', desc: '변동성 + %R + 자금관리 결합', icon: Shield, color: 'gold' },
];

const RISK_COLORS = {
  low: { bg: 'bg-teal-500/20', text: 'text-teal-400', border: 'border-teal-500/30', label: '저위험' },
  medium: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30', label: '중위험' },
  high: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30', label: '고위험' },
};

function App() {
  const [balances, setBalances] = useState([]);
  const [krwBalance, setKrwBalance] = useState(0);
  const [totalValue, setTotalValue] = useState(0);
  const [trades, setTrades] = useState([]);
  const [aiLogs, setAiLogs] = useState([]);
  const [signals, setSignals] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date());
  
  // 인증 상태
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [userSettings, setUserSettings] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [authLoading, setAuthLoading] = useState(true);
  
  // 사용자별 데이터
  const [userBalances, setUserBalances] = useState([]);
  const [userTotalKRW, setUserTotalKRW] = useState(0);
  const [userTrades, setUserTrades] = useState([]);
  
  // AI 자동매매 상태
  const [isRunning, setIsRunning] = useState(false);
  const [selectedStrategies, setSelectedStrategies] = useState(['max_profit', 'momentum_breakout', 'rsi_reversal']);
  const [tradeAmount, setTradeAmount] = useState(10000);
  const [signalStrength, setSignalStrength] = useState(80);
  const [aiSellAnalysis, setAiSellAnalysis] = useState(true);
  const [budgetLimit, setBudgetLimit] = useState(false);
  const [scannedCoins, setScannedCoins] = useState(0);
  const [selectedAiModel, setSelectedAiModel] = useState('claude-opus-4.5');
  const [aiModels, setAiModels] = useState([]);
  const [positions, setPositions] = useState(0);
  const [maxPositions, setMaxPositions] = useState(3);
  
  // 시장 데이터
  const [btcPrice, setBtcPrice] = useState({ price: 0, change: 0 });
  const [ethPrice, setEthPrice] = useState({ price: 0, change: 0 });
  
  // 포지션 모니터링
  const [positionDetails, setPositionDetails] = useState([]);
  const [sellStrategyConfig, setSellStrategyConfig] = useState(null);

  // 인증 상태 감지
  useEffect(() => {
    // 현재 세션 확인
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      if (session?.user) {
        loadUserSettings(session.user.id);
        fetchUserData(session.access_token);
      }
      setAuthLoading(false);
    });

    // 인증 상태 변경 감지
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setUser(session?.user ?? null);
      if (session?.user) {
        loadUserSettings(session.user.id);
        fetchUserData(session.access_token);
      } else {
        setUserSettings(null);
        setUserBalances([]);
        setUserTotalKRW(0);
        setUserTrades([]);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  // 사용자별 데이터 조회
  const fetchUserData = async (accessToken) => {
    if (!accessToken) return;
    
    try {
      // 잔고 조회
      const balanceRes = await fetch(`${API_BASE}/api/user/balance`, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      const balanceData = await balanceRes.json();
      
      if (balanceData.auth_status === 'connected') {
        setUserBalances(balanceData.balances || []);
        setUserTotalKRW(balanceData.total_krw || 0);
      }
      
      // 거래 기록 조회
      const tradesRes = await fetch(`${API_BASE}/api/user/trades?limit=50`, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      const tradesData = await tradesRes.json();
      setUserTrades(tradesData.trades || []);
      
    } catch (err) {
      console.error('사용자 데이터 조회 실패:', err);
    }
  };

  // 주기적으로 사용자 데이터 갱신
  useEffect(() => {
    if (!session?.access_token) return;
    
    const interval = setInterval(() => {
      fetchUserData(session.access_token);
    }, 30000); // 30초마다 갱신
    
    return () => clearInterval(interval);
  }, [session]);

  // 사용자 설정 로드
  const loadUserSettings = async (userId) => {
    const { data, error } = await getUserSettings(userId);
    if (data) {
      setUserSettings(data);
      // 설정값 적용
      if (data.default_trade_amount) setTradeAmount(data.default_trade_amount);
      if (data.max_positions) setMaxPositions(data.max_positions);
    }
  };

  // 로그인 핸들러
  const handleLogin = async () => {
    await signInWithGoogle();
  };

  // 로그아웃 핸들러
  const handleLogout = async () => {
    await signOut();
    setUser(null);
    setUserSettings(null);
  };

  // 설정 저장 핸들러
  const handleSaveSettings = async (settings) => {
    if (!user) return;
    const { data, error } = await saveUserSettings(user.id, settings);
    if (error) throw error;
    setUserSettings(data);
    // 설정값 적용
    if (data.default_trade_amount) setTradeAmount(data.default_trade_amount);
    if (data.max_positions) setMaxPositions(data.max_positions);
  };

  // 시간 업데이트
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // API 호출 함수들
  const fetchBalances = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/balance`);
      const data = await res.json();
      console.log('💰 잔고 API 응답:', data);
      const balanceList = data.balances || [];
      setBalances(balanceList);
      setTotalValue(data.total_krw || 0);
      
      // KRW 잔고 찾기
      const krw = balanceList.find(b => b.currency === 'KRW');
      console.log('💵 KRW 잔고:', krw?.balance);
      setKrwBalance(krw?.balance || 0);
    } catch (e) {
      console.error('잔고 조회 실패:', e);
    }
  }, []);

  const fetchTrades = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ai-scalping/logs?limit=50`);
      const data = await res.json();
      setTrades(data.logs || []);
    } catch (e) {
      console.error('거래 기록 조회 실패:', e);
    }
  }, []);

  const fetchAIStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ai-scalping/status`);
      const data = await res.json();
      setIsRunning(data.is_running || false);
      setPositions(data.current_positions || 0);
      setMaxPositions(data.max_positions || 3);
      setScannedCoins(data.scanned_coins || 0);
      if (data.strategies && data.strategies.length > 0) {
        setSelectedStrategies(data.strategies);
      }
      if (data.ai_model) {
        setSelectedAiModel(data.ai_model);
      }
      if (data.available_models) {
        setAiModels(data.available_models);
      }
    } catch (e) {
      console.error('AI 상태 조회 실패:', e);
    }
  }, []);

  const changeAiModel = async (modelKey) => {
    try {
      await fetch(`${API_BASE}/api/ai-scalping/models/${modelKey}`, { method: 'POST' });
      setSelectedAiModel(modelKey);
    } catch (e) {
      console.error('모델 변경 실패:', e);
    }
  };

  const fetchMarketPrices = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/prices?tickers=KRW-BTC,KRW-ETH`);
      const data = await res.json();
      if (data['KRW-BTC']) {
        setBtcPrice({ 
          price: data['KRW-BTC'].trade_price || 0, 
          change: data['KRW-BTC'].signed_change_rate * 100 || 0 
        });
      }
      if (data['KRW-ETH']) {
        setEthPrice({ 
          price: data['KRW-ETH'].trade_price || 0, 
          change: data['KRW-ETH'].signed_change_rate * 100 || 0 
        });
      }
    } catch (e) {
      console.error('시세 조회 실패:', e);
    }
  }, []);

  const fetchPositionDetails = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ai-scalping/positions`);
      const data = await res.json();
      console.log('🔍 포지션 데이터:', data);
      setPositionDetails(data.positions || []);
      if (data.sell_strategy_config) {
        setSellStrategyConfig(data.sell_strategy_config);
      }
    } catch (e) {
      console.error('포지션 상세 조회 실패:', e);
    }
  }, []);

  // AI 자동매매 제어
  const startTrading = async () => {
    try {
      await fetch(`${API_BASE}/api/ai-scalping/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategies: selectedStrategies,
          trade_amount: tradeAmount,
          max_positions: maxPositions
        })
      });
      await fetch(`${API_BASE}/api/ai-scalping/start`, { method: 'POST' });
      setIsRunning(true);
    } catch (e) {
      console.error('시작 실패:', e);
    }
  };

  const stopTrading = async () => {
    try {
      await fetch(`${API_BASE}/api/ai-scalping/stop`, { method: 'POST' });
      setIsRunning(false);
    } catch (e) {
      console.error('중지 실패:', e);
    }
  };

  // 즉시 스캔 - AI 분석 포함
  const handleManualScan = async () => {
    try {
      console.log('🔍 즉시 스캔 시작...');
      const res = await fetch(`${API_BASE}/api/scalping/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      console.log('📊 스캔 결과:', data);
      // 스캔 후 상태 업데이트
      await fetchAIStatus();
      await fetchAILogs();
      await fetchPositionDetails();
    } catch (e) {
      console.error('스캔 실패:', e);
    }
  };

  const toggleStrategy = (strategyId) => {
    setSelectedStrategies(prev => 
      prev.includes(strategyId) 
        ? prev.filter(s => s !== strategyId)
        : [...prev, strategyId]
    );
  };

  // WebSocket 연결
  useEffect(() => {
    let ws;
    let reconnectTimeout;

    const connect = () => {
      // 프로덕션: Railway WSS, 개발: 로컬 WS
      const wsUrl = import.meta.env.PROD
        ? 'wss://coinhero-production.up.railway.app/ws'
        : `ws://${window.location.hostname}:8000/ws`;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'balances') {
          setBalances(data.data);
        } else if (data.type === 'trade' || data.type === 'ai_scalping_trade') {
          fetchTrades();
          fetchBalances();
        } else if (data.type === 'signal') {
          setSignals(prev => [data.data, ...prev].slice(0, 10));
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        reconnectTimeout = setTimeout(connect, 3000);
      };
    };

    connect();
    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [fetchTrades, fetchBalances]);

  // 초기 데이터 로드
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchBalances(),
        fetchTrades(),
        fetchAIStatus(),
        fetchMarketPrices(),
        fetchPositionDetails(),
      ]);
      setLoading(false);
    };
    loadData();

    const interval = setInterval(() => {
      fetchBalances();
      fetchTrades();
      fetchAIStatus();
      fetchMarketPrices();
      fetchPositionDetails();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchBalances, fetchTrades, fetchAIStatus, fetchMarketPrices, fetchPositionDetails]);

  // 보유 코인 (KRW 제외)
  const heldCoins = balances.filter(b => b.currency !== 'KRW' && b.balance > 0);

  // AI 활동 로그 (최근 거래에서 추출)
  const aiActivities = trades.slice(0, 10).map(t => ({
    type: t.action === 'buy' ? '매수' : '매도',
    time: new Date(t.timestamp),
    message: `${t.coin_name} ${t.action === 'buy' ? '매수' : '매도'} - ${t.ai_reason || '전략 실행'}`,
    strategy: t.strategy
  }));

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      
      {/* ========== 상단 헤더 ========== */}
      <header className="bg-[#12121a] border-b border-gray-800 px-4 py-3">
        <div className="max-w-[1800px] mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Zap className="w-6 h-6 text-cyan-400" />
            <h1 className="text-xl font-bold">AI 자동매매</h1>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              isRunning ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
            }`}>
              {isRunning ? '● 실행중' : '○ 대기중'}
            </span>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-[#1a1a2e] px-4 py-2 rounded-lg">
              <Clock className="w-4 h-4 text-gray-400" />
              <span className="text-lg font-mono font-bold">
                {currentTime.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              <span className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${
                isConnected ? 'bg-cyan-500/20 text-cyan-400' : 'bg-red-500/20 text-red-400'
              }`}>
                {isConnected ? '연결됨' : '오프라인'}
              </span>
            </div>
            <button 
              onClick={() => { fetchBalances(); fetchTrades(); fetchAIStatus(); fetchMarketPrices(); }}
              className="flex items-center gap-2 px-3 py-2 bg-[#1a1a2e] hover:bg-[#252538] rounded-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              <span className="text-sm">새로고침</span>
            </button>
            
            {/* 로그인/사용자 버튼 */}
            <AuthButton 
              user={user}
              onLogin={handleLogin}
              onLogout={handleLogout}
              onSettings={() => setShowSettings(true)}
            />
          </div>
        </div>
      </header>
      
      {/* 설정 모달 */}
      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        user={user}
        settings={userSettings}
        onSave={handleSaveSettings}
        session={session}
      />

      {/* ========== 시장 지수 바 ========== */}
      <div className="bg-[#12121a] border-b border-gray-800 px-4 py-3">
        <div className="max-w-[1800px] mx-auto grid grid-cols-4 gap-4">
          {/* BTC */}
          <div className="bg-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-400 text-sm">BTC</span>
              <LineChart className="w-4 h-4 text-gray-500" />
            </div>
            <div className="text-2xl font-bold">{(btcPrice.price / 1000000).toFixed(1)}M</div>
            <div className={`text-sm font-medium ${btcPrice.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {btcPrice.change >= 0 ? '+' : ''}{btcPrice.change.toFixed(2)}%
            </div>
          </div>
          
          {/* ETH */}
          <div className="bg-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-400 text-sm">ETH</span>
              <LineChart className="w-4 h-4 text-gray-500" />
            </div>
            <div className="text-2xl font-bold">{(ethPrice.price / 1000000).toFixed(2)}M</div>
            <div className={`text-sm font-medium ${ethPrice.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {ethPrice.change >= 0 ? '+' : ''}{ethPrice.change.toFixed(2)}%
            </div>
          </div>
          
          {/* 예수금 (로그인 시에만 표시) */}
          <div className="bg-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-400 text-sm">내 예수금</span>
              <DollarSign className="w-4 h-4 text-gray-500" />
            </div>
            <div className="text-2xl font-bold">
              {user 
                ? ((userBalances.length > 0 
                    ? userBalances.find(b => b.currency === 'KRW')?.balance 
                    : krwBalance) || 0).toLocaleString()
                : <span className="text-gray-500 text-base">로그인 필요</span>}
              {user && <span className="text-sm text-gray-400 ml-1">원</span>}
            </div>
          </div>
          
          {/* 총 평가금액 (로그인 시에만 표시) */}
          <div className="bg-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-400 text-sm">내 총 평가</span>
              <Target className="w-4 h-4 text-gray-500" />
            </div>
            <div className="text-2xl font-bold text-cyan-400">
              {user 
                ? ((userTotalKRW > 0 ? userTotalKRW : totalValue) || 0).toLocaleString()
                : <span className="text-gray-500 text-base">로그인 필요</span>}
              {user && <span className="text-sm text-gray-400 ml-1">원</span>}
            </div>
          </div>
        </div>
      </div>

      {/* ========== 사용자 계좌 정보 (로그인 시) ========== */}
      {user && userBalances.length > 0 && (
        <div className="bg-[#12121a] border-b border-gray-800 px-4 py-4">
          <div className="max-w-[1800px] mx-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-green-400" />
                내 보유 코인
              </h3>
              <button 
                onClick={() => fetchUserData(session?.access_token)}
                className="text-sm text-gray-400 hover:text-white flex items-center gap-1"
              >
                <RefreshCw className="w-4 h-4" />
                새로고침
              </button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {userBalances.filter(b => b.currency !== 'KRW' && b.eval_amount > 1000).map((coin) => (
                <div key={coin.currency} className="bg-[#1a1a2e] rounded-xl p-3 border border-gray-800 hover:border-cyan-500/30 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-white">{coin.currency}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      coin.profit_rate > 0 ? 'bg-green-500/20 text-green-400' :
                      coin.profit_rate < 0 ? 'bg-red-500/20 text-red-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                      {coin.profit_rate > 0 ? '+' : ''}{coin.profit_rate?.toFixed(2)}%
                    </span>
                  </div>
                  <div className="text-sm text-gray-400">
                    {coin.eval_amount?.toLocaleString()}원
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    평균가: {coin.avg_buy_price?.toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ========== 거래 로그 (로그인 시) ========== */}
      {user && userTrades.length > 0 && (
        <div className="bg-[#12121a] border-b border-gray-800 px-4 py-4">
          <div className="max-w-[1800px] mx-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Activity className="w-5 h-5 text-cyan-400" />
                최근 거래 내역
              </h3>
              <span className="text-sm text-gray-400">{userTrades.length}건</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-800">
                    <th className="text-left py-2 px-3">시간</th>
                    <th className="text-left py-2 px-3">종목</th>
                    <th className="text-left py-2 px-3">유형</th>
                    <th className="text-right py-2 px-3">가격</th>
                    <th className="text-right py-2 px-3">금액</th>
                    <th className="text-right py-2 px-3">수익률</th>
                    <th className="text-left py-2 px-3">전략</th>
                  </tr>
                </thead>
                <tbody>
                  {userTrades.slice(0, 10).map((trade, idx) => (
                    <tr key={idx} className="border-b border-gray-800/50 hover:bg-[#1a1a2e]">
                      <td className="py-2 px-3 text-gray-400">
                        {trade.executed_at ? new Date(trade.executed_at).toLocaleString('ko-KR', { 
                          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' 
                        }) : '-'}
                      </td>
                      <td className="py-2 px-3 font-medium text-white">
                        {trade.market?.replace('KRW-', '') || '-'}
                      </td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          trade.trade_type === 'buy' 
                            ? 'bg-green-500/20 text-green-400' 
                            : 'bg-red-500/20 text-red-400'
                        }`}>
                          {trade.trade_type === 'buy' ? '매수' : '매도'}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right text-gray-300">
                        {trade.price?.toLocaleString() || '-'}
                      </td>
                      <td className="py-2 px-3 text-right text-gray-300">
                        {trade.amount?.toLocaleString() || '-'}원
                      </td>
                      <td className={`py-2 px-3 text-right font-medium ${
                        (trade.profit_rate || 0) > 0 ? 'text-green-400' :
                        (trade.profit_rate || 0) < 0 ? 'text-red-400' : 'text-gray-400'
                      }`}>
                        {trade.profit_rate ? `${trade.profit_rate > 0 ? '+' : ''}${trade.profit_rate.toFixed(2)}%` : '-'}
                      </td>
                      <td className="py-2 px-3 text-gray-400 text-xs">
                        {trade.strategy || trade.ai_model || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========== 메인 컨텐츠 ========== */}
      <div className="max-w-[1800px] mx-auto p-4">
        
        {/* AI 자동매매 컨트롤 패널 */}
        <div className="bg-gradient-to-r from-[#1a1a2e] to-[#16162a] rounded-2xl p-6 mb-6 border border-cyan-500/20">
          <div className="flex items-start justify-between mb-6">
            {/* 좌측: AI 정보 */}
            <div className="flex items-center gap-6">
              <div className={`w-16 h-16 rounded-2xl flex items-center justify-center ${
                selectedAiModel.includes('claude') ? 'bg-gradient-to-br from-purple-500 to-violet-600' :
                selectedAiModel.includes('gpt') ? 'bg-gradient-to-br from-green-500 to-emerald-600' :
                'bg-gradient-to-br from-blue-500 to-cyan-600'
              }`}>
                <Brain className="w-8 h-8 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold mb-1">AI 자동매매</h2>
                {/* AI 모델 선택 드롭다운 */}
                <select 
                  value={selectedAiModel}
                  onChange={(e) => changeAiModel(e.target.value)}
                  className="bg-[#252538] border border-cyan-500/30 rounded-lg px-3 py-1 text-sm text-cyan-400 font-mono cursor-pointer hover:border-cyan-500/50"
                >
                  <option value="claude-opus-4.5">🟣 Claude Opus 4.5</option>
                  <option value="gpt-5.2">🟢 GPT 5.2</option>
                  <option value="gemini-3">🔵 Gemini 3</option>
                  <option value="gemini-3-flash">⚡ Gemini 3 Flash</option>
                </select>
                <div className="flex items-center gap-6 mt-2 text-sm text-gray-400">
                  <span><Activity className="w-4 h-4 inline mr-1" />{scannedCoins.toLocaleString()}개 종목</span>
                  <span><Zap className="w-4 h-4 inline mr-1" />{selectedStrategies.length}개 전략</span>
                  <span><DollarSign className="w-4 h-4 inline mr-1" />{tradeAmount.toLocaleString()}원/회</span>
                </div>
              </div>
            </div>
            
            {/* 우측: 액션 버튼들 */}
            <div className="flex items-center gap-3">
              <button 
                onClick={handleManualScan}
                className="px-4 py-3 bg-[#252538] hover:bg-[#2d2d45] rounded-xl flex items-center gap-2 transition-colors"
              >
                <Search className="w-4 h-4" />
                <span>즉시 스캔</span>
              </button>
              <button className="px-4 py-3 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-xl flex items-center gap-2 transition-colors">
                <BarChart3 className="w-4 h-4" />
                <span>일간 최대화</span>
              </button>
              <button 
                onClick={startTrading}
                disabled={isRunning}
                className="px-4 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 disabled:opacity-50 rounded-xl flex items-center gap-2 transition-all"
              >
                <Sparkles className="w-4 h-4" />
                <span>수익률 최대화</span>
              </button>
              <button 
                onClick={isRunning ? stopTrading : startTrading}
                className={`px-4 py-3 rounded-xl flex items-center gap-2 transition-all ${
                  isRunning 
                    ? 'bg-red-500/20 hover:bg-red-500/30 text-red-400' 
                    : 'bg-green-500/20 hover:bg-green-500/30 text-green-400'
                }`}
              >
                {isRunning ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                <span>{isRunning ? '중지' : '시작'}</span>
              </button>
            </div>
          </div>
          
          {/* 하단: 설정 옵션들 */}
          <div className="flex items-center justify-between pt-4 border-t border-gray-700/50">
            <div className="flex items-center gap-6">
              {/* 1회 거래금액 */}
              <div className="flex items-center gap-2">
                <span className="text-gray-400 text-sm">1회 거래:</span>
                <select 
                  value={tradeAmount}
                  onChange={(e) => setTradeAmount(Number(e.target.value))}
                  className="bg-[#252538] border border-gray-700 rounded-lg px-3 py-1.5 text-sm"
                >
                  <option value={10000}>1만원</option>
                  <option value={50000}>5만원</option>
                  <option value={100000}>10만원</option>
                  <option value={500000}>50만원</option>
                </select>
              </div>
              
              {/* 신호 강도 */}
              <div className="flex items-center gap-3">
                <span className="text-gray-400 text-sm">신호 강도:</span>
                <input 
                  type="range" 
                  min="50" 
                  max="100" 
                  value={signalStrength}
                  onChange={(e) => setSignalStrength(Number(e.target.value))}
                  className="w-24 accent-cyan-500"
                />
                <span className="text-cyan-400 font-bold">{signalStrength}+</span>
              </div>
            </div>
            
            <div className="flex items-center gap-6">
              {/* AI 매도 분석 */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={aiSellAnalysis}
                  onChange={(e) => setAiSellAnalysis(e.target.checked)}
                  className="w-4 h-4 accent-cyan-500"
                />
                <span className="text-sm text-gray-300">AI 매도 분석</span>
              </label>
              
              {/* 예산 제한 */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={budgetLimit}
                  onChange={(e) => setBudgetLimit(e.target.checked)}
                  className="w-4 h-4 accent-cyan-500"
                />
                <span className="text-sm text-gray-300">예산 제한</span>
              </label>
            </div>
          </div>
        </div>

        {/* ========== 매매 전략 선택 ========== */}
        <div className="bg-[#12121a] rounded-2xl p-6 mb-6 border border-gray-800">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Layers className="w-5 h-5 text-gray-400" />
              <h3 className="text-lg font-bold">매매 전략 선택</h3>
              <span className="text-gray-500 text-sm">클릭하여 선택/해제</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-cyan-400 text-sm font-medium">{selectedStrategies.length}개 선택됨</span>
              <button 
                onClick={() => setSelectedStrategies([])}
                className="text-gray-500 hover:text-gray-300 text-sm"
              >
                전체 해제
              </button>
            </div>
          </div>
          
          {/* 현재 선택된 전략들 */}
          {selectedStrategies.length > 0 && (
            <div className="flex items-center gap-2 mb-4 flex-wrap">
              <span className="text-gray-400 text-sm">✓ 현재 선택:</span>
              {selectedStrategies.map(stratId => {
                const strat = STRATEGIES.find(s => s.id === stratId);
                if (!strat) return null;
                return (
                  <span 
                    key={stratId}
                    className="px-3 py-1 bg-cyan-500/20 text-cyan-400 rounded-full text-sm flex items-center gap-1"
                  >
                    {strat.emoji} {strat.name}
                    <X 
                      className="w-3 h-3 cursor-pointer hover:text-white" 
                      onClick={() => toggleStrategy(stratId)}
                    />
                  </span>
                );
              })}
            </div>
          )}
          
          {/* 전략 카드 그리드 */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {STRATEGIES.map(strategy => {
              const isSelected = selectedStrategies.includes(strategy.id);
              const risk = RISK_COLORS[strategy.risk];
              const Icon = strategy.icon;
              
              return (
                <button
                  key={strategy.id}
                  onClick={() => toggleStrategy(strategy.id)}
                  className={`relative p-4 rounded-xl border-2 transition-all text-left ${
                    isSelected 
                      ? 'border-cyan-500 bg-cyan-500/10' 
                      : 'border-gray-700 bg-[#1a1a2e] hover:border-gray-600'
                  }`}
                >
                  {/* 위험도 뱃지 */}
                  <span className={`absolute top-2 right-2 px-2 py-0.5 rounded text-[10px] font-medium ${risk.bg} ${risk.text}`}>
                    {risk.label}
                  </span>
                  
                  {/* 선택 체크 */}
                  {isSelected && (
                    <div className="absolute bottom-2 right-2 w-5 h-5 bg-cyan-500 rounded-full flex items-center justify-center">
                      <CheckCircle2 className="w-3 h-3 text-white" />
                    </div>
                  )}
                  
                  <div className="w-10 h-10 bg-[#252538] rounded-xl flex items-center justify-center mb-3">
                    <Icon className={`w-5 h-5 ${isSelected ? 'text-cyan-400' : 'text-gray-400'}`} />
                  </div>
                  <h4 className="font-bold text-sm mb-1">{strategy.name}</h4>
                  <p className="text-xs text-gray-500 line-clamp-2">{strategy.desc}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* ========== 🎭 AI 3대장 토론 ========== */}
        <div className="mb-4">
          <AIDebatePanel />
        </div>

        {/* ========== 📊 포지션 모니터링 (이동됨) ========== */}
        <div className="bg-[#12121a] rounded-2xl p-6 border border-gray-800 mb-4">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-purple-500/20 rounded-xl">
                <Eye className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <h3 className="text-xl font-bold">포지션 모니터링</h3>
                <p className="text-xs text-gray-500">Position Monitor & Sell Strategy</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 bg-purple-500/10 rounded-full text-xs font-bold text-purple-400">
                {positionDetails.length}개 포지션
              </span>
              <span className="px-2 py-1 bg-cyan-500/10 rounded-full text-[10px] text-cyan-400">
                AI {positionDetails.filter(p => p.is_ai_managed).length}
              </span>
              <span className="px-2 py-1 bg-gray-500/10 rounded-full text-[10px] text-gray-400">
                수동 {positionDetails.filter(p => !p.is_ai_managed).length}
              </span>
              <button 
                onClick={fetchPositionDetails}
                className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
              >
                <RefreshCw className="w-4 h-4 text-gray-500" />
              </button>
            </div>
          </div>

          {/* 매도 전략 설정 */}
          {sellStrategyConfig && (
            <div className="mb-6 p-4 bg-[#1a1a2e] rounded-xl border border-gray-800">
              <div className="flex items-center gap-2 mb-3">
                <Shield className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold text-gray-400">매도 전략 설정</span>
              </div>
              <div className="grid grid-cols-5 gap-3 text-center text-xs">
                <div className="bg-[#0a0a0f] rounded-lg p-2">
                  <p className="text-red-400 font-bold">손절선</p>
                  <p className="font-mono text-red-400">{sellStrategyConfig.stop_loss_pct}%</p>
                </div>
                <div className="bg-[#0a0a0f] rounded-lg p-2">
                  <p className="text-yellow-400 font-bold">목표 수익</p>
                  <p className="font-mono text-yellow-400">+{sellStrategyConfig.target_profit}%</p>
                </div>
                <div className="bg-[#0a0a0f] rounded-lg p-2">
                  <p className="text-cyan-400 font-bold">AI 분석</p>
                  <p className="font-mono text-cyan-400">+{sellStrategyConfig.min_profit_for_ai_analysis}%</p>
                </div>
                <div className="bg-[#0a0a0f] rounded-lg p-2">
                  <p className="text-green-400 font-bold">트레일링</p>
                  <p className="font-mono text-green-400">+{sellStrategyConfig.min_profit_for_trailing}%</p>
                </div>
                <div className="bg-[#0a0a0f] rounded-lg p-2">
                  <p className="text-gray-400 font-bold">최소 보유</p>
                  <p className="font-mono text-gray-300">{sellStrategyConfig.min_holding_seconds / 60}분</p>
                </div>
              </div>
            </div>
          )}

          {/* 포지션 카드 그리드 */}
          {positionDetails.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {positionDetails.map((pos, idx) => {
                const statusColors = {
                  red: 'border-red-500/50 bg-red-500/5',
                  gold: 'border-yellow-500/50 bg-yellow-500/5',
                  green: 'border-green-500/50 bg-green-500/5',
                  cyan: 'border-cyan-500/50 bg-cyan-500/5',
                  orange: 'border-orange-500/50 bg-orange-500/5',
                  gray: 'border-gray-600/50 bg-gray-800/20'
                };
                const profitColor = pos.profit_rate >= 0 ? 'text-green-400' : 'text-red-400';
                const isManual = !pos.is_ai_managed;
                
                return (
                  <div 
                    key={idx} 
                    className={`rounded-xl p-4 border-2 ${statusColors[pos.status_color] || 'border-gray-700 bg-[#1a1a2e]'}`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <div className={`w-10 h-10 ${isManual ? 'bg-gray-600/20' : 'bg-purple-500/20'} rounded-lg flex items-center justify-center`}>
                          <span className={`text-sm font-bold ${isManual ? 'text-gray-400' : 'text-purple-400'}`}>{pos.coin_name?.slice(0, 3)}</span>
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-bold">{pos.coin_name}</p>
                            <span className={`text-[8px] px-1.5 py-0.5 rounded ${isManual ? 'bg-gray-600/30 text-gray-400' : 'bg-cyan-500/30 text-cyan-400'}`}>
                              {isManual ? '수동' : 'AI'}
                            </span>
                          </div>
                          <p className="text-[10px] text-gray-500">{pos.ticker}</p>
                        </div>
                      </div>
                      <span className="text-xs px-2 py-1 rounded-lg bg-[#0a0a0f]">{pos.status}</span>
                    </div>
                    
                    <div className="text-center py-3 mb-3 bg-[#0a0a0f] rounded-lg">
                      <p className={`text-3xl font-bold ${profitColor}`}>
                        {pos.profit_rate >= 0 ? '+' : ''}{pos.profit_rate}%
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        최고: <span className="text-cyan-400">+{pos.max_profit}%</span>
                      </p>
                    </div>
                    
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between">
                        <span className="text-gray-500">매수가</span>
                        <span className="font-mono">₩{pos.entry_price?.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">현재가</span>
                        <span className={`font-mono ${profitColor}`}>₩{pos.current_price?.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">보유 시간</span>
                        <span className="font-mono">{pos.holding_time}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">투자 금액</span>
                        <span className="font-mono">₩{Math.round(pos.invest_amount || 0).toLocaleString()}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 bg-[#1a1a2e] rounded-xl border border-gray-800">
              <Eye className="w-12 h-12 text-gray-700 mx-auto mb-3" />
              <p className="text-gray-500 font-medium">보유 중인 종목이 없습니다</p>
              <p className="text-xs text-gray-600 mt-1">자동매매가 활성화되면 매수한 종목이 여기에 표시됩니다</p>
            </div>
          )}
        </div>

        {/* ========== 하단 3분할 ========== */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          
          {/* 실시간 AI 활동 */}
          <div className="bg-[#12121a] rounded-2xl p-4 border border-gray-800">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-cyan-400" />
                <h3 className="font-bold">실시간 AI 활동</h3>
              </div>
              <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs font-medium animate-pulse">
                ● LIVE
              </span>
            </div>
            
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {aiActivities.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Brain className="w-10 h-10 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">AI 활동 대기중...</p>
                </div>
              ) : (
                aiActivities.map((activity, idx) => (
                  <div key={idx} className="flex items-start gap-3 p-3 bg-[#1a1a2e] rounded-lg">
                    <div className={`mt-1 w-2 h-2 rounded-full ${
                      activity.type === '매수' ? 'bg-green-400' : 'bg-red-400'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                          activity.type === '매수' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                        }`}>
                          {activity.type}
                        </span>
                        <span className="text-xs text-gray-500">
                          {activity.time.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-sm text-gray-300 mt-1 truncate">{activity.message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
          
          {/* 발견된 신호 */}
          <div className="bg-[#12121a] rounded-2xl p-4 border border-gray-800">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Zap className="w-5 h-5 text-yellow-400" />
                <h3 className="font-bold">발견된 신호</h3>
              </div>
              <span className="text-gray-500 text-sm">{signals.length}개</span>
            </div>
            
            {signals.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Search className="w-10 h-10 mx-auto mb-2 opacity-30" />
                <p className="text-sm">발견된 신호가 없습니다</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {signals.map((signal, idx) => (
                  <div key={idx} className="p-3 bg-[#1a1a2e] rounded-lg border border-yellow-500/20">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-yellow-400">{signal.coin_name}</span>
                      <span className="text-xs text-gray-400">{signal.strategy}</span>
                    </div>
                    <p className="text-sm text-gray-400 mt-1">{signal.reason}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* 보유 종목 */}
          <div className="bg-[#12121a] rounded-2xl p-4 border border-gray-800">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Target className="w-5 h-5 text-purple-400" />
                <h3 className="font-bold">보유 종목</h3>
              </div>
              <span className="text-gray-500 text-sm">{heldCoins.length}종목</span>
            </div>
            
            {heldCoins.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <DollarSign className="w-10 h-10 mx-auto mb-2 opacity-30" />
                <p className="text-sm">보유 종목이 없습니다</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {heldCoins.map((coin, idx) => {
                  const profitRate = coin.profit_rate || 0;
                  const isProfit = profitRate >= 0;
                  
                  return (
                    <div key={idx} className="flex items-center justify-between p-3 bg-[#1a1a2e] rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-purple-500/20 rounded-lg flex items-center justify-center">
                          <span className="text-xs font-bold text-purple-400">{coin.currency?.slice(0, 2)}</span>
                        </div>
                        <div>
                          <span className="font-medium text-sm">{coin.currency}</span>
                          {coin.ai_managed && (
                            <span className="ml-1 text-[10px] bg-cyan-500/20 text-cyan-400 px-1 rounded">AI</span>
                          )}
                          <p className="text-xs text-gray-500">{coin.balance?.toFixed(4)}개</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                          {isProfit ? '+' : ''}{profitRate.toFixed(2)}%
                        </p>
                        <p className={`text-xs ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                          {isProfit ? '+' : ''}{(coin.profit || 0).toLocaleString()}원
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ========== 푸터 ========== */}
      <footer className="bg-[#12121a] border-t border-gray-800 px-4 py-4 mt-8">
        <div className="max-w-[1800px] mx-auto text-center text-gray-600 text-xs">
          <p>⚠️ 자동거래는 투자 손실의 위험이 있습니다. 신중하게 사용하세요.</p>
          <p className="mt-1">CoinHero v2.0.0 | Powered by Upbit API & Claude AI</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
