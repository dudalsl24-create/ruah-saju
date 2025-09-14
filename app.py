# app.py  — 외부 API 없이 ‘교재 규칙’으로만 4주 계산
import streamlit as st
from datetime import date
from saju_rules import get_pillars, five_element_counts

st.set_page_config(page_title="사주명리코치 루아", page_icon="🔮")
st.title("🔮 사주명리코치 루아")

st.caption("절입일·+30분 보정·야/조자시 규칙을 적용합니다. (음력 입력 미지원)")

# ── 입력 UI (양력 + 2시간대)
today = date.today()
c1, c2, c3 = st.columns(3)
y = c1.number_input("연도", 1900, today.year, 2000)
m = c2.number_input("월", 1, 12, 1)
d = c3.number_input("일", 1, 31, 1)

choices = [
    ("23:30–00:30 (子·야자)", 23, 40),
    ("00:30–01:30 (子·조자)", 0, 40),
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
label2hm = {lab:(hh,mm) for lab,hh,mm in choices}
time_label = st.selectbox("시간대", [x[0] for x in choices], index=5)

if st.button("만세력 확인하기"):
    try:
        hh, mm = label2hm[time_label]
        pillars = get_pillars(int(y), int(m), int(d), hh, mm, is_lunar=False)

        line = f"{pillars['year_gz']}년 {pillars['month_gz']}월 {pillars['day_gz']}일 {pillars['time_gz']}시"
        st.success(line)
        if pillars["time_gz"].endswith("子"):
            st.caption("자시 판정: " + ("야자(전날 子)" if pillars["is_ya"] else "조자(당일 子)"))

        cnt = five_element_counts(pillars)
        st.bar_chart(cnt)
        main_elem = max(cnt, key=cnt.get)
        st.info(f"가장 많은 오행: {main_elem}")

    except Exception as e:
        st.error(f"오류: {e}")
