# app.py — 사주명리코치 루아 (간결 UI, 2시간대 선택, rerun 수정)
import os
import streamlit as st
import pandas as pd
import google.generativeai as genai
from saju_rules import get_pillars_by_textbook_rules, five_element_counts

st.set_page_config(page_title="사주명리코치 루아", page_icon="🔮")
st.title("🔮 사주명리코치 루아")
st.markdown("---")

# 사이드바 (필요 최소)
STYLE_TO_MAXTOK = {"짧게(≈150자)": 220, "보통(≈300자)": 420}
with st.sidebar:
    resp_style = st.radio("응답 길이", list(STYLE_TO_MAXTOK.keys()), index=0)
    engine = st.selectbox("엔진", ["Mock", "Gemini"], index=0)

# 2시간대(표준시 경계 +30분)
SLOTS = [
    ("23:30–01:30 (子)", 0, 30),  ("01:30–03:30 (丑)", 2, 30),
    ("03:30–05:30 (寅)", 4, 30),  ("05:30–07:30 (卯)", 6, 30),
    ("07:30–09:30 (辰)", 8, 30),  ("09:30–11:30 (巳)",10, 30),
    ("11:30–13:30 (午)",12, 30),  ("13:30–15:30 (未)",14, 30),
    ("15:30–17:30 (申)",16, 30),  ("17:30–19:30 (酉)",18, 30),
    ("19:30–21:30 (戌)",20, 30),  ("21:30–23:30 (亥)",22, 30),
]

def init_gemini():
    key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key: raise RuntimeError("GOOGLE_API_KEY 없음")
    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        generation_config={"max_output_tokens": STYLE_TO_MAXTOK[resp_style], "temperature":0.6},
        system_instruction="한국어로 간결하게, 핵심만. 목록 최대 3개."
    )
    return model.start_chat(history=[])

# 세션
if "chat" not in st.session_state: st.session_state.chat = None
if "pillars" not in st.session_state: st.session_state.pillars = None
if "five" not in st.session_state: st.session_state.five = None
if "messages" not in st.session_state: st.session_state.messages = []

# 입력 폼
with st.form(key="saju_form_v2"):
    st.write("생년월일과 시간대를 선택하세요.")
    c1,c2,c3 = st.columns(3)
    y = c1.number_input("연도", 1901, 2099, 1971)
    m = c2.number_input("월", 1, 12, 7)
    d = c3.number_input("일", 1, 31, 7)
    slot_label = st.selectbox("시간대", [s[0] for s in SLOTS], index=11)  # 亥
    ok = st.form_submit_button("만세력 확인하기")

if ok:
    hh, mm = next((h,mn) for label,h,mn in SLOTS if label == slot_label)
    p = get_pillars_by_textbook_rules(int(y), int(m), int(d), int(hh), int(mm))
    st.session_state.pillars = p
    st.session_state.five = five_element_counts(p.year, p.month, p.day, p.hour)

    intro = f"{p.year}년 {p.month}월 {p.day}일 {p.hour}시 / {p.note}\n" \
            f"큰 흐름 3줄, 실행 1가지, 다음 질문 1개."
    if engine == "Gemini":
        try:
            if not st.session_state.chat:
                st.session_state.chat = init_gemini()
            res = st.session_state.chat.send_message(intro)
            st.session_state.messages = [{"role":"assistant","content":res.text}]
        except Exception:
            st.session_state.chat = None
            st.session_state.messages = [{"role":"assistant","content":"요약 3줄·실행 1·다음 질문 1"}]
    else:
        st.session_state.messages = [{"role":"assistant","content":"요약 3줄·실행 1·다음 질문 1"}]

    st.rerun()

# 결과
if st.session_state.pillars:
    p = st.session_state.pillars
    st.success(f"{p.year}년 {p.month}월 {p.day}일 {p.hour}시")
    st.caption(p.note)   # 필요 없으면 이 줄 삭제

    if st.session_state.five:
        col1, col2 = st.columns([2,1])
        with col1:
            st.bar_chart(pd.DataFrame.from_dict(st.session_state.five, orient="index", columns=["개수"]))
        with col2:
            top = max(st.session_state.five, key=st.session_state.five.get)
            st.info(f"가장 많은 오행: **{top}**")

# 대화
if st.session_state.messages:
    for m in st.session_state.messages[-10:]:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if q := st.chat_input("질문 입력"):
        with st.chat_message("user"): st.markdown(q)
        if st.session_state.chat:
            try:
                res = st.session_state.chat.send_message(
                    f"{st.session_state.pillars.year}년 {st.session_state.pillars.month}월 "
                    f"{st.session_state.pillars.day}일 {st.session_state.pillars.hour}시\n{q}"
                )
                out = res.text
            except Exception:
                st.session_state.chat = None
                out = "요약 3줄·실행 1·다음 질문 1"
        else:
            out = "요약 3줄·실행 1·다음 질문 1"
        with st.chat_message("assistant"): st.markdown(out)
        st.session_state.messages.append({"role":"user","content":q})
        st.session_state.messages.append({"role":"assistant","content":out})
