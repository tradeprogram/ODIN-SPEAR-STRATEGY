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
st.title("⚔️ ODIN'S SPEAR STRATEGY (Cloud Auto Version)")

# =====================================
# 환율
# =====================================
@st.cache_data(ttl=300)
def get_usdkrw():
    try:
        df = yf.download("USDKRW=X", period="1d", interval="1m", progress=False)
        return float(df["Close"].iloc[-1])
    except Exception:
        return 1400.0

usdkrw = get_usdkrw()
st.metric("💱 USD/KRW", f"{usdkrw:,.2f} 원")

st.markdown("---")

# =====================================
# GitHub 레포 내 폴더 구조
# =====================================
BASE = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(BASE, "RESULT")
DECISION_DIR = os.path.join(BASE, "DECISION")

FOLDER_MAP = {
    "RESULT": RESULT_DIR,
    "DECISION": DECISION_DIR
}

# =====================================
# 폴더 선택
# =====================================
folder_choice = st.sidebar.selectbox("📁 폴더 선택", ["RESULT", "DECISION"])

TARGET_DIR = FOLDER_MAP[folder_choice]

st.write(f"📂 현재 선택된 폴더: `{folder_choice}`")

if not os.path.exists(TARGET_DIR):
    st.error(f"❌ {folder_choice} 폴더가 존재하지 않습니다. GitHub 레포에 `{folder_choice}` 폴더를 추가하세요.")
    st.stop()

# =====================================
# 파일 목록
# =====================================
files = sorted(
    [
        f for f in os.listdir(TARGET_DIR)
        if f.endswith(".xlsx") and not f.startswith("~$")
    ],
    reverse=True
)

if not files:
    st.warning(f"📂 {folder_choice} 폴더에 엑셀 파일이 없습니다.")
    st.stop()

selected = st.selectbox("📄 분석 파일 선택", files)
file_path = os.path.join(TARGET_DIR, selected)

st.caption(f"현재 선택된 파일: **{selected}**")

# =====================================
# 엑셀 로드 & 모드 감지
# =====================================
xls = pd.ExcelFile(file_path)
sheets = xls.sheet_names

def load_and_detect(path):
    x = pd.ExcelFile(path)
    names = x.sheet_names

    # SUMMARY 모드
    if "SUMMARY" in names:
        df = pd.read_excel(path, sheet_name="SUMMARY")
        req = {"티커", "시그널가격(USD)", "RSI"}
        if req.issubset(df.columns):
            return "SUMMARY", df

    # LEGACY 모드
    raw = pd.read_excel(path, sheet_name=names[0])
    req_old = {"티커", "종가", "RSI"}
    if req_old.issubset(raw.columns):
        df2 = pd.DataFrame()
        df2["티커"] = raw["티커"]
        df2["종가"] = raw["종가"]
        df2["RSI"] = raw["RSI"]
        df2["종목명"] = raw["종목명"] if "종목명" in raw.columns else raw["티커"]
        df2["신호"] = raw["판단"] if "판단" in raw.columns else "-"
        df2["점수"] = raw["점수"] if "점수" in raw.columns else None
        return "LEGACY", df2

    # UNKNOWN
    return "UNKNOWN", raw

mode, df = load_and_detect(file_path)

if mode == "UNKNOWN":
    st.error("❌ 파일 구조 인식 실패")
    st.dataframe(df.head())
    st.stop()

st.success(f"📄 파일 구조 인식 성공 — {mode} 모드")

st.dataframe(df, use_container_width=True)

# 종목 선택
if "종목명" in df.columns:
    names = df["종목명"].tolist()
else:
    names = df["티커"].tolist()

ticker_list = df["티커"].tolist()
mapping = dict(zip(names, ticker_list))

st.sidebar.header("종목 선택")
selected_name = st.sidebar.selectbox("티커 선택", names)
ticker = mapping[selected_name]

row = df[df["티커"] == ticker].iloc[0]

# SUMMARY 모드 값 파싱
if mode == "SUMMARY":
    sig_usd = float(row["시그널가격(USD)"])
    sig_krw = float(row.get("시그널가격(KRW)", sig_usd * usdkrw))
    rsi = float(row["RSI"])
    grade = row["등급"]
else:
    sig_usd = float(row["종가"])
    sig_krw = sig_usd * usdkrw
    rsi = float(row["RSI"])
    grade = row["신호"]

# UI 표시
st.subheader(f"📊 {selected_name} ({ticker}) 분석")
st.metric("시그널가 ($)", f"{sig_usd:,.2f}")
st.metric("시그널가 (₩)", f"{sig_krw:,.0f}")

# 가격 데이터 로드
@st.cache_data(ttl=300)
def load_price(ticker):
    df = yf.download(ticker, period="5d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.reset_index()
    time_col = df.columns[0]
    return df, time_col


# ==========================================
# 🔥🔥🔥 실시간 환율 기반 KRW Plotly 차트 🔥🔥🔥
# ==========================================
try:
    price, time_col = load_price(ticker)

    # USD → KRW 변환한 Close 추가
    price["Close_KRW"] = price["Close"] * usdkrw

    chart = price[[time_col, "Close_KRW"]]

    # 🔥 최근 3시간 필터링
    recent = chart[chart[time_col] >= chart[time_col].max() - timedelta(hours=3)]

    # 🔥 TP / SL (SUMMARY 기반 3%, -3%)
    tp_krw = sig_usd * 1.03 * usdkrw
    sl_krw = sig_usd * 0.97 * usdkrw

    # Plotly 그래프
    fig = go.Figure()

    # 가격선 (원화)
    fig.add_trace(go.Scatter(
        x=recent[time_col],
        y=recent["Close_KRW"],
        mode="lines",
        name="Price (KRW)",
        line=dict(width=2, color="blue")
    ))

    # TP 라인 (KRW)
    fig.add_hline(
        y=tp_krw,
        line=dict(color="green", width=2, dash="dash"),
        annotation_text=f"TP {tp_krw:,.0f}원",
        annotation_position="top left"
    )

    # SL 라인 (KRW)
    fig.add_hline(
        y=sl_krw,
        line=dict(color="red", width=2, dash="dash"),
        annotation_text=f"SL {sl_krw:,.0f}원",
        annotation_position="bottom left"
    )

    fig.update_xaxes(
        tickformat="%H:%M",
        dtick=600000,
        showgrid=True
    )

    fig.update_layout(
        title="📈 최근 가격 차트 (KRW 기준 / 최근 3시간 / 5분봉)",
        height=350,
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis_title="KRW (원)"
    )

    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error("가격 데이터를 불러올 수 없습니다.")
    st.write(e)
