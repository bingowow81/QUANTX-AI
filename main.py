import os
import re
import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# 웹사이트(큐샵 등)에서 자유롭게 API를 호출할 수 있도록 CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

def calc_indicators(hist):
    if hist is None or hist.empty or len(hist) < 60:
        return None
    close = hist["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()
    if len(close) < 60:
        return None

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    price = float(close.iloc[-1])
    ma20 = float(close.rolling(20).mean().iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])

    return {
        "close": price,
        "rsi": float(rsi.iloc[-1]) if np.isfinite(rsi.iloc[-1]) else 50.0,
        "ma20": ma20,
        "ma60": ma60,
    }

def fetch_stock_quant(code_or_name: str):
    code = code_or_name.strip()
    name_map = {
        "삼성전자": "005930", "SK하이닉스": "000660", "LG에너지솔루션": "373220",
        "삼성바이오로직스": "207940", "현대차": "005380", "기아": "000270",
        "셀트리온": "068270", "KB금융": "105560", "NAVER": "035420", "네이버": "035420",
        "카카오": "035720", "신한지주": "055550", "포스코홀딩스": "005490", "POSCO홀딩스": "005490"
    }
    target_code = name_map.get(code, code)

    # 코스피(.KS)와 코스닥(.KQ) 자동 검색
    candidates = [target_code] if "." in target_code else [f"{target_code}.KS", f"{target_code}.KQ"]
    hist = None
    target_sym = None
    ticker = None

    for sym in candidates:
        try:
            t = yf.Ticker(sym)
            h = t.history(period="1y", auto_adjust=True)
            if h is not None and not h.empty and len(h) >= 60:
                hist = h
                target_sym = sym
                ticker = t
                break
        except Exception:
            continue

    if hist is None:
        return None

    tech = calc_indicators(hist)
    if tech is None:
        return None

    info = ticker.info or {}
    price = tech["close"]

    def to_num(val, default=np.nan):
        try:
            return float(val) if val is not None and np.isfinite(float(val)) else default
        except Exception:
            return default

    per = to_num(info.get("trailingPE"))
    pbr = to_num(info.get("priceToBook"))
    roe = to_num(info.get("returnOnEquity"))
    op_margin = to_num(info.get("operatingMargins"))
    rev_growth = to_num(info.get("revenueGrowth"))
    name = info.get("shortName") or info.get("longName") or code_or_name

    val_score = 50.0
    if np.isfinite(per): val_score += np.clip((15 - per) * 2.5, -30, 25)
    if np.isfinite(pbr): val_score += np.clip((2.0 - pbr) * 10, -20, 20)
    val_score = float(np.clip(val_score, 10, 99))

    profit_score = 50.0
    if np.isfinite(roe): profit_score += np.clip(roe * 100, -35, 35)
    if np.isfinite(op_margin): profit_score += np.clip(op_margin * 50, -20, 25)
    profit_score = float(np.clip(profit_score, 10, 99))

    growth_score = 50.0
    if np.isfinite(rev_growth): growth_score += np.clip(rev_growth * 100, -30, 30)
    growth_score = float(np.clip(growth_score, 10, 99))

    tech_score = 50.0
    if price > tech["ma20"]: tech_score += 15
    if price > tech["ma60"]: tech_score += 15
    if 40 <= tech["rsi"] <= 65: tech_score += 15
    elif tech["rsi"] > 75: tech_score -= 15
    tech_score = float(np.clip(tech_score, 10, 99))

    total_score = round(val_score * 0.3 + profit_score * 0.25 + growth_score * 0.2 + tech_score * 0.25, 1)

    return {
        "name": name,
        "symbol": target_sym.replace(".KS", "").replace(".KQ", ""),
        "price": round(price, 0),
        "total_score": total_score,
        "value_score": round(val_score, 0),
        "profit_score": round(profit_score, 0),
        "growth_score": round(growth_score, 0),
        "tech_score": round(tech_score, 0),
        "per": round(per, 2) if np.isfinite(per) else "N/A",
        "pbr": round(pbr, 2) if np.isfinite(pbr) else "N/A",
        "rsi": round(tech["rsi"], 1)
    }

@app.get("/")
def read_root():
    return {"status": "QUANTX API Running"}

@app.get("/api/analyze")
def analyze(query: str):
    res = fetch_stock_quant(query)
    if not res:
        return {"error": "종목을 찾을 수 없거나 데이터 수집에 실패했습니다."}
    return res

@app.post("/api/chat")
def chat(req: ChatRequest):
    user_msg = req.message
    matched_code = None
    codes = re.findall(r'\b\d{6}\b', user_msg)
    if codes:
        matched_code = codes[0]
    else:
        for name in ["삼성전자", "SK하이닉스", "LG에너지솔루션", "현대차", "기아", "카카오", "네이버", "셀트리온"]:
            if name in user_msg:
                matched_code = name
                break

    if matched_code:
        data = fetch_stock_quant(matched_code)
        if data:
            answer = (
                f"📊 **{data['name']}({data['symbol']})** QUANTX 분석 요약입니다:\n\n"
                f"• 현재가: {data['price']:,.0f}원\n"
                f"• 종합 점수: **{data['total_score']}점** / 100점\n"
                f"• 세부 점수: 가치평가 {data['value_score']}점 | 수익성 {data['profit_score']}점 | 기술분석 {data['tech_score']}점\n"
                f"• 주요 지표: PER {data['per']}배, PBR {data['pbr']}배, RSI {data['rsi']}\n\n"
                f"💡 RSI({data['rsi']})와 점수를 볼 때 "
                f"{'단기 모멘텀이 양호하며 긍정적 흐름입니다.' if data['total_score'] >= 70 else '보수적인 관망세를 추천합니다.'}"
            )
            return {"answer": answer}

    return {
        "answer": f"질문하신 내용: '{user_msg}'\n\n특정 종목의 진단을 원하시면 종목명이나 6자리 코드(예: 삼성전자, 005930)를 함께 입력해주세요. QUANTX 정량 지표로 즉시 분석해 드립니다."
    }
