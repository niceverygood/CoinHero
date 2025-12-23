import React, { useState } from 'react';
import { Bot, Play, Pause, Settings, Cpu, Zap, Target, TrendingUp, Activity, BarChart2, Layers, ChevronDown, ChevronUp, Check } from 'lucide-react';

const strategies = [
  { 
    id: 'volatility', 
    name: '변동성 돌파', 
    desc: '전일 변동폭의 K배를 당일 시가에 더한 가격 돌파 시 매수',
    icon: Zap,
    color: 'from-yellow-500 to-orange-500',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/30',
    features: ['단기 트레이딩', '높은 변동성 활용', '당일 청산']
  },
  { 
    id: 'ma_cross', 
    name: '이동평균 교차', 
    desc: '단기 이동평균이 장기 이동평균을 돌파할 때 매매',
    icon: TrendingUp,
    color: 'from-blue-500 to-cyan-500',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    features: ['중기 트레이딩', '추세 추종', '골든/데드 크로스']
  },
  { 
    id: 'rsi', 
    name: 'RSI 전략', 
    desc: 'RSI 지표로 과매수/과매도 구간을 판단하여 매매',
    icon: Activity,
    color: 'from-purple-500 to-pink-500',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/30',
    features: ['역추세 매매', 'RSI 30/70 기준', '반등/조정 포착']
  },
  { 
    id: 'combined', 
    name: '복합 전략', 
    desc: '여러 전략의 신호를 종합하여 안정적으로 매매',
    icon: Layers,
    color: 'from-green-500 to-emerald-500',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-green-500/30',
    features: ['안정적 매매', '다중 신호 확인', '낮은 리스크']
  },
];

const targetCoins = [
  { ticker: 'KRW-BTC', name: 'Bitcoin', symbol: 'BTC' },
  { ticker: 'KRW-ETH', name: 'Ethereum', symbol: 'ETH' },
  { ticker: 'KRW-XRP', name: 'Ripple', symbol: 'XRP' },
  { ticker: 'KRW-SOL', name: 'Solana', symbol: 'SOL' },
  { ticker: 'KRW-DOGE', name: 'Dogecoin', symbol: 'DOGE' },
];

// 최소 거래대금 옵션
const volumeOptions = [
  { value: 1_000_000_000, label: '10억 이상' },
  { value: 5_000_000_000, label: '50억 이상' },
  { value: 10_000_000_000, label: '100억 이상' },
];

// 최소 점수 옵션
const scoreOptions = [
  { value: 55, label: '55점 (공격적)' },
  { value: 65, label: '65점 (보통)' },
  { value: 75, label: '75점 (보수적)' },
];

function BotControl({ status, onStart, onStop }) {
  const [selectedStrategy, setSelectedStrategy] = useState(status?.strategy || 'volatility');
  const [selectedCoins, setSelectedCoins] = useState(status?.target_coins || ['KRW-BTC', 'KRW-ETH']);
  const [tradeAmount, setTradeAmount] = useState(status?.trade_amount || 10000);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isConfiguring, setIsConfiguring] = useState(false);
  
  // 전체 코인 스캔 모드
  const [scanMode, setScanMode] = useState(status?.scan_mode || false);
  const [minVolume, setMinVolume] = useState(status?.min_volume || 1_000_000_000);
  const [minScore, setMinScore] = useState(status?.min_score || 65);
  const [scanResults, setScanResults] = useState([]);
  const [isScanning, setIsScanning] = useState(false);

  const isRunning = status?.is_running || false;

  const handleCoinToggle = (ticker) => {
    setSelectedCoins(prev => 
      prev.includes(ticker) 
        ? prev.filter(t => t !== ticker)
        : [...prev, ticker]
    );
  };

  const handleStartBot = async () => {
    setIsConfiguring(true);
    try {
      // 먼저 설정 저장
      await fetch('/api/bot/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy: selectedStrategy,
          coins: scanMode ? [] : selectedCoins,  // 스캔 모드면 빈 배열
          amount: tradeAmount,
          interval: scanMode ? 300 : 60,  // 스캔 모드는 5분 간격
          scan_mode: scanMode,
          min_score: minScore,
          min_volume: minVolume
        })
      });
      // 봇 시작
      await onStart();
    } catch (e) {
      console.error('봇 시작 실패:', e);
    }
    setIsConfiguring(false);
  };

  // 전체 코인 스캔 실행
  const handleScan = async () => {
    setIsScanning(true);
    try {
      const res = await fetch(`/api/scan?min_volume=${minVolume}`, { method: 'POST' });
      const data = await res.json();
      setScanResults(data.coins || []);
    } catch (e) {
      console.error('스캔 실패:', e);
    }
    setIsScanning(false);
  };

  // 스캔 결과 조회
  const fetchScanResults = async () => {
    try {
      const res = await fetch(`/api/scan/buy-candidates?min_score=${minScore}`);
      const data = await res.json();
      setScanResults(data.coins || []);
    } catch (e) {
      console.error('스캔 결과 조회 실패:', e);
    }
  };

  const currentStrategy = strategies.find(s => s.id === selectedStrategy);
  const Icon = currentStrategy?.icon || Zap;

  return (
    <div className="glass-card rounded-2xl p-5">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${currentStrategy?.color || 'from-blue-500 to-purple-500'} flex items-center justify-center`}>
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-white font-semibold">자동매매 봇</h3>
            <p className="text-xs text-gray-500">AI Trading Bot</p>
          </div>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
          isRunning 
            ? 'bg-crypto-green/20 text-crypto-green' 
            : 'bg-gray-700/50 text-gray-400'
        }`}>
          <div className={`w-2 h-2 rounded-full ${
            isRunning ? 'bg-crypto-green animate-pulse' : 'bg-gray-500'
          }`}></div>
          <span className="text-xs font-medium">
            {isRunning ? 'RUNNING' : 'STOPPED'}
          </span>
        </div>
      </div>

      {/* 전략 선택 그리드 */}
      {!isRunning && (
        <div className="mb-5">
          <label className="text-xs text-gray-400 mb-2 block">투자 전략 선택</label>
          <div className="grid grid-cols-2 gap-2">
            {strategies.map((strategy) => {
              const StrategyIcon = strategy.icon;
              const isSelected = selectedStrategy === strategy.id;
              
              return (
                <button
                  key={strategy.id}
                  onClick={() => setSelectedStrategy(strategy.id)}
                  className={`relative p-3 rounded-xl border-2 transition-all text-left ${
                    isSelected 
                      ? `${strategy.bgColor} ${strategy.borderColor} scale-[1.02]`
                      : 'bg-crypto-darker/50 border-crypto-border/50 hover:border-crypto-border'
                  }`}
                >
                  {isSelected && (
                    <div className="absolute top-2 right-2">
                      <div className={`w-5 h-5 rounded-full bg-gradient-to-br ${strategy.color} flex items-center justify-center`}>
                        <Check className="w-3 h-3 text-white" />
                      </div>
                    </div>
                  )}
                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${strategy.color} flex items-center justify-center mb-2`}>
                    <StrategyIcon className="w-4 h-4 text-white" />
                  </div>
                  <div className="text-sm font-medium text-white mb-1">{strategy.name}</div>
                  <div className="text-xs text-gray-500 line-clamp-2">{strategy.desc}</div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 선택된 전략 정보 (실행 중일 때) */}
      {isRunning && currentStrategy && (
        <div className={`mb-5 p-4 rounded-xl ${currentStrategy.bgColor} border ${currentStrategy.borderColor}`}>
          <div className="flex items-center gap-3 mb-3">
            <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${currentStrategy.color} flex items-center justify-center`}>
              <Icon className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-white font-medium">{currentStrategy.name}</div>
              <div className="text-xs text-gray-400">{currentStrategy.desc}</div>
            </div>
          </div>
          <div className="flex flex-wrap gap-1">
            {currentStrategy.features.map((feature, i) => (
              <span key={i} className="text-xs px-2 py-1 bg-white/10 rounded-full text-gray-300">
                {feature}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 코인 선택 모드 */}
      {!isRunning && (
        <div className="mb-5">
          <label className="text-xs text-gray-400 mb-2 block">코인 선택 모드</label>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setScanMode(false)}
              className={`p-3 rounded-xl border-2 transition-all text-center ${
                !scanMode 
                  ? 'bg-blue-500/10 border-blue-500/30'
                  : 'bg-crypto-darker/50 border-crypto-border/50 hover:border-crypto-border'
              }`}
            >
              <Target className="w-5 h-5 mx-auto mb-1 text-blue-400" />
              <div className="text-sm font-medium text-white">특정 코인</div>
              <div className="text-xs text-gray-500">직접 선택</div>
            </button>
            <button
              onClick={() => setScanMode(true)}
              className={`p-3 rounded-xl border-2 transition-all text-center ${
                scanMode 
                  ? 'bg-purple-500/10 border-purple-500/30'
                  : 'bg-crypto-darker/50 border-crypto-border/50 hover:border-crypto-border'
              }`}
            >
              <BarChart2 className="w-5 h-5 mx-auto mb-1 text-purple-400" />
              <div className="text-sm font-medium text-white">전체 스캔</div>
              <div className="text-xs text-gray-500">자동 선별</div>
            </button>
          </div>
        </div>
      )}

      {/* 특정 코인 선택 (특정 코인 모드) */}
      {!isRunning && !scanMode && (
        <div className="mb-5">
          <label className="text-xs text-gray-400 mb-2 block">거래 대상 코인</label>
          <div className="flex flex-wrap gap-2">
            {targetCoins.map((coin) => {
              const isSelected = selectedCoins.includes(coin.ticker);
              return (
                <button
                  key={coin.ticker}
                  onClick={() => handleCoinToggle(coin.ticker)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                    isSelected
                      ? 'bg-crypto-accent/20 text-crypto-accent border border-crypto-accent/30'
                      : 'bg-crypto-darker text-gray-400 border border-crypto-border hover:border-gray-500'
                  }`}
                >
                  {coin.symbol}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 전체 스캔 설정 (스캔 모드) */}
      {!isRunning && scanMode && (
        <div className="mb-5 space-y-4">
          {/* 최소 거래대금 */}
          <div>
            <label className="text-xs text-gray-400 mb-2 block">최소 거래대금 (24시간)</label>
            <div className="grid grid-cols-3 gap-2">
              {volumeOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setMinVolume(opt.value)}
                  className={`py-2 rounded-lg text-xs font-medium transition-all ${
                    minVolume === opt.value
                      ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                      : 'bg-crypto-darker text-gray-400 border border-crypto-border'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* 최소 점수 */}
          <div>
            <label className="text-xs text-gray-400 mb-2 block">최소 매수 점수</label>
            <div className="grid grid-cols-3 gap-2">
              {scoreOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setMinScore(opt.value)}
                  className={`py-2 rounded-lg text-xs font-medium transition-all ${
                    minScore === opt.value
                      ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                      : 'bg-crypto-darker text-gray-400 border border-crypto-border'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* 스캔 버튼 */}
          <button
            onClick={handleScan}
            disabled={isScanning}
            className="w-full py-2 rounded-lg bg-purple-500/20 text-purple-400 border border-purple-500/30 hover:bg-purple-500/30 transition-all flex items-center justify-center gap-2"
          >
            {isScanning ? (
              <>
                <div className="w-4 h-4 border-2 border-purple-400/30 border-t-purple-400 rounded-full animate-spin"></div>
                스캔 중...
              </>
            ) : (
              <>
                <BarChart2 className="w-4 h-4" />
                지금 스캔하기
              </>
            )}
          </button>

          {/* 스캔 결과 미리보기 */}
          {scanResults.length > 0 && (
            <div className="p-3 bg-crypto-darker/50 rounded-xl">
              <div className="text-xs text-gray-400 mb-2">상위 매수 후보 ({scanResults.length}개)</div>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {scanResults.slice(0, 5).map((coin) => (
                  <div key={coin.ticker} className="flex items-center justify-between text-xs">
                    <span className="text-white font-medium">{coin.name}</span>
                    <div className="flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 rounded ${
                        coin.score >= 70 ? 'bg-crypto-green/20 text-crypto-green' :
                        coin.score >= 60 ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-gray-500/20 text-gray-400'
                      }`}>
                        {coin.score}점
                      </span>
                      <span className={coin.change_rate >= 0 ? 'text-crypto-green' : 'text-crypto-red'}>
                        {coin.change_rate >= 0 ? '+' : ''}{coin.change_rate}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 거래 금액 설정 */}
      {!isRunning && (
        <div className="mb-5">
          <label className="text-xs text-gray-400 mb-2 block">1회 거래 금액 (KRW)</label>
          <div className="flex gap-2">
            {[10000, 50000, 100000, 500000].map((amount) => (
              <button
                key={amount}
                onClick={() => setTradeAmount(amount)}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                  tradeAmount === amount
                    ? 'bg-crypto-accent/20 text-crypto-accent border border-crypto-accent/30'
                    : 'bg-crypto-darker text-gray-400 border border-crypto-border hover:border-gray-500'
                }`}
              >
                {amount >= 10000 ? `${amount / 10000}만` : amount.toLocaleString()}
              </button>
            ))}
          </div>
          <input
            type="number"
            value={tradeAmount}
            onChange={(e) => setTradeAmount(parseInt(e.target.value) || 10000)}
            className="w-full mt-2 bg-crypto-darker border border-crypto-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-crypto-accent"
            min="5000"
            step="5000"
          />
        </div>
      )}

      {/* 현재 설정 요약 (실행 중) */}
      {isRunning && (
        <div className="space-y-2 p-3 bg-crypto-darker/50 rounded-xl mb-5">
          {status?.scan_mode ? (
            <>
              <div className="flex items-center gap-2 mb-2">
                <BarChart2 className="w-4 h-4 text-purple-400" />
                <span className="text-purple-400 font-medium text-sm">전체 코인 스캔 모드</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">최소 거래대금</span>
                <span className="text-white">{(status.min_volume / 1e8).toFixed(0)}억 이상</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">최소 점수</span>
                <span className="text-white">{status.min_score}점 이상</span>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 flex items-center gap-1">
                <Target className="w-3 h-3" /> 대상 코인
              </span>
              <span className="text-white">
                {status?.target_coins?.map(t => t.replace('KRW-', '')).join(', ')}
              </span>
            </div>
          )}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 flex items-center gap-1">
              <Zap className="w-3 h-3" /> 거래금액
            </span>
            <span className="text-white">₩{status?.trade_amount?.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 flex items-center gap-1">
              <Cpu className="w-3 h-3" /> 마지막 체크
            </span>
            <span className="text-white text-xs">
              {status?.last_check ? new Date(status.last_check).toLocaleTimeString('ko-KR') : '-'}
            </span>
          </div>
        </div>
      )}

      {/* 거래 통계 */}
      <div className="grid grid-cols-2 gap-3 mb-5">
        <div className="p-3 bg-crypto-darker/50 rounded-xl text-center">
          <div className="text-2xl font-bold text-white">{status?.total_trades || 0}</div>
          <div className="text-xs text-gray-500">총 거래</div>
        </div>
        <div className="p-3 bg-crypto-darker/50 rounded-xl text-center">
          <div className="text-2xl font-bold text-crypto-green">{status?.successful_trades || 0}</div>
          <div className="text-xs text-gray-500">성공 거래</div>
        </div>
      </div>

      {/* 시작/중지 버튼 */}
      <button
        onClick={isRunning ? onStop : handleStartBot}
        disabled={isConfiguring || (!isRunning && !scanMode && selectedCoins.length === 0)}
        className={`w-full py-3 rounded-xl font-semibold transition-all flex items-center justify-center gap-2 ${
          isRunning 
            ? 'bg-gradient-to-r from-red-500 to-pink-500 text-white hover:from-red-600 hover:to-pink-600' 
            : (!scanMode && selectedCoins.length === 0)
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : scanMode
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:opacity-90'
                : `bg-gradient-to-r ${currentStrategy?.color || 'from-blue-500 to-purple-500'} text-white hover:opacity-90`
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
            자동매매 중지
          </>
        ) : scanMode ? (
          <>
            <BarChart2 className="w-5 h-5" />
            전체 코인 스캔 시작
          </>
        ) : (
          <>
            <Play className="w-5 h-5" />
            {currentStrategy?.name}으로 시작
          </>
        )}
      </button>

      {/* 경고 문구 */}
      {!isRunning && (
        <p className="text-xs text-gray-600 text-center mt-3">
          ⚠️ 자동매매는 투자 손실의 위험이 있습니다
        </p>
      )}
    </div>
  );
}

export default BotControl;
