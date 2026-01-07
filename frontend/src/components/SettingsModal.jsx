import React, { useState, useEffect } from 'react';
import { X, Key, Eye, EyeOff, Save, AlertTriangle, CheckCircle, Wallet, RefreshCw } from 'lucide-react';

export default function SettingsModal({ isOpen, onClose, user, settings, onSave, session }) {
  const [formData, setFormData] = useState({
    upbit_access_key: '',
    upbit_secret_key: '',
    trade_amount: 10000,
    max_positions: 3,
  });
  const [showSecrets, setShowSecrets] = useState({
    upbit_access: false,
    upbit_secret: false,
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [balances, setBalances] = useState(null);
  const [loadingBalance, setLoadingBalance] = useState(false);
  const [totalKRW, setTotalKRW] = useState(0);

  // API Base URL
  const API_BASE = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000' 
    : 'https://coinhero-production.up.railway.app';

  useEffect(() => {
    if (settings) {
      setFormData({
        upbit_access_key: settings.upbit_access_key || '',
        upbit_secret_key: settings.upbit_secret_key || '',
        trade_amount: settings.trade_amount || 10000,
        max_positions: settings.max_positions || 3,
      });
    }
  }, [settings]);

  // API 키가 있으면 잔고 조회
  useEffect(() => {
    if (isOpen && session?.access_token) {
      fetchBalance();
    }
  }, [isOpen, session]);

  const fetchBalance = async () => {
    if (!session?.access_token) return;
    
    setLoadingBalance(true);
    try {
      const res = await fetch(`${API_BASE}/api/user/balance`, {
        headers: {
          'Authorization': `Bearer ${session.access_token}`
        }
      });
      const data = await res.json();
      
      if (data.auth_status === 'connected') {
        setBalances(data.balances);
        setTotalKRW(data.total_krw);
      } else {
        setBalances(null);
      }
    } catch (err) {
      console.error('잔고 조회 실패:', err);
      setBalances(null);
    }
    setLoadingBalance(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await onSave(formData);
      setMessage({ type: 'success', text: '설정이 저장되었습니다!' });
      // 저장 후 잔고 다시 조회
      setTimeout(() => {
        fetchBalance();
        setMessage(null);
      }, 1500);
    } catch (error) {
      setMessage({ type: 'error', text: '저장 실패: ' + error.message });
    }
    setSaving(false);
  };

  const formatKRW = (amount) => {
    if (amount >= 100000000) return `${(amount / 100000000).toFixed(2)}억`;
    if (amount >= 10000) return `${(amount / 10000).toFixed(0)}만`;
    return amount.toLocaleString();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-zinc-900 rounded-2xl w-full max-w-lg mx-4 border border-zinc-800 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <h2 className="text-xl font-bold text-white">⚙️ 설정</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-zinc-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4 max-h-[70vh] overflow-y-auto">
          {/* User Info */}
          <div className="p-3 bg-zinc-800/50 rounded-lg">
            <p className="text-sm text-zinc-400">로그인 계정</p>
            <p className="text-white font-medium">{user?.email}</p>
          </div>

          {/* 계좌 정보 (API 연결 시) */}
          {balances && balances.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-green-400 flex items-center gap-2">
                  <Wallet className="w-4 h-4" />
                  내 계좌
                </h3>
                <button
                  onClick={fetchBalance}
                  disabled={loadingBalance}
                  className="p-1 hover:bg-zinc-700 rounded transition-colors"
                >
                  <RefreshCw className={`w-4 h-4 text-zinc-400 ${loadingBalance ? 'animate-spin' : ''}`} />
                </button>
              </div>
              
              {/* 총 자산 */}
              <div className="p-3 bg-gradient-to-r from-green-500/20 to-cyan-500/20 border border-green-500/30 rounded-lg">
                <p className="text-xs text-zinc-400">총 평가금액</p>
                <p className="text-2xl font-bold text-white">{formatKRW(totalKRW)}원</p>
              </div>
              
              {/* 보유 코인 목록 */}
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {balances.map((coin) => (
                  <div key={coin.currency} className="flex items-center justify-between p-2 bg-zinc-800/50 rounded-lg">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-white">{coin.currency}</span>
                      {coin.currency !== 'KRW' && (
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          coin.profit_rate > 0 ? 'bg-green-500/20 text-green-400' :
                          coin.profit_rate < 0 ? 'bg-red-500/20 text-red-400' :
                          'bg-zinc-700 text-zinc-400'
                        }`}>
                          {coin.profit_rate > 0 ? '+' : ''}{coin.profit_rate?.toFixed(2)}%
                        </span>
                      )}
                    </div>
                    <span className="text-sm text-zinc-300">{formatKRW(coin.eval_amount)}원</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* API 미연결 안내 */}
          {!balances && !loadingBalance && (
            <div className="p-3 bg-zinc-800/50 border border-zinc-700 rounded-lg">
              <p className="text-sm text-zinc-400 text-center">
                업비트 API 키를 입력하면 계좌 정보가 표시됩니다
              </p>
            </div>
          )}

          {loadingBalance && (
            <div className="p-3 bg-zinc-800/50 rounded-lg flex items-center justify-center">
              <RefreshCw className="w-5 h-5 text-cyan-400 animate-spin mr-2" />
              <span className="text-sm text-zinc-400">잔고 조회 중...</span>
            </div>
          )}

          {/* Upbit API Keys */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-cyan-400 flex items-center gap-2">
              <Key className="w-4 h-4" />
              업비트 API 설정
            </h3>
            
            <div>
              <label className="block text-sm text-zinc-400 mb-1">Access Key</label>
              <div className="relative">
                <input
                  type={showSecrets.upbit_access ? 'text' : 'password'}
                  value={formData.upbit_access_key}
                  onChange={(e) => setFormData({ ...formData, upbit_access_key: e.target.value })}
                  placeholder="업비트 Access Key 입력"
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:border-cyan-500 focus:outline-none pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowSecrets({ ...showSecrets, upbit_access: !showSecrets.upbit_access })}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-zinc-500 hover:text-zinc-300"
                >
                  {showSecrets.upbit_access ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm text-zinc-400 mb-1">Secret Key</label>
              <div className="relative">
                <input
                  type={showSecrets.upbit_secret ? 'text' : 'password'}
                  value={formData.upbit_secret_key}
                  onChange={(e) => setFormData({ ...formData, upbit_secret_key: e.target.value })}
                  placeholder="업비트 Secret Key 입력"
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:border-cyan-500 focus:outline-none pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowSecrets({ ...showSecrets, upbit_secret: !showSecrets.upbit_secret })}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-zinc-500 hover:text-zinc-300"
                >
                  {showSecrets.upbit_secret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="p-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
              <p className="text-xs text-yellow-400 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                업비트 API 키는 안전하게 암호화되어 저장됩니다. 
                출금 권한이 없는 API 키 사용을 권장합니다.
              </p>
            </div>
          </div>

          {/* Trading Settings */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-green-400">💰 거래 설정</h3>
            
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-zinc-400 mb-1">기본 거래금액</label>
                <select
                  value={formData.trade_amount}
                  onChange={(e) => setFormData({ ...formData, trade_amount: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:border-green-500 focus:outline-none"
                >
                  <option value={10000}>1만원</option>
                  <option value={50000}>5만원</option>
                  <option value={100000}>10만원</option>
                  <option value={500000}>50만원</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-zinc-400 mb-1">최대 포지션</label>
                <select
                  value={formData.max_positions}
                  onChange={(e) => setFormData({ ...formData, max_positions: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:border-green-500 focus:outline-none"
                >
                  <option value={1}>1개</option>
                  <option value={3}>3개</option>
                  <option value={5}>5개</option>
                  <option value={10}>10개</option>
                  <option value={0}>제한 없음</option>
                </select>
              </div>
            </div>
          </div>

          {/* Message */}
          {message && (
            <div className={`p-3 rounded-lg flex items-center gap-2 ${
              message.type === 'success' 
                ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                : 'bg-red-500/20 text-red-400 border border-red-500/30'
            }`}>
              {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
              {message.text}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-800 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-300 transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 rounded-lg text-white font-medium transition-all flex items-center gap-2 disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {saving ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  );
}

