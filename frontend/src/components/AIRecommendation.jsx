import React, { useState, useEffect, useCallback } from 'react';
import { 
  Sparkles, TrendingUp, TrendingDown, Minus, RefreshCw, 
  Brain, Target, Zap, Clock, Star, AlertCircle, ChevronRight,
  BarChart3, Activity, DollarSign, Trophy, Users
} from 'lucide-react';

const API_BASE = import.meta.env.PROD
  ? 'https://coinhero-production.up.railway.app'
  : '';

// AI 전문가 정보
const AI_EXPERTS = {
  claude: { name: '클로드 리', emoji: '🟠', color: 'from-orange-500 to-amber-500', role: '균형 분석가' },
  gemini: { name: '제미 나인', emoji: '🟢', color: 'from-emerald-500 to-teal-500', role: '트렌드 전략가' },
  gpt: { name: '지피 테일러', emoji: '🔵', color: 'from-blue-500 to-indigo-500', role: '리스크 총괄' }
};

// 추천 강도 색상
const getRecommendationColor = (action, confidence) => {
  if (action === 'BUY') {
    if (confidence >= 80) return 'from-green-500 to-emerald-500';
    if (confidence >= 60) return 'from-green-400 to-teal-400';
    return 'from-green-300 to-green-400';
  }
  if (action === 'SELL') {
    if (confidence >= 80) return 'from-red-500 to-rose-500';
    if (confidence >= 60) return 'from-red-400 to-pink-400';
    return 'from-red-300 to-red-400';
  }
  return 'from-gray-500 to-gray-600';
};

export default function AIRecommendation() {
  const [debateStatus, setDebateStatus] = useState(null);
  const [latestDebate, setLatestDebate] = useState(null);
  const [topPicks, setTopPicks] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDebating, setIsDebating] = useState(false);

  // 데이터 로드
  const fetchData = useCallback(async () => {
    try {
      const [statusRes, latestRes, picksRes] = await Promise.all([
        fetch(`${API_BASE}/api/debate/status`),
        fetch(`${API_BASE}/api/debate/latest`),
        fetch(`${API_BASE}/api/debate/top-picks?n=10`)
      ]);
      
      const status = await statusRes.json();
      const latest = await latestRes.json();
      const picks = await picksRes.json();
      
      setDebateStatus(status);
      setLatestDebate(latest);
      setTopPicks(picks.picks || []);
    } catch (err) {
      console.error('데이터 로드 실패:', err);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // 즉시 토론 실행
  const runDebateNow = async () => {
    setIsDebating(true);
    try {
      const res = await fetch(`${API_BASE}/api/debate/run-now`, { method: 'POST' });
      const data = await res.json();
      console.log('토론 시작:', data);
      
      // 토론 완료까지 대기 후 데이터 갱신
      setTimeout(() => {
        fetchData();
        setIsDebating(false);
      }, 60000); // 1분 후 갱신
    } catch (err) {
      console.error('토론 실행 실패:', err);
      setIsDebating(false);
    }
  };

  // 시간 포맷
  const formatTime = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleString('ko-KR', { 
      month: 'short', day: 'numeric', 
      hour: '2-digit', minute: '2-digit' 
    });
  };

  return (
    <div className="space-y-6">
      {/* 상단 히어로 섹션 */}
      <div className="bg-gradient-to-br from-[#1a1a2e] via-[#16162a] to-[#1a1a2e] rounded-3xl p-8 border border-cyan-500/20 relative overflow-hidden">
        {/* 배경 효과 */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxwYXRoIGQ9Ik0zNiAxOGMtOS45NDEgMC0xOCA4LjA1OS0xOCAxOHM4LjA1OSAxOCAxOCAxOCAxOC04LjA1OSAxOC0xOC04LjA1OS0xOC0xOC0xOHptMCAzMmMtNy43MzIgMC0xNC02LjI2OC0xNC0xNHM2LjI2OC0xNCAxNC0xNCAxNCA2LjI2OCAxNCAxNC02LjI2OCAxNC0xNCAxNHoiIGZpbGw9IiMwZWE1ZTkiIGZpbGwtb3BhY2l0eT0iLjAzIi8+PC9nPjwvc3ZnPg==')] opacity-30" />
        
        <div className="relative flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                <Sparkles className="w-7 h-7 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">AI 코인추천</h2>
                <p className="text-gray-400 text-sm">3개 AI가 실시간 토론하여 추천합니다</p>
              </div>
            </div>
            
            {/* AI 전문가 소개 */}
            <div className="flex gap-4 mt-6">
              {Object.entries(AI_EXPERTS).map(([id, expert]) => (
                <div key={id} className="flex items-center gap-2 bg-[#252538]/50 px-3 py-2 rounded-xl">
                  <span className="text-xl">{expert.emoji}</span>
                  <div>
                    <p className="text-white text-sm font-medium">{expert.name}</p>
                    <p className="text-gray-500 text-xs">{expert.role}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* 상태 및 버튼 */}
          <div className="text-right">
            <div className="mb-4">
              <p className="text-gray-400 text-sm mb-1">마지막 분석</p>
              <p className="text-white font-mono">{formatTime(latestDebate?.timestamp)}</p>
            </div>
            <button
              onClick={runDebateNow}
              disabled={isDebating}
              className={`px-6 py-3 rounded-xl font-medium flex items-center gap-2 transition-all ${
                isDebating
                  ? 'bg-gray-600 cursor-not-allowed'
                  : 'bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 shadow-lg shadow-cyan-500/25'
              }`}
            >
              {isDebating ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  AI 토론 중...
                </>
              ) : (
                <>
                  <Brain className="w-5 h-5" />
                  즉시 분석
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* 추천 코인 그리드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {latestDebate?.results?.map((result, idx) => (
          <CoinRecommendCard key={result.ticker || idx} result={result} rank={idx + 1} />
        ))}
        
        {(!latestDebate?.results || latestDebate.results.length === 0) && (
          <div className="col-span-full bg-[#1a1a2e] rounded-2xl p-12 border border-gray-800 text-center">
            <Brain className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-gray-400 mb-2">아직 분석 결과가 없습니다</h3>
            <p className="text-gray-500 mb-6">위의 "즉시 분석" 버튼을 클릭하여 AI 토론을 시작하세요</p>
            <button
              onClick={runDebateNow}
              disabled={isDebating}
              className="px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-xl font-medium"
            >
              AI 분석 시작하기
            </button>
          </div>
        )}
      </div>

      {/* 토론 요약 */}
      {latestDebate?.summary && (
        <div className="bg-[#1a1a2e] rounded-2xl p-6 border border-gray-800">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-cyan-400" />
            AI 토론 요약
          </h3>
          <p className="text-gray-300 leading-relaxed">{latestDebate.summary}</p>
        </div>
      )}
    </div>
  );
}

// 코인 추천 카드 컴포넌트
function CoinRecommendCard({ result, rank }) {
  const consensus = result.consensus || {};
  const action = consensus.action || 'HOLD';
  const confidence = consensus.confidence || 50;
  const coinName = result.ticker?.replace('KRW-', '') || 'Unknown';
  
  const getActionIcon = () => {
    if (action === 'BUY') return <TrendingUp className="w-5 h-5" />;
    if (action === 'SELL') return <TrendingDown className="w-5 h-5" />;
    return <Minus className="w-5 h-5" />;
  };
  
  const getActionColor = () => {
    if (action === 'BUY') return 'text-green-400 bg-green-500/20';
    if (action === 'SELL') return 'text-red-400 bg-red-500/20';
    return 'text-gray-400 bg-gray-500/20';
  };
  
  const getActionText = () => {
    if (action === 'BUY') return '매수 추천';
    if (action === 'SELL') return '매도 추천';
    return '관망';
  };

  return (
    <div className="bg-gradient-to-br from-[#1a1a2e] to-[#16162a] rounded-2xl p-5 border border-gray-800 hover:border-cyan-500/30 transition-all group">
      {/* 헤더 */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          {rank <= 3 && (
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
              rank === 1 ? 'bg-yellow-500/20 text-yellow-400' :
              rank === 2 ? 'bg-gray-400/20 text-gray-300' :
              'bg-orange-500/20 text-orange-400'
            }`}>
              <Trophy className="w-4 h-4" />
            </div>
          )}
          <div>
            <h4 className="text-lg font-bold text-white">{coinName}</h4>
            <p className="text-gray-500 text-xs">{result.ticker}</p>
          </div>
        </div>
        <div className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 ${getActionColor()}`}>
          {getActionIcon()}
          <span className="font-medium text-sm">{getActionText()}</span>
        </div>
      </div>
      
      {/* 신뢰도 바 */}
      <div className="mb-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-400">AI 합의 신뢰도</span>
          <span className={`font-bold ${
            confidence >= 70 ? 'text-green-400' : confidence >= 50 ? 'text-yellow-400' : 'text-gray-400'
          }`}>{confidence}%</span>
        </div>
        <div className="h-2 bg-[#252538] rounded-full overflow-hidden">
          <div 
            className={`h-full rounded-full bg-gradient-to-r ${getRecommendationColor(action, confidence)}`}
            style={{ width: `${confidence}%` }}
          />
        </div>
      </div>
      
      {/* AI 의견 */}
      <div className="space-y-2">
        {result.opinions?.slice(0, 3).map((opinion, idx) => {
          const expertId = ['claude', 'gemini', 'gpt'][idx];
          const expert = AI_EXPERTS[expertId] || AI_EXPERTS.claude;
          return (
            <div key={idx} className="flex items-center gap-2 text-sm">
              <span>{expert.emoji}</span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                opinion.action === 'BUY' ? 'bg-green-500/20 text-green-400' :
                opinion.action === 'SELL' ? 'bg-red-500/20 text-red-400' :
                'bg-gray-500/20 text-gray-400'
              }`}>
                {opinion.action}
              </span>
              <span className="text-gray-500">{opinion.confidence}%</span>
            </div>
          );
        })}
      </div>
      
      {/* 이유 */}
      {consensus.reason && (
        <p className="mt-4 text-gray-400 text-sm line-clamp-2 group-hover:line-clamp-none transition-all">
          {consensus.reason}
        </p>
      )}
    </div>
  );
}

