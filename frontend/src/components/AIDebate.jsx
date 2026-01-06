import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageSquare, Users, Trophy, Play, RefreshCw, 
  TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp,
  Sparkles, Target, AlertCircle, CheckCircle2
} from 'lucide-react';

// AI 전문가 캐릭터 정보
const EXPERTS = {
  claude: {
    id: 'claude',
    name: 'Claude Lee',
    name_kr: '클로드 리',
    role: '균형 분석가',
    focus: '기술적 지표 · 온체인 데이터',
    color: 'from-orange-500 to-amber-500',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/30',
    textColor: 'text-orange-400',
    avatar: '👨‍💼'
  },
  gemini: {
    id: 'gemini',
    name: 'Gemi Nine',
    name_kr: '제미 나인',
    role: '트렌드 전략가',
    focus: '신기술 트렌드 · 생태계 분석',
    color: 'from-emerald-500 to-teal-500',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30',
    textColor: 'text-emerald-400',
    avatar: '🧑‍💻'
  },
  gpt: {
    id: 'gpt',
    name: 'G.P. Taylor',
    name_kr: '지피 테일러',
    role: '리스크 총괄',
    focus: '거시경제 · 리스크 분석',
    color: 'from-blue-500 to-indigo-500',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    textColor: 'text-blue-400',
    avatar: '👴'
  }
};

const OPINION_STYLES = {
  strong_buy: { label: '강력 매수', color: 'text-green-400', bg: 'bg-green-500/20', icon: '🚀' },
  buy: { label: '매수', color: 'text-green-400', bg: 'bg-green-500/10', icon: '📈' },
  hold: { label: '관망', color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: '⏸️' },
  sell: { label: '매도', color: 'text-red-400', bg: 'bg-red-500/10', icon: '📉' },
  strong_sell: { label: '강력 매도', color: 'text-red-400', bg: 'bg-red-500/20', icon: '⚠️' },
};

function AIDebate() {
  const [selectedCoin, setSelectedCoin] = useState('KRW-BTC');
  const [debateResult, setDebateResult] = useState(null);
  const [isDebating, setIsDebating] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState([]);
  const [topPicks, setTopPicks] = useState([]);
  const [displayedMessages, setDisplayedMessages] = useState([]);
  const messagesEndRef = useRef(null);

  const coins = [
    { ticker: 'KRW-BTC', name: 'Bitcoin', symbol: 'BTC' },
    { ticker: 'KRW-ETH', name: 'Ethereum', symbol: 'ETH' },
    { ticker: 'KRW-XRP', name: 'Ripple', symbol: 'XRP' },
    { ticker: 'KRW-SOL', name: 'Solana', symbol: 'SOL' },
    { ticker: 'KRW-DOGE', name: 'Dogecoin', symbol: 'DOGE' },
  ];

  // 토론 기록 조회
  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/debate/history?limit=5');
      const data = await res.json();
      setHistory(data.debates || []);
    } catch (e) {
      console.error('토론 기록 조회 실패:', e);
    }
  };

  // Top Picks 조회
  const fetchTopPicks = async () => {
    try {
      const res = await fetch('/api/debate/top-picks?n=3');
      const data = await res.json();
      setTopPicks(data.picks || []);
    } catch (e) {
      console.error('Top Picks 조회 실패:', e);
    }
  };

  useEffect(() => {
    fetchHistory();
    fetchTopPicks();
  }, []);

  // 메시지 순차 표시 애니메이션
  useEffect(() => {
    if (debateResult?.messages) {
      setDisplayedMessages([]);
      debateResult.messages.forEach((msg, index) => {
        setTimeout(() => {
          setDisplayedMessages(prev => [...prev, msg]);
        }, index * 1500); // 1.5초 간격으로 메시지 표시
      });
    }
  }, [debateResult]);

  // 스크롤 자동 이동
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [displayedMessages]);

  // 토론 시작
  const handleStartDebate = async () => {
    setIsDebating(true);
    setDebateResult(null);
    setDisplayedMessages([]);
    
    try {
      const res = await fetch(`/api/debate/${selectedCoin}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setDebateResult(data);
        fetchHistory();
        fetchTopPicks();
      }
    } catch (e) {
      console.error('토론 실패:', e);
    }
    setIsDebating(false);
  };

  const getExpertInfo = (expertId) => EXPERTS[expertId] || EXPERTS.claude;

  return (
    <div className="glass-card rounded-2xl p-5 h-full flex flex-col">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
            <Users className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-white font-semibold flex items-center gap-2">
              AI 3대장 토론
              <span className="text-xs px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded-full">LIVE</span>
            </h3>
            <p className="text-xs text-gray-500">Claude · Gemini · GPT</p>
          </div>
        </div>
        <button 
          onClick={() => { fetchHistory(); fetchTopPicks(); }}
          className="p-2 rounded-lg hover:bg-crypto-border/50 transition-colors"
        >
          <RefreshCw className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      {/* 전문가 소개 */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        {Object.values(EXPERTS).map((expert) => (
          <div 
            key={expert.id}
            className={`p-2 rounded-xl ${expert.bgColor} border ${expert.borderColor} text-center`}
          >
            <div className="text-2xl mb-1">{expert.avatar}</div>
            <div className={`text-xs font-medium ${expert.textColor}`}>{expert.name_kr}</div>
            <div className="text-[10px] text-gray-500">{expert.role}</div>
          </div>
        ))}
      </div>

      {/* 코인 선택 */}
      <div className="mb-4">
        <label className="text-xs text-gray-400 mb-2 block">토론 대상 코인</label>
        <div className="flex flex-wrap gap-2">
          {coins.map((coin) => (
            <button
              key={coin.ticker}
              onClick={() => setSelectedCoin(coin.ticker)}
              disabled={isDebating}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                selectedCoin === coin.ticker
                  ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                  : 'bg-crypto-darker text-gray-400 border border-crypto-border hover:border-gray-500'
              } disabled:opacity-50`}
            >
              {coin.symbol}
            </button>
          ))}
        </div>
      </div>

      {/* 토론 시작 버튼 */}
      <button
        onClick={handleStartDebate}
        disabled={isDebating}
        className="w-full py-3 rounded-xl font-semibold transition-all flex items-center justify-center gap-2 mb-4 bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:opacity-90 disabled:opacity-50"
      >
        {isDebating ? (
          <>
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            AI 전문가들이 토론 중...
          </>
        ) : (
          <>
            <Play className="w-5 h-5" />
            {selectedCoin.replace('KRW-', '')} 토론 시작
          </>
        )}
      </button>

      {/* 토론 진행 상황 */}
      {(isDebating || displayedMessages.length > 0) && (
        <div className="flex-1 overflow-y-auto mb-4 space-y-3 max-h-[400px] p-2 rounded-xl bg-crypto-darker/30">
          {/* 토론 시작 알림 */}
          {isDebating && displayedMessages.length === 0 && (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-purple-500/20 flex items-center justify-center">
                <MessageSquare className="w-8 h-8 text-purple-400 animate-pulse" />
              </div>
              <p className="text-gray-400 text-sm">AI 전문가들이 {selectedCoin.replace('KRW-', '')}를 분석하고 있습니다...</p>
              <p className="text-gray-500 text-xs mt-2">토론이 시작되면 메시지가 순차적으로 표시됩니다</p>
            </div>
          )}

          {/* 메시지 목록 */}
          {displayedMessages.map((msg, index) => {
            const expert = getExpertInfo(msg.expert_id);
            const opinion = OPINION_STYLES[msg.opinion] || OPINION_STYLES.hold;
            
            return (
              <div 
                key={msg.id || index}
                className={`p-4 rounded-xl ${expert.bgColor} border ${expert.borderColor} animate-fadeIn`}
              >
                {/* 전문가 헤더 */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{expert.avatar}</span>
                    <div>
                      <span className={`font-medium ${expert.textColor}`}>{msg.expert_name}</span>
                      <span className="text-xs text-gray-500 ml-2">{expert.role}</span>
                    </div>
                  </div>
                  <div className={`flex items-center gap-1 px-2 py-1 rounded-full ${opinion.bg}`}>
                    <span>{opinion.icon}</span>
                    <span className={`text-xs font-medium ${opinion.color}`}>{opinion.label}</span>
                    <span className="text-xs text-gray-500">{msg.confidence}%</span>
                  </div>
                </div>

                {/* 메시지 내용 */}
                <p className="text-sm text-gray-300 mb-2">{msg.content}</p>

                {/* 핵심 포인트 */}
                {msg.key_points && msg.key_points.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {msg.key_points.map((point, i) => (
                      <span 
                        key={i}
                        className="text-xs px-2 py-0.5 rounded-full bg-crypto-darker text-gray-400"
                      >
                        {point}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {/* 최종 결론 */}
          {debateResult && displayedMessages.length === debateResult.messages?.length && (
            <div className="p-4 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 animate-fadeIn">
              <div className="flex items-center gap-2 mb-3">
                <Trophy className="w-5 h-5 text-yellow-400" />
                <span className="font-semibold text-white">AI 3대장 합의</span>
              </div>
              
              <div className="text-2xl font-bold text-center mb-2">
                {debateResult.final_verdict}
              </div>
              
              <div className="text-center text-gray-400 text-sm mb-3">
                신뢰도: <span className="text-white font-medium">{debateResult.consensus_confidence}%</span>
              </div>

              {debateResult.key_reasons && (
                <div className="space-y-1">
                  <div className="text-xs text-gray-500 mb-1">주요 근거:</div>
                  {debateResult.key_reasons.map((reason, i) => (
                    <div key={i} className="flex items-center gap-1 text-xs text-gray-300">
                      <CheckCircle2 className="w-3 h-3 text-green-400" />
                      {reason}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Top Picks */}
      {topPicks.length > 0 && !isDebating && displayedMessages.length === 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-medium text-white">오늘의 AI Pick</span>
          </div>
          <div className="space-y-2">
            {topPicks.map((pick, i) => (
              <div 
                key={i}
                className="p-3 rounded-xl bg-crypto-darker/50 border border-crypto-border flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold text-yellow-400">#{i + 1}</span>
                  <div>
                    <span className="font-medium text-white">{pick.coin}</span>
                    <span className="text-xs text-gray-500 ml-2">{pick.verdict}</span>
                  </div>
                </div>
                <span className="text-sm text-gray-400">{pick.confidence}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 토론 기록 */}
      <div>
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="flex items-center justify-between w-full text-xs text-gray-400 mb-2"
        >
          <span className="flex items-center gap-1">
            <MessageSquare className="w-3 h-3" />
            최근 토론 기록 ({history.length})
          </span>
          {showHistory ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showHistory && (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {history.length === 0 ? (
              <div className="text-center text-gray-500 text-xs py-4">
                아직 토론 기록이 없습니다
              </div>
            ) : (
              history.map((debate, i) => (
                <div 
                  key={i}
                  className="p-2 rounded-lg bg-crypto-darker/50 border border-crypto-border"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-white text-sm">{debate.coin_name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      debate.consensus.includes('buy') ? 'bg-green-500/20 text-green-400' :
                      debate.consensus.includes('sell') ? 'bg-red-500/20 text-red-400' :
                      'bg-yellow-500/20 text-yellow-400'
                    }`}>
                      {debate.final_verdict}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {new Date(debate.timestamp).toLocaleString('ko-KR')}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.5s ease-out;
        }
      `}</style>
    </div>
  );
}

export default AIDebate;







