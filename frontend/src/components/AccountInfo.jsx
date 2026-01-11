import React, { useState, useEffect } from 'react';
import { Wallet, TrendingUp, TrendingDown, RefreshCw, Settings, CheckCircle2, XCircle, Loader2, Calendar, Clock } from 'lucide-react';

const API_BASE = import.meta.env.PROD 
  ? 'https://coinhero-production.up.railway.app' 
  : '';

export default function AccountInfo({ onOpenSettings }) {
  const [accountData, setAccountData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAccountInfo = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/settings/upbit`);
      const data = await response.json();
      setAccountData(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccountInfo();
    // 30초마다 새로고침
    const interval = setInterval(fetchAccountInfo, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !accountData) {
    return (
      <div className="bg-[#1a1a2e] rounded-2xl p-6 border border-gray-800">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
          <span className="ml-2 text-gray-400">계좌 정보 로딩 중...</span>
        </div>
      </div>
    );
  }

  // 연결되지 않은 경우
  if (!accountData?.connected) {
    return (
      <div className="bg-gradient-to-br from-[#1a1a2e] to-[#16162a] rounded-2xl p-6 border border-yellow-500/30">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-500/20 rounded-xl">
              <Wallet className="w-6 h-6 text-yellow-400" />
            </div>
            <div>
              <h3 className="font-bold text-lg">내 계좌</h3>
              <p className="text-xs text-yellow-400">연결 필요</p>
            </div>
          </div>
          <button
            onClick={onOpenSettings}
            className="flex items-center gap-2 px-4 py-2 bg-yellow-500/20 hover:bg-yellow-500/30 border border-yellow-500/50 rounded-xl text-yellow-400 transition-all"
          >
            <Settings className="w-4 h-4" />
            API 연결
          </button>
        </div>
        <div className="bg-yellow-500/10 rounded-xl p-4 text-center">
          <p className="text-yellow-400 mb-2">업비트 API를 연결하면 실시간 계좌 정보를 확인할 수 있습니다</p>
          <p className="text-xs text-gray-500">{accountData?.message || '설정에서 API 키를 입력해주세요'}</p>
        </div>
      </div>
    );
  }

  const { account } = accountData;
  const totalProfit = account?.coins?.reduce((sum, coin) => {
    const profitAmount = coin.eval_amount * (coin.profit_rate / 100);
    return sum + profitAmount;
  }, 0) || 0;
  const totalProfitRate = account?.total_eval > account?.krw_balance 
    ? ((account.total_eval - account.krw_balance) / (account.total_eval - totalProfit) * 100) 
    : 0;

  return (
    <div className="bg-gradient-to-br from-[#1a1a2e] to-[#16162a] rounded-2xl border border-cyan-500/20 overflow-hidden">
      {/* 헤더 */}
      <div className="bg-gradient-to-r from-cyan-600/20 to-blue-600/20 p-4 border-b border-cyan-500/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-xl">
              <Wallet className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <h3 className="font-bold text-lg">내 계좌</h3>
              <div className="flex items-center gap-2 text-xs">
                <CheckCircle2 className="w-3 h-3 text-green-400" />
                <span className="text-green-400">연결됨</span>
                <span className="text-gray-500">({accountData.api_key_preview})</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchAccountInfo}
              className="p-2 hover:bg-white/5 rounded-lg transition-colors"
              title="새로고침"
            >
              <RefreshCw className={`w-4 h-4 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onOpenSettings}
              className="p-2 hover:bg-white/5 rounded-lg transition-colors"
              title="설정"
            >
              <Settings className="w-4 h-4 text-gray-400" />
            </button>
          </div>
        </div>
      </div>

      {/* 총 자산 */}
      <div className="p-4 border-b border-gray-800/50">
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <p className="text-xs text-gray-400 mb-1">보유 현금</p>
            <p className="text-xl font-bold text-white">
              {(account?.krw_balance || 0).toLocaleString()}
              <span className="text-sm text-gray-400 ml-1">원</span>
            </p>
          </div>
          <div className="text-center border-x border-gray-800/50">
            <p className="text-xs text-gray-400 mb-1">총 평가금액</p>
            <p className="text-xl font-bold text-cyan-400">
              {(account?.total_eval || 0).toLocaleString()}
              <span className="text-sm text-gray-400 ml-1">원</span>
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-gray-400 mb-1">보유 코인</p>
            <p className="text-xl font-bold text-purple-400">
              {account?.coin_count || 0}
              <span className="text-sm text-gray-400 ml-1">종목</span>
            </p>
          </div>
        </div>
      </div>

      {/* 보유 코인 목록 */}
      {account?.coins && account.coins.length > 0 && (
        <div className="p-4">
          <h4 className="text-sm font-medium text-gray-400 mb-3">보유 코인</h4>
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            {account.coins.map((coin, idx) => {
              // 매수일시 포맷팅
              const formatBuyDate = (dateStr) => {
                if (!dateStr) return null;
                try {
                  const date = new Date(dateStr);
                  return {
                    date: date.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }),
                    time: date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
                  };
                } catch { return null; }
              };
              const buyDateInfo = formatBuyDate(coin.buy_datetime);
              
              return (
                <div 
                  key={idx} 
                  className="bg-[#252538] rounded-xl p-4 hover:bg-[#2a2a42] transition-colors"
                >
                  {/* 상단: 코인명 + 수익률 */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-sm font-bold">
                        {coin.currency.slice(0, 2)}
                      </div>
                      <div>
                        <p className="font-bold text-lg">{coin.currency}</p>
                        <p className="text-xs text-gray-400">
                          {coin.balance.toFixed(4)} 개
                        </p>
                      </div>
                    </div>
                    <div className={`px-3 py-1 rounded-lg text-sm font-bold ${
                      coin.profit_rate >= 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {coin.profit_rate >= 0 ? (
                        <span className="flex items-center gap-1">
                          <TrendingUp className="w-4 h-4" />
                          +{coin.profit_rate.toFixed(2)}%
                        </span>
                      ) : (
                        <span className="flex items-center gap-1">
                          <TrendingDown className="w-4 h-4" />
                          {coin.profit_rate.toFixed(2)}%
                        </span>
                      )}
                    </div>
                  </div>
                  
                  {/* 중간: 가격 정보 그리드 */}
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="bg-[#1a1a2e] rounded-lg p-2">
                      <p className="text-xs text-gray-500 mb-1">평균 매수가</p>
                      <p className="text-sm font-medium text-yellow-400">
                        {(coin.avg_buy_price || 0).toLocaleString()}원
                      </p>
                    </div>
                    <div className="bg-[#1a1a2e] rounded-lg p-2">
                      <p className="text-xs text-gray-500 mb-1">현재가</p>
                      <p className="text-sm font-medium text-cyan-400">
                        {(coin.current_price || 0).toLocaleString()}원
                      </p>
                    </div>
                    <div className="bg-[#1a1a2e] rounded-lg p-2">
                      <p className="text-xs text-gray-500 mb-1">매수 총액</p>
                      <p className="text-sm font-medium text-gray-300">
                        {(coin.buy_total || 0).toLocaleString()}원
                      </p>
                    </div>
                    <div className="bg-[#1a1a2e] rounded-lg p-2">
                      <p className="text-xs text-gray-500 mb-1">평가 금액</p>
                      <p className="text-sm font-medium text-white">
                        {(coin.eval_amount || 0).toLocaleString()}원
                      </p>
                    </div>
                  </div>
                  
                  {/* 하단: 손익금액 + 매수일시 */}
                  <div className="flex items-center justify-between pt-2 border-t border-gray-700/50">
                    <div>
                      <span className="text-xs text-gray-500 mr-2">손익</span>
                      <span className={`text-sm font-bold ${
                        (coin.profit_amount || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {(coin.profit_amount || 0) >= 0 ? '+' : ''}{(coin.profit_amount || 0).toLocaleString()}원
                      </span>
                    </div>
                    {buyDateInfo ? (
                      <div className="flex items-center gap-2 text-xs text-gray-500">
                        <Calendar className="w-3 h-3" />
                        <span>{buyDateInfo.date}</span>
                        <Clock className="w-3 h-3" />
                        <span>{buyDateInfo.time}</span>
                      </div>
                    ) : (
                      <div className="text-xs text-gray-600">매수일 정보 없음</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 코인이 없는 경우 */}
      {(!account?.coins || account.coins.length === 0) && (
        <div className="p-6 text-center text-gray-500">
          <p>보유 중인 코인이 없습니다</p>
        </div>
      )}
    </div>
  );
}
