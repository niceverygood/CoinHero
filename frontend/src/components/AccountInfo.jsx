import React, { useState, useEffect } from 'react';
import { 
  Wallet, Shield, ShieldOff, RefreshCw, Key, 
  CheckCircle, XCircle, AlertTriangle, Eye, EyeOff,
  TrendingUp, TrendingDown, Coins, DollarSign
} from 'lucide-react';

function AccountInfo() {
  const [authStatus, setAuthStatus] = useState(null);
  const [balances, setBalances] = useState([]);
  const [totalValue, setTotalValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showDetails, setShowDetails] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // 인증 상태 확인
  const checkAuth = async () => {
    try {
      const res = await fetch('/api/auth/status');
      const data = await res.json();
      setAuthStatus(data);
    } catch (e) {
      setAuthStatus({
        authenticated: false,
        status: 'error',
        message: '서버 연결 실패'
      });
    }
  };

  // 잔고 조회
  const fetchBalances = async () => {
    try {
      const res = await fetch('/api/balance');
      const data = await res.json();
      setBalances(data.balances || []);
      setTotalValue(data.total_krw || 0);
    } catch (e) {
      console.error('잔고 조회 실패:', e);
    }
  };

  // 새로고침
  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([checkAuth(), fetchBalances()]);
    setRefreshing(false);
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([checkAuth(), fetchBalances()]);
      setLoading(false);
    };
    loadData();

    // 30초마다 자동 새로고침
    const interval = setInterval(() => {
      checkAuth();
      fetchBalances();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  // 인증 상태 아이콘 및 색상
  const getStatusInfo = () => {
    if (!authStatus) return { icon: AlertTriangle, color: 'text-gray-400', bg: 'bg-gray-500/20' };
    
    switch (authStatus.status) {
      case 'connected':
        return { icon: Shield, color: 'text-crypto-green', bg: 'bg-crypto-green/20', label: '연결됨' };
      case 'expired':
        return { icon: ShieldOff, color: 'text-crypto-red', bg: 'bg-crypto-red/20', label: 'API 키 만료' };
      case 'invalid_key':
        return { icon: XCircle, color: 'text-crypto-red', bg: 'bg-crypto-red/20', label: '잘못된 키' };
      default:
        return { icon: AlertTriangle, color: 'text-crypto-yellow', bg: 'bg-crypto-yellow/20', label: '연결 오류' };
    }
  };

  const statusInfo = getStatusInfo();
  const StatusIcon = statusInfo.icon;

  // 코인별 잔고 (KRW 제외) - balance를 명시적으로 숫자로 변환
  const coinBalances = balances.filter(b => b.currency !== 'KRW' && parseFloat(b.balance) > 0);
  const krwBalance = balances.find(b => b.currency === 'KRW');

  if (loading) {
    return (
      <div className="glass-card rounded-2xl p-5">
        <div className="flex items-center justify-center py-8">
          <div className="w-8 h-8 border-4 border-crypto-accent/30 border-t-crypto-accent rounded-full animate-spin"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card rounded-2xl p-5">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Wallet className="w-5 h-5 text-crypto-accent" />
          <span className="text-sm text-gray-400">계좌 정보</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="p-1.5 rounded-lg hover:bg-crypto-border/50 transition-colors"
          >
            {showDetails ? <Eye className="w-4 h-4 text-gray-400" /> : <EyeOff className="w-4 h-4 text-gray-400" />}
          </button>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="p-1.5 rounded-lg hover:bg-crypto-border/50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 text-gray-400 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* API 연결 상태 */}
      <div className={`p-4 rounded-xl ${statusInfo.bg} border ${
        authStatus?.authenticated ? 'border-crypto-green/30' : 'border-crypto-red/30'
      } mb-4`}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <StatusIcon className={`w-5 h-5 ${statusInfo.color}`} />
            <span className={`font-medium ${statusInfo.color}`}>
              {authStatus?.authenticated ? '업비트 연결됨' : statusInfo.label}
            </span>
          </div>
          {authStatus?.authenticated ? (
            <CheckCircle className="w-5 h-5 text-crypto-green" />
          ) : (
            <XCircle className="w-5 h-5 text-crypto-red" />
          )}
        </div>
        
        {/* API 키 미리보기 */}
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Key className="w-3 h-3" />
          <span>API Key: {authStatus?.api_key_preview || '없음'}</span>
        </div>
        
        {/* 오류 메시지 */}
        {!authStatus?.authenticated && authStatus?.message && (
          <div className="mt-2 text-xs text-crypto-red">
            ⚠️ {authStatus.message}
          </div>
        )}
      </div>

      {/* 총 자산 */}
      <div className="mb-4">
        <div className="text-xs text-gray-500 mb-1">총 평가자산</div>
        <div className="text-3xl font-bold text-white">
          {showDetails ? `₩${totalValue.toLocaleString()}` : '₩ ********'}
        </div>
      </div>

      {/* KRW 잔고 */}
      {krwBalance && (
        <div className="p-3 bg-crypto-darker/50 rounded-xl mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-yellow-500 to-orange-500 flex items-center justify-center">
                <DollarSign className="w-4 h-4 text-white" />
              </div>
              <div>
                <div className="text-white font-medium">KRW</div>
                <div className="text-xs text-gray-500">보유 원화</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-white font-medium">
                {showDetails ? `₩${Math.floor(krwBalance.balance).toLocaleString()}` : '₩ ********'}
              </div>
              {krwBalance.locked > 0 && (
                <div className="text-xs text-crypto-yellow">
                  잠김: ₩{Math.floor(krwBalance.locked).toLocaleString()}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 보유 코인 */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Coins className="w-4 h-4 text-crypto-purple" />
          <span className="text-xs text-gray-400">보유 코인 ({coinBalances.length})</span>
        </div>
        
        {coinBalances.length > 0 ? (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {coinBalances.map((balance) => (
              <div 
                key={balance.currency}
                className="p-3 bg-crypto-darker/50 rounded-xl"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-xs font-bold text-white">
                      {balance.currency.slice(0, 2)}
                    </div>
                    <span className="text-white font-medium">{balance.currency}</span>
                  </div>
                  <div className={`flex items-center gap-1 text-sm ${
                    balance.profit_rate >= 0 ? 'text-crypto-green' : 'text-crypto-red'
                  }`}>
                    {balance.profit_rate >= 0 ? (
                      <TrendingUp className="w-3 h-3" />
                    ) : (
                      <TrendingDown className="w-3 h-3" />
                    )}
                    {balance.profit_rate >= 0 ? '+' : ''}{balance.profit_rate}%
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-gray-500">보유량</span>
                    <div className="text-white">
                      {showDetails ? balance.balance.toFixed(8) : '********'}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-gray-500">평가금액</span>
                    <div className="text-white">
                      {showDetails ? `₩${Math.floor(balance.eval_amount).toLocaleString()}` : '₩ ********'}
                    </div>
                  </div>
                  <div>
                    <span className="text-gray-500">평균매수가</span>
                    <div className="text-gray-300">
                      ₩{balance.avg_buy_price.toLocaleString()}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-gray-500">현재가</span>
                    <div className="text-gray-300">
                      ₩{balance.current_price?.toLocaleString() || '-'}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500">
            <Coins className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">보유 코인 없음</p>
            {!authStatus?.authenticated && (
              <p className="text-xs mt-1 text-crypto-yellow">
                API 키 연결 후 확인 가능합니다
              </p>
            )}
          </div>
        )}
      </div>

      {/* API 키 안내 */}
      {!authStatus?.authenticated && (
        <div className="mt-4 p-3 bg-crypto-yellow/10 border border-crypto-yellow/30 rounded-xl">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-crypto-yellow mt-0.5" />
            <div className="text-xs text-gray-300">
              <p className="font-medium text-crypto-yellow mb-1">API 키 설정 필요</p>
              <p>업비트에서 새 API 키를 발급받아 설정해주세요.</p>
              <p className="text-gray-500 mt-1">업비트 → 마이페이지 → Open API 관리</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AccountInfo;



