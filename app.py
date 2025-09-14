# app.py 진짜 최종 완성 코드 (sajupy 함수 이름 오류 수정)
import streamlit as st
import google.generativeai as genai
import sajupy
import datetime

# --- 초기 설정 ---
# Gemini API 키 설정 (Streamlit Cloud 배포 버전)
# Streamlit의 'Secrets'에 저장된 키를 안전하게 불러옵니다.
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    # Secrets 설정이 안 되어 있을 경우, 화면에 안내 메시지를 표시합니다.
    st.error("오류: Streamlit Cloud의 Secrets에 GOOGLE_API_KEY가 설정되지 않았습니다.")
    pass

# --- 핵심 기능 및 AI 설정 ---
# AI 모델 설정
model = genai.GenerativeModel('gemini-1.5-flash')

# 대화 시작을 위한 초기 프롬프트 생성 함수
def get_initial_prompt(year, month, day, hour, gender, is_lunar):
    try:
        # sajupy의 정확한 함수 이름인 get_saju_str로 수정!
        saju_info = sajupy.get_saju_str(year, month, day, hour, gender, is_lunar)
        prompt = f"""
        당신은 사주를 통해 인생 코칭을 해주는 지혜로운 멘토입니다.
        이제부터 당신은 아래 사주 정보를 가진 사람과 대화를 시작하게 됩니다.
        먼저 이 사람의 사주를 간략하게 전체적으로 설명해주고, 무엇이든 궁금한 점을 질문하라고 말하며 대화를 시작해주세요.

        [분석할 사주 데이터]
        {saju_info}
        """
        return prompt
    except Exception as e:
        # 오류 메시지를 st.error로 화면에 표시
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
            chat = model.start_chat(history=[])
            with st.spinner("AI 챗봇이 당신과의 대화를 준비하고 있습니다..."):
                response = chat.send_message(initial_prompt)
                st.session_state.chat = chat
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.session_state.saju_info_provided = True
                st.rerun()

# 2. 채팅 UI (사주 정보가 입력된 후)
else:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("사주에 대해 궁금한 점을 물어보세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("AI가 답변을 생각하고 있어요..."):
                response = st.session_state.chat.send_message(prompt)
                st.markdown(response.text)
        
        st.session_state.messages.append({"role": "assistant", "content": response.text})
