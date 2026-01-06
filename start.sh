#!/bin/bash

# CoinHero 시작 스크립트

echo "🚀 CoinHero 자동거래 시스템 시작"
echo "================================"

# Backend 시작
echo "📡 Backend 서버 시작 중..."
cd backend
if [ ! -d "venv" ]; then
    echo "가상환경 생성 중..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
python main.py &
BACKEND_PID=$!
cd ..

# Frontend 시작
echo "🎨 Frontend 서버 시작 중..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "의존성 설치 중..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ 서버가 시작되었습니다!"
echo ""
echo "📌 접속 주소:"
echo "   - Frontend: http://localhost:8080"
echo "   - Backend API: http://localhost:8000"
echo "   - API 문서: http://localhost:8000/docs"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."

# 종료 핸들러
trap "echo '서버 종료 중...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

# 대기
wait







