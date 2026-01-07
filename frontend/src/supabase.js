import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://laazktyyucltcdqhgemsz.supabase.co'
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxhYXprdHl5dWNsdGNkcWhnZW1zeiIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNzM2MjI3NjM4LCJleHAiOjIwNTE4MDM2Mzh9.placeholder'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Google 로그인
export const signInWithGoogle = async () => {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: window.location.origin
    }
  })
  return { data, error }
}

// 로그아웃
export const signOut = async () => {
  const { error } = await supabase.auth.signOut()
  return { error }
}

// 현재 사용자 가져오기
export const getCurrentUser = async () => {
  const { data: { user } } = await supabase.auth.getUser()
  return user
}

// 사용자 설정 가져오기
export const getUserSettings = async (userId) => {
  const { data, error } = await supabase
    .from('user_settings')
    .select('*')
    .eq('user_id', userId)
    .single()
  return { data, error }
}

// 사용자 설정 저장/업데이트
export const saveUserSettings = async (userId, settings) => {
  const { data, error } = await supabase
    .from('user_settings')
    .upsert({
      user_id: userId,
      ...settings,
      updated_at: new Date().toISOString()
    })
    .select()
    .single()
  return { data, error }
}

// 사용자 거래 내역 가져오기
export const getUserTrades = async (userId, limit = 50) => {
  const { data, error } = await supabase
    .from('user_trades')
    .select('*')
    .eq('user_id', userId)
    .order('executed_at', { ascending: false })
    .limit(limit)
  return { data, error }
}

