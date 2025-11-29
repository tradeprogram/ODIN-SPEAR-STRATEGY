import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import timedelta
import plotly.graph_objects as go
import numpy as np

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
    except Exception:
        return 1400.0

usdkrw = get_usdkrw()
# 혹시라도 이상한 타입/값 들어오면 방어
try:
    usdkrw = float(usdkrw)
except Exception:
    usdkrw = 1400.0

st.metric("💱 USD/KRW", f"{usdkrw:,.2f} 원")
st.markdown("---")

# =====================================
# 폴더/파일 경로 설정
# =====================================
BASE = os.path.dirname(os.path.abspath(__file__))

RESULT_DIR = os.path.join(BASE, "RESULT")
DECISION_DIR = os.path.join(BASE, "DECISION")

FOLDER_MAP = {
    "DECISION (추천)": DECISION_DIR,
    "RESULT (구버전)": RESULT_DIR,
}

# =====================================
# 숫자 변환 유틸
# =====================================
def to_float(val, default=0.0):
    try:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            if pd.isna(val):
                return default
            return float(val)
        s = str(val).strip().replace(",", "").replace("%", "")
        if s == "" or s.lower() in ("nan", "none"):
            return default
        return float(s)
    except Exception:
        return default

@st.cache_data(ttl=600)
def compute_rsi_fallback(ticker: str, period: str = "3mo") -> float:
    """
    엑셀에 RSI가 비어있거나 0일 때, yfinance로 14일 RSI를 대충 계산해서 채워주는 용도.
    엑셀 값이 정상일 때는 건드리지 않음.
    """
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False)
        if df is None or df.empty:
            return 0.0

        close = df["Close"].astype(float)
        delta = close.diff()

        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi_series = 100 - (100 / (1 + rs))
        last = rsi_series.iloc[-1]
        if pd.isna(last):
            return 0.0
        return float(last)
    except Exception:
        return 0.0

# =====================================
# 사이드바 - 폴더 & 파일 선택
# =====================================
folder_choice = st.sidebar.selectbox("📁 폴더 선택", list(FOLDER_MAP.keys()))
TARGET_DIR = FOLDER_MAP[folder_choice]

st.write(f"📂 현재 선택된 폴더: `{folder_choice}`")

if not os.path.exists(TARGET_DIR):
    st.error(f"❌ {TARGET_DIR} 폴더가 존재하지 않습니다.")
    st.stop()

files = sorted(
    [f for f in os.listdir(TARGET_DIR) if f.endswith(".xlsx") and not f.startswith("~$")],
    reverse=True,
)

if not files:
    st.warning(f"📂 {TARGET_DIR} 폴더에 엑셀 파일이 없습니다.")
    st.stop()

selected = st.selectbox("📄 분석 파일 선택", files)
file_path = os.path.join(TARGET_DIR, selected)
st.caption(f"현재 선택된 파일: **{selected}**")

# =====================================
# 엑셀 로드 & 포맷 감지
# =====================================
def load_and_detect(path: str):
    x = pd.ExcelFile(path)
    names = x.sheet_names

    # 1) SUMMARY 모드
    if "SUMMARY" in names:
        df = pd.read_excel(path, sheet_name="SUMMARY")
        req = {"티커", "시그널가격(USD)", "RSI"}
        if req.issubset(df.columns):
            return "SUMMARY", df

    # 2) 새 ODIN_AI 모드
    raw = pd.read_excel(path, sheet_name=names[0])

    # ---- 여기서 신규 포맷 컬럼명 매핑 (최소 수정) ----
    alt_map = {
        "최종점수": "점수",
        "3일상승확률": "3일확률",
        "3일상승확률(%)": "3일확률",
        "5일상승확률": "5일확률",
        "5일상승확률(%)": "5일확률",
        "10일상승확률": "10일확률",
        "10일상승확률(%)": "10일확률",
    }
    for old, new in alt_map.items():
        if old in raw.columns and new not in raw.columns:
            raw[new] = raw[old]

    base_req = {"티커", "종가", "RSI"}
    prob_req = {"3일확률", "5일확률", "10일확률"}

    if base_req.issubset(raw.columns) and prob_req.issubset(raw.columns):
        df2 = raw.copy()
        if "종목명" not in df2.columns:
            df2["종목명"] = df2["티커"]
        if "5일수익률" not in df2.columns:
            df2["5일수익률"] = 0.0
        if "점수" not in df2.columns:
            df2["점수"] = 0.0
        if "판단" not in df2.columns:
            df2["판단"] = "-"
        return "ODIN_AI", df2

    # 3) LEGACY 모드
    if base_req.issubset(raw.columns):
        df2 = pd.DataFrame()
        df2["티커"] = raw["티커"]
        df2["종가"] = raw["종가"]
        df2["RSI"] = raw["RSI"]
        df2["종목명"] = raw["종목명"] if "종목명" in raw.columns else raw["티커"]
        df2["판단"] = raw["판단"] if "판단" in raw.columns else "-"
        df2["점수"] = raw["점수"] if "점수" in raw.columns else 0.0
        df2["5일수익률"] = raw["5일수익률"] if "5일수익률" in raw.columns else 0.0
        # LEGACY는 ML값이 없으니 그냥 50으로 채워둠
        df2["3일확률"] = 50
        df2["5일확률"] = 50
        df2["10일확률"] = 50
        return "LEGACY", df2

    # 4) UNKNOWN
    return "UNKNOWN", raw

mode, df = load_and_detect(file_path)

if mode == "UNKNOWN":
    st.error("❌ 파일 구조 인식 실패 (UNKNOWN MODE)")
    st.dataframe(df.head())
    st.stop()

st.success(f"📄 파일 구조 인식 성공 — {mode} 모드")
st.dataframe(df, use_container_width=True)

# =====================================
# 종목 선택
# =====================================
if "종목명" in df.columns:
    name_list = df["종목명"].tolist()
else:
    name_list = df["티커"].tolist()

ticker_list = df["티커"].tolist()
mapping = dict(zip(name_list, ticker_list))

st.sidebar.header("종목 선택")
selected_name = st.sidebar.selectbox("티커 선택", name_list)
ticker = mapping[selected_name]

row = df[df["티커"] == ticker].iloc[0]

# =====================================
# 공통 값 파싱 (RSI NaN/0 보정 포함)
# =====================================
if mode == "SUMMARY":
    sig_usd = to_float(row["시그널가격(USD)"])
    sig_krw = to_float(row.get("시그널가격(KRW)", sig_usd * usdkrw))
    rsi_raw = row["RSI"]
    rsi = to_float(rsi_raw, None)
    if rsi is None or rsi == 0.0:
        rsi = compute_rsi_fallback(ticker)
    score = to_float(row.get("점수", 0))
    p3 = p5 = p10 = None
    signal_raw = row.get("등급", "-")
    ret5 = None
else:
    sig_usd = to_float(row["종가"])
    sig_krw = sig_usd * usdkrw

    rsi_raw = row.get("RSI", None)
    rsi = to_float(rsi_raw, None)
    if rsi is None or rsi == 0.0:
        rsi = compute_rsi_fallback(ticker)

    score = to_float(row.get("점수", 0))
    ret5 = to_float(row.get("5일수익률", 0))
    p3 = to_float(row.get("3일확률", 50))
    p5 = to_float(row.get("5일확률", 50))
    p10 = to_float(row.get("10일확률", 50))
    signal_raw = row.get("판단", "-")

# =====================================
# 판단 이모지 + 자동 판단 생성
# =====================================
def auto_signal(rsi_val: float, score_val: float) -> str:
    # 점수를 우선, 그다음 RSI로 보정
    if score_val >= 80:
        return "강한 매수 구간"
    if score_val >= 60:
        return "매수 우위 구간"
    if rsi_val < 25:
        return "바닥권 접근"
    if rsi_val < 35:
        return "저점 매수 관찰"
    if rsi_val > 80:
        return "건드리지 말기"
    if rsi_val > 70:
        return "단기 과열"
    return "관망 구간"

def interpret_signal(text: str) -> str:
    t = str(text)
    if "강한 매수" in t:
        return f"🚀 {t}"
    if "매수 우위" in t or ("매수" in t and "강한" not in t):
        return f"📈 {t}"
    if "바닥" in t or "저점" in t:
        return f"📉 {t}"
    if "건드리지 말기" in t:
        return f"⛔ {t}"
    if "관망" in t:
        return f"⏳ {t}"
    if "과열" in t:
        return f"⚠️ {t}"
    return f"❔ {t}"

# 원본 판단 텍스트가 없거나 "-"면 자동 판단 생성
if isinstance(signal_raw, str) and signal_raw not in ["", "-"]:
    base_signal = signal_raw
else:
    base_signal = auto_signal(rsi, score)

final_signal = interpret_signal(base_signal)

# =====================================
# 상단 혼합형 레이아웃 (네가 만들었던 그대로)
# =====================================
left, right = st.columns([2, 3])

with left:
    st.subheader(f"📊 {selected_name} ({ticker}) 최종 판단")
    st.markdown(
        f"""
        <div style="
            padding: 1.2rem;
            border-radius: 1.2rem;
            border: 1px solid #44444422;
            background: #f5f7fb;
        ">
            <div style="font-size: 1.3rem; font-weight: 700; margin-bottom: 0.3rem;">
                {final_signal}
            </div>
            <div style="font-size: 0.9rem; opacity: 0.8;">
                엔진 + 패턴 + ML + MACRO 종합 판단
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 💡 기술/심리 요약")
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("RSI", f"{rsi:.1f}")
        st.metric("기술 점수", f"{score:.0f} / 100")
    with col_b:
        st.metric("시그널가 ($)", f"{sig_usd:,.2f}")
        st.metric("시그널가 (₩)", f"{sig_krw:,.0f}")

    if ret5 is not None:
        st.metric("최근 5일 수익률", f"{ret5:.2f} %")

with right:
    st.subheader("📈 ML 상승 확률 (3/5/10일)")
    if p3 is not None:
        p_df = pd.DataFrame(
            {
                "기간": ["3일", "5일", "10일"],
                "상승확률": [p3, p5, p10],
            }
        ).set_index("기간")
        st.bar_chart(p_df)

        c1, c2, c3 = st.columns(3)
        c1.metric("3일 상승 확률", f"{p3:.1f} %")
        c2.metric("5일 상승 확률", f"{p5:.1f} %")
        c3.metric("10일 상승 확률", f"{p10:.1f} %")
    else:
        st.info("이 파일 포맷에서는 ML 확률 정보가 없습니다. (SUMMARY 모드)")

# =====================================
# 가격 차트 (KRW 기준 / TP·SL 포함)
# =====================================
@st.cache_data(ttl=300)
def load_price(tkr: str):
    df = yf.download(tkr, period="5d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.reset_index()
    time_col = df.columns[0]
    return df, time_col

st.markdown("---")
st.subheader("📉 최근 가격 차트 (KRW 기준 / TP·SL 포함)")

try:
    price, time_col = load_price(ticker)

    # datetime 형 변환 (float 방지)
    price[time_col] = pd.to_datetime(price[time_col], errors="coerce")

    # KRW 변환
    price["Close_KRW"] = price["Close"] * usdkrw

    # 최근 3시간만 표시
    cutoff = price[time_col].max() - timedelta(hours=3)
    recent = price[price[time_col] >= cutoff]

    # TP / SL (기본: ±3%)
    tp_krw = sig_krw * 1.03
    sl_krw = sig_krw * 0.97

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=recent[time_col],
            y=recent["Close_KRW"],
            mode="lines",
            name="Price (KRW)",
            line=dict(width=2, color="blue"),
        )
    )

    fig.add_hline(
        y=tp_krw,
        line=dict(color="green", width=2, dash="dash"),
        annotation_text=f"TP {tp_krw:,.0f}원",
        annotation_position="top left",
    )

    fig.add_hline(
        y=sl_krw,
        line=dict(color="red", width=2, dash="dash"),
        annotation_text=f"SL {sl_krw:,.0f}원",
        annotation_position="bottom left",
    )

    fig.update_xaxes(tickformat="%H:%M", dtick=600000)
    fig.update_layout(
        title=f"{ticker} 최근 3시간 (KRW 기준)",
        height=400,
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
st.subheader("📋 전체 종목 리스트")
st.dataframe(df, use_container_width=True)
