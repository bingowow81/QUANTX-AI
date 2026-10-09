import math
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf

app = FastAPI(title="QUANTX AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 공개 시에는 큐샵 도메인으로 제한 권장
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class AnalyzeRequest(BaseModel):
    symbol: str

KOREAN_TICKERS = {
    "삼성전자": ("005930.KS", "삼성전자", "KRW"),
    "005930": ("005930.KS", "삼성전자", "KRW"),
    "SK하이닉스": ("000660.KS", "SK하이닉스", "KRW"),
    "000660": ("000660.KS", "SK하이닉스", "KRW"),
    "현대차": ("005380.KS", "현대차", "KRW"),
    "005380": ("005380.KS", "현대차", "KRW"),
    "LG에너지솔루션": ("373220.KS", "LG에너지솔루션", "KRW"),
    "373220": ("373220.KS", "LG에너지솔루션", "KRW"),
    "네이버": ("035420.KS", "NAVER", "KRW"),
    "NAVER": ("035420.KS", "NAVER", "KRW"),
    "035420": ("035420.KS", "NAVER", "KRW"),
    "카카오": ("035720.KS", "카카오", "KRW"),
    "035720": ("035720.KS", "카카오", "KRW"),
    "셀트리온": ("068270.KS", "셀트리온", "KRW"),
    "068270": ("068270.KS", "셀트리온", "KRW"),
    "에코프로": ("086520.KQ", "에코프로", "KRW"),
    "086520": ("086520.KQ", "에코프로", "KRW"),
    "에코프로비엠": ("247540.KQ", "에코프로비엠", "KRW"),
    "247540": ("247540.KQ", "에코프로비엠", "KRW"),
}

def resolve_symbol(raw: str):
    query = raw.strip()
    key = query.upper()
    if query in KOREAN_TICKERS:
        return KOREAN_TICKERS[query]
    if key in KOREAN_TICKERS:
        return KOREAN_TICKERS[key]
    if re.fullmatch(r"\d{6}", query):
        for suffix in (".KS", ".KQ"):
            ticker = query + suffix
            try:
                hist = yf.Ticker(ticker).history(period="3mo", auto_adjust=True)
                if not hist.empty:
                    return (ticker, query, "KRW")
            except Exception:
                pass
        raise HTTPException(status_code=404, detail="종목코드를 찾지 못했습니다. 6자리 코드를 확인해주세요.")
    # US/other market symbols are passed through as entered
    return (key, key, "USD")

@app.get("/")
def root():
    return {"ok": True, "service": "QUANTX AI"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    if not req.symbol.strip():
        raise HTTPException(status_code=400, detail="종목명 또는 종목코드를 입력해주세요.")

    ticker, name, currency = resolve_symbol(req.symbol)
    try:
        hist = yf.Ticker(ticker).history(period="3mo", auto_adjust=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"주가 데이터를 가져오지 못했습니다: {exc}")

    if hist is None or hist.empty or len(hist) < 2:
        raise HTTPException(status_code=404, detail="해당 종목의 주가 데이터를 찾지 못했습니다.")

    closes = hist["Close"].dropna()
    if len(closes) < 2:
        raise HTTPException(status_code=404, detail="분석에 필요한 가격 데이터가 부족합니다.")

    current = float(closes.iloc[-1])
    previous = float(closes.iloc[-2])
    daily_pct = (current / previous - 1) * 100 if previous else 0.0
    start_20 = float(closes.iloc[-21]) if len(closes) >= 21 else float(closes.iloc[0])
    return_20d = (current / start_20 - 1) * 100 if start_20 else 0.0

    ma20 = float(closes.tail(20).mean())
    ma50 = float(closes.tail(50).mean()) if len(closes) >= 50 else ma20
    # Simple technical score from price trend only; not a valuation/fundamental score.
    trend_score = 50
    trend_score += 20 if current > ma20 else -20
    trend_score += 15 if ma20 > ma50 else -15
    trend_score += max(-15, min(15, return_20d * 0.75))
    technical_score = max(0, min(100, round(trend_score)))
    score = technical_score

    direction = "상승 흐름" if current > ma20 else "하락 흐름"
    summary = (
        f"최근 가격 기준으로 {direction}입니다. "
        f"종가는 20일 이동평균 대비 {'위' if current > ma20 else '아래'}에 있습니다. "
        "이 점수는 가격 추세를 단순화한 참고 지표이며 기업 가치·수익성 점수가 아닙니다."
    )
    return {
        "name": name,
        "symbol": ticker,
        "currency": currency,
        "current_price": round(current, 2),
        "daily_change_pct": round(daily_pct, 2),
        "return_20d": round(return_20d, 2),
        "technical_score": technical_score,
        "score": score,
        "summary": summary,
        "data_date": str(closes.index[-1].date()),
    }

@app.post("/api/chat")
def chat(req: ChatRequest):
    msg = req.message.strip()
    if not msg:
        return {"reply": "질문을 입력해주세요."}
    # Basic chat endpoint for connection testing. It is not an LLM yet.
    if any(word in msg for word in ["분석", "주가", "종목", "삼성전자", "SK하이닉스"]):
        return {"reply": "종목 분석은 홈페이지의 'AI 종목 분석' 입력란을 사용해주세요. 현재 채팅 API는 연결 확인용이며, 실제 대화형 AI 모델은 아직 연결되지 않았습니다."}
    return {"reply": f"QUANTX 서버 연결 성공. 입력한 질문: {msg}\n현재 채팅은 연결 테스트 단계이며, 실제 AI 모델 연결은 별도 설정이 필요합니다."}
