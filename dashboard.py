import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import timedelta
import plotly.graph_objects as go

# =====================================
# 공통 숫자 변환 (NaN/None/문자/공백 모두 안전)
# =====================================
def safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        # Pandas NA
        try:
            import pandas as _pd
            if _pd.isna(x):
                return default
        except Exception:
            pass
        # 문자열 처리
        if isinstance(x, str):
            s = x.strip().replace(",", "").replace("%", "")
            if s == "" or s.lower() in ("nan", "none"):
                return default
            return float(s)
        return float(x)
    except Exception:
        return default


# =====================================
# 컬럼명 정규화 (제로폭 스페이스 제거)
# =====================================
def clean_columns(df):
    new_cols = {}
    for c in df.columns:
        clean = (
            str(c)
            .replace("\u200b", "")
            .replace("\ufeff", "")
            .replace("\xa0", "")
            .strip()
        )
        new_cols[c] = clean
    df.rename(columns=new_cols, inplace=True)
    return df


# =====================================
# Streamlit 기본 설정
# =====================================
st.set_page_config(page_title="ODIN SPEAR DASHBOARD", layout="wide")
st.title("⚔️ ODIN'S SPEAR STRATEGY (MASTER DASHBOARD)")


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


usdkrw = safe_float(get_usdkrw(), 1400.0)
st.sidebar.metric("💱 USD/KRW", f"{usdkrw:,.2f} 원")


# =====================================
# 폴더 선택
# =====================================
BASE = os.path.dirname(os.path.abspath(__file__))
DIR_MAP = {
    "DECISION (추천)": os.path.join(BASE, "DECISION"),
    "RESULT (백테스트)": os.path.join(BASE, "RESULT"),
}

folder = st.sidebar.selectbox("📁 폴더 선택", list(DIR_MAP.keys()))
TARGET = DIR_MAP[folder]

if not os.path.exists(TARGET):
    st.stop()

excel_list = sorted(
    [f for f in os.listdir(TARGET) if f.endswith(".xlsx") and not f.startswith("~$")],
    reverse=True,
)
if not excel_list:
    st.stop()

file_sel = st.selectbox("📄 분석 파일 선택", excel_list)
file_path = os.path.join(TARGET, file_sel)
st.caption(f"현재 선택된 파일: **{file_sel}**")


# =====================================
# 파일 로드 + 구조 감지 (패치 2.0)
# =====================================
def load_file(path):
    x = pd.ExcelFile(path)
    sheet = x.sheet_names[0]
    raw = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    raw = clean_columns(raw)

    # 확률 컬럼 통일
    prob_map = {
        "3일확률": ["3일확률", "3일상승확률(%)", "3일상승확률"],
        "5일확률": ["5일확률", "5일상승확률(%)", "5일상승확률"],
        "10일확률": ["10일확률", "10일상승확률(%)", "10일상승확률"],
    }
    for canon, alias in prob_map.items():
        if canon not in raw.columns:
            for a in alias:
                if a in raw.columns:
                    raw[canon] = raw[a]
                    break

    base_req = {"티커", "종가", "RSI"}
    prob_req = {"3일확률", "5일확률", "10일확률"}

    # 완전 AI 모드
    if base_req.issubset(raw.columns) and prob_req.issubset(raw.columns):
        if "종목명" not in raw.columns:
            raw["종목명"] = raw["티커"]
        if "점수" not in raw.columns:
            raw["점수"] = raw.get("최종점수", 0)
        if "5일수익률" not in raw.columns:
            raw["5일수익률"] = 0
        if "판단" not in raw.columns:
            raw["판단"] = "-"

        if "MACRO_SCORE" not in raw.columns:
            raw["MACRO_SCORE"] = None
        if "MACRO_SIGNAL" not in raw.columns:
            raw["MACRO_SIGNAL"] = ""

        return "ODIN_AI", raw

    # 레거시
    if base_req.issubset(raw.columns):
        df = pd.DataFrame()
        df["티커"] = raw["티커"]
        df["종가"] = raw["종가"]
        df["RSI"] = raw["RSI"]
        df["종목명"] = raw["종목명"] if "종목명" in raw.columns else raw["티커"]
        df["판단"] = raw["판단"] if "판단" in raw.columns else "-"
        df["점수"] = raw.get("점수", raw.get("최종점수", 0))
        df["5일수익률"] = raw.get("5일수익률", 0)
        df["3일확률"] = 50
        df["5일확률"] = 50
        df["10일확률"] = 50
        df["MACRO_SCORE"] = None
        df["MACRO_SIGNAL"] = ""
        return "LEGACY", df

    return "UNKNOWN", raw


mode, df = load_file(file_path)

st.success(f"📄 파일 구조 인식 성공 — {mode} 모드")
st.dataframe(df, use_container_width=True)


# =====================================
# 종목 선택
# =====================================
name_col = "종목명" if "종목명" in df.columns else "티커"
ticker_name = st.selectbox("종목 선택", df[name_col].tolist())
row = df[df[name_col] == ticker_name].iloc[0]
ticker = row["티커"]


# =====================================
# 값 파싱
# =====================================
price_usd = safe_float(row.get("종가"), 0)
price_krw = price_usd * usdkrw

rsi = safe_float(row.get("RSI"), 0)
score = safe_float(row.get("점수"), 0)
ret5 = safe_float(row.get("5일수익률"), None)

p3 = safe_float(row.get("3일확률"), None)
p5 = safe_float(row.get("5일확률"), None)
p10 = safe_float(row.get("10일확률"), None)

macro_score = row.get("MACRO_SCORE", None)
macro_score = safe_float(macro_score, None)
macro_signal = str(row.get("MACRO_SIGNAL", "") or "")

decision = str(row.get("판단", "-"))


# =====================================
# 자동 판단 보정
# =====================================
def auto_signal(rsi_v, score_v):
    if score_v >= 80: return "🚀 강한 매수"
    if score_v >= 60: return "🟢 매수 우위"
    if score_v >= 40: return "⚖️ 관망"
    if score_v >= 20: return "🔻 매도 우위"
    return "⛔ 강한 매도"

if decision.strip() == "-":
    decision = auto_signal(rsi, score)


# =====================================
# 표시 UI
# =====================================
st.markdown("---")
st.subheader(f"📚 {ticker_name} 최종 판단")
st.markdown(f"### {decision}")

if macro_score is not None:
    st.info(f"🌐 MACRO Score: **{macro_score:.2f}** | Signal: **{macro_signal}**")


# =====================================
# ML 확률
# =====================================
st.subheader("📈 ML 상승 확률")
if mode == "ODIN_AI" and all(v is not None for v in [p3, p5, p10]):
    p_df = pd.DataFrame(
        {"기간": ["3일", "5일", "10일"], "상승 확률": [p3, p5, p10]}
    ).set_index("기간")
    st.bar_chart(p_df)

    c1, c2, c3 = st.columns(3)
    c1.metric("3일 상승", f"{p3:.1f}%")
    c2.metric("5일 상승", f"{p5:.1f}%")
    c3.metric("10일 상승", f"{p10:.1f}%")
else:
    st.info("이 파일에는 ML 확률 정보가 없습니다.")


# =====================================
# 기술/심리 요약
# =====================================
st.markdown("---")
st.subheader("💡 기술/심리 요약")

c1, c2, c3, c4 = st.columns(4)
c1.metric("RSI", f"{rsi:.2f}")
c2.metric("점수", f"{score:.1f}")
c3.metric("종가 ($)", f"{price_usd:,.2f}")
c4.metric("종가 (₩)", f"{price_krw:,.0f}")

if ret5 is not None:
    st.metric("최근 5일 수익률", f"{ret5:.2f}%")


# =====================================
# 가격 차트 (TP/SL 버그 수정판)
# =====================================
@st.cache_data(ttl=300)
def load_price(sym):
    df = yf.download(sym, period="5d", interval="30m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.reset_index()

try:
    price = load_price(ticker)
    tcol = "Datetime" if "Datetime" in price.columns else "Date"
    price["Close_KRW"] = price["Close"] * usdkrw

    recent = price[price[tcol] >= price[tcol].max() - timedelta(days=2)]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=recent[tcol], y=recent["Close_KRW"],
            mode="lines", name="Price (KRW)", line=dict(color="blue")
        )
    )

    tp = price_krw * 1.03
    sl = price_krw * 0.97

    fig.add_hline(y=tp, line=dict(dash="dash", color="green"), annotation_text="TP")
    fig.add_hline(y=sl, line=dict(dash="dash", color="red"), annotation_text="SL")

    fig.update_layout(
        height=400,
        title=f"{ticker_name} 최근 가격 (KRW 기준)",
        yaxis_title="KRW",
    )
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error("차트 로딩 실패")
    st.write(e)


# =====================================
# 전체 테이블
# =====================================
st.markdown("---")
st.subheader("📋 전체 종목 데이터")
st.dataframe(df, use_container_width=True)
