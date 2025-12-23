import React from 'react';
import { ArrowUpRight, ArrowDownRight, Clock, CheckCircle, XCircle, Brain, TrendingUp, TrendingDown } from 'lucide-react';

function TradeLog({ trades }) {
  if (!trades || trades.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="w-5 h-5 text-crypto-accent" />
          <span className="text-sm text-gray-400">거래 기록</span>
        </div>
        <div className="text-center text-gray-500 py-8">
          <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>거래 기록이 없습니다</p>
        </div>
      </div>
    );
  }

  // 총 수익 계산
  const totalProfit = trades
    .filter(t => t.profit !== undefined && t.profit !== null)
    .reduce((sum, t) => sum + (t.profit || 0), 0);

  return (
    <div className="glass-card rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-crypto-accent" />
          <span className="text-sm text-gray-400">실시간 거래 기록</span>
        </div>
        <span className="text-xs text-gray-500">{trades.length}건</span>
      </div>
      
      {/* 총 수익/손실 요약 */}
      {totalProfit !== 0 && (
        <div className={`mb-4 p-3 rounded-xl flex items-center justify-between ${
          totalProfit >= 0 
            ? 'bg-crypto-green/10 border border-crypto-green/30' 
            : 'bg-crypto-red/10 border border-crypto-red/30'
        }`}>
          <div className="flex items-center gap-2">
            {totalProfit >= 0 
              ? <TrendingUp className="w-4 h-4 text-crypto-green" />
              : <TrendingDown className="w-4 h-4 text-crypto-red" />
            }
            <span className="text-xs text-gray-400">누적 실현손익</span>
          </div>
          <span className={`font-semibold ${
            totalProfit >= 0 ? 'text-crypto-green' : 'text-crypto-red'
          }`}>
            {totalProfit >= 0 ? '+' : ''}₩{Math.round(totalProfit).toLocaleString()}
          </span>
        </div>
      )}
      
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {trades.map((trade, index) => {
          const isBuy = trade.side === 'buy';
          const isAI = trade.strategy?.startsWith('AI-') || trade.ai_confidence > 0;
          const time = new Date(trade.timestamp);
          const hasProfit = trade.profit_rate !== undefined && trade.profit_rate !== null;
          
          return (
            <div 
              key={index} 
              className={`p-3 rounded-xl border transition-all hover:scale-[1.01] ${
                isBuy 
                  ? 'bg-crypto-green/5 border-crypto-green/20' 
                  : 'bg-crypto-red/5 border-crypto-red/20'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                    isBuy ? 'bg-crypto-green/20' : 'bg-crypto-red/20'
                  }`}>
                    {isBuy 
                      ? <ArrowUpRight className="w-4 h-4 text-crypto-green" />
                      : <ArrowDownRight className="w-4 h-4 text-crypto-red" />
                    }
                  </div>
                  <span className={`text-sm font-medium ${isBuy ? 'text-crypto-green' : 'text-crypto-red'}`}>
                    {isBuy ? '매수' : '매도'}
                  </span>
                  <span className="text-white text-sm font-semibold">
                    {trade.coin_name || trade.ticker?.replace('KRW-', '')}
                  </span>
                  {isAI && (
                    <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-xs">
                      <Brain className="w-3 h-3" />
                      AI
                      {trade.ai_confidence > 0 && ` ${trade.ai_confidence}%`}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {trade.success !== false
                    ? <CheckCircle className="w-4 h-4 text-crypto-green" />
                    : <XCircle className="w-4 h-4 text-crypto-red" />
                  }
                </div>
              </div>
              
              {/* 가격 및 금액 정보 */}
              <div className="flex items-center justify-between text-xs mb-1">
                <div className="text-gray-400">
                  {trade.price > 0 && (
                    <span>₩{trade.price?.toLocaleString()}</span>
                  )}
                  {trade.quantity > 0 && (
                    <span className="ml-1">× {trade.quantity?.toFixed(4)}</span>
                  )}
                </div>
                <span className="text-white font-medium">
                  ₩{Math.floor(trade.amount || 0).toLocaleString()}
                </span>
              </div>
              
              {/* 수익/손실 (매도 시) */}
              {hasProfit && !isBuy && (
                <div className={`flex items-center justify-between py-1.5 px-2 rounded-lg mt-1 ${
                  trade.profit_rate >= 0 
                    ? 'bg-crypto-green/10' 
                    : 'bg-crypto-red/10'
                }`}>
                  <span className="text-xs text-gray-400">실현손익</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-sm font-semibold ${
                      trade.profit_rate >= 0 ? 'text-crypto-green' : 'text-crypto-red'
                    }`}>
                      {trade.profit_rate >= 0 ? '+' : ''}{trade.profit_rate?.toFixed(2)}%
                    </span>
                    {trade.profit !== undefined && (
                      <span className={`text-xs ${
                        trade.profit >= 0 ? 'text-crypto-green' : 'text-crypto-red'
                      }`}>
                        ({trade.profit >= 0 ? '+' : ''}₩{Math.round(trade.profit)?.toLocaleString()})
                      </span>
                    )}
                  </div>
                </div>
              )}
              
              {/* 전략 및 시간 */}
              <div className="flex items-center justify-between text-xs mt-1">
                <div className="text-gray-500">
                  <span className="px-1.5 py-0.5 rounded bg-crypto-darker">
                    {trade.strategy?.replace('AI-', '🤖 ')}
                  </span>
                </div>
                <div className="text-gray-600">
                  {time.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </div>
              </div>
              
              {/* AI 판단 이유 */}
              {trade.reason && (
                <div className="mt-2 p-2 rounded-lg bg-crypto-darker/50 border-l-2 border-purple-500/50">
                  <p className="text-xs text-gray-400 leading-relaxed">
                    🤖 <span className="text-purple-300">AI:</span> {trade.reason}
                  </p>
                </div>
              )}
              
              {trade.error && (
                <div className="mt-2 text-xs text-crypto-red truncate" title={trade.error}>
                  ⚠️ {trade.error}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default TradeLog;
