import React, { useState, useEffect, useCallback } from 'react';
import { 
  RefreshCw, Zap, Wifi, WifiOff, Clock, Brain, TrendingUp, TrendingDown, 
  DollarSign, Activity, Target, Search, Play, Pause, BarChart3, 
  ChevronDown, X, AlertTriangle, CheckCircle2, CheckCircle, AlertCircle, Sparkles, LineChart,
  Layers, Shield, Flame, Eye, ArrowUpRight, ArrowDownRight
} from 'lucide-react';
import { supabase, signInWithGoogle, signOut, getUserSettings, saveUserSettings } from './supabase';
import AuthButton from './components/AuthButton';
import SettingsModal from './components/SettingsModal';
import AIDebatePanel from './components/AIDebatePanel';
import AccountInfo from './components/AccountInfo';
import UpbitSettingsModal from './components/UpbitSettingsModal';

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
  
  // 업비트 설정 모달
  const [showUpbitSettings, setShowUpbitSettings] = useState(false);
  
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
  const [noTradeLimit, setNoTradeLimit] = useState(false);  // 1회 거래 제한 없음
  const [noSignalLimit, setNoSignalLimit] = useState(false);  // 신호강도 제한 없음
  const [noBudgetLimit, setNoBudgetLimit] = useState(false);  // 현금보유 한도 없음
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
  
  // AI 수익률 최대화 스캔
  const [maxProfitScanning, setMaxProfitScanning] = useState(false);
  const [maxProfitResult, setMaxProfitResult] = useState(null);
  const [showMaxProfitModal, setShowMaxProfitModal] = useState(false);
  const [showAlgorithmInfo, setShowAlgorithmInfo] = useState(false);
  const [buyElapsedTime, setBuyElapsedTime] = useState(0);
  
  // AI 자동 매수/매도 연속 실행
  const [autoBuyEnabled, setAutoBuyEnabled] = useState(false);
  const [autoSellEnabled, setAutoSellEnabled] = useState(false);
  
  // AI 수익률 최대화 매도
  const [sellScanning, setSellScanning] = useState(false);
  const [sellResult, setSellResult] = useState(null);
  const [showSellModal, setShowSellModal] = useState(false);
  const [sellElapsedTime, setSellElapsedTime] = useState(0);
  
  // 매수/매도 실행 로그
  const [buyLogs, setBuyLogs] = useState([]);
  const [sellLogs, setSellLogs] = useState([]);
  
  // AI 자동 분석 (30초마다)
  const [aiAutoEnabled, setAiAutoEnabled] = useState(false);
  const [aiBuyThoughts, setAiBuyThoughts] = useState([]);
  const [aiSellThoughts, setAiSellThoughts] = useState([]);
  const [aiAnalyzing, setAiAnalyzing] = useState(false);
  const [lastAnalysisTime, setLastAnalysisTime] = useState(null);

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
      const balanceList = data.balances || [];
      setBalances(balanceList);
      setTotalValue(data.total_krw || 0);
      
      // KRW 잔고 찾기
      const krw = balanceList.find(b => b.currency === 'KRW');
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

  // 🧠 AI 자율 전략 스캔 - AI가 직접 전략 설계 (백그라운드 실행)
  const runMaxProfitScan = async () => {
    setMaxProfitScanning(true);
    setBuyElapsedTime(0);
    
    // 로그 추가 - 시작
    const startTime = new Date();
    setBuyLogs(prev => [{
      id: Date.now(),
      time: startTime.toLocaleTimeString('ko-KR'),
      status: 'running',
      message: 'AI 3대장 매수 분석 시작...',
      details: null
    }, ...prev.slice(0, 9)]);
    
    // 타이머 시작
    const timerInterval = setInterval(() => {
      setBuyElapsedTime(prev => prev + 1);
    }, 1000);
    
    try {
      console.log('🧠 AI 3대장 전 종목 스캔 시작...');
      
      // 무제한 설정 적용
      const amount = noTradeLimit ? 0 : tradeAmount; // 0이면 백엔드에서 전액 투자
      const minConfidence = noSignalLimit ? 0 : 70; // 0이면 모든 신호 허용
      
      // AI 3대장이 직접 전략을 설계하고 최적의 종목을 선정 (전 종목 대상)
      const res = await fetch(`${API_BASE}/api/ai-max-profit/ai-scan?amount=${amount}&top_n=200&no_trade_limit=${noTradeLimit}&no_signal_limit=${noSignalLimit}&no_budget_limit=${noBudgetLimit}&min_confidence=${minConfidence}`, {
        method: 'POST'
      });
      const data = await res.json();
      
      const endTime = new Date();
      const duration = Math.round((endTime - startTime) / 1000);
      
      // 매수 결과 알림 및 로그 추가
      if (data.bought && data.bought.length > 0) {
        setBuyLogs(prev => [{
          id: Date.now(),
          time: endTime.toLocaleTimeString('ko-KR'),
          status: 'success',
          message: `✅ ${data.bought.length}개 매수 완료 (${duration}초)`,
          details: data.bought.map(b => `${b.ticker?.replace('KRW-', '')} (${b.votes}/3 동의)`).join(', ')
        }, ...prev.slice(0, 9)]);
        fetchTrades();
        fetchPositionDetails();
        fetchBalances();
      } else {
        setBuyLogs(prev => [{
          id: Date.now(),
          time: endTime.toLocaleTimeString('ko-KR'),
          status: 'info',
          message: `📊 분석 완료 - 매수 조건 미충족 (${duration}초)`,
          details: data.top_picks ? `관심종목: ${data.top_picks.slice(0, 3).map(p => p.ticker?.replace('KRW-', '')).join(', ')}` : null
        }, ...prev.slice(0, 9)]);
      }
      
      setMaxProfitResult(data);
    } catch (e) {
      console.error('AI 자율 스캔 실패:', e);
      setBuyLogs(prev => [{
        id: Date.now(),
        time: new Date().toLocaleTimeString('ko-KR'),
        status: 'error',
        message: `❌ 오류 발생: ${e.message}`,
        details: null
      }, ...prev.slice(0, 9)]);
    } finally {
      clearInterval(timerInterval);
      setMaxProfitScanning(false);
    }
  };
  
  // 알고리즘 정보 조회
  const showAlgorithmDetails = async () => {
    setShowAlgorithmInfo(true);
  };

  // 🤖 AI 자율 매도 알고리즘
  const runSellScan = async () => {
    setSellScanning(true);
    setShowSellModal(true);
    setSellResult(null);
    setSellElapsedTime(0);
    
    // 로그 추가 - 시작
    const startTime = new Date();
    setSellLogs(prev => [{
      id: Date.now(),
      time: startTime.toLocaleTimeString('ko-KR'),
      status: 'running',
      message: 'AI 3대장 매도 분석 시작...',
      details: null
    }, ...prev.slice(0, 9)]);
    
    // 타이머 시작
    const timerInterval = setInterval(() => {
      setSellElapsedTime(prev => prev + 1);
    }, 1000);
    
    try {
      // 새로운 AI 자율 매도 API 사용
      const res = await fetch(`${API_BASE}/api/ai-max-profit/ai-sell?min_confidence=60&auto_execute=true`, {
        method: 'POST'
      });
      const data = await res.json();
      setSellResult(data);
      
      const endTime = new Date();
      const duration = Math.round((endTime - startTime) / 1000);
      
      // 매도가 완료되면 데이터 새로고침 및 로그 추가
      if (data.sold && data.sold.length > 0) {
        const totalProfit = data.sold.reduce((sum, s) => sum + (s.value * s.profit_rate / 100), 0);
        setSellLogs(prev => [{
          id: Date.now(),
          time: endTime.toLocaleTimeString('ko-KR'),
          status: 'success',
          message: `✅ ${data.sold.length}개 매도 완료 (${duration}초)`,
          details: data.sold.map(s => `${s.currency} (${s.profit_rate >= 0 ? '+' : ''}${s.profit_rate?.toFixed(1)}%)`).join(', ')
        }, ...prev.slice(0, 9)]);
        fetchTrades();
        fetchPositionDetails();
        fetchBalances();
      } else {
        setSellLogs(prev => [{
          id: Date.now(),
          time: endTime.toLocaleTimeString('ko-KR'),
          status: 'info',
          message: `📊 분석 완료 - 매도 조건 미충족 (${duration}초)`,
          details: data.kept ? `보유 유지: ${data.kept.length}개` : null
        }, ...prev.slice(0, 9)]);
      }
    } catch (e) {
      console.error('AI 매도 분석 실패:', e);
      setSellResult({ error: e.message });
      setSellLogs(prev => [{
        id: Date.now(),
        time: new Date().toLocaleTimeString('ko-KR'),
        status: 'error',
        message: `❌ 오류 발생: ${e.message}`,
        details: null
      }, ...prev.slice(0, 9)]);
    } finally {
      clearInterval(timerInterval);
      setSellScanning(false);
    }
  };

  const toggleStrategy = (strategyId) => {
    setSelectedStrategies(prev => 
      prev.includes(strategyId) 
        ? prev.filter(s => s !== strategyId)
        : [...prev, strategyId]
    );
  };

  // AI 자동 분석 함수 (30초마다 실행)
  const runAiAutoAnalysis = async () => {
    if (aiAnalyzing) return;
    
    setAiAnalyzing(true);
    const now = new Date();
    setLastAnalysisTime(now.toLocaleTimeString('ko-KR'));
    
    // 타임아웃 설정 (25초)
    const timeout = 25000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
      // 1. 매수 분석 - 전체 코인 대상
      setAiBuyThoughts(prev => [{
        id: Date.now(),
        time: now.toLocaleTimeString('ko-KR'),
        thought: '🔍 전체 코인 시장 스캔 중...',
        type: 'scanning'
      }, ...prev.slice(0, 4)]);
      
      try {
        const buyRes = await fetch(`${API_BASE}/api/ai-max-profit/quick-analysis?type=buy&limit=5`, {
          method: 'POST',
          signal: controller.signal
        });
        
        if (buyRes.ok) {
          const buyData = await buyRes.json();
          if (buyData.analysis) {
            // 시그널 메시지들을 개별 로그로 추가
            const signals = buyData.analysis.signals || [];
            const newThoughts = signals.slice(0, 3).map((sig, idx) => ({
              id: Date.now() + idx,
              time: new Date().toLocaleTimeString('ko-KR'),
              thought: sig,
              type: 'analysis'
            }));
            
            if (newThoughts.length > 0) {
              setAiBuyThoughts(prev => [...newThoughts, ...prev.slice(0, 4 - newThoughts.length)]);
            } else {
              setAiBuyThoughts(prev => [{
                id: Date.now(),
                time: new Date().toLocaleTimeString('ko-KR'),
                thought: buyData.analysis.summary || '📊 시장 안정 - 특이 시그널 없음',
                type: 'info'
              }, ...prev.slice(0, 4)]);
            }
          }
        }
      } catch (buyErr) {
        if (buyErr.name !== 'AbortError') {
          console.error('매수 분석 오류:', buyErr);
        }
      }
      
      // 2. 매도 분석 - 보유 코인 대상
      setAiSellThoughts(prev => [{
        id: Date.now(),
        time: now.toLocaleTimeString('ko-KR'),
        thought: '📊 보유 코인 분석 중...',
        type: 'scanning'
      }, ...prev.slice(0, 4)]);
      
      try {
        const sellRes = await fetch(`${API_BASE}/api/ai-max-profit/quick-analysis?type=sell&limit=5`, {
          method: 'POST',
          signal: controller.signal
        });
        
        if (sellRes.ok) {
          const sellData = await sellRes.json();
          if (sellData.analysis) {
            // 시그널 메시지들을 개별 로그로 추가
            const signals = sellData.analysis.signals || [];
            const newThoughts = signals.slice(0, 3).map((sig, idx) => ({
              id: Date.now() + idx + 100,
              time: new Date().toLocaleTimeString('ko-KR'),
              thought: sig,
              type: 'analysis'
            }));
            
            if (newThoughts.length > 0) {
              setAiSellThoughts(prev => [...newThoughts, ...prev.slice(0, 4 - newThoughts.length)]);
            } else {
              setAiSellThoughts(prev => [{
                id: Date.now(),
                time: new Date().toLocaleTimeString('ko-KR'),
                thought: sellData.analysis.summary || '📊 보유 코인 안정적',
                type: 'info'
              }, ...prev.slice(0, 4)]);
            }
          }
        }
      } catch (sellErr) {
        if (sellErr.name !== 'AbortError') {
          console.error('매도 분석 오류:', sellErr);
        }
      }
      
    } catch (e) {
      console.error('AI 자동 분석 오류:', e);
      if (e.name !== 'AbortError') {
        setAiBuyThoughts(prev => [{
          id: Date.now(),
          time: new Date().toLocaleTimeString('ko-KR'),
          thought: `⚠️ 분석 중단됨`,
          type: 'error'
        }, ...prev.slice(0, 4)]);
      }
    } finally {
      clearTimeout(timeoutId);
      setAiAnalyzing(false);
    }
  };

  // 30초마다 AI 자동 분석 실행
  useEffect(() => {
    if (!aiAutoEnabled) return;
    
    // 즉시 한 번 실행
    runAiAutoAnalysis();
    
    // 30초마다 반복
    const interval = setInterval(() => {
      runAiAutoAnalysis();
    }, 30000);
    
    return () => clearInterval(interval);
  }, [aiAutoEnabled]);

  // 🔄 AI 자동 매수 연속 실행 (60초마다)
  useEffect(() => {
    if (!autoBuyEnabled) return;
    
    // 즉시 한 번 실행
    runMaxProfitScan();
    
    // 60초마다 반복 (매수 완료 후 다음 스캔)
    const interval = setInterval(() => {
      if (!maxProfitScanning) {
        runMaxProfitScan();
      }
    }, 60000);
    
    return () => clearInterval(interval);
  }, [autoBuyEnabled]);

  // 🔄 AI 자동 매도 연속 실행 (60초마다)
  useEffect(() => {
    if (!autoSellEnabled) return;
    
    // 즉시 한 번 실행
    runSellScan();
    
    // 60초마다 반복 (매도 완료 후 다음 스캔)
    const interval = setInterval(() => {
      if (!sellScanning) {
        runSellScan();
      }
    }, 60000);
    
    return () => clearInterval(interval);
  }, [autoSellEnabled]);

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
            
            {/* 24시간 자동매매 - 연결 상태 표시 */}
            <div className="flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-green-600/20 to-cyan-600/20 border border-green-500/30 rounded-lg">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              <span className="text-sm text-green-400 font-medium">24H 자동매매</span>
            </div>
            
            {/* 설정 버튼 */}
            <button 
              onClick={() => setShowUpbitSettings(true)}
              className="flex items-center gap-2 px-3 py-2 bg-[#1a1a2e] hover:bg-[#252538] border border-gray-700 rounded-lg transition-colors"
            >
              <Target className="w-4 h-4 text-cyan-400" />
              <span className="text-sm">API 설정</span>
            </button>
          </div>
        </div>
      </header>
      
      {/* 업비트 설정 모달 */}
      <UpbitSettingsModal 
        isOpen={showUpbitSettings}
        onClose={() => setShowUpbitSettings(false)}
        onSuccess={(info) => {
          fetchBalances();
          fetchTrades();
        }}
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
          
          {/* 예수금 */}
          <div className="bg-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-400 text-sm">예수금</span>
              <DollarSign className="w-4 h-4 text-gray-500" />
            </div>
            <div className="text-2xl font-bold">
              {krwBalance.toLocaleString()}
              <span className="text-sm text-gray-400 ml-1">원</span>
            </div>
          </div>
          
          {/* 총 평가금액 */}
          <div className="bg-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-400 text-sm">총 평가금액</span>
              <Target className="w-4 h-4 text-gray-500" />
            </div>
            <div className="text-2xl font-bold text-cyan-400">
              {user ? userTotalKRW.toLocaleString() : totalValue.toLocaleString()}
              <span className="text-sm text-gray-400 ml-1">원</span>
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
        
        {/* 계좌 정보 + AI 토론 패널 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* 내 계좌 정보 */}
          <div className="lg:col-span-1">
            <AccountInfo onOpenSettings={() => setShowUpbitSettings(true)} />
          </div>
          
          {/* AI 3대장 토론 패널 */}
          <div className="lg:col-span-2">
            <AIDebatePanel 
              onBuyComplete={(pick) => {
                console.log('AI 토론 매수 완료:', pick);
                fetchBalances();
                fetchTrades();
              }}
            />
          </div>
        </div>
        
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
            
          </div>
          
          {/* 하단: 설정 옵션들 */}
          <div className="flex flex-col gap-3 pt-4 border-t border-gray-700/50">
            {/* 상단: 거래 설정 */}
            <div className="flex items-center gap-6 flex-wrap">
              {/* 1회 거래금액 */}
              <div className="flex items-center gap-2">
                <span className="text-gray-400 text-sm">1회 거래:</span>
                <select 
                  value={tradeAmount}
                  onChange={(e) => setTradeAmount(Number(e.target.value))}
                  disabled={noTradeLimit}
                  className={`bg-[#252538] border border-gray-700 rounded-lg px-3 py-1.5 text-sm ${noTradeLimit ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <option value={10000}>1만원</option>
                  <option value={50000}>5만원</option>
                  <option value={100000}>10만원</option>
                  <option value={500000}>50만원</option>
                </select>
                <label className="flex items-center gap-1 cursor-pointer ml-2">
                  <input 
                    type="checkbox" 
                    checked={noTradeLimit}
                    onChange={(e) => setNoTradeLimit(e.target.checked)}
                    className="w-3.5 h-3.5 accent-orange-500"
                  />
                  <span className={`text-xs ${noTradeLimit ? 'text-orange-400 font-bold' : 'text-gray-500'}`}>무제한</span>
                </label>
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
                  disabled={noSignalLimit}
                  className={`w-24 accent-cyan-500 ${noSignalLimit ? 'opacity-50 cursor-not-allowed' : ''}`}
                />
                <span className={`font-bold ${noSignalLimit ? 'text-orange-400' : 'text-cyan-400'}`}>
                  {noSignalLimit ? 'ALL' : `${signalStrength}+`}
                </span>
                <label className="flex items-center gap-1 cursor-pointer ml-2">
                  <input 
                    type="checkbox" 
                    checked={noSignalLimit}
                    onChange={(e) => setNoSignalLimit(e.target.checked)}
                    className="w-3.5 h-3.5 accent-orange-500"
                  />
                  <span className={`text-xs ${noSignalLimit ? 'text-orange-400 font-bold' : 'text-gray-500'}`}>무제한</span>
                </label>
              </div>
            </div>
            
            {/* 하단: 체크박스 옵션들 */}
            <div className="flex items-center gap-6 flex-wrap">
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
              
              {/* 현금보유 한도 없음 */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={noBudgetLimit}
                  onChange={(e) => setNoBudgetLimit(e.target.checked)}
                  className="w-4 h-4 accent-orange-500"
                />
                <span className={`text-sm ${noBudgetLimit ? 'text-orange-400 font-bold' : 'text-gray-300'}`}>
                  💰 현금한도 무제한
                </span>
              </label>
            </div>
          </div>
          
          {/* ========== AI 자동 분석 (30초마다) ========== */}
          <div className="mt-6 mb-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${aiAutoEnabled ? 'bg-green-500/20' : 'bg-gray-700/50'}`}>
                  <Brain className={`w-5 h-5 ${aiAutoEnabled ? 'text-green-400 animate-pulse' : 'text-gray-500'}`} />
                </div>
                <div>
                  <h4 className="font-bold text-white">AI 실시간 분석</h4>
                  <p className="text-xs text-gray-400">
                    {aiAutoEnabled 
                      ? `30초마다 자동 분석 • 마지막: ${lastAnalysisTime || '분석 대기중'}`
                      : '비활성화됨'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setAiAutoEnabled(!aiAutoEnabled)}
                className={`px-4 py-2 rounded-lg font-bold transition-all ${
                  aiAutoEnabled 
                    ? 'bg-green-500 hover:bg-green-600 text-white' 
                    : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                }`}
              >
                {aiAutoEnabled ? '● 분석 중' : '○ 시작'}
              </button>
        </div>

            {/* AI 생각 표시 영역 */}
            {aiAutoEnabled && (
              <div className="grid grid-cols-2 gap-3">
                {/* 매수 AI 생각 */}
                <div className="bg-purple-500/5 border border-purple-500/20 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-4 h-4 text-purple-400" />
                    <span className="text-xs font-bold text-purple-300">매수 AI 분석</span>
                    {aiAnalyzing && <div className="w-2 h-2 bg-purple-400 rounded-full animate-ping" />}
                  </div>
                  <div className="space-y-1 max-h-24 overflow-y-auto">
                    {aiBuyThoughts.length > 0 ? (
                      aiBuyThoughts.map(t => (
                        <div key={t.id} className={`text-xs p-1.5 rounded ${
                          t.type === 'scanning' ? 'bg-yellow-500/10 text-yellow-300' :
                          t.type === 'error' ? 'bg-red-500/10 text-red-300' :
                          'bg-purple-500/10 text-purple-200'
                        }`}>
                          <span className="text-gray-500 mr-1">{t.time}</span>
                          {t.thought}
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-gray-500">분석 대기 중...</p>
                    )}
                  </div>
                </div>
                
                {/* 매도 AI 생각 */}
                <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingDown className="w-4 h-4 text-red-400" />
                    <span className="text-xs font-bold text-red-300">매도 AI 분석</span>
                    {aiAnalyzing && <div className="w-2 h-2 bg-red-400 rounded-full animate-ping" />}
                  </div>
                  <div className="space-y-1 max-h-24 overflow-y-auto">
                    {aiSellThoughts.length > 0 ? (
                      aiSellThoughts.map(t => (
                        <div key={t.id} className={`text-xs p-1.5 rounded ${
                          t.type === 'scanning' ? 'bg-yellow-500/10 text-yellow-300' :
                          t.type === 'error' ? 'bg-red-500/10 text-red-300' :
                          'bg-red-500/10 text-red-200'
                        }`}>
                          <span className="text-gray-500 mr-1">{t.time}</span>
                          {t.thought}
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-gray-500">분석 대기 중...</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
          
          {/* ========== AI 매수/매도 실행 섹션 ========== */}
          <div className="grid grid-cols-2 gap-4">
            {/* 🧠 AI 매수 섹션 */}
            <div className={`rounded-xl border p-4 ${autoBuyEnabled ? 'bg-gradient-to-br from-purple-500/20 to-pink-500/20 border-purple-400' : 'bg-gradient-to-br from-purple-500/10 to-pink-500/10 border-purple-500/30'}`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
                  <Sparkles className={`w-5 h-5 ${autoBuyEnabled ? 'text-purple-300 animate-pulse' : 'text-purple-400'}`} />
                  <h4 className="font-bold text-purple-300">AI 매수</h4>
                  <span className="text-xs text-gray-500">(전체 코인)</span>
                  {autoBuyEnabled && <span className="text-xs text-green-400 animate-pulse">● 자동</span>}
            </div>
              <button 
                  onClick={() => setAutoBuyEnabled(!autoBuyEnabled)}
                  className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-all text-sm font-bold shadow-lg ${
                    autoBuyEnabled 
                      ? 'bg-red-500 hover:bg-red-600 shadow-red-500/30' 
                      : 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 shadow-purple-500/30'
                  }`}
                >
                  {maxProfitScanning ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>{buyElapsedTime}초</span>
                    </>
                  ) : autoBuyEnabled ? (
                    <>
                      <Pause className="w-4 h-4" />
                      <span>중지</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      <span>자동 시작</span>
                    </>
                  )}
              </button>
              </div>
              
              {/* 매수 로그 */}
              <div className="bg-black/30 rounded-lg p-3 max-h-32 overflow-y-auto">
                {buyLogs.length === 0 ? (
                  <p className="text-gray-500 text-xs text-center py-2">실행 로그가 없습니다</p>
                ) : (
                  <div className="space-y-2">
                    {buyLogs.map(log => (
                      <div key={log.id} className={`text-xs p-2 rounded ${
                        log.status === 'running' ? 'bg-yellow-500/10 border border-yellow-500/30' :
                        log.status === 'success' ? 'bg-green-500/10 border border-green-500/30' :
                        log.status === 'error' ? 'bg-red-500/10 border border-red-500/30' :
                        'bg-blue-500/10 border border-blue-500/30'
                      }`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-gray-400">{log.time}</span>
                          <span className={
                            log.status === 'running' ? 'text-yellow-400' :
                            log.status === 'success' ? 'text-green-400' :
                            log.status === 'error' ? 'text-red-400' : 'text-blue-400'
                          }>{log.message}</span>
                        </div>
                        {log.details && (
                          <p className="text-gray-500 text-[10px] truncate">{log.details}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
            </div>
          </div>
          
            {/* 🤖 AI 매도 섹션 */}
            <div className={`rounded-xl border p-4 ${autoSellEnabled ? 'bg-gradient-to-br from-red-500/20 to-orange-500/20 border-red-400' : 'bg-gradient-to-br from-red-500/10 to-orange-500/10 border-red-500/30'}`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <TrendingDown className={`w-5 h-5 ${autoSellEnabled ? 'text-red-300 animate-pulse' : 'text-red-400'}`} />
                  <h4 className="font-bold text-red-300">AI 매도</h4>
                  <span className="text-xs text-gray-500">(보유 코인)</span>
                  {autoSellEnabled && <span className="text-xs text-green-400 animate-pulse">● 자동</span>}
                </div>
                <button 
                  onClick={() => setAutoSellEnabled(!autoSellEnabled)}
                  className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-all text-sm font-bold shadow-lg ${
                    autoSellEnabled 
                      ? 'bg-gray-600 hover:bg-gray-700 shadow-gray-500/30' 
                      : 'bg-gradient-to-r from-red-500 to-orange-500 hover:from-red-600 hover:to-orange-600 shadow-red-500/30'
                  }`}
                >
                  {sellScanning ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>{sellElapsedTime}초</span>
                    </>
                  ) : autoSellEnabled ? (
                    <>
                      <Pause className="w-4 h-4" />
                      <span>중지</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      <span>자동 시작</span>
                    </>
                  )}
                </button>
              </div>
              
              {/* 매도 로그 */}
              <div className="bg-black/30 rounded-lg p-3 max-h-32 overflow-y-auto">
                {sellLogs.length === 0 ? (
                  <p className="text-gray-500 text-xs text-center py-2">실행 로그가 없습니다</p>
                ) : (
                  <div className="space-y-2">
                    {sellLogs.map(log => (
                      <div key={log.id} className={`text-xs p-2 rounded ${
                        log.status === 'running' ? 'bg-yellow-500/10 border border-yellow-500/30' :
                        log.status === 'success' ? 'bg-green-500/10 border border-green-500/30' :
                        log.status === 'error' ? 'bg-red-500/10 border border-red-500/30' :
                        'bg-blue-500/10 border border-blue-500/30'
                      }`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-gray-400">{log.time}</span>
                          <span className={
                            log.status === 'running' ? 'text-yellow-400' :
                            log.status === 'success' ? 'text-green-400' :
                            log.status === 'error' ? 'text-red-400' : 'text-blue-400'
                          }>{log.message}</span>
                        </div>
                        {log.details && (
                          <p className="text-gray-500 text-[10px] truncate">{log.details}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ========== 📊 포지션 모니터링 ========== */}
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
                        <span className="text-gray-500">매수일시</span>
                        <span className="font-mono text-xs">
                          {pos.entry_time ? new Date(pos.entry_time).toLocaleString('ko-KR', {
                            year: 'numeric', month: '2-digit', day: '2-digit',
                            hour: '2-digit', minute: '2-digit'
                          }) : '정보없음'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">보유 기간</span>
                        <span className="font-mono">{pos.holding_time || '0m'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">매수금액</span>
                        <span className="font-mono">₩{Math.round(pos.invest_amount || 0).toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">평가금액</span>
                        <span className={`font-mono ${profitColor}`}>
                          ₩{Math.round((pos.invest_amount || 0) * (1 + (pos.profit_rate || 0) / 100)).toLocaleString()}
                        </span>
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

        {/* ========== 거래 로그 ========== */}
        <div className="mt-6 bg-[#12121a] rounded-2xl p-4 border border-gray-800">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-cyan-400" />
              <h3 className="font-bold">거래 로그</h3>
              <span className="text-xs text-gray-500">최근 거래 내역</span>
            </div>
            <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-400 rounded text-xs font-medium">
              {trades.length}건
            </span>
          </div>
          
          {trades.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Clock className="w-10 h-10 mx-auto mb-2 opacity-30" />
              <p className="text-sm">아직 거래 내역이 없습니다</p>
              <p className="text-xs text-gray-600 mt-1">자동매매가 실행되면 거래 내역이 여기에 표시됩니다</p>
            </div>
          ) : (
            <div className="space-y-3 max-h-[600px] overflow-y-auto">
              {trades.slice(0, 30).map((trade, idx) => {
                    const isBuy = trade.action === 'buy';
                    const profitRate = trade.profit_rate || 0;
                const isProfit = profitRate >= 0;
                const aiReason = trade.ai_reason || trade.reason || '';
                const reasons = aiReason.split(' | ').filter(r => r.trim());
                    
                    return (
                  <div 
                    key={trade.id || idx} 
                    className={`bg-[#1a1a2e] rounded-xl p-4 border ${
                      isBuy ? 'border-green-500/20' : 'border-red-500/20'
                    } hover:border-cyan-500/30 transition-all`}
                  >
                    {/* 상단: 기본 정보 */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold ${
                          isBuy 
                            ? 'bg-green-500/20 text-green-400' 
                            : 'bg-red-500/20 text-red-400'
                        }`}>
                          {isBuy ? '매수' : '매도'}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-lg">{trade.ticker?.replace('KRW-', '') || trade.coin_name}</span>
                            <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-400 rounded text-xs">
                              {trade.strategy || 'AI 자동'}
                            </span>
                          </div>
                          <p className="text-xs text-gray-500">
                            {trade.timestamp ? new Date(trade.timestamp).toLocaleString('ko-KR', {
                              year: 'numeric',
                            month: '2-digit', 
                            day: '2-digit', 
                            hour: '2-digit', 
                              minute: '2-digit',
                              second: '2-digit'
                            }) : '-'}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-lg">₩{Math.round(trade.amount || trade.total_krw || 0).toLocaleString()}</p>
                        {!isBuy && (
                          <p className={`text-sm font-medium ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                            {isProfit ? '+' : ''}{profitRate.toFixed(2)}%
                          </p>
                        )}
                      </div>
                    </div>
                    
                    {/* 중간: 가격 정보 */}
                    <div className="grid grid-cols-3 gap-2 mb-3 text-sm">
                      <div className="bg-[#252538] rounded-lg p-2 text-center">
                        <p className="text-xs text-gray-500">거래가</p>
                        <p className="font-mono text-gray-300">₩{(trade.price || 0).toLocaleString()}</p>
                      </div>
                      <div className="bg-[#252538] rounded-lg p-2 text-center">
                        <p className="text-xs text-gray-500">수량</p>
                        <p className="font-mono text-gray-300">{(trade.volume || trade.quantity || 0).toFixed(4)}</p>
                      </div>
                      <div className="bg-[#252538] rounded-lg p-2 text-center">
                        <p className="text-xs text-gray-500">총액</p>
                        <p className="font-mono text-cyan-400">₩{Math.round(trade.amount || trade.total_krw || 0).toLocaleString()}</p>
                      </div>
                    </div>
                    
                    {/* 하단: AI 판단 이유 */}
                    {reasons.length > 0 && (
                      <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 rounded-lg p-3 border border-purple-500/20">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-medium text-purple-400">🤖 AI 판단 이유</span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {reasons.map((reason, i) => (
                            <span 
                              key={i}
                              className="px-2 py-1 bg-[#1a1a2e] rounded-lg text-xs text-gray-300 border border-gray-700"
                            >
                              {reason}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {/* AI 이유가 없는 경우 */}
                    {reasons.length === 0 && (trade.strategy || trade.reason) && (
                      <div className="text-xs text-gray-500 pt-2 border-t border-gray-800">
                        📝 {trade.strategy || trade.reason}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ========== 수익률 최대화 결과 모달 ========== */}
      {showMaxProfitModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#12121a] rounded-2xl border border-gray-700 max-w-4xl w-full max-h-[90vh] overflow-hidden">
            {/* 헤더 */}
            <div className="p-4 border-b border-gray-700 flex items-center justify-between bg-gradient-to-r from-cyan-500/10 to-blue-500/10">
              <div className="flex items-center gap-3">
                <Sparkles className="w-6 h-6 text-cyan-400" />
                <div>
                  <h2 className="font-bold text-lg">🧠 AI 자율 전략 스캔</h2>
                  <p className="text-xs text-gray-400">AI 3대장이 직접 전략을 설계하고 최적의 종목을 선정</p>
                </div>
              </div>
              <button 
                onClick={() => setShowMaxProfitModal(false)}
                className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            {/* 내용 */}
            <div className="p-4 overflow-y-auto max-h-[70vh]">
              {maxProfitScanning ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                  <p className="text-lg font-medium">🧠 AI 3대장 분석 중...</p>
                  <p className="text-sm text-gray-400 mt-2">GPT, Gemini, Claude가 실시간 데이터를 분석하고 매매 전략을 설계 중</p>
                </div>
              ) : maxProfitResult ? (
                <div className="space-y-4">
                  {/* 시장 개요 */}
                  {maxProfitResult.market_overview && (
                    <div className={`p-3 rounded-lg ${maxProfitResult.market_overview.btc_change_24h >= 0 ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
                      <div className="flex items-center justify-between">
                        <span className="font-medium">📊 시장 분위기: {maxProfitResult.market_overview.market_sentiment}</span>
                        <span className={maxProfitResult.market_overview.btc_change_24h >= 0 ? 'text-green-400' : 'text-red-400'}>
                          BTC {maxProfitResult.market_overview.btc_change_24h >= 0 ? '+' : ''}{maxProfitResult.market_overview.btc_change_24h}% (24H)
                          </span>
                      </div>
                    </div>
                  )}
                  
                  {/* 결과 메시지 */}
                  <div className="p-4 bg-[#1a1a2e] rounded-lg text-center">
                    <p className="text-lg">{maxProfitResult.message}</p>
                    {maxProfitResult.scan_count && (
                      <p className="text-sm text-gray-400 mt-1">총 {maxProfitResult.scan_count}개 코인 분석 완료</p>
                    )}
                  </div>
                  
                  {/* 매수된 코인 */}
                  {maxProfitResult.bought && maxProfitResult.bought.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="font-bold text-green-400 flex items-center gap-2">
                        <CheckCircle className="w-4 h-4" /> 🎯 AI 합의 매수 완료 ({maxProfitResult.bought.length}개)
                      </h3>
                      {maxProfitResult.bought.map((coin, idx) => (
                        <div key={idx} className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-green-400">{coin.ticker?.replace('KRW-', '')}</span>
                            <span className="text-cyan-400 font-mono">동의 {coin.votes}/3 ({coin.confidence}%)</span>
                          </div>
                          <p className="text-sm text-gray-400 mt-1">{coin.reasons?.slice(0,2).join(' | ')}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* AI TOP 픽 (동의했지만 아직 미매수) */}
                  {maxProfitResult.top_picks && maxProfitResult.top_picks.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="font-bold text-yellow-400 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" /> 🏆 AI 3대장 TOP 픽
                      </h3>
                      {maxProfitResult.top_picks.map((pick, idx) => (
                        <div key={idx} className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                          <div className="flex items-center justify-between">
                            <span className="font-bold">{pick.ticker?.replace('KRW-', '')}</span>
                            <span className="text-cyan-400 font-mono">
                              동의 {pick.votes}/3 | 신뢰도 {pick.avg_confidence}%
                            </span>
                          </div>
                          <p className="text-sm text-gray-400 mt-1">{pick.reasons?.slice(0,2).join(' | ')}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* AI 전문가 분석 */}
                  {maxProfitResult.ai_analysis && maxProfitResult.ai_analysis.length > 0 && (
                    <div className="space-y-3">
                      <h3 className="font-bold text-gray-300 mb-2">🧠 AI 전문가 분석</h3>
                      {maxProfitResult.ai_analysis.map((ai, idx) => (
                        <div key={idx} className="p-3 bg-[#1a1a2e] rounded-lg border border-gray-700">
                          <div className="flex items-center gap-2 mb-2">
                            <span className={`w-2 h-2 rounded-full ${
                              ai.expert.includes('GPT') ? 'bg-blue-500' :
                              ai.expert.includes('Gemini') ? 'bg-green-500' : 'bg-orange-500'
                            }`}></span>
                            <span className="font-bold">{ai.expert}</span>
                          </div>
                          {ai.analysis ? (
                            <div className="text-sm space-y-1">
                              <p className="text-gray-400"><span className="text-gray-300">전략:</span> {ai.analysis.strategy?.substring(0, 100)}...</p>
                              <p className="text-gray-400"><span className="text-gray-300">시장 관점:</span> {ai.analysis.market_view?.substring(0, 100)}...</p>
                            </div>
                          ) : (
                            <p className="text-xs text-gray-500">분석 응답 파싱 실패 - 원본 응답 확인 필요</p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* 기존 스캔 결과 (fallback) */}
                  {maxProfitResult.scanned_coins && maxProfitResult.scanned_coins.length > 0 && (
                    <div>
                      <h3 className="font-bold text-gray-300 mb-2">
                        📋 스캔 결과 (총 {maxProfitResult.scan_count || maxProfitResult.scanned_coins.length}개 중 상위 10개)
                      </h3>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-gray-500 text-xs border-b border-gray-700">
                              <th className="text-left py-2">코인</th>
                              <th className="text-right py-2">점수</th>
                              <th className="text-right py-2">RSI</th>
                              <th className="text-right py-2">BB%</th>
                              <th className="text-right py-2">%R</th>
                              <th className="text-right py-2">거래량</th>
                            </tr>
                          </thead>
                          <tbody>
                            {maxProfitResult.scanned_coins.slice(0, 10).map((coin, idx) => (
                              <tr key={idx} className={`border-b border-gray-800 ${coin.score >= 60 ? 'bg-cyan-500/5' : ''}`}>
                                <td className="py-2 font-medium">{coin.coin_name}</td>
                                <td className={`py-2 text-right font-mono ${coin.score >= 60 ? 'text-cyan-400' : 'text-gray-400'}`}>
                                  {coin.score}
                        </td>
                                <td className={`py-2 text-right font-mono text-xs ${coin.indicators?.rsi_day < 30 ? 'text-green-400' : ''}`}>
                                  {coin.indicators?.rsi_day}
                        </td>
                                <td className={`py-2 text-right font-mono text-xs ${coin.indicators?.bb_percent_day < 20 ? 'text-green-400' : ''}`}>
                                  {coin.indicators?.bb_percent_day}%
                        </td>
                                <td className={`py-2 text-right font-mono text-xs ${coin.indicators?.williams_r_day < -80 ? 'text-green-400' : ''}`}>
                                  {coin.indicators?.williams_r_day}
                        </td>
                                <td className={`py-2 text-right font-mono text-xs ${coin.indicators?.volume_ratio >= 1.5 ? 'text-green-400' : ''}`}>
                                  {coin.indicators?.volume_ratio}x
                        </td>
                      </tr>
                            ))}
                </tbody>
              </table>
                      </div>
            </div>
          )}
        </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  결과를 불러오는 중...
                </div>
              )}
      </div>
            
            {/* 푸터 */}
            <div className="p-4 border-t border-gray-700 flex justify-between items-center">
              <button 
                onClick={() => setShowAlgorithmInfo(true)}
                className="text-sm text-cyan-400 hover:text-cyan-300"
              >
                📖 알고리즘 상세 보기
              </button>
              <button 
                onClick={() => setShowMaxProfitModal(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* ========== AI 자율 매도 결과 모달 ========== */}
      {showSellModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#12121a] rounded-2xl border border-gray-700 max-w-5xl w-full max-h-[90vh] overflow-hidden">
            {/* 헤더 */}
            <div className="p-4 border-b border-gray-700 flex items-center justify-between bg-gradient-to-r from-red-500/10 to-orange-500/10">
              <div className="flex items-center gap-3">
                <TrendingDown className="w-6 h-6 text-red-400" />
                <div>
                  <h2 className="font-bold text-lg">🤖 AI 자율 매도 알고리즘</h2>
                  <p className="text-xs text-gray-400">GPT 5.2 × Gemini 3 × Claude Opus 4.5 | 실시간 매도 타이밍 분석</p>
                </div>
              </div>
              <button 
                onClick={() => setShowSellModal(false)}
                className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            {/* 내용 */}
            <div className="p-4 overflow-y-auto max-h-[70vh]">
              {sellScanning ? (
                <div className="text-center py-12">
                  <div className="flex justify-center gap-4 mb-6">
                    <div className="w-14 h-14 bg-orange-500/20 rounded-full flex items-center justify-center animate-pulse">
                      <span className="text-2xl">🔴</span>
                    </div>
                    <div className="w-14 h-14 bg-green-500/20 rounded-full flex items-center justify-center animate-pulse" style={{animationDelay: '0.2s'}}>
                      <span className="text-2xl">🟢</span>
                    </div>
                    <div className="w-14 h-14 bg-purple-500/20 rounded-full flex items-center justify-center animate-pulse" style={{animationDelay: '0.4s'}}>
                      <span className="text-2xl">🟣</span>
                    </div>
                  </div>
                  <p className="text-lg font-medium">AI 3대장이 매도 타이밍을 분석 중...</p>
                  <p className="text-sm text-gray-400 mt-2">익절/손절/트레일링 스탑 전략을 종합 분석합니다</p>
                </div>
              ) : sellResult ? (
                <div className="space-y-4">
                  {/* 시장 상황 */}
                  {sellResult.market_status && (
                    <div className={`p-3 rounded-lg flex items-center justify-between ${
                      sellResult.market_status.sentiment === 'bullish' ? 'bg-green-500/10 border border-green-500/30' :
                      sellResult.market_status.sentiment === 'bearish' ? 'bg-red-500/10 border border-red-500/30' :
                      'bg-yellow-500/10 border border-yellow-500/30'
                    }`}>
                      <div className="flex items-center gap-2">
                        <span className="text-lg">
                          {sellResult.market_status.sentiment === 'bullish' ? '📈' :
                           sellResult.market_status.sentiment === 'bearish' ? '📉' : '📊'}
                        </span>
                        <span className="text-sm">BTC 24H: {sellResult.market_status.btc_change_24h >= 0 ? '+' : ''}{sellResult.market_status.btc_change_24h}%</span>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs ${
                        sellResult.market_status.risk_level === 'high' ? 'bg-red-500/20 text-red-400' :
                        sellResult.market_status.risk_level === 'low' ? 'bg-green-500/20 text-green-400' :
                        'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        리스크 {sellResult.market_status.risk_level === 'high' ? '높음' : sellResult.market_status.risk_level === 'low' ? '낮음' : '보통'}
                      </span>
                    </div>
                  )}

                  {/* 결과 메시지 */}
                  <div className={`p-4 rounded-lg text-center ${
                    sellResult.sold?.length > 0 
                      ? 'bg-green-500/10 border border-green-500/30' 
                      : 'bg-[#1a1a2e]'
                  }`}>
                    <p className="text-lg font-medium">{sellResult.message}</p>
                  </div>
                  
                  {/* 매도된 코인 */}
                  {sellResult.sold && sellResult.sold.length > 0 && (
                    <div className="space-y-3">
                      <h3 className="font-bold text-green-400 flex items-center gap-2">
                        <CheckCircle className="w-5 h-5" /> 매도 완료 ({sellResult.sold.length}개)
                      </h3>
                      {sellResult.sold.map((coin, idx) => (
                        <div key={idx} className="p-4 bg-green-500/10 border border-green-500/30 rounded-xl">
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center font-bold text-green-400">
                                {coin.currency?.slice(0, 2)}
                              </div>
                              <div>
                                <span className="font-bold text-lg">{coin.currency}</span>
                                <p className="text-xs text-gray-400">AI {coin.ai_votes || 0}/3 매도 합의</p>
                              </div>
                            </div>
                            <div className="text-right">
                              <span className={`text-xl font-bold ${coin.profit_rate >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {coin.profit_rate >= 0 ? '+' : ''}{coin.profit_rate}%
                              </span>
                              <p className="text-sm text-gray-400">₩{coin.value?.toLocaleString()}</p>
                            </div>
                          </div>
                          
                          <div className="grid grid-cols-3 gap-2 text-sm mb-3">
                            <div className="bg-black/30 rounded-lg p-2 text-center">
                              <p className="text-xs text-gray-500">매수가</p>
                              <p className="font-mono text-yellow-400">₩{coin.avg_buy_price?.toLocaleString()}</p>
                            </div>
                            <div className="bg-black/30 rounded-lg p-2 text-center">
                              <p className="text-xs text-gray-500">매도가</p>
                              <p className="font-mono text-cyan-400">₩{coin.current_price?.toLocaleString()}</p>
                            </div>
                            <div className="bg-black/30 rounded-lg p-2 text-center">
                              <p className="text-xs text-gray-500">고점대비</p>
                              <p className="font-mono text-orange-400">{coin.drop_from_high}%</p>
                            </div>
                          </div>
                          
                          {/* 매도 이유 */}
                          <div className="bg-gradient-to-r from-red-500/10 to-orange-500/10 rounded-lg p-3 border border-red-500/20">
                            <p className="text-xs font-medium text-red-400 mb-2">📌 매도 결정 이유</p>
                            <p className="text-sm text-gray-300">{coin.final_reason}</p>
                          </div>
                          
                          {/* AI 판단 상세 */}
                          {coin.ai_opinions && coin.ai_opinions.length > 0 && (
                            <div className="mt-3 grid grid-cols-3 gap-2">
                              {coin.ai_opinions.map((opinion, i) => (
                                <div key={i} className={`p-2 rounded-lg text-xs ${
                                  opinion.action === 'sell' || opinion.action === 'partial_sell' 
                                    ? 'bg-red-500/10 border border-red-500/20' 
                                    : 'bg-blue-500/10 border border-blue-500/20'
                                }`}>
                                  <div className="flex items-center justify-between mb-1">
                                    <span className="font-medium">{opinion.expert}</span>
                                    <span className={opinion.action === 'sell' ? 'text-red-400' : 'text-blue-400'}>
                                      {opinion.action === 'sell' ? '매도' : opinion.action === 'partial_sell' ? '일부매도' : '보유'}
                                    </span>
                                  </div>
                                  <p className="text-gray-500 line-clamp-2">{opinion.reason}</p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* 보유 유지 코인 */}
                  {sellResult.kept && sellResult.kept.length > 0 && (
                    <div className="space-y-3">
                      <h3 className="font-bold text-blue-400 flex items-center gap-2">
                        <Eye className="w-5 h-5" /> 보유 유지 추천 ({sellResult.kept.length}개)
                      </h3>
                      {sellResult.kept.map((coin, idx) => (
                        <div key={idx} className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-xl">
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center font-bold text-blue-400">
                                {coin.currency?.slice(0, 2)}
                              </div>
                              <div>
                                <span className="font-bold text-lg">{coin.currency}</span>
                                <p className="text-xs text-gray-400">AI 보유 추천</p>
                              </div>
                            </div>
                            <div className="text-right">
                              <span className={`text-xl font-bold ${coin.profit_rate >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {coin.profit_rate >= 0 ? '+' : ''}{coin.profit_rate}%
                              </span>
                              <p className="text-sm text-gray-400">₩{coin.value?.toLocaleString()}</p>
                            </div>
                          </div>
                          
                          {/* AI 의견 */}
                          {coin.ai_opinions && coin.ai_opinions.length > 0 && (
                            <div className="grid grid-cols-3 gap-2">
                              {coin.ai_opinions.map((opinion, i) => (
                                <div key={i} className="p-2 bg-black/30 rounded-lg text-xs">
                                  <div className="flex items-center justify-between mb-1">
                                    <span className="font-medium text-gray-300">{opinion.expert}</span>
                                    <span className={`${
                                      opinion.action === 'sell' ? 'text-red-400' :
                                      opinion.action === 'hold' ? 'text-yellow-400' : 'text-blue-400'
                                    }`}>
                                      {opinion.action === 'sell' ? '매도' : '보유'} ({opinion.confidence}%)
                                    </span>
                                  </div>
                                  <p className="text-gray-500 line-clamp-2">{opinion.reason}</p>
                                </div>
                              ))}
                            </div>
                          )}
                          
                          {/* 지표 */}
                          <div className="flex gap-3 mt-3 text-xs text-gray-500">
                            <span>고점대비: {coin.drop_from_high}%</span>
                            <span>평가금액: ₩{coin.value?.toLocaleString()}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* 보유 코인 없음 */}
                  {(!sellResult.holdings || sellResult.holdings.length === 0) && (
                    <div className="text-center py-8 text-gray-500">
                      <DollarSign className="w-12 h-12 mx-auto mb-3 opacity-30" />
                      <p>보유 중인 코인이 없습니다</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  결과를 불러오는 중...
                </div>
              )}
            </div>
            
            {/* 푸터 */}
            <div className="p-4 border-t border-gray-700 flex justify-end">
              <button 
                onClick={() => setShowSellModal(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* ========== 알고리즘 정보 모달 ========== */}
      {showAlgorithmInfo && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#12121a] rounded-2xl border border-gray-700 max-w-3xl w-full max-h-[90vh] overflow-hidden">
            {/* 헤더 */}
            <div className="p-4 border-b border-gray-700 flex items-center justify-between">
              <h2 className="font-bold text-lg">🚀 AI 수익률 최대화 알고리즘</h2>
              <button 
                onClick={() => setShowAlgorithmInfo(false)}
                className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            {/* 내용 */}
            <div className="p-4 overflow-y-auto max-h-[70vh] space-y-6">
              {/* 매수 알고리즘 */}
              <div>
                <h3 className="font-bold text-green-400 mb-3 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5" /> 매수 알고리즘 (100점 만점, 60점 이상 시 매수)
                </h3>
                <div className="space-y-3">
                  <div className="p-3 bg-[#1a1a2e] rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">📊 RSI (Relative Strength Index)</span>
                      <span className="text-cyan-400">최대 25점</span>
                    </div>
                    <p className="text-sm text-gray-400">• 일봉 RSI &lt; 25 → 25점 (극과매도)</p>
                    <p className="text-sm text-gray-400">• 60분봉 RSI &lt; 20 → 15점</p>
                  </div>
                  
                  <div className="p-3 bg-[#1a1a2e] rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">📈 볼린저 밴드 (Bollinger Bands)</span>
                      <span className="text-cyan-400">최대 25점</span>
                    </div>
                    <p className="text-sm text-gray-400">• 일봉 BB% &lt; 5 → 25점 (하단 터치)</p>
                    <p className="text-sm text-gray-400">• 60분봉 BB% &lt; 10 → 15점</p>
                  </div>
                  
                  <div className="p-3 bg-[#1a1a2e] rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">📉 MACD</span>
                      <span className="text-cyan-400">최대 20점</span>
                    </div>
                    <p className="text-sm text-gray-400">• 일봉 히스토그램 양전환 + 상승 → 20점</p>
                    <p className="text-sm text-gray-400">• 60분봉 히스토그램 양전환 + 상승 → 10점</p>
                  </div>
                  
                  <div className="p-3 bg-[#1a1a2e] rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">📊 Williams %R</span>
                      <span className="text-cyan-400">최대 15점</span>
                    </div>
                    <p className="text-sm text-gray-400">• 일봉 %R &lt; -90 → 15점 (극과매도)</p>
                    <p className="text-sm text-gray-400">• 60분봉 %R &lt; -80 → 10점</p>
                  </div>
                  
                  <div className="p-3 bg-[#1a1a2e] rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">📊 거래량 (Volume)</span>
                      <span className="text-cyan-400">최대 15점</span>
                    </div>
                    <p className="text-sm text-gray-400">• 20일 평균 대비 2배 이상 → 15점</p>
                    <p className="text-sm text-gray-400">• 20일 평균 대비 1.5배 이상 → 10점</p>
                  </div>
                </div>
              </div>
              
              {/* BTC 필터 */}
              <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                <h4 className="font-medium text-yellow-400 mb-1">⚠️ BTC 추세 필터</h4>
                <p className="text-sm text-gray-400">BTC가 1시간 내 0.5% 이상 하락 중이면 모든 매수 보류</p>
                <p className="text-xs text-gray-500 mt-1">알트코인은 BTC와 동반 하락하는 경향이 있음</p>
              </div>
              
              {/* 매도 알고리즘 */}
              <div>
                <h3 className="font-bold text-red-400 mb-3 flex items-center gap-2">
                  <TrendingDown className="w-5 h-5" /> 매도 알고리즘
                </h3>
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-2 bg-[#1a1a2e] rounded">
                    <span className="text-sm">RSI 과매수 익절</span>
                    <span className="text-xs text-gray-400">RSI &gt; 75 & 수익률 ≥ 5%</span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-[#1a1a2e] rounded">
                    <span className="text-sm">목표 수익률 달성</span>
                    <span className="text-xs text-gray-400">수익률 ≥ 10%</span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-[#1a1a2e] rounded">
                    <span className="text-sm">볼린저 밴드 상단 돌파</span>
                    <span className="text-xs text-gray-400">BB% &gt; 95</span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-red-500/10 border border-red-500/30 rounded">
                    <span className="text-sm text-red-400">🚨 손절</span>
                    <span className="text-xs text-red-400">수익률 ≤ -2%</span>
                  </div>
                </div>
              </div>
            </div>
            
            {/* 푸터 */}
            <div className="p-4 border-t border-gray-700 flex justify-end">
              <button 
                onClick={() => setShowAlgorithmInfo(false)}
                className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 rounded-lg transition-colors"
              >
                확인
              </button>
            </div>
          </div>
        </div>
      )}

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
