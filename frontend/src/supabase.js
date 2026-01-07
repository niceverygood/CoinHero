import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://lbnvztnbsbqisemvkvwe.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxibnZ6dG5ic2JxaXNlbXZrdndlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc3Njc5NDAsImV4cCI6MjA4MzM0Mzk0MH0.C5xcw2R14BpzJQS3e3AP6hI6V0F7_kTaYRsqdImG8fA'

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
    }, { onConflict: 'user_id' })
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

