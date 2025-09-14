# app.py — 사주명리코치 루아 (교재 규칙 버전: 입춘/절입일/야자·조자시/시두법)
import os
import streamlit as st
import pandas as pd
import google.generativeai as genai
from saju_rules import get_pillars_by_textbook_rules, five_element_counts

st.set_page_config(page_title="사주명리코치 루아", page_icon="🔮")
st.title("🔮 사주명리코치 루아")
st.markdown("---")

# ===== 사이드바(비용/모델) =====
STYLE_TO_MAXTOK = {"짧게(≈150자)": 220, "보통(≈300자)": 420}
with st.sidebar:
    st.header("설정")
    resp_style = st.radio("응답 길이", list(STYLE_TO_MAXTOK.keys()), index=0)
    engine = st.selectbox("엔진", ["Gemini(권장/저렴)", "Mock(오프라인)"], index=1)
    st.caption("Gemini 키가 없으면 자동으로 Mock으로 동작합니다.")

# ===== 2시간대 목록(한국표준 +30분 적용) =====
SLOTS = [
    ("23:30–01:30 (子)", 0, 30),
    ("01:30–03:30 (丑)", 2, 30),
    ("03:30–05:30 (寅)", 4, 30),
    ("05:30–07:30 (卯)", 6, 30),
    ("07:30–09:30 (辰)", 8, 30),
    ("09:30–11:30 (巳)",10, 30),
    ("11:30–13:30 (午)",12, 30),
    ("13:30–15:30 (未)",14, 30),
    ("15:30–17:30 (申)",16, 30),
    ("17:30–19:30 (酉)",18, 30),
    ("19:30–21:30 (戌)",20, 30),
    ("21:30–23:30 (亥)",22, 30),
]

# ===== Gemini 준비 (없으면 예외 → Mock) =====
def init_gemini():
    key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key: raise RuntimeError("GOOGLE_API_KEY 없음")
    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        generation_config={"max_output_tokens": STYLE_TO_MAXTOK[resp_style], "temperature":0.6},
        system_instruction=("당신은 사주 기반 코치입니다. 한국어로 간결하게, 리스트는 최대 3개, 중복/군더더기 금지.")
    )
    return model.start_chat(history=[])

# ===== 세션 =====
if "chat" not in st.session_state: st.session_state.chat = None
if "pillars" not in st.session_state: st.session_state.pillars = None
if "five" not in st.session_state: st.session_state.five = None
if "messages" not in st.session_state: st.session_state.messages = []

# ===== 입력 폼 =====
with st.form(key="saju_form_v2"):
    st.write("먼저 생년월일과 **2시간대**를 선택하세요. (교재 규칙만 사용)")
    c1,c2,c3 = st.columns(3)
    y = c1.number_input("연도", 1901, 2099, 1971)
    m = c2.number_input("월", 1, 12, 7)
    d = c3.number_input("일", 1, 31, 7)
    slot_label = st.selectbox("시간대(한국표준 +30분 적용)", [s[0] for s in SLOTS], index=11)  # 亥
    ok = st.form_submit_button("만세력 확인하기")

if ok:
    hh, mm = next((h,mn) for label,h,mn in SLOTS if label == slot_label)
    pillars = get_pillars_by_textbook_rules(int(y), int(m), int(d), int(hh), int(mm))
    st.session_state.pillars = pillars
    st.session_state.five = five_element_counts(pillars.year, pillars.month, pillars.day, pillars.hour)

    # Intro 메시지
    intro = (
        f"[만세력]\n{pillars.year}년 {pillars.month}월 {pillars.day}일 {pillars.hour}시\n"
        f"({pillars.note})\n\n"
        "이 사주의 큰 흐름을 3줄로 요약하고, 다음 질문 하나를 제안하세요."
    )
    # 대화 모델 선택
    use_gemini = False
    if engine.startswith("Gemini"):
        try:
            if not st.session_state.chat:
                st.session_state.chat = init_gemini()
            res = st.session_state.chat.send_message(intro)
            st.session_state.messages = [{"role":"assistant","content":res.text}]
            use_gemini = True
        except Exception as e:
            st.warning(f"Gemini 초기화/호출 실패: {e} → Mock으로 전환")
    if not use_gemini:
        mock = (
            f"사주요약: {pillars.year}·{pillars.month}·{pillars.day}·{pillars.hour}\n"
            "- 현재 장단점 각 1개\n- 이번 주 실행 1가지\n- 다음 질문 1개"
        )
        st.session_state.messages = [{"role":"assistant","content":mock}]
    st.experimental_rerun()

# ===== 결과/오행 표시 =====
if st.session_state.pillars:
    p = st.session_state.pillars
    st.success(f"만세력: {p.year}년 {p.month}월 {p.day}일 {p.hour}시")
    st.caption(p.note + " · 규칙: 입춘/절입일/야·조자시/시두법")

    if st.session_state.five:
        col1, col2 = st.columns([2,1])
        with col1:
            st.bar_chart(pd.DataFrame.from_dict(st.session_state.five, orient="index", columns=["개수"]))
        with col2:
            top = max(st.session_state.five, key=st.session_state.five.get)
            st.info(f"가장 많은 오행: **{top}**\n\n{st.session_state.five}")

# ===== 대화 =====
if st.session_state.messages:
    for m in st.session_state.messages[-10:]:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if q := st.chat_input("질문을 입력하세요 (짧을수록 저렴)"):
        with st.chat_message("user"): st.markdown(q)
        if st.session_state.chat:
            try:
                res = st.session_state.chat.send_message(
                    f"[만세력]\n{st.session_state.pillars.year}년 {st.session_state.pillars.month}월 "
                    f"{st.session_state.pillars.day}일 {st.session_state.pillars.hour}시\n\n[질문]\n{q}"
                )
                out = res.text
            except Exception as e:
                st.warning(f"Gemini 오류: {e} → Mock으로 전환")
                out = "핵심 3줄 요약 + 실행 1가지 + 다음 질문 1개"
                st.session_state.chat = None
        else:
            out = "핵심 3줄 요약 + 실행 1가지 + 다음 질문 1개"
        with st.chat_message("assistant"): st.markdown(out)
        st.session_state.messages.append({"role":"user","content":q})
        st.session_state.messages.append({"role":"assistant","content":out})
