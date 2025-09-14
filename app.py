# app.py 
import streamlit as st
from datetime import date
import pandas as pd
from saju_rules import get_pillars, five_element_counts

st.set_page_config(page_title="사주명리코치 루아", page_icon="🔮")
st.title("🔮 사주명리코치 루아")

# ─────────────────────────────────────────
# 1) KASI API 키 (Secrets)
# ─────────────────────────────────────────
 API_KEY = st.secrets.get("DATA_GO_KR_KEY")
 if not API_KEY:
     st.error("DATA_GO_KR_KEY 가 없습니다. Streamlit Cloud → Settings → Secrets 에 추가하세요.")
     st.stop()
+
+# 같은 입력에 대해 24시간 캐시
+@st.cache_data(ttl=60*60*24, show_spinner=False)
+def _pillars_cached(y, m, d, hh, mm, key):
+    return get_pillars(y, m, d, hh, mm, key)

# ─────────────────────────────────────────
# 2) 입력 UI (양력 + 2시간대)
#    교재 규칙: +30분 보정. 표시도 보정된 구간으로 안내.
#    자시는 야/조를 분리해 정확도를 높였습니다.
# ─────────────────────────────────────────
today = date.today()
col1, col2, col3 = st.columns(3)
y = col1.number_input("연도", min_value=1900, max_value=today.year, value=2000, step=1)
m = col2.number_input("월", min_value=1, max_value=12, value=1, step=1)
d = col3.number_input("일", min_value=1, max_value=31, value=1, step=1)

st.caption("시간대는 한국표준시 +30분 보정을 적용합니다.")

choices = [
    ("23:30–00:30 (子·야자)", 23, 40),  # 대표값(계산용)만 사용
    ("00:30–01:30 (子·조자)", 0, 40),
    ("01:30–03:30 (丑)", 2, 30),
    ("03:30–05:30 (寅)", 4, 30),
    ("05:30–07:30 (卯)", 6, 30),
    ("07:30–09:30 (辰)", 8, 30),
    ("09:30–11:30 (巳)", 10, 30),
    ("11:30–13:30 (午)", 12, 30),
    ("13:30–15:30 (未)", 14, 30),
    ("15:30–17:30 (申)", 16, 30),
    ("17:30–19:30 (酉)", 18, 30),
    ("19:30–21:30 (戌)", 20, 30),
    ("21:30–23:30 (亥)", 22, 30),
]
label_to_hm = {lab:(hh,mm) for lab,hh,mm in choices}
time_label = st.selectbox("시간대", [c[0] for c in choices], index=5)

if st.button("만세력 확인하기"):
    try:
        hh, mm = label_to_hm[time_label]
        pillars = _pillars_cached(int(y), int(m), int(d), hh, mm, API_KEY)
        # 표시
        st.success(f"{pillars['year_gz']}년 {pillars['month_gz']}월 {pillars['day_gz']}일 {pillars['time_gz']}시")
        if pillars["time_gz"].endswith("子"):
            st.caption("자시 판정: " + ("야자(전날 23~24시대)" if pillars["is_ya"] else "조자(당일 00~01시대)"))

        # 오행 카운트
        cnt = five_element_counts(pillars)
        df = pd.DataFrame({"오행": list(cnt.keys()), "개수": list(cnt.values())}).set_index("오행")
        st.bar_chart(df)
        biggest = df["개수"].idxmax()
        st.info(f"가장 많은 오행: {biggest}")
    except Exception as e:
        st.error(f"오류: {e}")

