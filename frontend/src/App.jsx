import React, { useState, useEffect, useCallback } from 'react';
import { 
  RefreshCw, Zap, Wifi, WifiOff, Clock, Brain, TrendingUp, TrendingDown, DollarSign
} from 'lucide-react';
import AccountInfo from './components/AccountInfo';
import UnifiedTrader from './components/UnifiedTrader';

const API_BASE = '';

function App() {
  const [balances, setBalances] = useState([]);
  const [totalValue, setTotalValue] = useState(0);
  const [trades, setTrades] = useState([]);
  const [aiLogs, setAiLogs] = useState([]);
  const [totalProfit, setTotalProfit] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  // API 호출 함수들
  const fetchBalances = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/balance`);
      const data = await res.json();
      setBalances(data.balances || []);
      setTotalValue(data.total_krw || 0);
    } catch (e) {
      console.error('잔고 조회 실패:', e);
    }
  }, []);

  const fetchTrades = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ai-scalping/logs?limit=50`);
      const data = await res.json();
      const logs = data.logs || [];
      setTrades(logs);
      setAiLogs(data.ai_logs || []);
      
      // 총 수익 계산
      const profit = logs
        .filter(log => log.action === 'sell' && log.profit)
        .reduce((sum, log) => sum + (log.profit || 0), 0);
      setTotalProfit(profit);
    } catch (e) {
      console.error('거래 기록 조회 실패:', e);
    }
  }, []);

  // WebSocket 연결
  useEffect(() => {
    let ws;
    let reconnectTimeout;

    const connect = () => {
      ws = new WebSocket(`ws://${window.location.hostname}:8000/ws`);

      ws.onopen = () => {
        setIsConnected(true);
        console.log('WebSocket 연결됨');
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'balances') {
          setBalances(data.data);
        } else if (data.type === 'trade' || data.type === 'ai_scalping_trade') {
          fetchTrades();
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        console.log('WebSocket 연결 끊김, 재연결 시도...');
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket 오류:', error);
      };
    };

    connect();

    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [fetchTrades]);

  // 초기 데이터 로드
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchBalances(),
        fetchTrades(),
      ]);
      setLoading(false);
    };
    loadData();

    // 주기적 업데이트
    const interval = setInterval(() => {
      fetchBalances();
      fetchTrades();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchBalances, fetchTrades]);

  return (
    <div className="min-h-screen p-4 md:p-6">
      {/* 헤더 */}
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-12 h-12 bg-gradient-to-br from-cyan-500 via-blue-500 to-purple-600 rounded-xl flex items-center justify-center animate-float">
                <Zap className="w-7 h-7 text-white" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-crypto-green rounded-full border-2 border-crypto-dark"></div>
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-display font-bold gradient-text">
                COINHERO
              </h1>
              <p className="text-xs text-gray-500">Upbit Auto Trading System</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
              isConnected ? 'bg-crypto-green/20 text-crypto-green' : 'bg-crypto-red/20 text-crypto-red'
            }`}>
              {isConnected ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
              <span className="text-xs font-medium">{isConnected ? 'LIVE' : 'OFFLINE'}</span>
            </div>
            <button 
              onClick={() => { fetchBalances(); fetchPrices(); fetchBotStatus(); }}
              className="p-2 glass-card rounded-lg hover:bg-crypto-border/50 transition-colors"
            >
              <RefreshCw className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* 메인 그리드 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 md:gap-6">
        
        {/* 좌측: 자산 & AI 자동매매 */}
        <div className="lg:col-span-4 space-y-4">
          {/* 계좌 정보 */}
          <AccountInfo />

          {/* AI 자동매매 */}
          <UnifiedTrader />
        </div>

        {/* 우측: 거래 기록 & AI 로그 */}
        <div className="lg:col-span-8 space-y-4">
          
          {/* 총 손익 현황 */}
          <div className={`glass-card rounded-2xl p-5 ${
            totalProfit >= 0 ? 'border border-green-500/30' : 'border border-red-500/30'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                  totalProfit >= 0 ? 'bg-green-500/20' : 'bg-red-500/20'
                }`}>
                  <DollarSign className={`w-6 h-6 ${totalProfit >= 0 ? 'text-green-400' : 'text-red-400'}`} />
                </div>
                <div>
                  <p className="text-sm text-gray-400">총 실현 손익</p>
                  <p className={`text-2xl font-bold ${totalProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {totalProfit >= 0 ? '+' : ''}₩{totalProfit.toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-400">총 거래</p>
                <p className="text-xl font-bold text-white">{trades.length}건</p>
              </div>
            </div>
          </div>

          {/* 거래 기록 */}
          <div className="glass-card rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-5 h-5 text-purple-400" />
              <span className="text-lg font-bold text-white">실시간 거래 기록</span>
              <span className="text-xs text-gray-500 ml-auto">{trades.length}건</span>
            </div>
            
            {trades.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>거래 기록이 없습니다</p>
                <p className="text-xs mt-1">AI 자동매매를 시작하면 여기에 기록됩니다</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {trades.map((trade, idx) => {
                  const isBuy = trade.action === 'buy';
                  const time = new Date(trade.timestamp);
                  
                  return (
                    <div 
                      key={trade.id || idx}
                      className={`p-4 rounded-xl border transition-all hover:scale-[1.01] ${
                        isBuy 
                          ? 'bg-green-500/5 border-green-500/20' 
                          : 'bg-red-500/5 border-red-500/20'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                            isBuy ? 'bg-green-500/20' : 'bg-red-500/20'
                          }`}>
                            {isBuy 
                              ? <TrendingUp className="w-5 h-5 text-green-400" />
                              : <TrendingDown className="w-5 h-5 text-red-400" />
                            }
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className={`font-bold ${isBuy ? 'text-green-400' : 'text-red-400'}`}>
                                {isBuy ? '매수' : '매도'}
                              </span>
                              <span className="text-white font-medium">{trade.coin_name}</span>
                              {trade.ai_confidence && isBuy && (
                                <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300">
                                  AI {trade.ai_confidence}%
                                </span>
                              )}
                            </div>
                            <span className="text-xs text-gray-500">
                              {time.toLocaleString('ko-KR', { 
                                month: 'short', day: 'numeric', 
                                hour: '2-digit', minute: '2-digit', second: '2-digit' 
                              })}
                            </span>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-white font-medium">₩{trade.price?.toLocaleString()}</p>
                          <p className="text-xs text-gray-400">
                            {trade.amount?.toFixed(6)} × ₩{trade.total_krw?.toLocaleString()}
                          </p>
                        </div>
                      </div>
                      
                      {/* 수익/손실 (매도 시) */}
                      {!isBuy && trade.profit_rate !== undefined && (
                        <div className={`mt-2 p-3 rounded-lg ${
                          trade.profit_rate >= 0 ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'
                        }`}>
                          {/* 매수/매도 금액 비교 */}
                          <div className="flex justify-between items-center text-xs text-gray-400 mb-2">
                            <span>매수: ₩{trade.buy_price?.toLocaleString()} × {trade.amount?.toFixed(4)}개</span>
                            <span>= ₩{trade.buy_total?.toLocaleString()}</span>
                          </div>
                          <div className="flex justify-between items-center text-xs text-gray-400 mb-2">
                            <span>매도: ₩{trade.price?.toLocaleString()} × {trade.amount?.toFixed(4)}개</span>
                            <span>= ₩{trade.total_krw?.toLocaleString()}</span>
                          </div>
                          {/* 손익 표시 */}
                          <div className={`flex items-center justify-between pt-2 border-t ${
                            trade.profit_rate >= 0 ? 'border-green-500/30' : 'border-red-500/30'
                          }`}>
                            <span className={`text-lg font-bold ${
                              trade.profit_rate >= 0 ? 'text-green-400' : 'text-red-400'
                            }`}>
                              {trade.profit_rate >= 0 ? '📈 수익' : '📉 손실'}
                            </span>
                            <div className="text-right">
                              <span className={`text-lg font-bold ${
                                trade.profit >= 0 ? 'text-green-400' : 'text-red-400'
                              }`}>
                                {trade.profit >= 0 ? '+' : ''}₩{Math.abs(trade.profit || 0).toLocaleString()}
                              </span>
                              <span className={`ml-2 text-sm ${
                                trade.profit_rate >= 0 ? 'text-green-400' : 'text-red-400'
                              }`}>
                                ({trade.profit_rate >= 0 ? '+' : ''}{trade.profit_rate?.toFixed(2)}%)
                              </span>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {/* AI 판단 이유 */}
                      {trade.ai_reason && (
                        <div className="mt-2 p-3 rounded-lg bg-purple-500/10 border-l-2 border-purple-500">
                          <div className="flex items-start gap-2">
                            <Brain className="w-4 h-4 text-purple-400 mt-0.5 flex-shrink-0" />
                            <p className="text-sm text-purple-200">{trade.ai_reason}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 푸터 */}
      <footer className="mt-8 text-center text-gray-600 text-xs">
        <p>⚠️ 자동거래는 투자 손실의 위험이 있습니다. 신중하게 사용하세요.</p>
        <p className="mt-1">CoinHero v1.0.0 | Powered by Upbit API</p>
      </footer>
    </div>
  );
}

export default App;

