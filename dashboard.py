import streamlit as st
import pandas as pd
import yfinance as yf
import os

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
st.metric("💱 USD/KRW", f"{usdkrw:,.2f} 원")

st.markdown("---")

# =====================================
# 폴더/파일 경로 설정
# (이 파일이 위치한 폴더 기준)
# =====================================
BASE = os.path.dirname(os.path.abspath(__file__))

# 기존 구조 유지: 레포 루트 안에 RESULT / DECISION
RESULT_DIR = os.path.join(BASE, "RESULT")
DECISION_DIR = os.path.join(BASE, "DECISION")

FOLDER_MAP = {
    "DECISION (추천)": DECISION_DIR,
    "RESULT (구버전)": RESULT_DIR,
}

# =====================================
# 사이드바 - 폴더 & 파일 선택
# =====================================
folder_choice = st.sidebar.selectbox(
    "📁 폴더 선택", list(FOLDER_MAP.keys())
)
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

    # 1) SUMMARY 모드 (예전 요약용 시트)
    if "SUMMARY" in names:
        df = pd.read_excel(path, sheet_name="SUMMARY")
        req = {"티커", "시그널가격(USD)", "RSI"}
        if req.issubset(df.columns):
            return "SUMMARY", df

    # 2) 새 ODIN_AI 모드 (마스터엔진 신규 포맷)
    #    날짜, 종목명, 티커, 종가, RSI, 5일수익률, 점수, 3일확률, 5일확률, 10일확률, 판단
    raw = pd.read_excel(path, sheet_name=names[0])
    base_req = {"티커", "종가", "RSI"}
    prob_req = {"3일확률", "5일확률", "10일확률"}
    if base_req.issubset(raw.columns) and prob_req.issubset(raw.columns):
        # 새 포맷 그대로 사용
        df2 = raw.copy()
        # 종목명 컬럼 보정
        if "종목명" not in df2.columns:
            df2["종목명"] = df2["티커"]
        # 5일수익률 컬럼 없으면 0으로
        if "5일수익률" not in df2.columns:
            df2["5일수익률"] = 0.0
        # 점수 없으면 0으로
        if "점수" not in df2.columns:
            df2["점수"] = 0.0
        # 판단 없으면 기본값
        if "판단" not in df2.columns:
            df2["판단"] = "-"
        return "ODIN_AI", df2

    # 3) LEGACY 모드 (예전 단순 분석 포맷)
    if base_req.issubset(raw.columns):
        df2 = pd.DataFrame()
        df2["티커"] = raw["티커"]
        df2["종가"] = raw["종가"]
        df2["RSI"] = raw["RSI"]
        df2["종목명"] = raw["종목명"] if "종목명" in raw.columns else raw["티커"]
        df2["판단"] = raw["판단"] if "판단" in raw.columns else "-"
        df2["점수"] = raw["점수"] if "점수" in raw.columns else 0.0
        # 새 컬럼은 기본값으로 채움
        df2["5일수익률"] = raw["5일수익률"] if "5일수익률" in raw.columns else 0.0
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

# 전체 테이블 미리보기
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
# 공통 값 파싱
# =====================================
if mode == "SUMMARY":
    sig_usd = float(row["시그널가격(USD)"])
    sig_krw = float(row.get("시그널가격(KRW)", sig_usd * usdkrw))
    rsi = float(row["RSI"])
    score = float(row.get("점수", 0))
    p3 = p5 = p10 = None
    signal = row.get("등급", "-")
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
    signal = row.get("판단", "-")

# =====================================
# 판단에 따른 이모지/라벨
# =====================================
def interpret_signal(text: str):
    text = str(text)
    if "강한 매수" in text:
        return "🚀 강한 매수 구간", "매수 우위"
    if "바닥권" in text:
        return "📈 바닥권 → 분할매수 준비", "저점 매수"
    if "과열" in text:
        return "⚠️ 단기 과열 구간", "조심 구간"
    if "건드리지 말기" in text:
        return "⛔ 건드리지 말기", "관망"
    return "❔ 판단 없음", "중립"

main_label, main_sub = interpret_signal(signal)

# =====================================
# 상단 혼합형 레이아웃
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
            background: #111111aa;
        ">
            <div style="font-size: 1.4rem; font-weight: 700; margin-bottom: 0.2rem;">
                {main_label}
            </div>
            <div style="font-size: 0.95rem; opacity: 0.8;">
                {main_sub} · 엔진 + 패턴 종합 판단
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
# 가격 차트
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
st.subheader("📉 최근 가격 차트 (5일 / 5분봉)")

try:
    price, time_col = load_price(ticker)
    chart_df = price[[time_col, "Close"]].set_index(time_col)
    st.line_chart(chart_df, height=350)
except Exception:
    st.error("가격 데이터를 불러올 수 없습니다.")

# =====================================
# 전체 테이블 (정렬/필터용)
# =====================================
st.markdown("---")
st.subheader("📋 전체 종목 리스트")

st.dataframe(df, use_container_width=True)
