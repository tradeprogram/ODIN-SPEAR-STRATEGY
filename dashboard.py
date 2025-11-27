import streamlit as st
import pandas as pd
import yfinance as yf
import os

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

# =====================================
# 이하 기존 SUMMARY/LEGACY 처리 로직 동일...
# (원래 네가 사용하던 UI 구조 그대로 유지)
# =====================================

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

try:
    price, time_col = load_price(ticker)
    chart_df = price[[time_col, "Close"]].set_index(time_col)
    st.line_chart(chart_df, height=350)
except:
    st.error("가격 데이터를 불러올 수 없습니다.")
