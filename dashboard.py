import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import timedelta, datetime
import plotly.graph_objects as go

# =====================================
# 숫자 안전 변환
# =====================================
def safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        try:
            import pandas as _pd
            if _pd.isna(x):
                return default
        except:
            pass
        if isinstance(x, str):
            s = x.strip().replace(",", "").replace("%", "")
            if s == "" or s.lower() in ("nan", "none"):
                return default
            return float(s)
        return float(x)
    except:
        return default


# =====================================
# 컬럼명 정규화
# =====================================
def clean_columns(df):
    new = {}
    for c in df.columns:
        clean = (
            str(c)
            .replace("\u200b", "")
            .replace("\ufeff", "")
            .replace("\xa0", "")
            .strip()
        )
        new[c] = clean
    df.rename(columns=new, inplace=True)
    return df


# =====================================
# Streamlit 설정
# =====================================
st.set_page_config(page_title="ODIN Dashboard", layout="wide")
st.title("⚔️ ODIN SPEAR — MASTER DASHBOARD")


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
D_MAP = {
    "DECISION (추천)": os.path.join(BASE, "DECISION"),
    "RESULT (백테스트)": os.path.join(BASE, "RESULT")
}

folder = st.sidebar.selectbox("📁 폴더 선택", list(D_MAP.keys()))
TARGET = D_MAP[folder]

files = sorted(
    [f for f in os.listdir(TARGET) if f.endswith(".xlsx") and not f.startswith("~$")],
    reverse=True,
)

file_sel = st.selectbox("📄 분석 파일 선택", files)
file_path = os.path.join(TARGET, file_sel)


# =====================================
# 파일 로드 + 구조 감지
# =====================================
def load_file(path):
    x = pd.ExcelFile(path)
    sheet = x.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    df = clean_columns(df)

    # 확률 컬럼 통합
    prob_map = {
        "3일확률": ["3일확률", "3일상승확률(%)", "3일상승확률"],
        "5일확률": ["5일확률", "5일상승확률(%)", "5일상승확률"],
        "10일확률": ["10일확률", "10일상승확률(%)", "10일상승확률"],
    }
    for canon, alias in prob_map.items():
        if canon not in df.columns:
            for a in alias:
                if a in df.columns:
                    df[canon] = df[a]
                    break

    base_req = {"티커", "종가", "RSI"}
    prob_req = {"3일확률", "5일확률", "10일확률"}

    if base_req.issubset(df.columns) and prob_req.issubset(df.columns):
        if "종목명" not in df.columns:
            df["종목명"] = df["티커"]
        if "점수" not in df.columns:
            df["점수"] = df.get("최종점수", 0)
        if "5일수익률" not in df.columns:
            df["5일수익률"] = 0
        if "판단" not in df.columns:
            df["판단"] = "-"
        if "MACRO_SCORE" not in df.columns:
            df["MACRO_SCORE"] = None
        if "MACRO_SIGNAL" not in df.columns:
            df["MACRO_SIGNAL"] = ""
        return "ODIN_AI", df

    return "LEGACY", df


mode, df = load_file(file_path)
df = clean_columns(df)

st.success(f"파일 구조 인식 성공 — {mode}")
st.dataframe(df, use_container_width=True)


# =====================================
# 종목 선택
# =====================================
name_col = "종목명" if "종목명" in df.columns else "티커"
name_sel = st.selectbox("종목 선택", df[name_col].tolist())

row = df[df[name_col] == name_sel].iloc[0]
ticker = row["티커"]


# =====================================
# 값 파싱 (RSI FIX 적용)
# =====================================
def get_col(dfrow, *keys):
    for k in keys:
        for col in df.columns:
            if col.strip() == k:
                return dfrow[col]
    return None

price_usd = safe_float(get_col(row, "종가"), 0)
price_krw = price_usd * usdkrw

rsi = safe_float(get_col(row, "RSI"), 0)
score = safe_float(get_col(row, "점수", "최종점수"), 0)
ret5 = safe_float(get_col(row, "5일수익률"), None)

p3 = safe_float(get_col(row, "3일확률"), None)
p5 = safe_float(get_col(row, "5일확률"), None)
p10 = safe_float(get_col(row, "10일확률"), None)

macro_score = safe_float(get_col(row, "MACRO_SCORE"), None)
macro_signal = str(get_col(row, "MACRO_SIGNAL") or "")

decision = str(get_col(row, "판단") or "-")


# =====================================
# 자동판단
# =====================================
def auto_sig(rsi_v, score_v):
    if score_v >= 80: return "🚀 강한 매수"
    if score_v >= 60: return "🟢 매수 우위"
    if score_v >= 40: return "⚖️ 관망"
    if score_v >= 20: return "🔻 매도 우위"
    return "⛔ 강한 매도"

if decision.strip() == "-":
    decision = auto_sig(rsi, score)


# =====================================
# 판단 표시
# =====================================
st.markdown("---")
st.subheader(f"📚 {name_sel} — 최종 판단")
st.markdown(f"### {decision}")

if macro_score is not None:
    st.info(f"🌐 MACRO Score: **{macro_score:.2f}** | Signal: **{macro_signal}**")


# =====================================
# ML 확률 표시
# =====================================
st.subheader("📈 ML 상승 확률")
if mode == "ODIN_AI" and all(v is not None for v in [p3, p5, p10]):
    dfp = pd.DataFrame(
        {"기간": ["3일", "5일", "10일"], "상승확률": [p3, p5, p10]}
    ).set_index("기간")
    st.bar_chart(dfp)

else:
    st.info("이 파일에는 ML 확률 정보가 없습니다.")


# =====================================
# 기술/심리 요약
# =====================================
st.markdown("---")
st.subheader("💡 기술 / 심리 요약")

c1, c2, c3, c4 = st.columns(4)
c1.metric("RSI", f"{rsi:.2f}")
c2.metric("점수", f"{score:.1f}")
c3.metric("종가 ($)", f"{price_usd:,.2f}")
c4.metric("종가 (₩)", f"{price_krw:,.0f}")

if ret5 is not None:
    st.metric("최근 5일 수익률", f"{ret5:.2f}%")


# =====================================
# 가격 차트 (3시간 / 10분봉)
# =====================================
@st.cache_data(ttl=120)
def load_price_10m(sym):
    df = yf.download(sym, period="1d", interval="10m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.reset_index()


try:
    price = load_price_10m(ticker)
    tcol = "Datetime" if "Datetime" in price.columns else "Date"

    # 최근 3시간만 필터링
    cutoff = price[tcol].max() - timedelta(hours=3)
    recent = price[price[tcol] >= cutoff].copy()

    recent["Close_KRW"] = recent["Close"] * usdkrw

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
        title=f"{name_sel} 최근 3시간 (10분봉)",
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
st.subheader("📋 전체 데이터")
st.dataframe(df, use_container_width=True)
