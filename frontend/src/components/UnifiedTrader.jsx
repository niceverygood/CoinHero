import React, { useState, useEffect, useCallback } from 'react';
import { 
  Play, Pause, RefreshCw, TrendingUp, TrendingDown,
  Clock, AlertTriangle, CheckCircle, Brain, Zap,
  ChevronDown, ChevronUp, DollarSign, Settings
} from 'lucide-react';

// 전략 카테고리
const STRATEGY_CATEGORIES = {
  max_profit: {
    name: '💎 수익률 최대화',
    emoji: '💎',
    color: 'from-emerald-400 to-cyan-400'
  },
  larry: {
    name: '래리 윌리엄스',
    emoji: '🏆',
    color: 'from-yellow-500 to-amber-600'
  },
  classic: {
    name: '클래식 전략',
    emoji: '📊',
    color: 'from-blue-500 to-cyan-500'
  },
  scalping: {
    name: '스캘핑',
    emoji: '⚡',
    color: 'from-purple-500 to-pink-500'
  }
};

const RISK_COLORS = {
  low: 'border-green-500/50 bg-green-500/10',
  medium: 'border-yellow-500/50 bg-yellow-500/10',
  high: 'border-red-500/50 bg-red-500/10'
};

const RISK_LABELS = {
  low: { text: '안전', color: 'text-green-400' },
  medium: { text: '보통', color: 'text-yellow-400' },
  high: { text: '공격', color: 'text-red-400' }
};

function UnifiedTrader() {
  const [strategies, setStrategies] = useState([]);
  const [status, setStatus] = useState(null);
  const [selectedStrategies, setSelectedStrategies] = useState([]); // 복수 선택
  const [tradeAmount, setTradeAmount] = useState(10000);
  const [maxPositions, setMaxPositions] = useState(3);
  const [isConfiguring, setIsConfiguring] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [logs, setLogs] = useState([]);
  const [showSettings, setShowSettings] = useState(false);
  const [totalProfit, setTotalProfit] = useState(0);

  const isRunning = status?.is_running || false;
  const selectedStrategyInfos = strategies.filter(s => selectedStrategies.includes(s.id));
  
  // 전략 토글
  const toggleStrategy = (strategyId) => {
    setSelectedStrategies(prev => 
      prev.includes(strategyId)
        ? prev.filter(id => id !== strategyId)
        : [...prev, strategyId]
    );
  };
  
  // 전체 선택/해제
  const toggleCategory = (categoryStrategies) => {
    const categoryIds = categoryStrategies.map(s => s.id);
    const allSelected = categoryIds.every(id => selectedStrategies.includes(id));
    
    if (allSelected) {
      setSelectedStrategies(prev => prev.filter(id => !categoryIds.includes(id)));
    } else {
      setSelectedStrategies(prev => [...new Set([...prev, ...categoryIds])]);
    }
  };

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

  // 상태 조회
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/ai-scalping/status');
      const data = await res.json();
      setStatus(data);
      if (data.strategies && data.strategies.length > 0) {
        setSelectedStrategies(data.strategies);
      } else if (data.strategy) {
        setSelectedStrategies([data.strategy]);
      }
    } catch (e) {
      console.error('상태 조회 실패:', e);
    }
  }, []);

  // 로그 조회
  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch('/api/ai-scalping/logs?limit=20');
      const data = await res.json();
      setLogs(data.logs || []);
      
      // 총 수익 계산
      const profit = (data.logs || [])
        .filter(log => log.action === 'sell' && log.profit)
        .reduce((sum, log) => sum + (log.profit || 0), 0);
      setTotalProfit(profit);
    } catch (e) {
      console.error('로그 조회 실패:', e);
    }
  }, []);

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

  // 설정 및 시작
  const handleStart = async () => {
    if (selectedStrategies.length === 0) {
      alert('매매 기법을 먼저 선택하세요');
      return;
    }

    setIsConfiguring(true);
    try {
      // 설정 (복수 전략 지원)
      await fetch('/api/ai-scalping/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategies: selectedStrategies, // 복수 전략
          strategy: selectedStrategies[0], // 기존 호환성
          trade_amount: tradeAmount,
          max_positions: maxPositions,
          scan_interval: 60
        })
      });

      // 시작
      await fetch('/api/ai-scalping/start', { method: 'POST' });
      await fetchStatus();
    } catch (e) {
      console.error('시작 실패:', e);
    } finally {
      setIsConfiguring(false);
    }
  };

  // 중지
  const handleStop = async () => {
    try {
      await fetch('/api/ai-scalping/stop', { method: 'POST' });
      await fetchStatus();
    } catch (e) {
      console.error('중지 실패:', e);
    }
  };

  // 전략 카테고리 분류
  const categorizedStrategies = {
    max_profit: strategies.filter(s => s.id === 'max_profit'),
    larry: strategies.filter(s => s.id.startsWith('larry')),
    classic: strategies.filter(s => ['volatility_breakout', 'rsi_reversal', 'bollinger_bounce', 'volume_surge', 'momentum_breakout'].includes(s.id)),
    scalping: strategies.filter(s => s.id === 'scalping_5min')
  };

  return (
    <div className="glass-card rounded-2xl p-5">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">AI 자동매매</h2>
            <p className="text-xs text-gray-400">전략 선택 → AI가 최적 매매</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button 
            onClick={() => { fetchStatus(); fetchLogs(); }}
            className="p-2 rounded-lg bg-crypto-darker hover:bg-crypto-border transition-colors"
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
          <button 
            onClick={() => setShowSettings(!showSettings)}
            className={`p-2 rounded-lg transition-colors ${showSettings ? 'bg-purple-500/30 text-purple-300' : 'bg-crypto-darker text-gray-400 hover:bg-crypto-border'}`}
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 상태 표시 */}
      {isRunning && selectedStrategyInfos.length > 0 && (
        <div className="mb-4 p-3 rounded-xl bg-gradient-to-r from-purple-500/20 to-pink-500/20 border border-purple-500/30">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
              <span className="text-sm text-white font-medium">🧠 AI 복합 전략 실행 중</span>
            </div>
            <span className="text-xs text-gray-400">포지션: {status?.current_positions || 0}/{maxPositions}</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {selectedStrategyInfos.map(s => (
              <span key={s.id} className="text-xs px-2 py-0.5 rounded-full bg-purple-500/30 text-purple-200">
                {s.emoji} {s.name_kr}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 수익/손실 현황 */}
      {logs.length > 0 && (
        <div className={`mb-4 p-3 rounded-xl flex items-center justify-between ${
          totalProfit >= 0 ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'
        }`}>
          <div className="flex items-center gap-2">
            <DollarSign className={`w-4 h-4 ${totalProfit >= 0 ? 'text-green-400' : 'text-red-400'}`} />
            <span className="text-xs text-gray-400">총 실현 손익</span>
          </div>
          <span className={`font-bold ${totalProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalProfit >= 0 ? '+' : ''}₩{totalProfit.toLocaleString()}
          </span>
        </div>
      )}

      {/* 설정 패널 */}
      {showSettings && !isRunning && (
        <div className="mb-4 p-4 rounded-xl bg-crypto-darker border border-crypto-border">
          <h3 className="text-sm font-medium text-white mb-3">⚙️ 매매 설정</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">1회 투자금</label>
              <input
                type="number"
                value={tradeAmount}
                onChange={(e) => setTradeAmount(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-lg bg-crypto-dark border border-crypto-border text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">최대 포지션</label>
              <select
                value={maxPositions}
                onChange={(e) => setMaxPositions(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-lg bg-crypto-dark border border-crypto-border text-white text-sm"
              >
                {[1, 2, 3, 4, 5].map(n => (
                  <option key={n} value={n}>{n}개</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* 전략 선택 (복수 선택 가능) */}
      {!isRunning && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-3">
            <label className="text-xs text-gray-400">🎯 매매 기법 선택 (복수 선택 가능)</label>
            {selectedStrategies.length > 0 && (
              <span className="text-xs text-purple-300">{selectedStrategies.length}개 선택</span>
            )}
          </div>
          
          {Object.entries(categorizedStrategies).map(([category, categoryStrategies]) => {
            if (categoryStrategies.length === 0) return null;
            const cat = STRATEGY_CATEGORIES[category];
            const categoryIds = categoryStrategies.map(s => s.id);
            const allSelected = categoryIds.every(id => selectedStrategies.includes(id));
            const someSelected = categoryIds.some(id => selectedStrategies.includes(id));
            
            return (
              <div key={category} className="mb-4">
                <button
                  onClick={() => toggleCategory(categoryStrategies)}
                  className={`text-xs font-medium mb-2 px-2 py-1 rounded-lg inline-flex items-center gap-2 bg-gradient-to-r ${cat.color} text-white hover:opacity-80 transition-opacity`}
                >
                  <span className={`w-3 h-3 rounded border flex items-center justify-center ${
                    allSelected ? 'bg-white border-white' : someSelected ? 'bg-white/50 border-white' : 'border-white/50'
                  }`}>
                    {allSelected && <span className="text-purple-600 text-[8px]">✓</span>}
                  </span>
                  {cat.emoji} {cat.name}
                </button>
                <div className="grid grid-cols-1 gap-2">
                  {categoryStrategies.map(strategy => {
                    const isSelected = selectedStrategies.includes(strategy.id);
                    return (
                      <button
                        key={strategy.id}
                        onClick={() => toggleStrategy(strategy.id)}
                        className={`p-3 rounded-xl border transition-all text-left ${
                          isSelected
                            ? 'border-purple-500 bg-purple-500/20 ring-1 ring-purple-500'
                            : `${RISK_COLORS[strategy.risk_level]} hover:border-white/30`
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <span className={`w-4 h-4 rounded border flex items-center justify-center ${
                              isSelected ? 'bg-purple-500 border-purple-500' : 'border-gray-500'
                            }`}>
                              {isSelected && <span className="text-white text-[10px]">✓</span>}
                            </span>
                            <span className="text-lg">{strategy.emoji}</span>
                            <span className="text-sm font-medium text-white">{strategy.name_kr}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`text-xs ${RISK_LABELS[strategy.risk_level].color}`}>
                              {RISK_LABELS[strategy.risk_level].text}
                            </span>
                            <span className="text-xs text-gray-500">{strategy.win_rate}</span>
                          </div>
                        </div>
                        <p className="text-xs text-gray-400 line-clamp-1 ml-6">{strategy.description}</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 시작/중지 버튼 */}
      <button
        onClick={isRunning ? handleStop : handleStart}
        disabled={isConfiguring || (!isRunning && selectedStrategies.length === 0)}
        className={`w-full py-3 rounded-xl font-medium transition-all flex items-center justify-center gap-2 ${
          isRunning
            ? 'bg-gradient-to-r from-red-500 to-orange-500 text-white hover:from-red-600 hover:to-orange-600'
            : selectedStrategies.length > 0
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600'
              : 'bg-crypto-darker text-gray-500 cursor-not-allowed'
        }`}
      >
        {isConfiguring ? (
          <>
            <RefreshCw className="w-4 h-4 animate-spin" />
            설정 중...
          </>
        ) : isRunning ? (
          <>
            <Pause className="w-4 h-4" />
            AI 자동매매 중지
          </>
        ) : (
          <>
            <Play className="w-4 h-4" />
            {selectedStrategies.length > 0
              ? `🧠 AI 복합 전략 (${selectedStrategies.length}개) 시작`
              : '매매 기법을 선택하세요'
            }
          </>
        )}
      </button>

      {/* AI 설명 */}
      {selectedStrategies.length > 0 && !isRunning && (
        <div className="mt-3 p-3 rounded-xl bg-purple-500/10 border border-purple-500/20">
          <p className="text-xs text-purple-300">
            🤖 <strong>{selectedStrategies.length}개 전략</strong>을 조합하여 AI가 시장을 분석합니다.
            각 전략의 신호를 종합 판단하여 최적의 매수/매도 타이밍을 찾습니다.
          </p>
          <div className="flex flex-wrap gap-1 mt-2">
            {selectedStrategyInfos.map(s => (
              <span key={s.id} className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-200">
                {s.emoji} {s.name_kr}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 거래 기록 토글 */}
      <button
        onClick={() => setShowLogs(!showLogs)}
        className="w-full mt-4 py-2 flex items-center justify-center gap-2 text-gray-400 hover:text-white transition-colors"
      >
        <Clock className="w-4 h-4" />
        <span className="text-xs">거래 기록 ({logs.length})</span>
        {showLogs ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {/* 거래 기록 */}
      {showLogs && logs.length > 0 && (
        <div className="mt-2 space-y-2 max-h-60 overflow-y-auto">
          {logs.map((log, idx) => (
            <div 
              key={log.id || idx}
              className={`p-3 rounded-lg border ${
                log.action === 'buy' 
                  ? 'bg-green-500/5 border-green-500/20' 
                  : 'bg-red-500/5 border-red-500/20'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className={log.action === 'buy' ? 'text-green-400' : 'text-red-400'}>
                    {log.action === 'buy' ? '📈 매수' : '📉 매도'}
                  </span>
                  <span className="text-white text-sm font-medium">{log.coin_name}</span>
                </div>
                <span className="text-xs text-gray-500">
                  {new Date(log.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-400">
                  ₩{log.price?.toLocaleString()} × {log.amount?.toFixed(4)}
                </span>
                {log.action === 'sell' && log.profit_rate !== undefined && (
                  <span className={log.profit_rate >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {log.profit_rate >= 0 ? '+' : ''}{log.profit_rate?.toFixed(2)}%
                    ({log.profit >= 0 ? '+' : ''}₩{log.profit?.toLocaleString()})
                  </span>
                )}
              </div>
              {log.ai_reason && (
                <p className="mt-1 text-xs text-purple-300/80 truncate">
                  🤖 {log.ai_reason}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default UnifiedTrader;

