import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import timedelta
import plotly.graph_objects as go

# ==========================================
# 0. 전역 컬럼 정규화 함수 (RSI NAN 문제의 핵심 해결)
# ==========================================
def clean_col_name(text):
    """엑셀 컬럼명의 공백/특수문자/전각문자 제거 → 완전한 표준 컬럼명으로 변환"""
    if not isinstance(text, str):
        text = str(text)

    # 기본 공백 제거
    t = text.strip()

    # zero-width 제거
    t = (
        t.replace("\u200b", "")
        .replace("\ufeff", "")
        .replace("\xa0", "")
        .replace("\u2060", "")
        .replace("\u202a", "")
        .replace("\u202c", "")
    )

    # 전각 → 반각
    half = ""
    for c in t:
        code = ord(c)
        if 0xFF01 <= code <= 0xFF5E:
            half += chr(code - 0xFEE0)
        else:
            half += c

    return half.upper()  # 대문자로 통일 → 키 충돌 없앰


# ==========================================
# 1. Streamlit 기본 설정
# ==========================================
st.set_page_config(page_title="ODIN Dashboard", layout="wide")
st.title("⚔️ ODIN MASTER DASHBOARD — 안정 패치 3.0")


# ==========================================
# 2. 환율
# ==========================================
@st.cache_data(ttl=300)
def get_usdkrw():
    try:
        df = yf.download("USDKRW=X", period="1d", interval="1m", progress=False)
        return float(df["Close"].iloc[-1])
    except:
        return 1400.0

usdkrw = get_usdkrw()
try:
    usdkrw = float(usdkrw)
except:
    usdkrw = 1400.0

st.sidebar.metric("💱 USD/KRW", f"{usdkrw:,.2f} 원")


# ==========================================
# 3. 폴더 선택
# ==========================================
BASE = os.path.dirname(os.path.abspath(__file__))
DECISION_DIR = os.path.join(BASE, "DECISION")
RESULT_DIR = os.path.join(BASE, "RESULT")

FOLDER_MAP = {
    "DECISION (추천)": DECISION_DIR,
    "RESULT (이전 기록)": RESULT_DIR,
}

folder_choice = st.sidebar.selectbox("📁 폴더 선택", list(FOLDER_MAP.keys()))
TARGET_DIR = FOLDER_MAP[folder_choice]

files = sorted(
    [f for f in os.listdir(TARGET_DIR) if f.endswith(".xlsx")],
    reverse=True,
)
file_sel = st.selectbox("📄 분석 파일 선택", files)
file_path = os.path.join(TARGET_DIR, file_sel)


# ==========================================
# 4. 파일 로드 + 컬럼 정규화
# ==========================================
def load_excel_clean(path):
    x = pd.ExcelFile(path)
    sheet = x.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")

    # 컬럼명 정규화 (핵심)
    df.columns = [clean_col_name(c) for c in df.columns]

    return df

df = load_excel_clean(file_path)

st.success("📌 파일 구조 인식 성공 — Zero-Width 제거 완료")
st.dataframe(df, use_container_width=True)


# ==========================================
# 5. 종목 선택
# ==========================================
if "종목명" in df.columns:
    name_list = df["종목명"].tolist()
else:
    name_list = df["티커"].tolist() if "티커" in df.columns else df.iloc[:, 0].tolist()

ticker_list = df["티커"].tolist()
mapping = dict(zip(name_list, ticker_list))

selected_name = st.sidebar.selectbox("종목 선택", name_list)
ticker = mapping[selected_name]

row = df[df["티커"] == ticker].iloc[0]


# ==========================================
# 6. 값 파싱 (정규화된 컬럼으로 100% 안정)
# ==========================================
def getf(key, default=0.0):
    return float(row[key]) if key in row and pd.notna(row[key]) else default

# RSI 문제 해결 부분
rsi = getf("RSI", 0.0)
score = getf("점수", 0.0)
sig_usd = getf("종가", 0.0)
sig_krw = sig_usd * usdkrw
ret5 = getf("5일수익률", None)

p3 = getf("3일확률", None)
p5 = getf("5일확률", None)
p10 = getf("10일확률", None)

decision_raw = row["판단"] if "판단" in row else "-"


# ==========================================
# 7. 자동 판단 보완
# ==========================================
def auto_signal(rsi, score):
    if score >= 80: return "🚀 강한 매수"
    if score >= 60: return "📈 매수 우위"
    if rsi < 25: return "📉 바닥권"
    if rsi < 35: return "💡 저점 관찰"
    if rsi > 80: return "⛔ 과열 정점"
    if rsi > 70: return "⚠️ 단기 과열"
    return "⏳ 관망"

if decision_raw in ["", "-", None]:
    decision = auto_signal(rsi, score)
else:
    decision = decision_raw


# ==========================================
# 8. 판단 카드
# ==========================================
st.markdown("---")
st.subheader(f"📊 {selected_name} — 최종 판단")

st.markdown(
    f"""
    <div style="padding: 1rem; border-radius: 15px; background-color:#F7F9FC;">
        <h3 style="margin:0;">{decision}</h3>
        <p style="opacity:0.7;">엔진 + 패턴 + ML 종합 판단</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ==========================================
# 9. 기술 지표 요약 (RSI/점수 정상 출력)
# ==========================================
st.subheader("💡 기술 / 심리 요약")

c1, c2, c3, c4 = st.columns(4)
c1.metric("RSI", f"{rsi:.1f}")
c2.metric("기술 점수", f"{score:.0f} / 100")
c3.metric("시그널가 ($)", f"{sig_usd:,.2f}")
c4.metric("시그널가 (₩)", f"{sig_krw:,.0f}")

if ret5 is not None:
    st.metric("최근 5일 수익률", f"{ret5:.2f} %")


# ==========================================
# 10. ML 확률
# ==========================================
st.subheader("📈 ML 상승 확률 (3/5/10일)")

if p3 is not None:
    dfp = pd.DataFrame(
        {"기간": ["3일", "5일", "10일"], "상승확률": [p3, p5, p10]}
    ).set_index("기간")
    st.bar_chart(dfp)

else:
    st.info("ML 확률 데이터가 없는 파일입니다.")


# ==========================================
# 11. 가격 차트 — 최근 3시간 / 5분봉 + 10분 눈금 (안정화)
# ==========================================
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

    # 시간 컬럼 찾기
    time_col = "Datetime" if "Datetime" in price.columns else price.columns[0]
    price[time_col] = pd.to_datetime(price[time_col], errors="coerce")

    # 최근 3시간 필터
    cutoff = price[time_col].max() - timedelta(hours=3)
    recent = price[price[time_col] >= cutoff]

    # KRW 변환
    recent["Close_KRW"] = recent["Close"] * usdkrw

    # TP / SL
    tp = sig_krw * 1.03
    sl = sig_krw * 0.97

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=recent[time_col],
            y=recent["Close_KRW"],
            mode="lines",
            line=dict(color="blue", width=2),
            name="Price (KRW)"
        )
    )

    fig.add_hline(y=tp, line=dict(color="green", dash="dash"), annotation_text="TP")
    fig.add_hline(y=sl, line=dict(color="red", dash="dash"), annotation_text="SL")

    # 10분 눈금
    fig.update_xaxes(dtick=600000, tickformat="%H:%M")
    fig.update_layout(height=400)

    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error("차트 로딩 실패")
    st.write(e)


# ==========================================
# 12. 전체 데이터 테이블
# ==========================================
st.markdown("---")
st.subheader("📋 전체 데이터")
st.dataframe(df, use_container_width=True)
