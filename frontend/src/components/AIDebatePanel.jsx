import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageCircle, 
  Play, 
  Pause, 
  RefreshCw, 
  Clock,
  TrendingUp,
  TrendingDown,
  Minus,
  Users,
  Trophy,
  Sparkles,
  Brain
} from 'lucide-react';

const API_BASE = import.meta.env.PROD
  ? 'https://coinhero-production.up.railway.app'
  : '';

// AI 전문가 아바타
const ExpertAvatar = ({ expert, isThinking }) => {
  const colors = {
    claude: { bg: 'from-orange-500 to-amber-500', border: 'border-orange-400', emoji: '🟠' },
    gemini: { bg: 'from-emerald-500 to-teal-500', border: 'border-emerald-400', emoji: '🟢' },
    gpt: { bg: 'from-blue-500 to-indigo-500', border: 'border-blue-400', emoji: '🔵' }
  };
  const style = colors[expert.id] || colors.claude;
  
  return (
    <div className={`relative flex-shrink-0`}>
      <div className={`w-12 h-12 rounded-full bg-gradient-to-br ${style.bg} flex items-center justify-center border-2 ${style.border} ${isThinking ? 'animate-pulse' : ''}`}>
        <span className="text-2xl">{style.emoji}</span>
      </div>
      {isThinking && (
        <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-zinc-800 rounded-full flex items-center justify-center">
          <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
        </div>
      )}
    </div>
  );
};

// 의견 뱃지
const OpinionBadge = ({ opinion, confidence }) => {
  const styles = {
    strong_buy: { bg: 'bg-green-500/20', text: 'text-green-400', label: '강력 매수', icon: <TrendingUp className="w-3 h-3" /> },
    buy: { bg: 'bg-green-500/10', text: 'text-green-300', label: '매수', icon: <TrendingUp className="w-3 h-3" /> },
    hold: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', label: '관망', icon: <Minus className="w-3 h-3" /> },
    sell: { bg: 'bg-red-500/10', text: 'text-red-300', label: '매도', icon: <TrendingDown className="w-3 h-3" /> },
    strong_sell: { bg: 'bg-red-500/20', text: 'text-red-400', label: '강력 매도', icon: <TrendingDown className="w-3 h-3" /> }
  };
  const style = styles[opinion] || styles.hold;
  
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full ${style.bg} ${style.text} text-xs font-medium`}>
      {style.icon}
      <span>{style.label}</span>
      <span className="opacity-70">({confidence}%)</span>
    </div>
  );
};

// 토론 메시지
const DebateMessage = ({ message, expert }) => {
  const colors = {
    claude: 'border-l-orange-500',
    gemini: 'border-l-emerald-500',
    gpt: 'border-l-blue-500'
  };
  
  return (
    <div className={`flex gap-3 p-3 bg-zinc-800/50 rounded-lg border-l-4 ${colors[message.expert_id] || 'border-l-gray-500'}`}>
      <ExpertAvatar expert={{ id: message.expert_id }} isThinking={false} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-white">{message.expert_name}</span>
          <OpinionBadge opinion={message.opinion} confidence={message.confidence} />
        </div>
        <p className="text-sm text-zinc-300 leading-relaxed">{message.content}</p>
        {message.key_points && message.key_points.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {message.key_points.map((point, i) => (
              <span key={i} className="px-2 py-0.5 bg-zinc-700/50 rounded text-xs text-zinc-400">
                {point}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// 최종 추천 카드
const RecommendationCard = ({ recommendation }) => {
  if (!recommendation || !recommendation.final_pick) {
    return (
      <div className="p-4 bg-zinc-800/50 rounded-xl border border-zinc-700/50 text-center">
        <p className="text-zinc-400">아직 추천 결과가 없습니다</p>
      </div>
    );
  }
  
  const { final_pick, summary, timestamp } = recommendation;
  
  return (
    <div className="p-4 bg-gradient-to-br from-yellow-500/10 to-amber-500/5 rounded-xl border border-yellow-500/30">
      <div className="flex items-center gap-2 mb-3">
        <Trophy className="w-5 h-5 text-yellow-400" />
        <span className="font-bold text-yellow-400">AI 3대장 추천</span>
        <span className="text-xs text-zinc-400 ml-auto">
          {new Date(timestamp).toLocaleString('ko-KR')}
        </span>
      </div>
      
      <div className="flex items-center gap-4 mb-3">
        <div className="text-3xl font-bold text-white">{final_pick.coin_name}</div>
        <div className="flex-1">
          <div className="text-lg font-medium text-yellow-400">{final_pick.final_verdict}</div>
          <div className="text-sm text-zinc-400">신뢰도 {final_pick.consensus_confidence}%</div>
        </div>
      </div>
      
      {final_pick.key_reasons && final_pick.key_reasons.length > 0 && (
        <div className="space-y-1">
          {final_pick.key_reasons.slice(0, 3).map((reason, i) => (
            <div key={i} className="flex items-center gap-2 text-sm text-zinc-300">
              <span className="text-yellow-400">•</span>
              {reason}
            </div>
          ))}
        </div>
      )}
      
      <div className="flex gap-4 mt-3 pt-3 border-t border-zinc-700/50 text-xs text-zinc-400">
        <span>분석: {summary?.total_analyzed || 0}개</span>
        <span className="text-green-400">매수: {summary?.buy_recommendations || 0}개</span>
        <span className="text-yellow-400">관망: {summary?.hold_recommendations || 0}개</span>
        <span className="text-red-400">매도: {summary?.sell_recommendations || 0}개</span>
      </div>
    </div>
  );
};

export default function AIDebatePanel() {
  const [status, setStatus] = useState(null);
  const [latestRecommendation, setLatestRecommendation] = useState(null);
  const [liveMessages, setLiveMessages] = useState([]);
  const [currentCoin, setCurrentCoin] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  
  // 상태 조회
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/debate/status`);
      const data = await res.json();
      setStatus(data);
    } catch (e) {
      console.error('토론 상태 조회 실패:', e);
    }
  };
  
  // 최신 추천 조회
  const fetchLatest = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/debate/latest`);
      const data = await res.json();
      if (data.status === 'ok') {
        setLatestRecommendation(data.recommendation);
      }
    } catch (e) {
      console.error('추천 조회 실패:', e);
    }
  };
  
  // 스케줄러 시작
  const startScheduler = async () => {
    try {
      setIsLoading(true);
      await fetch(`${API_BASE}/api/debate/start-scheduler`, { method: 'POST' });
      await fetchStatus();
    } catch (e) {
      console.error('스케줄러 시작 실패:', e);
    } finally {
      setIsLoading(false);
    }
  };
  
  // 스케줄러 중지
  const stopScheduler = async () => {
    try {
      setIsLoading(true);
      await fetch(`${API_BASE}/api/debate/stop-scheduler`, { method: 'POST' });
      await fetchStatus();
    } catch (e) {
      console.error('스케줄러 중지 실패:', e);
    } finally {
      setIsLoading(false);
    }
  };
  
  // 즉시 실행
  const runNow = async () => {
    try {
      setIsLoading(true);
      setLiveMessages([]);
      const res = await fetch(`${API_BASE}/api/debate/run-now`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'completed') {
        setLatestRecommendation(data.result);
      }
      await fetchStatus();
    } catch (e) {
      console.error('즉시 실행 실패:', e);
    } finally {
      setIsLoading(false);
    }
  };
  
  // WebSocket으로 실시간 업데이트 수신
  useEffect(() => {
    const wsUrl = import.meta.env.PROD
      ? 'wss://coinhero-production.up.railway.app/ws'
      : `ws://${window.location.hostname}:8000/ws`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'debate_start') {
        setLiveMessages([]);
        setCurrentCoin(null);
      } else if (data.type === 'debate_progress') {
        setCurrentCoin(data.data.current_coin);
      } else if (data.type === 'expert_opinion') {
        setLiveMessages(prev => [...prev, data.data]);
      } else if (data.type === 'debate_complete') {
        setLatestRecommendation(data.data.recommendation);
        setCurrentCoin(null);
      }
    };
    
    return () => ws.close();
  }, []);
  
  // 초기 로드
  useEffect(() => {
    fetchStatus();
    fetchLatest();
    const interval = setInterval(() => {
      fetchStatus();
      fetchLatest();
    }, 30000);
    return () => clearInterval(interval);
  }, []);
  
  // 메시지 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [liveMessages]);
  
  return (
    <div className="bg-zinc-900/80 backdrop-blur rounded-2xl border border-zinc-800/50 overflow-hidden">
      {/* 헤더 */}
      <div className="p-4 border-b border-zinc-800/50 bg-gradient-to-r from-purple-500/10 to-blue-500/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-blue-500 rounded-xl flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="font-bold text-white flex items-center gap-2">
                AI 3대장 토론
                {status?.is_running && (
                  <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full animate-pulse">
                    ● 자동 실행 중
                  </span>
                )}
              </h2>
              <p className="text-xs text-zinc-400">
                Claude · GPT · Gemini가 매시간 토론하여 추천합니다
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={runNow}
              disabled={isLoading || status?.current_debate}
              className="px-3 py-2 bg-purple-500/20 hover:bg-purple-500/30 text-purple-400 rounded-lg flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4" />
              <span className="text-sm">즉시 토론</span>
            </button>
            
            {status?.is_running ? (
              <button
                onClick={stopScheduler}
                disabled={isLoading}
                className="px-3 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg flex items-center gap-2 transition-colors"
              >
                <Pause className="w-4 h-4" />
                <span className="text-sm">중지</span>
              </button>
            ) : (
              <button
                onClick={startScheduler}
                disabled={isLoading}
                className="px-3 py-2 bg-green-500/20 hover:bg-green-500/30 text-green-400 rounded-lg flex items-center gap-2 transition-colors"
              >
                <Play className="w-4 h-4" />
                <span className="text-sm">매시간 자동</span>
              </button>
            )}
          </div>
        </div>
      </div>
      
      {/* AI 전문가 소개 */}
      <div className="p-4 border-b border-zinc-800/50">
        <div className="flex justify-around">
          {status?.experts && Object.values(status.experts).map((expert) => (
            <div key={expert.id} className="text-center">
              <ExpertAvatar 
                expert={expert} 
                isThinking={status?.current_debate && currentCoin}
              />
              <div className="mt-2">
                <div className="text-sm font-medium text-white">{expert.name_kr}</div>
                <div className="text-xs text-zinc-500">{expert.focus.split(',')[0]}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* 최신 추천 */}
      <div className="p-4 border-b border-zinc-800/50">
        <RecommendationCard recommendation={latestRecommendation} />
      </div>
      
      {/* 실시간 토론 */}
      {(liveMessages.length > 0 || currentCoin) && (
        <div className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <MessageCircle className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-medium text-white">실시간 토론</span>
            {currentCoin && (
              <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded-full">
                {currentCoin} 분석 중...
              </span>
            )}
          </div>
          
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {liveMessages.map((msg, i) => (
              <DebateMessage key={i} message={msg} expert={{ id: msg.expert_id }} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}
      
      {/* 푸터 */}
      <div className="p-3 border-t border-zinc-800/50 bg-zinc-800/30">
        <div className="flex items-center justify-between text-xs text-zinc-500">
          <div className="flex items-center gap-2">
            <Clock className="w-3 h-3" />
            <span>
              마지막 토론: {status?.last_debate_time 
                ? new Date(status.last_debate_time).toLocaleString('ko-KR')
                : '없음'}
            </span>
          </div>
          <span>총 {status?.total_debates || 0}회 토론 완료</span>
        </div>
      </div>
    </div>
  );
}

