# app.py 대화형 챗봇 업그레이드 코드
import streamlit as st
import google.generativeai as genai
import sajupy
import datetime

# --- 초기 설정 ---
# Gemini API 키 설정
try:
    # Streamlit의 secrets 관리 기능을 사용하면 더 안전합니다.
    # genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    # 직접 입력 방식: "YOUR_API_KEY"를 실제 키로 바꾸세요.
    genai.configure(api_key="AIzaSyBs9wVnliIm0g5fnOnNc1aqtUY_h5F-O5A")
except Exception as e:
    pass

# --- 핵심 기능 및 AI 설정 ---
# AI 모델 설정
model = genai.GenerativeModel('gemini-1.5-flash')

# 대화 시작을 위한 초기 프롬프트 생성 함수
def get_initial_prompt(year, month, day, hour, gender, is_lunar):
    try:
        saju_info = sajupy.get_saju(year, month, day, hour, gender, is_lunar)
        prompt = f"""
        당신은 사주를 통해 인생 코칭을 해주는 지혜로운 멘토입니다.
        이제부터 당신은 아래 사주 정보를 가진 사람과 대화를 시작하게 됩니다.
        먼저 이 사람의 사주를 간략하게 전체적으로 설명해주고, 무엇이든 궁금한 점을 질문하라고 말하며 대화를 시작해주세요.

        [분석할 사주 데이터]
        {saju_info}
        """
        return prompt
    except Exception as e:
        st.error(f"사주 정보를 계산하는 중 오류가 발생했습니다: {e}")
        return None

# --- Streamlit 웹 화면 구성 ---
st.set_page_config(page_title="나의 사주 챗봇 ✨", page_icon="🔮")
st.title("🔮 Gemini 사주 챗봇과 대화하기")
st.markdown("---")

# 세션 상태(메모리) 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "saju_info_provided" not in st.session_state:
    st.session_state.saju_info_provided = False

# 1. 사주 정보 입력 (아직 입력되지 않았을 경우)
if not st.session_state.saju_info_provided:
    with st.form("saju_form"):
        st.write("#### 먼저, 당신의 생년월일시를 알려주세요")
        # (기존 입력 폼과 동일)
        cal_type = st.radio("달력 종류", ('양력', '음력'), horizontal=True)
        is_lunar_input = (cal_type == '음력')
        today = datetime.datetime.now()
        col1, col2, col3 = st.columns(3)
        with col1: year_input = st.number_input("태어난 연도", 1930, today.year, 2000)
        with col2: month_input = st.number_input("태어난 월", 1, 12, 1)
        with col3: day_input = st.number_input("태어난 일", 1, 31, 1)
        col4, col5 = st.columns(2)
        with col4: hour_input = st.selectbox("태어난 시간", list(range(24)), 12, format_func=lambda x: f"{x:02d} 시")
        with col5: gender_input = st.radio("성별", ("남", '여'), horizontal=True)

        submitted = st.form_submit_button("사주 정보로 대화 시작하기 🚀")

    if submitted:
        gender_map = "남자" if gender_input == "남" else "여자"
        initial_prompt = get_initial_prompt(year_input, month_input, day_input, hour_input, gender_map, is_lunar_input)
        
        if initial_prompt:
            # 대화 시작
            chat = model.start_chat(history=[])
            with st.spinner("AI 챗봇이 당신과의 대화를 준비하고 있습니다..."):
                response = chat.send_message(initial_prompt)
                st.session_state.chat = chat
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.session_state.saju_info_provided = True
                st.rerun() # 화면을 새로고침하여 채팅 UI를 보여줌

# 2. 채팅 UI (사주 정보가 입력된 후)
else:
    # 이전 대화 내용 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 사용자 입력
    if prompt := st.chat_input("사주에 대해 궁금한 점을 물어보세요"):
        # 사용자 메시지 저장 및 표시
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AI 응답
        with st.chat_message("assistant"):
            with st.spinner("AI가 답변을 생각하고 있어요..."):
                response = st.session_state.chat.send_message(prompt)
                st.markdown(response.text)
        
        # AI 메시지 저장
        st.session_state.messages.append({"role": "assistant", "content": response.text})