import React, { useState } from 'react';
import { Brain, Sparkles, MessageSquare, TrendingUp, TrendingDown, Loader2, Zap, Target, Users } from 'lucide-react';

const API_BASE = import.meta.env.PROD 
  ? 'https://coinhero-production.up.railway.app' 
  : '';

// AI 전문가 정보
const EXPERT_INFO = {
  claude: {
    name: '클로드 오퍼스',
    model: 'Claude Opus 4.5',
    color: 'from-orange-500 to-amber-500',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/30',
    text: 'text-orange-400',
    avatar: '🟠'
  },
  gemini: {
    name: '제미니 쓰리',
    model: 'Gemini 3',
    color: 'from-emerald-500 to-teal-500',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    text: 'text-emerald-400',
    avatar: '🟢'
  },
  gpt: {
    name: 'GPT 파이브',
    model: 'GPT 5.2',
    color: 'from-blue-500 to-indigo-500',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    text: 'text-blue-400',
    avatar: '🔵'
  }
};

const OPINION_LABELS = {
  strong_buy: { label: '🚀 강력 매수', color: 'text-green-400 bg-green-500/20' },
  buy: { label: '📈 매수', color: 'text-emerald-400 bg-emerald-500/20' },
  hold: { label: '⏸️ 관망', color: 'text-yellow-400 bg-yellow-500/20' },
  sell: { label: '📉 매도', color: 'text-orange-400 bg-orange-500/20' },
  strong_sell: { label: '⚠️ 강력 매도', color: 'text-red-400 bg-red-500/20' }
};

export default function AIDebatePanel({ onBuyComplete }) {
  const [isDebating, setIsDebating] = useState(false);
  const [debateResult, setDebateResult] = useState(null);
  const [scanResults, setScanResults] = useState(null);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState('quick'); // 'quick' | 'full'

  // 빠른 픽 (상위 5개 스캔)
  const handleQuickPick = async () => {
    setIsDebating(true);
    setError(null);
    setDebateResult(null);
    setScanResults(null);

    try {
      const response = await fetch(`${API_BASE}/api/debate/quick-pick?amount=10000`, {
        method: 'POST'
      });
      const data = await response.json();
      
      if (data.success) {
        setScanResults(data);
        if (data.action === 'bought' && onBuyComplete) {
          onBuyComplete(data.pick);
        }
      } else {
        setError(data.detail || '토론 실패');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsDebating(false);
    }
  };

  // 전체 스캔 (상위 10개)
  const handleFullScan = async () => {
    setIsDebating(true);
    setError(null);
    setDebateResult(null);
    setScanResults(null);

    try {
      const response = await fetch(`${API_BASE}/api/debate/scan-and-buy?amount=10000&top_n=10`, {
        method: 'POST'
      });
      const data = await response.json();
      
      if (data.success) {
        setScanResults(data);
        if (data.bought?.length > 0 && onBuyComplete) {
          data.bought.forEach(item => onBuyComplete(item));
        }
      } else {
        setError(data.detail || '스캔 실패');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsDebating(false);
    }
  };

  // 특정 코인 토론
  const handleSingleDebate = async (ticker) => {
    setIsDebating(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/debate/${ticker}`, {
        method: 'POST'
      });
      const data = await response.json();
      setDebateResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsDebating(false);
    }
  };

  return (
    <div className="bg-gradient-to-br from-[#1a1a2e] to-[#16162a] rounded-2xl border border-purple-500/20 overflow-hidden">
      {/* 헤더 */}
      <div className="bg-gradient-to-r from-purple-600/20 to-pink-600/20 p-4 border-b border-purple-500/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-xl">
              <Users className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                AI 3대장 토론
              </h2>
              <p className="text-xs text-gray-400">Gemini 3 × Claude Opus 4.5 × GPT 5.2</p>
            </div>
          </div>
          
          {/* 모드 선택 */}
          <div className="flex gap-2">
            <button
              onClick={handleQuickPick}
              disabled={isDebating}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all ${
                isDebating 
                  ? 'bg-gray-700 text-gray-400 cursor-not-allowed' 
                  : 'bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white shadow-lg shadow-cyan-500/25'
              }`}
            >
              {isDebating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              빠른 픽
            </button>
            <button
              onClick={handleFullScan}
              disabled={isDebating}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all ${
                isDebating 
                  ? 'bg-gray-700 text-gray-400 cursor-not-allowed' 
                  : 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-400 hover:to-pink-400 text-white shadow-lg shadow-purple-500/25'
              }`}
            >
              {isDebating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Target className="w-4 h-4" />
              )}
              전체 스캔
            </button>
          </div>
        </div>
      </div>

      {/* 로딩 상태 */}
      {isDebating && (
        <div className="p-8 flex flex-col items-center justify-center">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 rounded-full bg-orange-500/20 flex items-center justify-center animate-bounce" style={{ animationDelay: '0ms' }}>
              <span className="text-2xl">🟠</span>
            </div>
            <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center animate-bounce" style={{ animationDelay: '150ms' }}>
              <span className="text-2xl">🟢</span>
            </div>
            <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center animate-bounce" style={{ animationDelay: '300ms' }}>
              <span className="text-2xl">🔵</span>
            </div>
          </div>
          <p className="text-gray-400 animate-pulse">AI 3대장이 토론 중입니다...</p>
          <p className="text-xs text-gray-500 mt-2">각 AI가 시장 데이터를 분석하고 의견을 교환합니다</p>
        </div>
      )}

      {/* 에러 */}
      {error && (
        <div className="p-4 m-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400">
          {error}
        </div>
      )}

      {/* 스캔 결과 */}
      {scanResults && !isDebating && (
        <div className="p-4 space-y-4">
          {/* 요약 */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-[#252538] rounded-xl p-3 text-center">
              <div className="text-2xl font-bold text-cyan-400">{scanResults.summary?.total_scanned || 0}</div>
              <div className="text-xs text-gray-400">분석 완료</div>
            </div>
            <div className="bg-[#252538] rounded-xl p-3 text-center">
              <div className="text-2xl font-bold text-green-400">{scanResults.summary?.total_bought || scanResults.bought?.length || 0}</div>
              <div className="text-xs text-gray-400">매수 실행</div>
            </div>
            <div className="bg-[#252538] rounded-xl p-3 text-center">
              <div className="text-2xl font-bold text-gray-400">{scanResults.summary?.total_skipped || scanResults.skipped?.length || 0}</div>
              <div className="text-xs text-gray-400">패스</div>
            </div>
          </div>

          {/* 매수 완료 */}
          {(scanResults.bought?.length > 0 || scanResults.pick) && (
            <div className="bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/30 rounded-xl p-4">
              <h3 className="text-green-400 font-bold mb-3 flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                ✅ 매수 완료
              </h3>
              {scanResults.pick ? (
                <div className="bg-[#1a1a2e] rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-lg font-bold text-white">{scanResults.pick.ticker}</span>
                    <span className={`px-2 py-1 rounded text-xs ${OPINION_LABELS[scanResults.pick.verdict?.toLowerCase().replace(' ', '_')]?.color || 'bg-gray-500/20'}`}>
                      {scanResults.pick.verdict}
                    </span>
                  </div>
                  <div className="text-sm text-gray-400">
                    신뢰도: <span className="text-cyan-400">{scanResults.pick.confidence}%</span>
                  </div>
                  <div className="mt-2 text-xs text-gray-500">
                    {scanResults.pick.reasons?.join(' • ')}
                  </div>
                </div>
              ) : (
                scanResults.bought?.map((item, i) => (
                  <div key={i} className="bg-[#1a1a2e] rounded-lg p-3 mb-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold">{item.ticker}</span>
                      <span className="text-green-400">{item.verdict}</span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {item.reasons?.join(' • ')}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* 토론 내용 */}
          {(scanResults.all_debates || scanResults.debates)?.slice(0, 3).map((debate, index) => (
            <div key={index} className="bg-[#252538] rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="font-bold text-white">{debate.ticker} ({debate.coin_name})</span>
                <span className={`px-2 py-1 rounded text-xs ${OPINION_LABELS[debate.consensus]?.color || 'bg-gray-500/20'}`}>
                  {debate.final_verdict}
                </span>
              </div>
              
              {/* AI 의견들 */}
              <div className="space-y-2">
                {debate.messages?.map((msg, i) => {
                  const expert = EXPERT_INFO[msg.expert_id];
                  return (
                    <div key={i} className={`${expert?.bg} ${expert?.border} border rounded-lg p-3`}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg">{expert?.avatar}</span>
                        <span className={`font-medium ${expert?.text}`}>{expert?.name}</span>
                        <span className={`ml-auto px-2 py-0.5 rounded text-xs ${OPINION_LABELS[msg.opinion]?.color}`}>
                          {OPINION_LABELS[msg.opinion]?.label}
                        </span>
                      </div>
                      <p className="text-sm text-gray-300">{msg.content}</p>
                      {msg.key_points?.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {msg.key_points.map((point, j) => (
                            <span key={j} className="text-xs bg-black/20 px-2 py-0.5 rounded text-gray-400">
                              {point}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {/* 매수 안 함 메시지 */}
          {scanResults.action === 'no_buy' && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 text-center">
              <p className="text-yellow-400">{scanResults.message}</p>
              <p className="text-xs text-gray-500 mt-1">더 좋은 기회를 기다리고 있습니다</p>
            </div>
          )}
        </div>
      )}

      {/* 초기 상태 */}
      {!isDebating && !scanResults && !error && (
        <div className="p-8 text-center">
          <div className="flex justify-center gap-4 mb-4">
            <div className="w-16 h-16 rounded-full bg-orange-500/10 flex items-center justify-center">
              <span className="text-3xl">🟠</span>
            </div>
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center">
              <span className="text-3xl">🟢</span>
            </div>
            <div className="w-16 h-16 rounded-full bg-blue-500/10 flex items-center justify-center">
              <span className="text-3xl">🔵</span>
            </div>
          </div>
          <h3 className="text-lg font-bold text-white mb-2">AI 3대장 토론 시스템</h3>
          <p className="text-gray-400 text-sm mb-4">
            Gemini 3, Claude Opus 4.5, GPT 5.2가 시장을 분석하고<br/>
            토론을 통해 최적의 매수 타이밍을 찾습니다
          </p>
          <div className="flex justify-center gap-4">
            <div className="text-center">
              <div className="text-cyan-400 font-bold">빠른 픽</div>
              <div className="text-xs text-gray-500">상위 5개 코인 스캔</div>
            </div>
            <div className="text-center">
              <div className="text-purple-400 font-bold">전체 스캔</div>
              <div className="text-xs text-gray-500">상위 10개 코인 분석</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

