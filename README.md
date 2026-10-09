# QUANTX AI 분석 서버

## Render 설정
- Runtime: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

## 중요
1. Render에 `app.py`와 `requirements.txt`를 배포합니다.
2. 배포 주소가 예를 들어 `https://quantx-ai.onrender.com`이면 `index.html` 안의
   `const QUANTX_API_BASE = "https://YOUR-RENDER-SERVICE.onrender.com";`
   를 실제 주소로 바꿉니다.
3. 큐샵에 수정된 HTML을 적용합니다.

분석은 Yahoo Finance/yfinance의 최근 가격 이력을 이용합니다. 이는 단순 가격 추세 분석이며
기업 재무제표 기반 가치평가나 매수/매도 수익 보장을 의미하지 않습니다.
