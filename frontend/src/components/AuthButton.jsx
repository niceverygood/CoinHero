import React from 'react';
import { LogIn, LogOut, User, Settings } from 'lucide-react';

export default function AuthButton({ user, onLogin, onLogout, onSettings }) {
  if (user) {
    return (
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 rounded-lg">
          {user.user_metadata?.avatar_url ? (
            <img 
              src={user.user_metadata.avatar_url} 
              alt="Profile" 
              className="w-6 h-6 rounded-full"
            />
          ) : (
            <User className="w-5 h-5 text-zinc-400" />
          )}
          <span className="text-sm text-zinc-300 max-w-[100px] truncate">
            {user.user_metadata?.full_name || user.email?.split('@')[0]}
          </span>
        </div>
        <button
          onClick={onSettings}
          className="p-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
          title="설정"
        >
          <Settings className="w-5 h-5 text-zinc-400" />
        </button>
        <button
          onClick={onLogout}
          className="p-2 bg-zinc-800 hover:bg-red-900/50 rounded-lg transition-colors"
          title="로그아웃"
        >
          <LogOut className="w-5 h-5 text-zinc-400" />
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={onLogin}
      className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 rounded-lg font-medium transition-all"
    >
      <LogIn className="w-5 h-5" />
      <span>로그인</span>
    </button>
  );
}

