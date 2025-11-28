import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import timedelta
import plotly.graph_objects as go
import plotly.express as px

# =====================================
# 기본 설정
# =====================================
st.set_page_config(page_title="ODIN'S SPEAR STRATEGY", layout="wide")
st.title("⚔️ ODIN'S SPEAR STRATEGY (Cloud Auto Version)")

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

FOLDERS = {"RESULT": RESULT_DIR, "DECISION": DECISION_DIR}

# =====================================
# 폴더 선택
# =====================================
folder_choice = st.sidebar.selectbox("📁 폴더 선택", ["RESULT", "DECISION"])
TARGET_DIR = FOLDERS[folder_choice]

if not os.path.exists(TARGET_DIR):
    st.error("❌ 해당 폴더가 없습니다.")
    st.stop()

files = sorted(
    [f for f in os.listdir(TARGET_DIR) if f.endswith(".xlsx") and not f.startswith("~$")],
    reverse=True,
)

if not files:
    st.warning("📂 폴더 안에 엑셀 파일이 없습니다.")
    st.stop()

selected = st.selectbox("📄 분석 파일 선택", files)
file_path = os.path.join(TARGET_DIR, selected)
st.caption(f"현재 선택: {selected}")

# =====================================
# SUMMARY 로드
# =====================================
try:
    df_summary = pd.read_excel(file_path, sheet_name="SUMMARY")
except:
    st.error("❌ SUMMARY 시트를 찾을 수 없습니다.")
    st.stop()

st.success("SUMMARY 시트 로드 성공")

# =====================================
# 티커 선택
# =====================================
tickers = df_summary["티커"].tolist()
ticker = st.sidebar.selectbox("티커 선택", tickers)

row = df_summary[df_summary["티커"] == ticker].iloc[0]

# SUMMARY 파싱
usd = float(row["USD"])
krw = float(row["KRW"])
tp_usd = float(row["TP_USD"])
sl_usd = float(row["SL_USD"])
tp_krw = float(row["TP_KRW"])
sl_krw = float(row["SL_KRW"])
grade = row["등급"]
conf = row["신뢰도"]
hold = int(row["HOLD"])
winrate = float(row["승률"])
prob_3 = float(row["3일상승확률(%)"])
prob_5 = float(row["5일상승확률(%)"])
prob_10 = float(row["10일상승확률(%)"])
judgment = row["판단"]

# ================================
# 🔮 판단 메시지 (차트 위)
# ================================
st.markdown("## 🔮 판단 메시지")
st.info(f"### **{judgment}**")

# ================================
# 📈 상승확률 3종 막대그래프
# ================================
st.markdown("## 📊 미래 상승 확률 (ML/패턴 기반)")

prob_df = pd.DataFrame({
    "기간": ["3일", "5일", "10일"],
    "상승확률": [prob_3, prob_5, prob_10]
})

fig_prob = px.bar(
    prob_df,
    x="상승확률",
    y="기간",
    orientation="h",
    text="상승확률",
    color="상승확률",
    range_x=[0, 100]
)
fig_prob.update_layout(height=300)
st.plotly_chart(fig_prob, use_container_width=True)

# ================================
# 📌 핵심 요약 박스 UI
# ================================
st.markdown("## 📌 핵심 요약")

c1, c2, c3 = st.columns(3)
c1.metric("등급", grade)
c2.metric("신뢰도", f"{conf:.1f}%" if conf else "-")
c3.metric("HOLD", f"{hold}일")

c4, c5, c6 = st.columns(3)
c4.metric("승률", f"{winrate:.1f}%")
c5.metric("현재가(₩)", f"{krw:,.0f}")
if "RSI" in row:
    c6.metric("RSI", f"{row['RSI']:.1f}")

# ================================
# 💰 가격 정보
# ================================
st.markdown("## 💰 가격 정보")
st.write(f"**매수가 USD:** {usd:.2f}")
st.write(f"**매수가 KRW:** {krw:,.0f} 원")

# ================================
# 🎯 TP / 🛡 SL
# ================================
st.markdown("## 🎯 목표가 / 🛡 손절가 (엔진추천)")
st.write(f"**TP (USD):** {tp_usd:.2f} → **TP (KRW):** {tp_krw:,.0f} 원")
st.write(f"**SL (USD):** {sl_usd:.2f} → **SL (KRW):** {sl_krw:,.0f} 원")

# ================================
# 가격 데이터 로드
# ================================
@st.cache_data(ttl=300)
def load_price(ticker):
    df = yf.download(ticker, period="5d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.reset_index()
    return df, df.columns[0]

# ================================
# 📈 KRW Plotly 차트 (차트는 맨 아래)
# ================================
try:
    price, time_col = load_price(ticker)
    price["Close_KRW"] = price["Close"] * usdkrw
    chart = price[[time_col, "Close_KRW"]]
    recent = chart[chart[time_col] >= chart[time_col].max() - timedelta(hours=3)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=recent[time_col],
        y=recent["Close_KRW"],
        mode="lines",
        name="Price (KRW)",
        line=dict(width=2, color="blue")
    ))

    fig.add_hline(
        y=tp_krw,
        line=dict(color="green", width=2, dash="dash"),
        annotation_text=f"TP {tp_krw:,.0f}원",
        annotation_position="top left"
    )
    fig.add_hline(
        y=sl_krw,
        line=dict(color="red", width=2, dash="dash"),
        annotation_text=f"SL {sl_krw:,.0f}원",
        annotation_position="bottom left"
    )

    fig.update_xaxes(
        tickformat="%H:%M",
        dtick=600000
    )
    fig.update_layout(
        title=f"📈 {ticker} (최근 3시간 / KRW 기준)",
        height=400,
        yaxis_title="KRW"
    )

    st.markdown("## 📈 가격 차트 (KRW)")
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error("❌ 차트 로딩 실패")
    st.write(e)
