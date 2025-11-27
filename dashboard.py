import streamlit as st
import pandas as pd
import yfinance as yf

# =====================================
# 기본 설정
# =====================================
st.set_page_config(page_title="ODIN'S SPEAR STRATEGY", layout="wide")
st.title("⚔️ ODIN'S SPEAR STRATEGY (Cloud Version)")

# =====================================
# 환율 불러오기
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
# 파일 업로드
# =====================================
uploaded = st.file_uploader("📂 RESULT 엑셀 파일 업로드", type=["xlsx"])

if uploaded is None:
    st.info("결과 파일(.xlsx)을 업로드하면 분석이 시작됩니다.")
    st.stop()

# =====================================
# 엑셀 로드 & 모드 감지
# =====================================
xls = pd.ExcelFile(uploaded)
sheets = xls.sheet_names

def load_and_detect(xls):
    sheet_names = xls.sheet_names

    # 1) SUMMARY 모드
    if "SUMMARY" in sheet_names:
        df_sum = pd.read_excel(xls, sheet_name="SUMMARY")
        if {"티커", "시그널가격(USD)", "RSI"}.issubset(df_sum.columns):
            return "SUMMARY", df_sum

    # 2) LEGACY 모드
    raw = pd.read_excel(xls, sheet_name=sheet_names[0])
    if {"티커", "종가", "RSI"}.issubset(raw.columns):
        df2 = pd.DataFrame()
        df2["티커"] = raw["티커"]
        df2["종가"] = raw["종가"]
        df2["RSI"] = raw["RSI"]
        df2["종목명"] = raw["종목명"] if "종목명" in raw else raw["티커"]
        df2["신호"] = raw["판단"] if "판단" in raw else "-"
        df2["점수"] = raw["점수"] if "점수" in raw.columns else None
        return "LEGACY", df2

    # 3) 인식 실패
    return "UNKNOWN", raw

mode, df = load_and_detect(xls)

if mode == "UNKNOWN":
    st.error("❌ 파일 구조를 자동 인식하지 못했습니다.")
    st.write("시트 목록:", sheets)
    st.dataframe(df.head())
    st.stop()

st.success(f"📄 파일 로드 완료 — 모드: {mode}")
st.dataframe(df, use_container_width=True)

st.markdown("---")

# =====================================
# 종목 선택
# =====================================
if "종목명" in df.columns:
    names = df["종목명"].tolist()
else:
    names = df["티커"].tolist()

ticker_map = dict(zip(names, df["티커"].tolist()))

st.sidebar.header("⚙️ 종목 선택")
selected_name = st.sidebar.selectbox("관심 종목", names)
ticker = ticker_map[selected_name]

row = df[df["티커"] == ticker].iloc[0]

# =====================================
# SUMMARY / LEGACY 값 파싱
# =====================================
if mode == "SUMMARY":
    sig_usd = float(row["시그널가격(USD)"])
    sig_krw = float(row["시그널가격(KRW)"]) if not pd.isna(row["시그널가격(KRW)"]) else None
    dist = float(row["저점대비(%)"])
    rsi = float(row["RSI"])
    grade = row["등급"]
    hold = int(row["HOLD"])
    tp_pct = float(row["TP(%)"])
    sl_pct = float(row["SL(%)"])
    tp_usd = float(row["TP목표가(USD)"])
    sl_usd = float(row["SL손절가(USD)"])
    tp_krw = float(row["TP목표가(KRW)"]) if not pd.isna(row["TP목표가(KRW)"]) else None
    sl_krw = float(row["SL손절가(KRW)"]) if not pd.isna(row["SL손절가(KRW)"]) else None
    win_rate = float(row["승률(%)"])
    avg_ret = float(row["평균수익률(%)"])
    confidence = row["신뢰도(%)"] if "신뢰도(%)" in row and not pd.isna(row["신뢰도(%)"]) else None

elif mode == "LEGACY":
    sig_usd = float(row["종가"])
    sig_krw = sig_usd * usdkrw
    rsi = float(row["RSI"])
    grade = row["신호"]
    dist = None
    hold = None
    tp_pct = None
    sl_pct = None
    tp_usd = None
    sl_usd = None
    tp_krw = None
    sl_krw = None
    win_rate = None
    avg_ret = None
    confidence = None

# =====================================
# 상단 카드 UI
# =====================================
st.subheader(f"📊 {selected_name} ({ticker}) 분석")

c1, c2, c3, c4 = st.columns(4)
c1.metric("시그널가 ($)", f"{sig_usd:,.2f}")
c2.metric("시그널가 (₩)", f"{sig_krw:,.0f} 원" if sig_krw else "-")
c3.metric("저점대비 (%)", f"{dist:.2f}%" if dist else "-")
c4.metric("RSI / 신호", f"{rsi:.1f} / {grade}")

c5, c6, c7, c8 = st.columns(4)

if mode == "SUMMARY":
    c5.metric("HOLD (일)", f"{hold}일")
    c6.metric("TP / SL (%)", f"{tp_pct:.1f}% / {sl_pct:.1f}%")
    c7.metric("승률 (%)", f"{win_rate:.1f}%")
    c8.metric("평균 수익률 (%)", f"{avg_ret:.2f}%")
else:
    c5.metric("점수", f"{row['점수']}" if "점수" in row else "-")
    c6.metric("RSI", f"{rsi:.1f}")
    c7.metric("판단", grade)
    c8.metric("데이터 모드", "LEGACY")

# 신뢰도
if mode == "SUMMARY":
    if confidence:
        st.metric("🛡 신뢰도 (ML 예측)", f"{confidence:.1f}%")
    else:
        st.info("🛡 신뢰도 모델이 아직 없습니다. (confidence_model.pkl)")

st.markdown("---")

# =====================================
# 가격 차트
# =====================================
@st.cache_data(ttl=300)
def load_price_data(ticker):
    df = yf.download(ticker, period="5d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):    # flatten
        df.columns = [c[0] for c in df.columns]
    df = df.reset_index()
    time_col = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]
    time_col = time_col[0] if time_col else df.columns[0]
    return df, time_col

try:
    price_df, time_col = load_price_data(ticker)
except Exception as e:
    st.error("❌ 가격 데이터를 불러오지 못했습니다.")
    st.write(e)
    st.stop()

st.subheader("📈 최근 5일 5분봉 차트 (Close)")

if "Close" not in price_df.columns:
    st.error("'Close' 컬럼이 없습니다.")
else:
    chart_df = price_df[[time_col, "Close"]].set_index(time_col)
    st.line_chart(chart_df, height=450)

st.markdown("---")

# =====================================
# 기준 가격 표
# =====================================
st.subheader("📏 기준 가격 요약")

lines = {"시그널 가격 ($)": sig_usd}
if mode == "SUMMARY":
    lines["TP 목표가 ($)"] = tp_usd
    lines["SL 손절가 ($)"] = sl_usd

guide_df = pd.DataFrame(lines.values(), index=lines.keys(), columns=["가격 ($)"])
guide_df["가격 (₩)"] = guide_df["가격 ($)"] * usdkrw

st.table(guide_df)
st.caption("⏱ 데이터는 yfinance 기준 / 업로드한 SUMMARY 기반 표시")
