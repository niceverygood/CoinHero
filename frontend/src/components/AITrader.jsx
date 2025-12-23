import React, { useState, useEffect } from 'react';
import { 
  Brain, Play, Pause, Sparkles, TrendingUp, TrendingDown, 
  Minus, RefreshCw, Settings, Zap, Target, Clock, 
  CheckCircle, XCircle, AlertCircle, ChevronDown, ChevronUp,
  Wand2, BarChart3, Activity
} from 'lucide-react';

const AI_MODELS = [
  { id: 'claude', name: 'Claude Opus 4.5', desc: 'Anthropic 최신 추론 AI', color: 'from-orange-500 to-amber-500' },
  { id: 'gpt', name: 'GPT 5.2', desc: 'OpenAI 최강 AI', color: 'from-green-500 to-emerald-500' },
  { id: 'gemini', name: 'Gemini 3', desc: 'Google 차세대 AI', color: 'from-blue-500 to-cyan-500' },
  { id: 'grok', name: 'Grok 4.1', desc: 'xAI 실시간 분석 AI', color: 'from-red-500 to-rose-500' },
];

const STRATEGY_INFO = {
  volatility: { name: '변동성 돌파', icon: '⚡', color: 'text-yellow-400', desc: '고변동성 시장에 유리' },
  moving_average: { name: '이동평균 교차', icon: '📈', color: 'text-green-400', desc: '추세장에 유리' },
  rsi: { name: 'RSI 전략', icon: '📊', color: 'text-blue-400', desc: '과매수/과매도 포착' },
  combined: { name: '복합 전략', icon: '🎯', color: 'text-purple-400', desc: '안정적인 매매' },
  hold: { name: '관망', icon: '⏸️', color: 'text-gray-400', desc: '시장 불확실' },
};

const MARKET_CONDITIONS = {
  strong_uptrend: { name: '강한 상승세', color: 'text-green-500', icon: '🚀' },
  uptrend: { name: '상승세', color: 'text-green-400', icon: '📈' },
  sideways: { name: '횡보', color: 'text-yellow-400', icon: '➡️' },
  downtrend: { name: '하락세', color: 'text-red-400', icon: '📉' },
  strong_downtrend: { name: '강한 하락세', color: 'text-red-500', icon: '💥' },
  high_volatility: { name: '고변동성', color: 'text-orange-400', icon: '🔥' },
  low_volatility: { name: '저변동성', color: 'text-gray-400', icon: '😴' },
};

const targetCoins = [
  { ticker: 'KRW-BTC', symbol: 'BTC' },
  { ticker: 'KRW-ETH', symbol: 'ETH' },
  { ticker: 'KRW-XRP', symbol: 'XRP' },
  { ticker: 'KRW-SOL', symbol: 'SOL' },
  { ticker: 'KRW-DOGE', symbol: 'DOGE' },
];

function AITrader() {
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [selectedModel, setSelectedModel] = useState('claude');
  const [selectedCoins, setSelectedCoins] = useState(['KRW-BTC', 'KRW-ETH', 'KRW-XRP']);
  const [tradeAmount, setTradeAmount] = useState(10000);
  const [isConfiguring, setIsConfiguring] = useState(false);
  const [showLogs, setShowLogs] = useState(true);
  const [analyzing, setAnalyzing] = useState(null);
  
  // 시장 분석 & 전략 추천
  const [marketAnalysis, setMarketAnalysis] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [strategyStatus, setStrategyStatus] = useState(null);

  // 상태 조회
  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/ai/status');
      const data = await res.json();
      setStatus(data);
      setSelectedModel(data.model || 'claude');
    } catch (e) {
      console.error('AI 상태 조회 실패:', e);
    }
  };

  // 로그 조회
  const fetchLogs = async () => {
    try {
      const res = await fetch('/api/ai/logs?limit=20');
      const data = await res.json();
      setLogs(data.logs || []);
    } catch (e) {
      console.error('AI 로그 조회 실패:', e);
    }
  };

  // 시장 분석 조회
  const fetchMarketAnalysis = async () => {
    try {
      const tickers = selectedCoins.join(',');
      const res = await fetch(`/api/market/best-strategy?tickers=${tickers}`);
      const data = await res.json();
      setMarketAnalysis(data);
    } catch (e) {
      console.error('시장 분석 실패:', e);
    }
  };

  // 전략 상태 조회
  const fetchStrategyStatus = async () => {
    try {
      const res = await fetch('/api/ai/strategy-status');
      const data = await res.json();
      setStrategyStatus(data);
    } catch (e) {
      console.error('전략 상태 조회 실패:', e);
    }
  };

  // 시장 분석 실행
  const handleAnalyzeMarket = async () => {
    setIsAnalyzing(true);
    await fetchMarketAnalysis();
    setIsAnalyzing(false);
  };

  useEffect(() => {
    fetchStatus();
    fetchLogs();
    fetchStrategyStatus();
    const interval = setInterval(() => {
      fetchStatus();
      fetchLogs();
      fetchStrategyStatus();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // 코인 토글
  const handleCoinToggle = (ticker) => {
    setSelectedCoins(prev => 
      prev.includes(ticker) 
        ? prev.filter(t => t !== ticker)
        : [...prev, ticker]
    );
  };

  // AI 시작
  const handleStart = async () => {
    setIsConfiguring(true);
    try {
      // 설정 저장
      await fetch('/api/ai/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy: selectedModel,
          coins: selectedCoins,
          amount: tradeAmount,
          interval: 300
        })
      });
      // 시작
      await fetch('/api/ai/start', { method: 'POST' });
      fetchStatus();
    } catch (e) {
      console.error('AI 시작 실패:', e);
    }
    setIsConfiguring(false);
  };

  // AI 중지
  const handleStop = async () => {
    try {
      await fetch('/api/ai/stop', { method: 'POST' });
      fetchStatus();
    } catch (e) {
      console.error('AI 중지 실패:', e);
    }
  };

  // 수동 분석
  const handleAnalyze = async (ticker) => {
    setAnalyzing(ticker);
    try {
      const res = await fetch(`/api/ai/analyze/${ticker}`, { method: 'POST' });
      if (res.ok) {
        fetchLogs();
      }
    } catch (e) {
      console.error('분석 실패:', e);
    }
    setAnalyzing(null);
  };

  const isRunning = status?.is_running || false;
  const currentModelInfo = AI_MODELS.find(m => m.id === selectedModel) || AI_MODELS[0];

  const getDecisionIcon = (decision) => {
    switch (decision) {
      case 'buy': return <TrendingUp className="w-4 h-4 text-crypto-green" />;
      case 'sell': return <TrendingDown className="w-4 h-4 text-crypto-red" />;
      default: return <Minus className="w-4 h-4 text-gray-400" />;
    }
  };

  const getDecisionColor = (decision) => {
    switch (decision) {
      case 'buy': return 'bg-crypto-green/10 border-crypto-green/30 text-crypto-green';
      case 'sell': return 'bg-crypto-red/10 border-crypto-red/30 text-crypto-red';
      default: return 'bg-gray-500/10 border-gray-500/30 text-gray-400';
    }
  };

  return (
    <div className="glass-card rounded-2xl p-5">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${currentModelInfo.color} flex items-center justify-center relative`}>
            <Brain className="w-6 h-6 text-white" />
            {isRunning && (
              <div className="absolute -top-1 -right-1 w-4 h-4 bg-crypto-green rounded-full border-2 border-crypto-dark flex items-center justify-center">
                <Sparkles className="w-2 h-2 text-white" />
              </div>
            )}
          </div>
          <div>
            <h3 className="text-white font-semibold flex items-center gap-2">
              AI 자동매매
              {isRunning && <span className="text-xs px-2 py-0.5 bg-crypto-green/20 text-crypto-green rounded-full">LIVE</span>}
            </h3>
            <p className="text-xs text-gray-500">{currentModelInfo.name}</p>
          </div>
        </div>
        <button 
          onClick={() => { fetchStatus(); fetchLogs(); }}
          className="p-2 rounded-lg hover:bg-crypto-border/50 transition-colors"
        >
          <RefreshCw className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      {/* AI 모델 선택 */}
      {!isRunning && (
        <div className="mb-5">
          <label className="text-xs text-gray-400 mb-2 block">AI 모델 선택</label>
          <div className="grid grid-cols-2 gap-2">
            {AI_MODELS.map((model) => (
              <button
                key={model.id}
                onClick={() => setSelectedModel(model.id)}
                className={`p-3 rounded-xl border-2 transition-all text-center ${
                  selectedModel === model.id 
                    ? `bg-gradient-to-br ${model.color} bg-opacity-10 border-white/30`
                    : 'bg-crypto-darker/50 border-crypto-border/50 hover:border-crypto-border'
                }`}
              >
                <div className="text-sm font-medium text-white">{model.id.toUpperCase()}</div>
                <div className="text-xs text-gray-500 truncate">{model.desc}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 대상 코인 */}
      {!isRunning && (
        <div className="mb-5">
          <label className="text-xs text-gray-400 mb-2 block">분석 대상 코인</label>
          <div className="flex flex-wrap gap-2">
            {targetCoins.map((coin) => (
              <button
                key={coin.ticker}
                onClick={() => handleCoinToggle(coin.ticker)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  selectedCoins.includes(coin.ticker)
                    ? 'bg-crypto-accent/20 text-crypto-accent border border-crypto-accent/30'
                    : 'bg-crypto-darker text-gray-400 border border-crypto-border'
                }`}
              >
                {coin.symbol}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 거래 금액 */}
      {!isRunning && (
        <div className="mb-5">
          <label className="text-xs text-gray-400 mb-2 block">1회 거래 금액</label>
          <div className="flex gap-2">
            {[10000, 50000, 100000].map((amount) => (
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
      )}

      {/* 🆕 시장 분석 & AI 전략 추천 */}
      {!isRunning && (
        <div className="mb-5 p-4 rounded-xl bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Wand2 className="w-4 h-4 text-indigo-400" />
              <span className="text-sm font-medium text-white">AI 자동 전략 선택</span>
            </div>
            <button
              onClick={handleAnalyzeMarket}
              disabled={isAnalyzing || selectedCoins.length === 0}
              className="flex items-center gap-1 px-3 py-1 rounded-lg text-xs bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30 transition-all disabled:opacity-50"
            >
              {isAnalyzing ? (
                <div className="w-3 h-3 border-2 border-indigo-400/30 border-t-indigo-400 rounded-full animate-spin"></div>
              ) : (
                <Activity className="w-3 h-3" />
              )}
              시장 분석
            </button>
          </div>

          {/* 시장 분석 결과 */}
          {marketAnalysis && (
            <div className="space-y-3">
              {/* 추천 전략 */}
              <div className="flex items-center justify-between p-2 rounded-lg bg-crypto-darker/50">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{STRATEGY_INFO[marketAnalysis.best_strategy]?.icon || '🎯'}</span>
                  <div>
                    <div className={`text-sm font-medium ${STRATEGY_INFO[marketAnalysis.best_strategy]?.color || 'text-white'}`}>
                      {STRATEGY_INFO[marketAnalysis.best_strategy]?.name || marketAnalysis.best_strategy}
                    </div>
                    <div className="text-xs text-gray-500">
                      {STRATEGY_INFO[marketAnalysis.best_strategy]?.desc}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-bold text-white">{marketAnalysis.confidence}%</div>
                  <div className="text-xs text-gray-500">신뢰도</div>
                </div>
              </div>

              {/* 시장 요약 */}
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="p-2 rounded-lg bg-crypto-darker/30 text-center">
                  <div className="text-gray-500 mb-1">평균 RSI</div>
                  <div className={`font-medium ${
                    marketAnalysis.market_summary?.avg_rsi < 30 ? 'text-green-400' :
                    marketAnalysis.market_summary?.avg_rsi > 70 ? 'text-red-400' : 'text-white'
                  }`}>
                    {marketAnalysis.market_summary?.avg_rsi?.toFixed(1) || '-'}
                  </div>
                </div>
                <div className="p-2 rounded-lg bg-crypto-darker/30 text-center">
                  <div className="text-gray-500 mb-1">추세 강도</div>
                  <div className={`font-medium ${
                    marketAnalysis.market_summary?.avg_trend > 10 ? 'text-green-400' :
                    marketAnalysis.market_summary?.avg_trend < -10 ? 'text-red-400' : 'text-yellow-400'
                  }`}>
                    {marketAnalysis.market_summary?.avg_trend?.toFixed(1) || '-'}
                  </div>
                </div>
                <div className="p-2 rounded-lg bg-crypto-darker/30 text-center">
                  <div className="text-gray-500 mb-1">변동성</div>
                  <div className="font-medium text-white">
                    {marketAnalysis.market_summary?.avg_volatility?.toFixed(2)}%
                  </div>
                </div>
              </div>

              {/* 분석 이유 */}
              {marketAnalysis.reasons?.length > 0 && (
                <div className="text-xs text-gray-400 space-y-1">
                  {marketAnalysis.reasons.slice(0, 3).map((reason, i) => (
                    <div key={i}>{reason}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {!marketAnalysis && (
            <div className="text-center text-gray-500 text-xs py-2">
              "시장 분석" 버튼을 눌러 AI가 최적의 전략을 추천받으세요
            </div>
          )}
        </div>
      )}

      {/* 현재 상태 (실행 중) */}
      {isRunning && (
        <div className="mb-5 p-4 rounded-xl bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-crypto-green rounded-full animate-pulse"></div>
              <span className="text-sm text-white">AI 분석 중</span>
            </div>
            <span className="text-xs text-gray-400">{status?.check_interval || 300}초 간격</span>
          </div>
          
          {/* 현재 추천 전략 */}
          {strategyStatus?.current_recommended_strategy && (
            <div className="mb-3 p-2 rounded-lg bg-crypto-darker/50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span>{STRATEGY_INFO[strategyStatus.current_recommended_strategy]?.icon || '🎯'}</span>
                <span className={`text-sm font-medium ${STRATEGY_INFO[strategyStatus.current_recommended_strategy]?.color || 'text-white'}`}>
                  {STRATEGY_INFO[strategyStatus.current_recommended_strategy]?.name || strategyStatus.current_recommended_strategy}
                </span>
              </div>
              <span className="text-xs text-gray-500">현재 전략</span>
            </div>
          )}
          
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">총 분석</span>
              <span className="text-white">{status?.total_analyses || 0}회</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">실행 거래</span>
              <span className="text-crypto-green">{status?.executed_trades || 0}회</span>
            </div>
          </div>
        </div>
      )}

      {/* 시작/중지 버튼 */}
      <button
        onClick={isRunning ? handleStop : handleStart}
        disabled={isConfiguring || (!isRunning && selectedCoins.length === 0)}
        className={`w-full py-3 rounded-xl font-semibold transition-all flex items-center justify-center gap-2 mb-5 ${
          isRunning 
            ? 'bg-gradient-to-r from-red-500 to-pink-500 text-white hover:from-red-600 hover:to-pink-600' 
            : selectedCoins.length === 0
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : `bg-gradient-to-r ${currentModelInfo.color} text-white hover:opacity-90`
        }`}
      >
        {isConfiguring ? (
          <>
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            설정 중...
          </>
        ) : isRunning ? (
          <>
            <Pause className="w-5 h-5" />
            AI 트레이딩 중지
          </>
        ) : (
          <>
            <Brain className="w-5 h-5" />
            {currentModelInfo.name}로 시작
          </>
        )}
      </button>

      {/* 수동 분석 버튼 */}
      <div className="mb-5">
        <label className="text-xs text-gray-400 mb-2 block">수동 AI 분석</label>
        <div className="flex flex-wrap gap-2">
          {selectedCoins.map((ticker) => (
            <button
              key={ticker}
              onClick={() => handleAnalyze(ticker)}
              disabled={analyzing === ticker}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm bg-crypto-darker border border-crypto-border hover:border-crypto-accent transition-all disabled:opacity-50"
            >
              {analyzing === ticker ? (
                <div className="w-3 h-3 border-2 border-crypto-accent/30 border-t-crypto-accent rounded-full animate-spin"></div>
              ) : (
                <Zap className="w-3 h-3 text-crypto-accent" />
              )}
              <span className="text-white">{ticker.replace('KRW-', '')}</span>
            </button>
          ))}
        </div>
      </div>

      {/* AI 로그 */}
      <div>
        <button
          onClick={() => setShowLogs(!showLogs)}
          className="flex items-center justify-between w-full text-xs text-gray-400 mb-3"
        >
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            AI 활동 로그 ({logs.length})
          </span>
          {showLogs ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        
        {showLogs && (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {logs.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                <Brain className="w-10 h-10 mx-auto mb-2 opacity-30" />
                <p className="text-sm">아직 AI 분석 기록이 없습니다</p>
              </div>
            ) : (
              logs.map((log) => (
                <div 
                  key={log.id} 
                  className={`p-4 rounded-xl border ${getDecisionColor(log.decision)}`}
                >
                  {/* 로그 헤더 */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {getDecisionIcon(log.decision)}
                      <span className="text-white font-medium">{log.ticker?.replace('KRW-', '') || 'N/A'}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        log.decision === 'buy' ? 'bg-crypto-green/20 text-crypto-green' :
                        log.decision === 'sell' ? 'bg-crypto-red/20 text-crypto-red' :
                        'bg-gray-500/20 text-gray-400'
                      }`}>
                        {log.decision === 'buy' ? '매수' : log.decision === 'sell' ? '매도' : '홀드'}
                      </span>
                      <span className="text-xs text-gray-500">
                        신뢰도 {log.confidence}%
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 bg-crypto-darker rounded text-gray-400">
                        {log.model}
                      </span>
                      {log.executed ? (
                        <CheckCircle className="w-4 h-4 text-crypto-green" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-gray-500" />
                      )}
                    </div>
                  </div>
                  
                  {/* 선택된 전략 & 시장 상태 */}
                  {(log.selected_strategy || log.market_condition) && (
                    <div className="flex flex-wrap gap-2 mb-2">
                      {log.selected_strategy && STRATEGY_INFO[log.selected_strategy] && (
                        <span className={`text-xs px-2 py-1 rounded-full bg-crypto-darker/50 ${STRATEGY_INFO[log.selected_strategy].color}`}>
                          {STRATEGY_INFO[log.selected_strategy].icon} {STRATEGY_INFO[log.selected_strategy].name}
                        </span>
                      )}
                      {log.market_condition && MARKET_CONDITIONS[log.market_condition] && (
                        <span className={`text-xs px-2 py-1 rounded-full bg-crypto-darker/50 ${MARKET_CONDITIONS[log.market_condition].color}`}>
                          {MARKET_CONDITIONS[log.market_condition].icon} {MARKET_CONDITIONS[log.market_condition].name}
                        </span>
                      )}
                    </div>
                  )}
                  
                  {/* AI 분석 */}
                  <div className="mb-2">
                    <p className="text-sm text-gray-300">{log.reasoning}</p>
                  </div>
                  
                  {/* 시장 분석 */}
                  <div className="text-xs text-gray-500 mb-2">
                    📊 {log.market_analysis}
                  </div>
                  
                  {/* 지표 */}
                  <div className="flex flex-wrap gap-2 text-xs">
                    {log.indicators?.rsi && (
                      <span className="px-2 py-1 bg-crypto-darker rounded">
                        RSI: {log.indicators.rsi}
                      </span>
                    )}
                    {log.indicators?.macd && (
                      <span className="px-2 py-1 bg-crypto-darker rounded">
                        MACD: {log.indicators.macd}
                      </span>
                    )}
                  </div>
                  
                  {/* 결과 */}
                  {log.result && (
                    <div className={`mt-2 text-xs ${log.executed ? 'text-crypto-green' : 'text-gray-500'}`}>
                      → {log.result}
                    </div>
                  )}
                  
                  {/* 시간 */}
                  <div className="mt-2 text-xs text-gray-600">
                    {new Date(log.timestamp).toLocaleString('ko-KR')}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default AITrader;

