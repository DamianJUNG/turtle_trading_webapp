# 🐢 터틀 트레이딩 시스템

한국 주식시장을 위한 터틀 트레이딩 전략 웹앱입니다. 

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

## 📈 주요 기능

### 🎯 터틀 트레이딩 전략
- **Donchian 채널 브레이크아웃**: 20일 신고가 돌파시 진입
- **ATR 기반 포지션 사이징**: 변동성을 고려한 과학적 포지션 계산
- **피라미딩 전략**: 수익이 날 때 추가 매수 (최대 4단계)
- **리스크 관리**: 거래당 2% 리스크 제한

### 📊 실시간 분석
- 한국거래소(KRX) 실시간 데이터 연동
- 인터랙티브 차트 (Plotly 기반)
- 진입/청산 신호 시각화
- 거래량 급증 감지

### 💼 포지션 관리
- 구글 시트 연동 포지션 기록
- 자동 손절/익절가 계산
- 포트폴리오 추적 관리

## 🚀 사용법

### 1️⃣ 종목 입력
```
삼성전자
005930
NAVER
카카오
```

### 2️⃣ 신호 분석
- "🔍 신호 분석 시작" 버튼 클릭
- 터틀 트레이딩 조건 자동 검사
- 진입/청산 신호 확인

### 3️⃣ 포지션 관리
- 구글 시트 URL 입력
- 신호 발생 종목 자동 저장
- 리스크 관리 정보 기록

## 🛠 기술 스택

- **Frontend**: Streamlit
- **Data Source**: pykrx (한국거래소 API)
- **Visualization**: Plotly
- **Database**: Google Sheets
- **Language**: Python 3.8+

## 📖 터틀 트레이딩 전략 소개

터틀 트레이딩은 1980년대 리처드 데니스(Richard Dennis)가 개발한 추세추종 전략입니다:

### 진입 조건
- 종가가 20일 Donchian 상단 돌파
- 충분한 거래량 확보
- ATR 기반 포지션 사이징

### 청산 조건
- **손절**: 진입가 - 2N (N = ATR)
- **익절**: 10일 Donchian 하단 하회

### 추가 매수 (피라미딩)
- 1차: 진입가 + 0.5N
- 2차: 진입가 + 1.0N  
- 3차: 진입가 + 1.5N

## 📊 백테스팅 결과 (예시)

| 지표 | 값 |
|------|-----|
| 연평균 수익률 | 15.2% |
| 최대 낙폭(MDD) | -12.3% |
| 샤프 비율 | 1.47 |
| 승률 | 43% |

## 🔧 로컬 실행

```bash
# 리포지토리 클론
git clone https://github.com/YOUR_USERNAME/turtle-trading-webapp.git
cd turtle-trading-webapp

# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# 앱 실행
streamlit run app.py
```

## 🔐 환경 설정

### Google Sheets 연동 (선택)
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Google Sheets API 활성화
3. 서비스 계정 생성 및 JSON 키 다운로드
4. Streamlit Cloud의 Secrets에 등록

```toml
# .streamlit/secrets.toml
[google]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "your-private-key"
client_email = "your-client-email"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
```

## 📚 참고 자료

- [터틀 트레이딩 원서](https://www.amazon.com/Complete-TurtleTrader-Legend-Rules-Money/dp/0061241717)
- [한국투자증권 API 문서](https://apiportal.koreainvestment.com/)
- [pykrx 라이브러리](https://github.com/sharebook-kr/pykrx)

## ⚠️ 면책조항

이 웹앱은 **교육 및 연구 목적**으로 제작되었습니다. 

- 실제 투자에 따른 손실에 대해 책임지지 않습니다
- 과거 수익률이 미래 수익을 보장하지 않습니다
- 모든 투자 결정은 신중히 하시기 바랍니다
- 충분한 백테스팅과 검증 후 사용하세요

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 📞 문의

프로젝트 관련 문의사항이 있으시면 GitHub Issues를 통해 연락주세요.

---

⭐ **이 프로젝트가 도움이 되셨다면 스타를 눌러주세요!** ⭐
