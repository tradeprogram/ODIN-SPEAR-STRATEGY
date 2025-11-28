import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import timedelta
import plotly.graph_objects as go


def safe_float(x, default=0.0):
    """Robust float converter: handles None/NaN/strings/percent/comma."""
    try:
        # Direct None
        if x is None:
            return default
        # Handle pandas NA / NaN
        try:
            import pandas as _pd
            if _pd.isna(x):
                return default
        except Exception:
            pass
        # String cleanup
        if isinstance(x, str):
            s = x.strip()
            if s == "" or s.lower() in ("nan", "none"):
                return default
            s = s.replace(",", "").replace("%", "")
            return float(s)
        # Fallback numeric
        return float(x)
    except Exception:
        return default


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

st.sidebar.metric("💱 USD/KRW", f"{usdkrw:,.2f} 원")

# =====================================
# 폴더 매핑
# =====================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FOLDER_MAP = {
    "DECISION (추천)": os.path.join(BASE_DIR, "DECISION"),
    "RESULT (백테스트)": os.path.join(BASE_DIR, "RESULT"),
}

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
    # 엑셀 시트 목록
    x = pd.ExcelFile(path)
    names = x.sheet_names

    # 1) SUMMARY 모드 (백테스트/집계용 요약 시트)
    if "SUMMARY" in names:
        df = pd.read_excel(path, sheet_name="SUMMARY", engine="openpyxl")
        req = {"티커", "시그널가격(USD)", "RSI"}
        if req.issubset(df.columns):
            # MACRO 컬럼이 없으면 기본값 추가
            if "MACRO_SCORE" not in df.columns:
                df["MACRO_SCORE"] = None
            if "MACRO_SIGNAL" not in df.columns:
                df["MACRO_SIGNAL"] = ""
            return "SUMMARY", df

    # 2) 일반 분석 시트 (DECISION용) – ODIN_AI / LEGACY 자동 판별
    raw = pd.read_excel(path, sheet_name=names[0], engine="openpyxl")

    # 확률 컬럼 이름 통합 (3일상승확률(%) → 3일확률 등)
    prob_aliases = {
        "3일확률": ["3일확률", "3일상승확률(%)", "3일상승확률"],
        "5일확률": ["5일확률", "5일상승확률(%)", "5일상승확률"],
        "10일확률": ["10일확률", "10일상승확률(%)", "10일상승확률"],
    }
    for canon, candidates in prob_aliases.items():
        if canon not in raw.columns:
            for c in candidates:
                if c in raw.columns:
                    raw[canon] = raw[c]
                    break

    base_req = {"티커", "종가", "RSI"}
    prob_req = {"3일확률", "5일확률", "10일확률"}

    # 2-1) 완전한 ODIN_AI 포맷 (ML + MACRO 포함)
    if base_req.issubset(raw.columns) and prob_req.issubset(raw.columns):
        df2 = raw.copy()
        if "종목명" not in df2.columns:
            df2["종목명"] = df2["티커"]
        if "5일수익률" not in df2.columns:
            df2["5일수익률"] = 0.0
        if "점수" not in df2.columns:
            if "최종점수" in df2.columns:
                df2["점수"] = df2["최종점수"]
            else:
                df2["점수"] = 0.0
        if "판단" not in df2.columns:
            df2["판단"] = "-"
        # MACRO 컬럼 기본값
        if "MACRO_SCORE" not in df2.columns:
            df2["MACRO_SCORE"] = None
        if "MACRO_SIGNAL" not in df2.columns:
            df2["MACRO_SIGNAL"] = ""
        return "ODIN_AI", df2

    # 3) 최소 포맷만 있는 LEGACY 모드 (확률/매크로 없음)
    if base_req.issubset(raw.columns):
        df2 = pd.DataFrame()
        df2["티커"] = raw["티커"]
        df2["종가"] = raw["종가"]
        df2["RSI"] = raw["RSI"]
        df2["종목명"] = raw["종목명"] if "종목명" in raw.columns else raw["티커"]
        df2["판단"] = raw["판단"] if "판단" in raw.columns else "-"
        # 점수 / 5일수익률이 있으면 가져오고, 없으면 0으로 채움
        if "점수" in raw.columns:
            df2["점수"] = raw["점수"]
        elif "최종점수" in raw.columns:
            df2["점수"] = raw["최종점수"]
        else:
            df2["점수"] = 0.0
        df2["5일수익률"] = raw["5일수익률"] if "5일수익률" in raw.columns else 0.0
        df2["3일확률"] = 50
        df2["5일확률"] = 50
        df2["10일확률"] = 50
        # MACRO 컬럼 기본값
        df2["MACRO_SCORE"] = None
        df2["MACRO_SIGNAL"] = ""
        return "LEGACY", df2

    # 4) 어디에도 맞지 않으면 UNKNOWN
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

ticker = st.selectbox("종목 선택", name_list)

# 티커 실제 값 찾기
if "종목명" in df.columns:
    row = df[df["종목명"] == ticker].iloc[0]
    ticker_sym = row["티커"]
else:
    row = df[df["티커"] == ticker].iloc[0]
    ticker_sym = ticker

row = df[df["티커"] == ticker_sym].iloc[0]

# =====================================
# 공통 값 파싱
# =====================================
if mode == "SUMMARY":
    sig_usd = safe_float(row.get("시그널가격(USD)"), default=0.0)
    # 시그널 KRW가 없으면 환율로 환산
    sig_krw = safe_float(row.get("시그널가격(KRW)"), default=sig_usd * usdkrw)
    rsi = safe_float(row.get("RSI"), default=0.0)
    score = safe_float(row.get("점수", 0.0), default=0.0)
    p3 = p5 = p10 = None
    signal_raw = row.get("등급", "-")
    ret5 = None
else:
    sig_usd = safe_float(row.get("종가"), default=0.0)
    sig_krw = sig_usd * usdkrw
    rsi = safe_float(row.get("RSI"), default=0.0)
    score = safe_float(row.get("점수", row.get("점수(룰)", 0.0)), default=0.0)
    ret5 = safe_float(row.get("5일수익률", 0.0), default=0.0)
    # AI_MASTER_ENGINE에서 생성한 확률 컬럼 또는 기본값(50%) 사용
    p3 = safe_float(row.get("3일확률", row.get("3일상승확률(%)", 50.0)), default=50.0)
    p5 = safe_float(row.get("5일확률", row.get("5일상승확률(%)", 50.0)), default=50.0)
    p10 = safe_float(row.get("10일확률", row.get("10일상승확률(%)", 50.0)), default=50.0)
    signal_raw = row.get("판단", "-")

macro_score_raw = row.get("MACRO_SCORE", None)
macro_score = safe_float(macro_score_raw, default=None)
macro_signal = str(row.get("MACRO_SIGNAL", "") or "")

# =====================================
# 판단 이모지 + 자동 판단 생성
# =====================================
def auto_signal(rsi_val: float, score_val: float) -> str:
    # 점수를 우선, 그다음 RSI로 보정
    if score_val >= 80:
        base = "강하게 매수 관점입니다."
        emoji = "🚀"
    elif score_val >= 60:
        base = "매수 우위입니다."
        emoji = "🟢"
    elif score_val >= 40:
        base = "중립/관망입니다."
        emoji = "⚖️"
    elif score_val >= 20:
        base = "매도 우위입니다."
        emoji = "🔻"
    else:
        base = "강하게 매도/관망입니다."
        emoji = "⛔"

    # RSI로 과매수/과매도 보정
    if rsi_val >= 70:
        tail = " (RSI 과매수 구간)"
    elif rsi_val <= 30:
        tail = " (RSI 과매도 구간)"
    else:
        tail = ""

    return f"{emoji} {base}{tail}"


if isinstance(signal_raw, str):
    final_signal = signal_raw
else:
    final_signal = auto_signal(rsi, score)

# =====================================
# 상단 카드 레이아웃
# =====================================
st.markdown("---")
st.markdown(
    f"""
    <h2 style="margin-bottom: 0.5rem;">
        📚 {ticker} 최종 판단
    </h2>
    """,
    unsafe_allow_html=True,
)

col_main, col_prob = st.columns([2, 2])

with col_main:
    st.markdown(
        f"""
        <div style="
            padding: 1.2rem;
            border-radius: 1.2rem;
            border: 1px solid #44444422;
            background: #f5f7fb;
            margin-bottom: 0.8rem;
        ">
            <div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 0.4rem;">
                최종 판단
            </div>
            <div style="font-size: 1.4rem; font-weight: 700;">
                {final_signal}
            </div>
            <div style="font-size: 0.9rem; opacity: 0.8; margin-top: 0.3rem;">
                엔진 + 패턴 + ML + MACRO 종합 판단
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # MACRO 카드 (있을 때만)
    if macro_score is not None or macro_signal:
        display_macro_score = f"{macro_score:.1f}" if macro_score is not None else "N/A"
        st.markdown(
            f"""
            <div style="
                padding: 0.9rem;
                border-radius: 1.0rem;
                border: 1px dashed #8882;
                background: #ffffff;
                margin-bottom: 0.8rem;
            ">
                <div style="font-size: 0.95rem; font-weight: 600; margin-bottom: 0.2rem;">
                    🌐 시장 이벤트 (MACRO)
                </div>
                <div style="font-size: 0.95rem;">
                    점수: <b>{display_macro_score}</b> / 시그널: <b>{macro_signal or "정보 없음"}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with col_prob:
    st.subheader("📈 ML 상승 확률 (3/5/10일)")
    if mode == "ODIN_AI" and all(v is not None for v in [p3, p5, p10]):
        p_df = pd.DataFrame(
            {
                "기간": ["3일", "5일", "10일"],
                "상승 확률": [p3, p5, p10],
            }
        ).set_index("기간")
        st.bar_chart(p_df)

        c1, c2, c3 = st.columns(3)
        c1.metric("3일 상승 확률", f"{p3:.1f} %")
        c2.metric("5일 상승 확률", f"{p5:.1f} %")
        c3.metric("10일 상승 확률", f"{p10:.1f} %")
    else:
        st.info("이 파일 포맷에서는 ML 확률 정보가 없습니다. (SUMMARY/LEGACY 모드)")

# =====================================
# 기술/심리 요약
# =====================================
st.markdown("---")
st.subheader("💡 기술/심리 요약")

c1, c2, c3, c4 = st.columns(4)
c1.metric("RSI", f"{rsi:.2f}")
c2.metric("기술 점수", f"{score:.1f} / 100")
c3.metric("시그널가 ($)", f"{sig_usd:,.2f}")
c4.metric("시그널가 (₩)", f"{sig_krw * usdkrw:,.0f}")

if ret5 is not None:
    st.metric("최근 5일 수익률", f"{ret5:.2f} %")

# =====================================
# 가격 차트 (KRW 기준 / TP·SL 포함)
# =====================================
@st.cache_data(ttl=300)
def load_price(tkr: str):
    df = yf.download(tkr, period="5d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.reset_index()


try:
    price = load_price(ticker_sym)
    if "Datetime" in price.columns:
        time_col = "Datetime"
    elif "Date" in price.columns:
        time_col = "Date"
    else:
        time_col = price.columns[0]

    price["Close_KRW"] = price["Close"] * usdkrw
    cutoff = price[time_col].max() - timedelta(days=2)
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
        y=tp_krw * usdkrw,
        line=dict(dash="dash", width=1, color="green"),
        annotation_text="TP ( +3% )",
        annotation_position="top left",
    )
    fig.add_hline(
        y=sl_krw * usdkrw,
        line=dict(dash="dash", width=1, color="red"),
        annotation_text="SL ( -3% )",
        annotation_position="bottom left",
    )
    fig.update_layout(
        title=f"최근 가격 차트 (KRW 기준, TP/SL 포함) - {ticker_sym}",
        xaxis_title="Time",
        yaxis_title="Price (KRW)",
        height=400,
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
