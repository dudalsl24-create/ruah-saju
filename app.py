# app.py — 사주명리코치 루아 (sajupy 우선 사용 + 만세력 확인 + 오행 차트 + Gemini/Mock)
import os
import re
import datetime
import streamlit as st
import google.generativeai as genai
import pandas as pd

# -------------------- 기본 UI 설정 --------------------
st.set_page_config(page_title="사주명리코치 루아", page_icon="🔮")
st.title("🔮 사주명리코치 루아")
st.markdown("---")

# -------------------- 비용/모델 설정 --------------------
STYLE_TO_MAXTOK = {"짧게(≈150자)": 220, "보통(≈300자)": 420}
SYS_KO = (
    "당신은 사주 기반 코치입니다. 한국어로, 군더더기 없이 핵심만 말하세요. "
    "리스트는 최대 3개, 문장은 짧게. 불필요한 인사/중복 금지."
)

with st.sidebar:
    st.header("설정")
    resp_style = st.radio("응답 길이", list(STYLE_TO_MAXTOK.keys()), index=0)
    prefer_engine = st.selectbox("엔진", ["Gemini(권장/저렴)", "Mock(오프라인)"], index=0)
    st.caption("짧게일수록 토큰/비용 절약 👍")

# -------------------- sajupy 자동 감지 --------------------
USE_SAJUPY = False
try:
    from sajupy.saju import get_saju_str as sj_get_saju_str  # pip로 설치됨 (requirements.txt)
    USE_SAJUPY = True
except Exception:
    USE_SAJUPY = False

SAJU_ENGINE = "sajupy" if USE_SAJUPY else "fallback"

# -------------------- 만세력 파싱/오행 계산 --------------------
CHEONGAN = {'甲':'목','乙':'목','丙':'화','丁':'화','戊':'토','己':'토','庚':'금','辛':'금','壬':'수','癸':'수'}
JIJI     = {'子':'수','丑':'토','寅':'목','卯':'목','辰':'토','巳':'화','午':'화','未':'토','申':'금','酉':'금','戌':'토','亥':'수'}

def parse_ganji_4pillars(saju_text:str):
    """
    예: '己亥년 丙子월 庚辰일 丁亥시' → ('己亥','丙子','庚辰','丁亥')
    """
    m = re.search(r'([\u4E00-\u9FFF]{2})년\s+([\u4E00-\u9FFF]{2})월\s+([\u4E00-\u9FFF]{2})일\s+([\u4E00-\u9FFF]{2})시', saju_text)
    if not m:
        return ("","","","")
    return m.group(1), m.group(2), m.group(3), m.group(4)

def count_five_elements(gy, gm, gd, gt):
    counts = {"목":0,"화":0,"토":0,"금":0,"수":0}
    for p in [gy, gm, gd, gt]:
        if not p: continue
        tg, dz = p[0], p[1]
        if tg in CHEONGAN: counts[CHEONGAN[tg]] += 1
        if dz in JIJI:     counts[JIJI[dz]]     += 1
    return counts

def compute_and_store_saju(y, m, d, h, gender, is_lunar):
    """
    sajupy가 설치되어 있으면 sj_get_saju_str 사용.
    결과를 session_state에 저장해서 UI에서 바로 사용.
    """
    try:
        if USE_SAJUPY:
            saju_text = sj_get_saju_str(y, m, d, h, gender, is_lunar)
        else:
            raise RuntimeError("sajupy가 설치되어 있지 않습니다.")
    except Exception as e:
        cal = "음력" if is_lunar else "양력"
        st.session_state.initial_saju = f"{cal} {y}-{m:02d}-{d:02d} {h:02d}시 / 성별:{'남' if '남' in gender else '여'} (계산 실패: {e})"
        st.session_state.ganji = ("","","","")
        st.session_state.five = None
        st.session_state.saju_engine = SAJU_ENGINE
        return

    gy, gm, gd, gt = parse_ganji_4pillars(saju_text)
    st.session_state.initial_saju = saju_text
    st.session_state.ganji = (gy, gm, gd, gt)
    st.session_state.five = count_five_elements(gy, gm, gd, gt)
    st.session_state.saju_engine = SAJU_ENGINE

# -------------------- Gemini 초기화 (키 없으면 Mock 폴백) --------------------
def init_gemini():
    key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY가 없습니다. Streamlit Secrets에 추가하세요.")
    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        system_instruction=SYS_KO,
        generation_config={"max_output_tokens": STYLE_TO_MAXTOK[resp_style], "temperature": 0.6}
    )
    return model.start_chat(history=[])

def mock_reply(prompt, initial_saju=""):
    head = f"사주요약: {initial_saju}\n" if initial_saju else ""
    body = (
        "핵심 조언 3가지\n"
        "1) 일일 루틴 1개 정착(수면/식사/운동 중 택1)\n"
        "2) 이번 주 목표 1가지를 수치로 정의\n"
        "3) 다음 질문을 구체화(예: 직장 스트레스 대처 3가지)"
    )
    return head + body

# -------------------- 세션 초기화 --------------------
if "chat" not in st.session_state: st.session_state.chat = None
if "initial_saju" not in st.session_state: st.session_state.initial_saju = ""
if "ganji" not in st.session_state: st.session_state.ganji = ("","","","")
if "five" not in st.session_state: st.session_state.five = None
if "messages" not in st.session_state: st.session_state.messages = []

# -------------------- 엔진 준비 --------------------
if prefer_engine.startswith("Gemini"):
    try:
        if not st.session_state.chat:
            st.session_state.chat = init_gemini()
        ai_type = "gemini"
    except Exception as e:
        st.warning(f"Gemini 초기화 실패: {e} → Mock으로 전환합니다.")
        ai_type = "mock"
else:
    ai_type = "mock"

# -------------------- 상단 상태 표시(만세력 + 오행) --------------------
if st.session_state.initial_saju:
    st.success(f"만세력: {st.session_state.initial_saju}")
    st.caption(f"계산 엔진: {st.session_state.get('saju_engine','-')}")
    if st.session_state.five:
        col1, col2 = st.columns([2,1])
        with col1:
            st.bar_chart(pd.DataFrame.from_dict(st.session_state.five, orient="index", columns=["개수"]))
        with col2:
            dom = max(st.session_state.five, key=st.session_state.five.get)
            st.info(f"가장 많은 오행: **{dom}**\n\n{st.session_state.five}")

# -------------------- 입력 폼(딱 1개만, 고유 key 사용) --------------------
with st.form(key="saju_form_v1", clear_on_submit=False):
    st.write("먼저 생년월일시를 입력하세요 (1971-07-07 해시 테스트 가능)")
    cal = st.radio("달력", ["양력","음력"], horizontal=True, index=0)
    is_lunar = (cal == "음력")
    today = datetime.datetime.now()
    c1,c2,c3 = st.columns(3)
    with c1: y = st.number_input("연도", 1901, today.year-1, 1971)
    with c2: m = st.number_input("월", 1, 12, 7)
    with c3: d = st.number_input("일", 1, 31, 7)
    c4,c5 = st.columns(2)
    with c4: h = st.selectbox("시간", list(range(24)), index=21, format_func=lambda x:f"{x:02d}시")
    with c5: gender = st.radio("성별", ["남","여"], horizontal=True, index=0)
    ok = st.form_submit_button("만세력 확인하기")

if ok:
    gender_map = "남자" if gender == "남" else "여자"
    compute_and_store_saju(int(y), int(m), int(d), int(h), gender_map, bool(is_lunar))
    # 초기 안내 한 번
    intro = (
        f"[사주 데이터]\n{st.session_state.initial_saju}\n\n"
        "이 사주의 큰 흐름을 3줄로 요약하고, 다음 질문 한 가지를 제안하세요."
    )
    if ai_type == "gemini":
        try:
            res = st.session_state.chat.send_message(intro)
            st.session_state.messages = [{"role":"assistant","content":res.text}]
        except Exception as e:
            st.warning(f"Gemini 호출 오류: {e} → Mock으로 전환")
            st.session_state.messages = [{"role":"assistant","content":mock_reply(intro, st.session_state.initial_saju)}]
            ai_type = "mock"
    else:
        st.session_state.messages = [{"role":"assistant","content":mock_reply(intro, st.session_state.initial_saju)}]
    st.rerun()

# -------------------- 대화 영역 --------------------
if st.session_state.messages:
    for m in st.session_state.messages[-10:]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if prompt := st.chat_input("질문을 입력하세요 (짧을수록 저렴)"):
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.markdown(prompt)
        q = f"[사주 데이터]\n{st.session_state.initial_saju}\n\n[질문]\n{prompt}"
        if ai_type == "gemini":
            try:
                res = st.session_state.chat.send_message(q)
                out = res.text
            except Exception as e:
                st.warning(f"Gemini 호출 오류: {e} → Mock으로 임시 전환")
                out = mock_reply(prompt, st.session_state.initial_saju)
                st.session_state.chat = None
                ai_type = "mock"
        else:
            out = mock_reply(prompt, st.session_state.initial_saju)
        with st.chat_message("assistant"):
            st.markdown(out)
        st.session_state.messages.append({"role":"assistant","content":out})
