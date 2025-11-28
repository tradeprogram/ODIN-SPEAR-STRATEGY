import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import timedelta
import plotly.graph_objects as go

# =============================================
# 기본 설정
# =============================================
st.set_page_config(page_title="ODIN Dashboard", layout="wide")
st.title("⚔️ ODIN MASTER DASHBOARD — Custom Format v1.0")

# =============================================
# 환율
# =============================================
@st.cache_data(ttl=300)
def get_usdkrw():
    try:
        df = yf.download("USDKRW=X", period="1d", interval="1m", progress=False)
        return float(df["Close"].iloc[-1])
    except:
        return 1400.0

usdkrw = get_usdkrw()
st.sidebar.metric("💱 USD/KRW", f"{usdkrw:,.2f} 원")

# =============================================
# 폴더 선택
# =============================================
BASE = os.path.dirname(os.path.abspath(__file__))
DECISION_DIR = os.path.join(BASE, "DECISION")
RESULT_DIR = os.path.join(BASE, "RESULT")

FOLDER_MAP = {
    "DECISION (추천)": DECISION_DIR,
    "RESULT (과거 기록)": RESULT_DIR,
}

folder_sel = st.sidebar.selectbox("📁 폴더 선택", list(FOLDER_MAP.keys()))
TARGET = FOLDER_MAP[folder_sel]

files = sorted(
    [f for f in os.listdir(TARGET) if f.endswith(".xlsx") and not f.startswith("~$")],
    reverse=True
)

file_sel = st.selectbox("📄 엑셀 파일 선택", files)
file_path = os.path.join(TARGET, file_sel)

# =============================================
# 파일 로드 (너 파일 형식 그대로 사용)
# =============================================
def load_file(path):
    df = pd.read_excel(path, engine="openpyxl")

    # 컬럼 정규화
    df.columns = [str(c).strip() for c in df.columns]

    # 컬럼 매핑
    rename_map = {
        "최종점수": "점수",
        "3일상승확률": "3일확률",
        "5일상승확률(%)": "5일확률",
        "10일상승확률(%)": "10일확률",
    }

    for old, new in rename_map.items():
        if old in df.columns:
            df.rename(columns={old: new}, inplace=True)

    # 종목명 없으면 생성
    if "종목명" not in df.columns:
        df["종목명"] = df["티커"]

    # ML 확률 없는 파일일 때 기본값 보정
    for col in ["3일확률", "5일확률", "10일확률"]:
        if col not in df.columns:
            df[col] = None

    return df


df = load_file(file_path)
st.success("📌 파일 구조 인식 성공 — ODIN_CUSTOM 모드")
st.dataframe(df, use_container_width=True)

# =============================================
# 종목 선택
# =============================================
name_list = df["종목명"].tolist()
ticker_list = df["티커"].tolist()
mapping = dict(zip(name_list, ticker_list))

ticker_sel = st.sidebar.selectbox("종목 선택", name_list)
ticker = mapping[ticker_sel]

row = df[df["티커"] == ticker].iloc[0]

# =============================================
# 값 파싱
# =============================================
def getf(col, default=None):
    return float(row[col]) if col in row and pd.notna(row[col]) else default

price_usd = getf("종가", 0)
price_krw = price_usd * usdkrw

rsi = getf("RSI", 0)
score = getf("점수", 0)
ret5 = getf("5일수익률", None)

p3 = getf("3일확률", None)
p5 = getf("5일확률", None)
p10 = getf("10일확률", None)

decision = row.get("판단", "-")
macro_score = row.get("MACRO_SCORE", None)
macro_signal = row.get("MACRO_SIGNAL", None)

# =============================================
# 자동 판단 보완
# =============================================
def auto_decision(rsi_val, score_val):
    if score_val >= 80: return "🚀 강한 매수"
    if score_val >= 60: return "📈 매수 우위"
    if rsi_val < 25: return "📉 바닥권"
    if rsi_val < 35: return "💡 저점 관찰"
    if rsi_val > 80: return "⛔ 과열"
    return "⏳ 관망"

if decision in ["", "-", None]:
    decision = auto_decision(rsi, score)

# =============================================
# 판단 출력
# =============================================
st.markdown("---")
st.subheader(f"📊 {ticker_sel} — 최종 판단")

st.markdown(
    f"""
    <div style="padding:1rem;border-radius:15px;background:#F6F9FF;">
        <h3 style="margin:0;">{decision}</h3>
        <p style="opacity:0.7;">엔진 + 패턴 + ML 종합 판단</p>
    </div>
    """,
    unsafe_allow_html=True
)

# =============================================
# 기술 요약
# =============================================
st.subheader("💡 기술 / 심리 요약")

c1, c2, c3, c4 = st.columns(4)
c1.metric("RSI", f"{rsi:.1f}")
c2.metric("기술 점수", f"{score:.0f} / 100")
c3.metric("시그널가 ($)", f"{price_usd:,.2f}")
c4.metric("시그널가 (₩)", f"{price_krw:,.0f}")

if ret5 is not None:
    st.metric("최근 5일 수익률", f"{ret5:.2f} %")

# =============================================
# ML 확률
# =============================================
st.subheader("📈 ML 상승 확률 (3/5/10일)")

if p3 is not None:
    p_df = pd.DataFrame(
        {"기간": ["3일", "5일", "10일"], "상승확률": [p3, p5, p10]}
    ).set_index("기간")
    st.bar_chart(p_df)
else:
    st.info("ML 확률 데이터가 없는 파일입니다.")

# =============================================
# 가격 차트
# =============================================
@st.cache_data(ttl=300)
def load_price(tkr):
    df = yf.download(tkr, period="1d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    return df

st.markdown("---")
st.subheader("📉 최근 가격 차트 (KRW 기준 / TP·SL 포함)")

try:
    price = load_price(ticker)
    time_col = "Datetime" if "Datetime" in price.columns else price.columns[0]

    price[time_col] = pd.to_datetime(price[time_col], errors="coerce")
    recent = price[price[time_col] >= price[time_col].max() - timedelta(hours=3)]
    recent["Close_KRW"] = recent["Close"] * usdkrw

    tp = price_krw * 1.03
    sl = price_krw * 0.97

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=recent[time_col], y=recent["Close_KRW"],
        mode="lines", name="Price (KRW)",
        line=dict(color="blue", width=2)
    ))

    fig.add_hline(y=tp, line=dict(color="green", dash="dash"), annotation_text="TP")
    fig.add_hline(y=sl, line=dict(color="red", dash="dash"), annotation_text="SL")

    fig.update_xaxes(dtick=600000, tickformat="%H:%M")
    fig.update_layout(height=400)

    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error("차트 로딩 실패")
    st.write(e)

# =============================================
# 전체 데이터
# =============================================
st.markdown("---")
st.subheader("📋 전체 데이터")
st.dataframe(df, use_container_width=True)
