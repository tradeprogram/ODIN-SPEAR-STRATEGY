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

FOLDERS = {
    "DECISION (추천)": DECISION_DIR,
    "RESULT (구버전)": RESULT_DIR,
}

# =====================================
# 파일 선택
# =====================================
folder_choice = st.sidebar.selectbox("📁 폴더 선택", list(FOLDERS.keys()))
TARGET_DIR = FOLDERS[folder_choice]

files = sorted(
    [f for f in os.listdir(TARGET_DIR) if f.endswith(".xlsx") and not f.startswith("~$")],
    reverse=True,
)
selected = st.selectbox("📄 파일 선택", files)
file_path = os.path.join(TARGET_DIR, selected)

# =====================================
# 포맷 감지
# =====================================
def load_and_detect(path):
    xl = pd.ExcelFile(path)
    names = xl.sheet_names

    # SUMMARY 모드
    if "SUMMARY" in names:
        df = pd.read_excel(path, sheet_name="SUMMARY")
        return "SUMMARY", df

    # 기타 포맷 로드
    raw = pd.read_excel(path, sheet_name=names[0])
    cols = set(raw.columns)

    req = {"티커", "종가", "RSI"}
    prob_req = {"3일확률", "5일확률", "10일확률"}

    if req.issubset(cols) and prob_req.issubset(cols):
        return "ODIN_AI", raw

    if req.issubset(cols):
        # LEGACY
        raw["3일확률"] = 50
        raw["5일확률"] = 50
        raw["10일확률"] = 50
        return "LEGACY", raw

    return "UNKNOWN", raw

mode, df = load_and_detect(file_path)

st.success(f"📄 파일 구조 인식 성공 — {mode}")
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
# 데이터 파싱
# =====================================
if mode == "SUMMARY":
    sig_usd = float(row["시그널가격(USD)"])
    sig_krw = float(row["시그널가격(KRW)"])
    rsi = float(row["RSI"])
    score = float(row.get("점수", 0))
    p3 = p5 = p10 = None
    judgment = row.get("등급", "-")
    ret5 = None
else:
    sig_usd = float(row["종가"])
    sig_krw = sig_usd * usdkrw
    rsi = float(row["RSI"])
    score = float(row.get("점수", 0))
    ret5 = float(row.get("5일수익률", 0))
    p3 = float(row.get("3일확률", 50))
    p5 = float(row.get("5일확률", 50))
    p10 = float(row.get("10일확률", 50))
    judgment = row.get("판단", "-")

# =====================================
# 자동 판단 생성 로직
# =====================================
def generate_signal(rsi, score):
    if score >= 80:
        return "🚀 강한 매수 — 엔진 고득점"
    if score >= 60:
        return "📈 매수 우위 — 점진적 매수"
    if rsi < 25:
        return "📉 강한 바닥권 — 매수 유리"
    if rsi < 35:
        return "📈 바닥권 접근 — 분할매수 고려"
    if rsi < 50:
        return "🧭 관찰 구간 — 추세 대기"
    if rsi < 70:
        return "📊 보통 — 무리한 진입 자제"
    if rsi < 80:
        return "⚠️ 단기 과열 — 조심"
    return "🔥 과열 — 건드리지 말기"

if isinstance(judgment, str) and judgment != "-" and judgment != "":
    final_signal = judgment
else:
    final_signal = generate_signal(rsi, score)

# =====================================
# UI — 판단 & 요약 & 확률 그래프
# =====================================
left, right = st.columns([2, 3])

with left:
    st.subheader(f"📊 {selected_name} 최종 판단")
    st.info(final_signal)

    colA, colB = st.columns(2)
    colA.metric("RSI", f"{rsi:.1f}")
    colA.metric("점수", f"{score:.0f}")
    colB.metric("USD", f"{sig_usd:.2f}")
    colB.metric("KRW", f"{sig_krw:,.0f}")

    if ret5 is not None:
        st.metric("5일 수익률", f"{ret5:.2f}%")

with right:
    st.subheader("📈 ML 상승 확률 (3/5/10일)")
    prob_df = pd.DataFrame(
        {"기간": ["3일", "5일", "10일"], "상승확률": [p3, p5, p10]}
    ).set_index("기간")
    st.bar_chart(prob_df)

# =====================================
# 📉 가격 차트 (KRW Plotly + TP·SL 포함)
# =====================================
@st.cache_data(ttl=300)
def load_price(ticker):
    df = yf.download(ticker, period="5d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.reset_index()
    return df, df.columns[0]

st.markdown("---")
st.subheader("📉 최근 가격 차트 (KRW 기준 / TP·SL 포함)")

try:
    price, time_col = load_price(ticker)

    # datetime 강제 변환 (오류 해결)
    price[time_col] = pd.to_datetime(price[time_col], errors="coerce")

    price["Close_KRW"] = price["Close"] * usdkrw

    cutoff = price[time_col].max() - timedelta(hours=3)
    recent = price[price[time_col] >= cutoff]

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
                  annotation_text=f"TP {tp_krw:,.0f}원")

    fig.add_hline(y=sl_krw, line=dict(color="red", dash="dash"),
                  annotation_text=f"SL {sl_krw:,.0f}원")

    fig.update_xaxes(tickformat="%H:%M", dtick=600000)
    fig.update_layout(
        height=400,
        title=f"{ticker} 최근 3시간 (KRW 기준)",
        yaxis_title="KRW"
    )

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
