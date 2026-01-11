import React, { useState, useEffect } from 'react';
import { X, Key, Shield, CheckCircle2, XCircle, Loader2, ExternalLink, Eye, EyeOff } from 'lucide-react';

const API_BASE = import.meta.env.PROD 
  ? 'https://coinhero-production.up.railway.app' 
  : '';

export default function UpbitSettingsModal({ isOpen, onClose, onSuccess }) {
  const [accessKey, setAccessKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [currentStatus, setCurrentStatus] = useState(null);

  // 현재 연결 상태 확인
  useEffect(() => {
    if (isOpen) {
      fetchCurrentStatus();
    }
  }, [isOpen]);

  const fetchCurrentStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/settings/upbit`);
      const data = await response.json();
      setCurrentStatus(data);
    } catch (err) {
      console.error('상태 확인 실패:', err);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE}/api/settings/upbit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          access_key: accessKey,
          secret_key: secretKey
        })
      });

      const data = await response.json();
      setResult(data);

      if (data.success) {
        // 성공 시 콜백 호출
        if (onSuccess) {
          onSuccess(data.account_info);
        }
        // 3초 후 모달 닫기
        setTimeout(() => {
          onClose();
          setResult(null);
          setAccessKey('');
          setSecretKey('');
        }, 3000);
      }
    } catch (err) {
      setResult({
        success: false,
        message: `연결 오류: ${err.message}`
      });
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[#1a1a2e] rounded-2xl border border-cyan-500/30 w-full max-w-md overflow-hidden shadow-2xl">
        {/* 헤더 */}
        <div className="bg-gradient-to-r from-cyan-600/20 to-blue-600/20 p-4 border-b border-cyan-500/20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-xl">
              <Key className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h2 className="font-bold text-lg">업비트 API 설정</h2>
              <p className="text-xs text-gray-400">계좌 연결을 위한 API 키 입력</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* 현재 연결 상태 */}
        {currentStatus && (
          <div className={`mx-4 mt-4 p-3 rounded-xl ${
            currentStatus.connected 
              ? 'bg-green-500/10 border border-green-500/30' 
              : 'bg-gray-500/10 border border-gray-500/30'
          }`}>
            <div className="flex items-center gap-2">
              {currentStatus.connected ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                  <span className="text-green-400 text-sm">현재 연결됨</span>
                  <span className="text-gray-500 text-xs">({currentStatus.api_key_preview})</span>
                </>
              ) : (
                <>
                  <XCircle className="w-4 h-4 text-gray-400" />
                  <span className="text-gray-400 text-sm">연결되지 않음</span>
                </>
              )}
            </div>
          </div>
        )}

        {/* 결과 표시 */}
        {result && (
          <div className={`mx-4 mt-4 p-4 rounded-xl ${
            result.success 
              ? 'bg-green-500/10 border border-green-500/30' 
              : 'bg-red-500/10 border border-red-500/30'
          }`}>
            <div className="flex items-start gap-3">
              {result.success ? (
                <CheckCircle2 className="w-6 h-6 text-green-400 flex-shrink-0" />
              ) : (
                <XCircle className="w-6 h-6 text-red-400 flex-shrink-0" />
              )}
              <div>
                <p className={`font-medium ${result.success ? 'text-green-400' : 'text-red-400'}`}>
                  {result.success ? '연결 성공!' : '연결 실패'}
                </p>
                <p className="text-sm text-gray-400 mt-1">{result.message}</p>
                {result.account_info && (
                  <div className="mt-2 text-sm">
                    <p className="text-cyan-400">
                      💰 보유 현금: {result.account_info.krw_balance?.toLocaleString()}원
                    </p>
                    <p className="text-purple-400">
                      📊 보유 코인: {result.account_info.coin_count}종목
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 폼 */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Access Key</label>
            <input
              type="text"
              value={accessKey}
              onChange={(e) => setAccessKey(e.target.value)}
              placeholder="업비트 Access Key 입력"
              className="w-full bg-[#252538] border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none transition-colors"
              required
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Secret Key</label>
            <div className="relative">
              <input
                type={showSecret ? 'text' : 'password'}
                value={secretKey}
                onChange={(e) => setSecretKey(e.target.value)}
                placeholder="업비트 Secret Key 입력"
                className="w-full bg-[#252538] border border-gray-700 rounded-xl px-4 py-3 pr-12 text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none transition-colors"
                required
              />
              <button
                type="button"
                onClick={() => setShowSecret(!showSecret)}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-white"
              >
                {showSecret ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-3">
            <div className="flex items-start gap-2">
              <Shield className="w-4 h-4 text-blue-400 mt-0.5" />
              <div className="text-xs text-gray-400">
                <p className="text-blue-400 font-medium mb-1">API 키 발급 방법</p>
                <ol className="list-decimal list-inside space-y-1">
                  <li>업비트 로그인 → 마이페이지 → Open API 관리</li>
                  <li>API 키 발급 (자산조회, 주문조회, 주문하기 권한)</li>
                  <li><strong className="text-yellow-400">IP 허용: "모든 IP 허용" 선택</strong></li>
                </ol>
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !accessKey || !secretKey}
            className={`w-full py-3 rounded-xl font-medium transition-all flex items-center justify-center gap-2 ${
              loading || !accessKey || !secretKey
                ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white shadow-lg shadow-cyan-500/25'
            }`}
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                연결 확인 중...
              </>
            ) : (
              <>
                <Key className="w-5 h-5" />
                연결 및 저장
              </>
            )}
          </button>

          <a
            href="https://upbit.com/mypage/open_api_management"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-center text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            업비트 Open API 관리 페이지 열기
            <ExternalLink className="w-3 h-3 inline ml-1" />
          </a>
        </form>
      </div>
    </div>
  );
}

