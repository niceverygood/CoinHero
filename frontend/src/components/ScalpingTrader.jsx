import React, { useState, useEffect, useCallback } from 'react';
import { 
  Zap, Play, Pause, RefreshCw, TrendingUp, TrendingDown,
  Target, Clock, BarChart2, AlertTriangle, CheckCircle,
  ChevronDown, ChevronUp, Scan, Coins, DollarSign, Brain
} from 'lucide-react';

// 전략 정보
const STRATEGY_ICONS = {
  volatility_breakout: '⚡',
  rsi_reversal: '📊',
  bollinger_bounce: '📈',
  volume_surge: '🔥',
  momentum_breakout: '🚀',
  scalping_5min: '⏱️',
  // 래리 윌리엄스 전략들
  larry_williams_r: '📉',
  larry_oops: '😱',
  larry_smash_day: '💥',
  larry_combo: '🏆'
};

const RISK_COLORS = {
  low: 'text-green-400',
  medium: 'text-yellow-400',
  high: 'text-red-400'
};

const RISK_BG = {
  low: 'bg-green-500/20 border-green-500/30',
  medium: 'bg-yellow-500/20 border-yellow-500/30',
  high: 'bg-red-500/20 border-red-500/30'
};

function ScalpingTrader() {
  const [strategies, setStrategies] = useState([]);
  const [status, setStatus] = useState(null);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [tradeAmount, setTradeAmount] = useState(10000);
  const [maxPositions, setMaxPositions] = useState(3);
  const [scanInterval, setScanInterval] = useState(60);
  const [isConfiguring, setIsConfiguring] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [logs, setLogs] = useState([]);
  const [scanResult, setScanResult] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [useAI, setUseAI] = useState(true);  // AI 모드 기본 활성화
  const [aiLogs, setAiLogs] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // 전략 목록 조회
  const fetchStrategies = useCallback(async () => {
    try {
      const res = await fetch('/api/scalping/strategies');
      const data = await res.json();
      setStrategies(data.strategies || []);
    } catch (e) {
      console.error('전략 조회 실패:', e);
    }
  }, []);

  // 상태 조회 (AI 모드에 따라 다른 API)
  const fetchStatus = useCallback(async () => {
    try {
      const endpoint = useAI ? '/api/ai-scalping/status' : '/api/scalping/status';
      const res = await fetch(endpoint);
      const data = await res.json();
      setStatus(data);
      if (data.selected_strategy) {
        setSelectedStrategy(data.selected_strategy);
      }
    } catch (e) {
      console.error('상태 조회 실패:', e);
    }
  }, [useAI]);

  // 거래 로그 조회
  const fetchLogs = useCallback(async () => {
    try {
      const endpoint = useAI ? '/api/ai-scalping/logs?limit=20' : '/api/scalping/logs?limit=20';
      const res = await fetch(endpoint);
      const data = await res.json();
      setLogs(data.logs || []);
      if (data.ai_decisions) {
        setAiLogs(data.ai_decisions || []);
      }
    } catch (e) {
      console.error('로그 조회 실패:', e);
    }
  }, [useAI]);

  useEffect(() => {
    fetchStrategies();
    fetchStatus();
    fetchLogs();

    const interval = setInterval(() => {
      fetchStatus();
      fetchLogs();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchStrategies, fetchStatus, fetchLogs]);

  // 설정 저장
  const handleConfigure = async () => {
    if (!selectedStrategy) return;
    
    setIsConfiguring(true);
    try {
      const endpoint = useAI ? '/api/ai-scalping/configure' : '/api/scalping/configure';
      await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy: selectedStrategy,
          trade_amount: tradeAmount,
          max_positions: maxPositions,
          scan_interval: scanInterval
        })
      });
      fetchStatus();
    } catch (e) {
      console.error('설정 실패:', e);
    }
    setIsConfiguring(false);
  };

  // 시작
  const handleStart = async () => {
    if (!selectedStrategy) {
      alert('전략을 먼저 선택하세요');
      return;
    }
    
    await handleConfigure();
    
    try {
      const endpoint = useAI ? '/api/ai-scalping/start' : '/api/scalping/start';
      await fetch(endpoint, { method: 'POST' });
      fetchStatus();
    } catch (e) {
      console.error('시작 실패:', e);
    }
  };

  // 중지
  const handleStop = async () => {
    try {
      const endpoint = useAI ? '/api/ai-scalping/stop' : '/api/scalping/stop';
      await fetch(endpoint, { method: 'POST' });
      fetchStatus();
    } catch (e) {
      console.error('중지 실패:', e);
    }
  };

  // 수동 스캔/분석
  const handleScan = async () => {
    setIsScanning(true);
    try {
      if (useAI) {
        // AI 분석
        setIsAnalyzing(true);
        const res = await fetch('/api/ai-scalping/analyze', { method: 'POST' });
        const data = await res.json();
        setScanResult(data);
        setIsAnalyzing(false);
      } else {
        // 규칙 기반 스캔
        const res = await fetch(`/api/scalping/scan${selectedStrategy ? `?strategy=${selectedStrategy}` : ''}`, {
          method: 'POST'
        });
        const data = await res.json();
        setScanResult(data);
      }
    } catch (e) {
      console.error('스캔 실패:', e);
    }
    setIsScanning(false);
    setIsAnalyzing(false);
  };

  const isRunning = status?.is_running;
  const currentStrategy = strategies.find(s => s.id === selectedStrategy);

  return (
    <div className="glass-card rounded-2xl p-5">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {useAI ? (
            <Brain className="w-5 h-5 text-purple-400" />
          ) : (
            <Zap className="w-5 h-5 text-crypto-yellow" />
          )}
          <h3 className="text-white font-semibold">
            {useAI ? 'AI 단타 자동매매' : '단타 자동매매'}
          </h3>
          {isRunning && (
            <span className="px-2 py-0.5 bg-crypto-green/20 text-crypto-green text-xs rounded-full animate-pulse">
              LIVE
            </span>
          )}
        </div>
        <button
          onClick={fetchStatus}
          className="p-2 rounded-lg hover:bg-crypto-border/50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 text-gray-400 ${isRunning ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* AI 모드 토글 */}
      {!isRunning && (
        <div className="mb-5 p-3 rounded-xl bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-purple-400" />
              <div>
                <span className="text-white font-medium text-sm">AI 트레이딩 모드</span>
                <p className="text-xs text-gray-400">AI가 전략을 바탕으로 최적의 매매 결정</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                className="sr-only peer" 
                checked={useAI}
                onChange={() => setUseAI(!useAI)}
              />
              <div className="w-11 h-6 bg-gray-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-500"></div>
            </label>
          </div>
          {useAI && (
            <div className="mt-2 text-xs text-purple-300/80">
              🤖 Claude AI가 시장을 분석하고 선택한 전략의 원칙에 따라 자동 매매합니다
            </div>
          )}
        </div>
      )}

      {/* 전략 선택 */}
      {!isRunning && (
        <div className="mb-5">
          <label className="text-xs text-gray-400 mb-3 block">💡 단타 전략 선택</label>
          <div className="grid grid-cols-2 gap-2">
            {strategies.map((strategy) => (
              <button
                key={strategy.id}
                onClick={() => setSelectedStrategy(strategy.id)}
                className={`p-3 rounded-xl text-left transition-all border ${
                  selectedStrategy === strategy.id
                    ? 'bg-gradient-to-r from-crypto-accent/20 to-purple-500/20 border-crypto-accent/50'
                    : 'bg-crypto-darker border-crypto-border hover:border-crypto-accent/30'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">{strategy.emoji}</span>
                  <span className="text-white text-sm font-medium">{strategy.name_kr}</span>
                </div>
                <p className="text-xs text-gray-500 line-clamp-2">{strategy.description}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className={`text-xs px-1.5 py-0.5 rounded border ${RISK_BG[strategy.risk_level]}`}>
                    {strategy.risk_level === 'low' ? '안전' : strategy.risk_level === 'medium' ? '보통' : '공격'}
                  </span>
                  <span className="text-xs text-gray-500">
                    승률 {strategy.win_rate}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 현재 전략 표시 (실행 중) */}
      {isRunning && currentStrategy && (
        <div className={`mb-5 p-4 rounded-xl border ${RISK_BG[currentStrategy.risk_level]}`}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xl">{currentStrategy.emoji}</span>
            <div>
              <p className="text-white font-semibold">{currentStrategy.name_kr}</p>
              <p className="text-xs text-gray-400">{currentStrategy.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-400 mt-2">
            <span>⏱️ {currentStrategy.holding_time}</span>
            <span>📊 승률 {currentStrategy.win_rate}</span>
          </div>
        </div>
      )}

      {/* 설정 */}
      {!isRunning && selectedStrategy && (
        <div className="mb-5 space-y-4">
          {/* 거래 금액 */}
          <div>
            <label className="text-xs text-gray-400 mb-2 block">1회 거래 금액</label>
            <div className="flex gap-2">
              {[10000, 30000, 50000, 100000].map((amount) => (
                <button
                  key={amount}
                  onClick={() => setTradeAmount(amount)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                    tradeAmount === amount
                      ? 'bg-crypto-accent/20 text-crypto-accent border border-crypto-accent/30'
                      : 'bg-crypto-darker text-gray-400 border border-crypto-border'
                  }`}
                >
                  {amount >= 10000 ? `${amount / 10000}만` : amount.toLocaleString()}
                </button>
              ))}
            </div>
          </div>

          {/* 최대 포지션 */}
          <div>
            <label className="text-xs text-gray-400 mb-2 block">최대 동시 보유 코인</label>
            <div className="flex gap-2">
              {[1, 2, 3, 5].map((num) => (
                <button
                  key={num}
                  onClick={() => setMaxPositions(num)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                    maxPositions === num
                      ? 'bg-crypto-accent/20 text-crypto-accent border border-crypto-accent/30'
                      : 'bg-crypto-darker text-gray-400 border border-crypto-border'
                  }`}
                >
                  {num}개
                </button>
              ))}
            </div>
          </div>

          {/* 스캔 간격 */}
          <div>
            <label className="text-xs text-gray-400 mb-2 block">스캔 간격</label>
            <div className="flex gap-2">
              {[30, 60, 120, 300].map((sec) => (
                <button
                  key={sec}
                  onClick={() => setScanInterval(sec)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                    scanInterval === sec
                      ? 'bg-crypto-accent/20 text-crypto-accent border border-crypto-accent/30'
                      : 'bg-crypto-darker text-gray-400 border border-crypto-border'
                  }`}
                >
                  {sec >= 60 ? `${sec / 60}분` : `${sec}초`}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 현재 상태 */}
      {status && (
        <div className="mb-5 p-3 rounded-xl bg-crypto-darker/50 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">보유 포지션</span>
            <span className="text-white">{status.current_positions} / {status.max_positions}</span>
          </div>
          {status.last_scan_time && (
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">마지막 스캔</span>
              <span className="text-white">
                {new Date(status.last_scan_time).toLocaleTimeString('ko-KR')}
              </span>
            </div>
          )}
          
          {/* 현재 포지션 */}
          {status.positions?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-crypto-border">
              <p className="text-xs text-gray-400 mb-2">📍 보유 중인 코인</p>
              {status.positions.map((pos) => (
                <div key={pos.ticker} className="flex items-center justify-between py-1">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium">{pos.coin_name}</span>
                    <span className="text-xs text-gray-500">{pos.strategy}</span>
                  </div>
                  <span className="text-sm text-gray-400">
                    ₩{pos.entry_price?.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
          
          {/* 최근 시그널 */}
          {status.recent_signals?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-crypto-border">
              <p className="text-xs text-gray-400 mb-2">📡 최근 시그널</p>
              {status.recent_signals.slice(0, 3).map((sig, i) => (
                <div key={i} className="flex items-center justify-between py-1">
                  <div className="flex items-center gap-2">
                    <span className="text-white">{sig.coin_name}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      sig.score >= 70 ? 'bg-crypto-green/20 text-crypto-green' : 'bg-yellow-500/20 text-yellow-400'
                    }`}>
                      {sig.score?.toFixed(0)}점
                    </span>
                  </div>
                  <span className="text-xs text-gray-500">{sig.reason?.slice(0, 20)}...</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 수동 스캔/분석 버튼 */}
      <button
        onClick={handleScan}
        disabled={isScanning || isAnalyzing}
        className={`w-full py-2.5 mb-3 rounded-xl font-medium transition-all flex items-center justify-center gap-2 ${
          useAI 
            ? 'bg-purple-500/10 text-purple-300 border border-purple-500/30 hover:border-purple-500/50'
            : 'bg-crypto-darker text-gray-300 border border-crypto-border hover:border-crypto-accent/50'
        }`}
      >
        {isScanning || isAnalyzing ? (
          <>
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            {useAI ? '🧠 AI가 시장 분석 중...' : '전체 코인 스캔 중...'}
          </>
        ) : (
          <>
            {useAI ? <Brain className="w-4 h-4" /> : <Scan className="w-4 h-4" />}
            {useAI 
              ? (selectedStrategy ? `🧠 AI 분석 (${currentStrategy?.name_kr || ''})` : '🧠 AI 시장 분석')
              : (selectedStrategy ? `${currentStrategy?.name_kr || '선택된 전략'}으로 스캔` : '전체 전략 스캔')
            }
          </>
        )}
      </button>

      {/* 시작/중지 버튼 */}
      <button
        onClick={isRunning ? handleStop : handleStart}
        disabled={!selectedStrategy && !isRunning}
        className={`w-full py-3 rounded-xl font-semibold transition-all flex items-center justify-center gap-2 ${
          isRunning
            ? 'bg-crypto-red/20 text-crypto-red border border-crypto-red/30 hover:bg-crypto-red/30'
            : selectedStrategy
              ? useAI 
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:opacity-90'
                : 'bg-gradient-to-r from-crypto-accent to-purple-500 text-white hover:opacity-90'
              : 'bg-gray-700 text-gray-500 cursor-not-allowed'
        }`}
      >
        {isRunning ? (
          <>
            <Pause className="w-5 h-5" />
            {useAI ? '🧠 AI 자동매매 중지' : '자동매매 중지'}
          </>
        ) : (
          <>
            <Play className="w-5 h-5" />
            {selectedStrategy 
              ? (useAI ? `🧠 AI + ${currentStrategy?.name_kr || ''} 시작` : `${currentStrategy?.name_kr || ''} 시작`)
              : '전략을 선택하세요'
            }
          </>
        )}
      </button>

      {/* 스캔/분석 결과 */}
      {scanResult && (
        <div className={`mt-5 p-4 rounded-xl border ${
          useAI 
            ? 'bg-purple-500/5 border-purple-500/30' 
            : 'bg-crypto-darker/50 border-crypto-border'
        }`}>
          <div className="flex items-center justify-between mb-3">
            <span className="text-white font-medium">
              {useAI ? '🧠 AI 분석 결과' : '🔍 스캔 결과'}
            </span>
            <span className="text-xs text-gray-500">
              {new Date(scanResult.timestamp).toLocaleTimeString('ko-KR')}
            </span>
          </div>
          
          {/* AI 결정 사항 */}
          {useAI && scanResult.decisions?.length > 0 && (
            <div className="mb-4 space-y-2">
              <p className="text-xs text-purple-300 mb-2">📊 AI 매매 결정</p>
              {scanResult.decisions.map((decision, i) => (
                <div key={i} className={`p-3 rounded-lg border ${
                  decision.action === 'buy' 
                    ? 'bg-crypto-green/10 border-crypto-green/30' 
                    : decision.action === 'sell'
                      ? 'bg-crypto-red/10 border-crypto-red/30'
                      : 'bg-gray-500/10 border-gray-500/30'
                }`}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium ${
                        decision.action === 'buy' ? 'text-crypto-green' :
                        decision.action === 'sell' ? 'text-crypto-red' : 'text-gray-400'
                      }`}>
                        {decision.action === 'buy' ? '📈 매수' : 
                         decision.action === 'sell' ? '📉 매도' : '⏸️ 관망'}
                      </span>
                      <span className="text-white font-medium">{decision.coin_name}</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      decision.confidence >= 80 ? 'bg-crypto-green/20 text-crypto-green' :
                      decision.confidence >= 60 ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                      {decision.confidence}% 확신
                    </span>
                  </div>
                  <p className="text-xs text-gray-300">{decision.reason}</p>
                  {decision.target_price && (
                    <p className="text-xs text-gray-500 mt-1">
                      목표가: ₩{decision.target_price?.toLocaleString()} | 
                      손절가: ₩{decision.stop_loss?.toLocaleString()}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
          
          {/* 스캔된 코인 목록 */}
          {scanResult.top_picks?.length > 0 || scanResult.top_signals?.length > 0 ? (
            <div className="space-y-2">
              <p className="text-xs text-gray-400 mb-2">📡 스캔된 매수 후보</p>
              {(scanResult.top_picks || scanResult.top_signals)?.map((pick, i) => (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-crypto-dark">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{STRATEGY_ICONS[pick.strategy]}</span>
                    <div>
                      <p className="text-white font-medium">{pick.coin_name}</p>
                      <p className="text-xs text-gray-500">{pick.reason?.slice(0, 30)}...</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className={`text-sm font-medium ${
                      pick.score >= 70 ? 'text-crypto-green' : 'text-yellow-400'
                    }`}>
                      {pick.score?.toFixed(0)}점
                    </p>
                    <p className="text-xs text-gray-500">
                      ₩{pick.current_price?.toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : !scanResult.decisions?.length && (
            <p className="text-center text-gray-500 py-4">
              현재 조건에 맞는 코인이 없습니다
            </p>
          )}
        </div>
      )}

      {/* AI 분석 로그 */}
      {useAI && aiLogs.length > 0 && (
        <div className="mt-5 p-4 rounded-xl bg-gradient-to-r from-purple-500/5 to-pink-500/5 border border-purple-500/20">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-purple-400" />
            <span className="text-white font-medium text-sm">🧠 AI 분석 로그</span>
            <span className="text-xs text-purple-300 ml-auto">{aiLogs.length}개 결정</span>
          </div>
          <div className="space-y-3 max-h-60 overflow-y-auto">
            {aiLogs.map((decision, i) => (
              <div key={i} className={`p-3 rounded-lg border ${
                decision.action === 'buy' 
                  ? 'bg-crypto-green/10 border-crypto-green/30' 
                  : decision.action === 'sell'
                    ? 'bg-crypto-red/10 border-crypto-red/30'
                    : 'bg-gray-500/10 border-gray-500/30'
              }`}>
                {/* 헤더 */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className={`text-lg ${
                      decision.action === 'buy' ? 'text-crypto-green' :
                      decision.action === 'sell' ? 'text-crypto-red' : 'text-gray-400'
                    }`}>
                      {decision.action === 'buy' ? '📈' : decision.action === 'sell' ? '📉' : '⏸️'}
                    </span>
                    <span className="text-white font-semibold">
                      {decision.ticker?.replace('KRW-', '')}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      decision.action === 'buy' ? 'bg-crypto-green/20 text-crypto-green' :
                      decision.action === 'sell' ? 'bg-crypto-red/20 text-crypto-red' : 
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                      {decision.action === 'buy' ? '매수' : decision.action === 'sell' ? '매도' : '관망'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      decision.confidence >= 80 ? 'bg-crypto-green/20 text-crypto-green' :
                      decision.confidence >= 60 ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                      신뢰도 {decision.confidence}%
                    </span>
                    <span className="text-xs text-gray-500">
                      {decision.timestamp && new Date(decision.timestamp).toLocaleTimeString('ko-KR')}
                    </span>
                  </div>
                </div>
                
                {/* AI 판단 이유 */}
                <div className="bg-crypto-darker/50 rounded-lg p-2 mb-2">
                  <p className="text-xs text-gray-300 leading-relaxed">
                    💭 <span className="text-purple-300">AI 판단:</span> {decision.reason}
                  </p>
                </div>
                
                {/* 목표가/손절가 */}
                {(decision.target_price || decision.stop_loss) && (
                  <div className="flex items-center gap-4 text-xs">
                    {decision.target_price && (
                      <span className="text-crypto-green">
                        🎯 목표가: ₩{decision.target_price?.toLocaleString()}
                      </span>
                    )}
                    {decision.stop_loss && (
                      <span className="text-crypto-red">
                        🛑 손절가: ₩{decision.stop_loss?.toLocaleString()}
                      </span>
                    )}
                    {decision.amount_percent && (
                      <span className="text-gray-400">
                        💰 투자비중: {decision.amount_percent}%
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 거래 실행 로그 */}
      <div className="mt-5">
        <button
          onClick={() => setShowLogs(!showLogs)}
          className="flex items-center justify-between w-full text-xs text-gray-400 mb-2"
        >
          <span className="flex items-center gap-1">
            <BarChart2 className="w-3 h-3" />
            거래 기록 ({logs.length})
          </span>
          {showLogs ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        
        {showLogs && (
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {logs.length === 0 ? (
              <div className="text-center text-gray-500 py-6">
                <Clock className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">아직 거래 기록이 없습니다</p>
              </div>
            ) : (
              logs.map((log) => (
                <div
                  key={log.id}
                  className={`p-3 rounded-xl border ${
                    log.action === 'buy'
                      ? 'bg-crypto-green/5 border-crypto-green/20'
                      : 'bg-crypto-red/5 border-crypto-red/20'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      {log.action === 'buy' ? (
                        <TrendingUp className="w-4 h-4 text-crypto-green" />
                      ) : (
                        <TrendingDown className="w-4 h-4 text-crypto-red" />
                      )}
                      <span className="text-white font-medium">{log.coin_name}</span>
                      <span className="text-xs text-gray-500">{log.strategy}</span>
                      {log.ai_confidence && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300">
                          AI {log.ai_confidence}%
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-500">
                      {new Date(log.timestamp).toLocaleTimeString('ko-KR')}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">
                      ₩{log.price?.toLocaleString()} × {log.amount?.toFixed(4)}
                    </span>
                    <span className="text-gray-400">
                      ₩{log.total_krw?.toLocaleString()}
                    </span>
                  </div>
                  {log.profit_rate !== undefined && log.profit_rate !== null && (
                    <div className={`flex items-center gap-2 mt-1 text-sm ${
                      log.profit_rate >= 0 ? 'text-crypto-green' : 'text-crypto-red'
                    }`}>
                      <span>{log.profit_rate >= 0 ? '📈' : '📉'}</span>
                      <span>{log.profit_rate >= 0 ? '+' : ''}{log.profit_rate?.toFixed(2)}%</span>
                      {log.profit && (
                        <span className="text-xs">
                          ({log.profit >= 0 ? '+' : ''}₩{log.profit?.toLocaleString()})
                        </span>
                      )}
                    </div>
                  )}
                  {/* AI 판단 이유 */}
                  {log.ai_reason && (
                    <div className="mt-2 p-2 rounded-lg bg-crypto-darker/50 border-l-2 border-purple-500">
                      <p className="text-xs text-gray-300">
                        🤖 <span className="text-purple-300">AI:</span> {log.ai_reason}
                      </p>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ScalpingTrader;

