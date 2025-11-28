import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import timedelta
import plotly.graph_objects as go

# =====================================
# 기본 설정
# =====================================
st.set_page_config(page_title="ODIN'S SPEAR STRATEGY", layout="wide")
st.title("⚔️ ODIN'S SPEAR STRATEGY (ODIN MASTER DASHBOARD)")

# =====================================
# 환율
# =====================================
@st.cache_data(ttl=300)
def get_usdkrw():
    try:
        df = yf.download("USDKRW=X", period="1d", interval="1m", progress=False)
        return float(df["Close"].iloc[-1])
    except:
        return 1400.0

usdkrw = get_usdkrw()
st.metric("💱 USD/KRW", f"{usdkrw:,.2f} 원")

st.markdown("---")

# =====================================
# 경로 설정
# =====================================
BASE = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(BASE, "RESULT")
DECISION_DIR = os.path.join(BASE, "DECISION")

FOLDER_MAP = {
    "DECISION (추천)": DECISION_DIR,
    "RESULT (구버전)": RESULT_DIR,
}

# =====================================
# 파일 선택
# =====================================
folder_choice = st.sidebar.selectbox("📁 폴더 선택", list(FOLDER_MAP.keys()))
TARGET_DIR = FOLDER_MAP[folder_choice]

st.write(f"📂 현재 선택된 폴더: `{folder_choice}`")

files = sorted([f for f in os.listdir(TARGET_DIR) if f.endswith(".xlsx")], reverse=True)
selected = st.selectbox("📄 파일 선택", files)
file_path = os.path.join(TARGET_DIR, selected)

st.caption(f"선택된 파일: {selected}")

# =====================================
# 포맷 감지
# =====================================
def load_and_detect(path):
    x = pd.ExcelFile(path)
    names = x.sheet_names

    # SUMMARY 모드
    if "SUMMARY" in names:
        df = pd.read_excel(path, sheet_name="SUMMARY")
        return "SUMMARY", df

    raw = pd.read_excel(path, sheet_name=names[0])
    req = {"티커", "종가", "RSI"}
    prob_req = {"3일확률", "5일확률", "10일확률"}

    if req.issubset(raw.columns) and prob_req.issubset(raw.columns):
        return "ODIN_AI", raw

    if req.issubset(raw.columns):
        return "LEGACY", raw

    return "UNKNOWN", raw

mode, df = load_and_detect(file_path)

if mode == "UNKNOWN":
    st.error("❌ 파일 구조 인식 실패")
    st.stop()

st.success(f"파일 인식 성공: {mode}")
st.dataframe(df, use_container_width=True)

# =====================================
# 종목 선택
# =====================================
names = df["종목명"].tolist() if "종목명" in df.columns else df["티커"].tolist()
mapping = dict(zip(names, df["티커"]))

selected_name = st.sidebar.selectbox("종목 선택", names)
ticker = mapping[selected_name]

row = df[df["티커"] == ticker].iloc[0]

# =====================================
# 값 파싱
# =====================================
sig_usd = float(row["종가"]) if mode != "SUMMARY" else float(row["시그널가격(USD)"])
sig_krw = sig_usd * usdkrw
rsi = float(row["RSI"])
score = float(row.get("점수", 0))
p3 = float(row.get("3일확률", 50))
p5 = float(row.get("5일확률", 50))
p10 = float(row.get("10일확률", 50))
signal = row.get("판단", "-")
ret5 = float(row.get("5일수익률", 0))

# =====================================
# 판단 문구 해석
# =====================================
def interpret(text):
    if "강한" in text:
        return "🚀 강한 매수 구간"
    if "바닥" in text:
        return "📈 바닥권 접근"
    if "관망" in text:
        return "⛔ 관망하십시오"
    return "❔ 판단 없음"

final_label = interpret(signal)

# =====================================
# UI 영역
# =====================================
left, right = st.columns([2, 3])

with left:
    st.subheader(f"📊 {selected_name} 최종 판단")
    st.info(final_label)

    colA, colB = st.columns(2)
    colA.metric("RSI", f"{rsi:.1f}")
    colA.metric("점수", f"{score:.0f}")
    colB.metric("USD", f"{sig_usd:.2f}")
    colB.metric("KRW", f"{sig_krw:,.0f}")

    st.metric("5일 수익률", f"{ret5:.2f}%")

with right:
    st.subheader("📈 ML 상승 확률")
    prob_df = pd.DataFrame({
        "기간": ["3일", "5일", "10일"],
        "상승확률": [p3, p5, p10]
    }).set_index("기간")
    st.bar_chart(prob_df)

# =====================================
# 🔥 가격 차트 (여기만 변경됨)
# =====================================
@st.cache_data(ttl=300)
def load_price(ticker):
    df = yf.download(ticker, period="5d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df.reset_index(), df.columns[0]

st.markdown("---")
st.subheader("📉 최근 가격 차트 (KRW 기준 / TP·SL 포함)")

try:
    price, time_col = load_price(ticker)
    price["Close_KRW"] = price["Close"] * usdkrw

    recent = price[price[time_col] >= price[time_col].max() - timedelta(hours=3)]

    # TP / SL (기본 3% / -3% 혹은 엔진 값 적용 가능)
    tp_krw = sig_krw * 1.03
    sl_krw = sig_krw * 0.97

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=recent[time_col],
        y=recent["Close_KRW"],
        mode="lines",
        name="Price (KRW)",
        line=dict(width=2, color="blue")
    ))

    fig.add_hline(y=tp_krw, line=dict(color="green", dash="dash"),
                  annotation_text=f"TP {tp_krw:,.0f}원", annotation_position="top left")

    fig.add_hline(y=sl_krw, line=dict(color="red", dash="dash"),
                  annotation_text=f"SL {sl_krw:,.0f}원", annotation_position="bottom left")

    fig.update_xaxes(tickformat="%H:%M", dtick=600000)

    fig.update_layout(height=400, title=f"{ticker} 최근 3시간 차트 (KRW)",
                      yaxis_title="KRW")

    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error("차트 로딩 실패")
    st.write(e)

# =====================================
# 전체 테이블
# =====================================
st.markdown("---")
st.subheader("📋 전체 종목 리스트")
st.dataframe(df, use_container_width=True)
