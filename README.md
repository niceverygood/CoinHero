# 🚀 CoinHero - 업비트 코인 자동거래 시스템

업비트 API를 활용한 암호화폐 자동거래 시스템입니다.

![CoinHero Dashboard](https://via.placeholder.com/800x400/0d1117/58a6ff?text=CoinHero+Dashboard)

## ✨ 주요 기능

- **실시간 시세 조회**: 업비트 마켓의 실시간 가격 모니터링
- **자동매매 봇**: 다양한 전략 기반 자동 거래 실행
- **포트폴리오 관리**: 보유 자산 현황 및 수익률 확인
- **거래 기록**: 모든 매수/매도 기록 추적
- **기술적 분석**: RSI, MACD, 볼린저밴드 등 지표 제공

## 🎯 자동매매 전략

1. **변동성 돌파 전략**: 전일 변동폭의 K배를 당일 시가에 더한 가격 돌파 시 매수
2. **이동평균 교차 전략**: 골든크로스/데드크로스 신호 기반 매매
3. **RSI 전략**: 과매수/과매도 구간 활용
4. **복합 전략**: 여러 전략의 신호를 종합하여 판단

## 🛠 기술 스택

### Backend
- Python 3.11+
- FastAPI
- pyupbit
- pandas, numpy

### Frontend
- React 18
- Vite
- TailwindCSS
- Recharts

## 📦 설치 방법

### 1. 저장소 클론
```bash
git clone https://github.com/yourusername/CoinHero.git
cd CoinHero
```

### 2. Backend 설정
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경변수 설정
`backend/.env` 파일을 생성하고 API 키를 설정합니다:
```bash
# backend/.env
UPBIT_ACCESS_KEY=your_upbit_access_key_here
UPBIT_SECRET_KEY=your_upbit_secret_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

- **Upbit API 키**: https://upbit.com/mypage/open_api_management
- **OpenRouter API 키**: https://openrouter.ai/keys

### 3. Frontend 설정
```bash
cd frontend
npm install
```

## 🚀 실행 방법

### Backend 서버 실행
```bash
cd backend
python main.py
# 또는
uvicorn main:app --reload --port 8000
```

### Frontend 개발 서버 실행
```bash
cd frontend
npm run dev
```

### 접속
- Frontend: http://localhost:8080
- Backend API: http://localhost:8000
- API 문서: http://localhost:8000/docs

## 📡 API 엔드포인트

### 시세 조회
- `GET /api/price/{ticker}` - 현재가 조회
- `GET /api/prices` - 여러 코인 현재가 조회
- `GET /api/ohlcv/{ticker}` - OHLCV 데이터 조회

### 잔고 조회
- `GET /api/balance` - 전체 잔고 조회
- `GET /api/balance/{currency}` - 특정 통화 잔고 조회

### 자동매매 봇
- `GET /api/bot/status` - 봇 상태 조회
- `POST /api/bot/configure` - 봇 설정 변경
- `POST /api/bot/start` - 자동매매 시작
- `POST /api/bot/stop` - 자동매매 중지

### 수동 거래
- `POST /api/trade/buy` - 시장가 매수
- `POST /api/trade/sell` - 시장가 매도

### 분석
- `GET /api/analysis/{ticker}` - 코인 분석 정보

### WebSocket
- `WS /ws` - 실시간 데이터 스트림

## ⚠️ 주의사항

1. **투자 위험**: 자동거래는 투자 손실의 위험이 있습니다. 신중하게 사용하세요.
2. **API 키 보안**: API 키는 절대 외부에 노출하지 마세요.
3. **테스트**: 실제 거래 전 반드시 소액으로 테스트하세요.
4. **업비트 정책**: 업비트 API 사용 정책을 준수하세요.

## 📁 프로젝트 구조

```
CoinHero/
├── backend/
│   ├── main.py           # FastAPI 서버
│   ├── config.py         # 설정
│   ├── upbit_client.py   # 업비트 API 클라이언트
│   ├── strategies.py     # 트레이딩 전략
│   ├── trading_engine.py # 자동매매 엔진
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── PriceChart.jsx
│   │   │   ├── TradeLog.jsx
│   │   │   ├── CoinList.jsx
│   │   │   └── BotControl.jsx
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## 📄 라이선스

MIT License

---

Made with ❤️ by CoinHero Team



