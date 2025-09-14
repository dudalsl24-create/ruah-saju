# app.py — 사주 챗봇 + 만세력 변환 블록 내장 + 루아 /Mock
import streamlit as st
st.set_page_config(page_title="사주명리코치 루아", page_icon="🔮")

import os, io, gzip, datetime, pathlib, re
import google.generativeai as genai

# === sajupy 자동 감지 ===
USE_SAJUPY = False
try:
    from sajupy.saju import get_saju_str as sj_get_saju_str
    USE_SAJUPY = True
except Exception:
    USE_SAJUPY = False

SAJU_ENGINE = "sajupy" if USE_SAJUPY else "fallback"

# === 만세력 파싱/오행 계산 ===
import re

CHEONGAN = {'甲':'목','乙':'목','丙':'화','丁':'화','戊':'토','己':'토','庚':'금','辛':'금','壬':'수','癸':'수'}
JIJI     = {'子':'수','丑':'토','寅':'목','卯':'목','辰':'토','巳':'화','午':'화','未':'토','申':'금','酉':'금','戌':'토','亥':'수'}

def parse_ganji_4pillars(saju_text:str):
    # 예: "己亥년 丙子월 庚辰일 丁丑시" → ('己亥','丙子','庚辰','丁丑')
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
    결과를 session_state에 저장해서 UI에서 바로 표시.
    """
    try:
        if USE_SAJUPY:
            saju_text = sj_get_saju_str(y, m, d, h, gender, is_lunar)
        else:
            # 내부 변환 함수가 없으면 이 분기에는 오지 않습니다.
            raise RuntimeError("sajupy 미설치 및 내부 변환기 없음")
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
# === 세션 기본값 ===
if "initial_saju" not in st.session_state: st.session_state.initial_saju = ""
if "ganji" not in st.session_state: st.session_state.ganji = ("","","","")
if "five" not in st.session_state: st.session_state.five = None

# === 상단: 현재 만세력 상태 표시 ===
if st.session_state.initial_saju:
    st.success(f"만세력: {st.session_state.initial_saju}")
    st.caption(f"계산 엔진: {st.session_state.get('saju_engine','-')}")

    if st.session_state.five:
        import pandas as pd
        col1, col2 = st.columns([2,1])
        with col1:
            st.bar_chart(pd.DataFrame.from_dict(st.session_state.five, orient="index", columns=["개수"]))
        with col2:
            dom = max(st.session_state.five, key=st.session_state.five.get)
            st.info(f"가장 많은 오행: **{dom}**\n\n{st.session_state.five}")

# === 입력 폼 (기본값을 1971-07-07 21시로 제공: 해시 테스트 용) ===
with st.form("saju_form"):
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
    compute_and_store_saju(y, m, d, h, gender_map, is_lunar)
    st.rerun()


st.title("🔮 사주명리코치 루아")
st.markdown("---")

# 상단: 계산된 만세력 표시 + 엔진 표기
if st.session_state.get("initial_saju"):
    st.success(f"만세력: {st.session_state.initial_saju}")
    st.caption(f"계산 엔진: {SAJU_ENGINE}")

# ===== 비용 절감 옵션 =====
STYLE_TO_MAXTOK = {"짧게(≈150자)": 220, "보통(≈300자)": 420}
SYS_KO = (
    "당신은 사주 기반 코치입니다. 한국어로, 군더더기 없이 핵심만 말하세요. "
    "리스트는 최대 3개, 문장은 짧게. 불필요한 인사/중복 금지."
)

# ===== 사이드바 =====
st.sidebar.header("설정")
engine = st.sidebar.selectbox("엔진", ["Gemini(권장/저렴)", "Mock(오프라인)"], index=0)
brevity = st.sidebar.radio("응답 길이", list(STYLE_TO_MAXTOK.keys()), index=0)
st.sidebar.caption("짧게일수록 토큰/비용 절약 👍")

# ===== 만세력 변환 블록(내장 + 외부 파일 지원) =====
MANSE_CSV_STRING_DATA = """
1900,1,1,월,1899,12,1,己亥,丙子,庚辰,丁丑,대한,大寒,190001210444
1900,1,2,화,1899,12,2,己亥,丙子,辛巳,丁丑,,
2050,12,31,일,2050,11,11,庚午,戊子,丁酉,己酉,,
""".strip()

CHEONGAN = {'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水'}
JIJI     = {'子':'水','丑':'土','寅':'木','卯':'木','辰':'土','巳':'火','午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'}

@st.cache_resource(show_spinner=False)
def load_manse_dict():
    db = {}
    gz_path = pathlib.Path("data/manse_utf8.csv.gz")
    if gz_path.exists():
        import codecs
        with gzip.open(gz_path, "rt", encoding="utf-8") as f:
            for raw in f: _push_line_to_db(raw, db)
        return db
    csv_path = pathlib.Path("data/manse_utf8.csv")
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            for raw in f: _push_line_to_db(raw, db)
        return db
    csv_io = io.StringIO(MANSE_CSV_STRING_DATA)
    for raw in csv_io: _push_line_to_db(raw, db)
    return db

def _push_line_to_db(raw_line: str, db: dict):
    line = raw_line.strip()
    if not line or line.startswith("#"): return
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 10: return
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        db[f"{y}-{m}-{d}"] = parts
    except Exception:
        return
    if len(parts) > 6 and parts[4] and parts[5] and parts[6]:
        try:
            ly, lm, ld = int(parts[4]), int(parts[5]), int(parts[6])
            db[f"{ly}-{lm}-{ld}-L"] = parts
        except Exception:
            pass

MANSE_DF = load_manse_dict()

def get_time_jiji(hour: int) -> str:
    h = int(hour)
    if 23 <= h or h < 1:  return '子'
    if 1 <= h < 3:        return '丑'
    if 3 <= h < 5:        return '寅'
    if 5 <= h < 7:        return '卯'
    if 7 <= h < 9:        return '辰'
    if 9 <= h < 11:       return '巳'
    if 11 <= h < 13:      return '午'
    if 13 <= h < 15:      return '未'
    if 15 <= h < 17:      return '申'
    if 17 <= h < 19:      return '酉'
    if 19 <= h < 21:      return '戌'
    if 21 <= h < 23:      return '亥'
    return ''

def get_time_ganji(day_ganji: str, hour: int) -> str:
    start_index = {'甲':0,'乙':2,'丙':4,'丁':6,'戊':8,'己':0,'庚':2,'辛':4,'壬':6,'癸':8}
    offset      = {'子':0,'丑':1,'寅':2,'卯':3,'辰':4,'巳':5,'午':6,'未':7,'申':8,'酉':9,'戌':10,'亥':11}
    day_cheongan = day_ganji[0]
    time_jiji_char = get_time_jiji(hour)
    s = start_index.get(day_cheongan, 0)
    idx = (s + offset[time_jiji_char]) % 10
    time_cheongan_char = list(CHEONGAN.keys())[idx]
    return time_cheongan_char + time_jiji_char

def get_saju(year:int, month:int, day:int, hour:int, gender:str, is_lunar:bool=False):
    if is_lunar:
        solar_info = MANSE_DF.get(f"{year}-{month}-{day}-L")
        if solar_info is None:
            raise ValueError(f"음력 {year}-{month}-{day}를 찾을 수 없습니다.")
        year, month, day = map(int, solar_info[0:3])
    date_key = f"{year}-{month}-{day}"
    date_info = MANSE_DF.get(date_key)
    if date_info is None:
        raise ValueError(f"양력 {year}-{month}-{day}를 찾을 수 없습니다.")
    ganji_year, ganji_month, ganji_day = date_info[7], date_info[8], date_info[9]
    jeolip_time_str = date_info[13] if len(date_info) > 13 else ""
    try:
        if jeolip_time_str:
            jeolip_dt = datetime.datetime.strptime(f"{year}{month:02d}{day:02d}{jeolip_time_str}", "%Y%m%d%H%M")
            now_dt = datetime.datetime(year, month, day, int(hour))
            if now_dt < jeolip_dt:
                prev = datetime.date(year, month, day) - datetime.timedelta(days=1)
                prev_info = MANSE_DF.get(f"{prev.year}-{prev.month}-{prev.day}")
                if prev_info:
                    ganji_month = prev_info[8]
    except Exception:
        pass
    return ganji_year, ganji_month, ganji_day

def get_saju_str(year, month, day, hour, gender, is_lunar=False):
    y, m, d = get_saju(year, month, day, hour, gender, is_lunar)
    t = get_time_ganji(d, hour)
    return f"{y}년 {m}월 {d}일 {t}시"

# ===== Gemini & Mock =====
def init_gemini():
    key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key: raise RuntimeError("GOOGLE_API_KEY가 없습니다. Streamlit Secrets에 추가하세요.")
    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        system_instruction=SYS_KO,
        generation_config={"max_output_tokens": STYLE_TO_MAXTOK[brevity], "temperature":0.6, "candidate_count":1},
    )
    return model.start_chat(history=[])

def mock_reply(prompt, initial_saju=""):
    head = f"사주요약: {initial_saju}\n" if initial_saju else ""
    body = ("핵심 조언 3가지\n"
            "1) 일일 루틴 1개 정착(수면/식사/운동 중 택1)\n"
            "2) 이번 주 목표 1가지를 수치로 정의\n"
            "3) 다음 질문을 구체화(예: 직장 스트레스 대처 3가지)")
    return head + body

if "chat" not in st.session_state: st.session_state.chat = None
if "initial_saju" not in st.session_state: st.session_state.initial_saju = ""
if "messages" not in st.session_state: st.session_state.messages = []

if engine.startswith("Gemini"):
    try:
        if not st.session_state.chat: st.session_state.chat = init_gemini()
        ai_type = "gemini"
    except Exception as e:
        st.warning(f"Gemini 초기화 실패: {e} → Mock으로 전환합니다.")
        ai_type = "mock"
else:
    ai_type = "mock"

st.title("🔮 저비용 Gemini 사주 챗봇")
st.markdown("---")

# 입력 폼
if not st.session_state.initial_saju:
    with st.form("saju_form"):
        st.write("먼저 생년월일시를 입력하세요 (DB 없으면 샘플로 동작)")
        cal = st.radio("달력", ["양력","음력"], horizontal=True)
        is_lunar = (cal=="음력")
        today = datetime.datetime.now()
        c1,c2,c3 = st.columns(3)
        with c1: y = st.number_input("연도", 1901, today.year-1, 2000)
        with c2: m = st.number_input("월", 1, 12, 1)
        with c3: d = st.number_input("일", 1, 31, 1)
        c4,c5 = st.columns(2)
        with c4: h = st.selectbox("시간", list(range(24)), index=12, format_func=lambda x:f"{x:02d}시")
        with c5: gender = st.radio("성별", ["남","여"], horizontal=True)
        ok = st.form_submit_button("대화 시작 🚀")
    if ok:
        try:
            st.session_state.initial_saju = get_saju_str(y,m,d,h, "남자" if gender=="남" else "여자", is_lunar)
        except Exception as e:
            st.warning(f"만세력 변환 실패: {e}")
            cal = "음력" if is_lunar else "양력"
            st.session_state.initial_saju = f"{cal} {y}-{m:02d}-{d:02d} {h:02d}시 / 성별:{gender} (DB 미탑재)"
        first_prompt = (f"[사주 데이터]\n{st.session_state.initial_saju}\n\n"
                        "이 사주의 큰 흐름을 3줄 이내로 요약하고, 다음 질문 1가지를 제안하세요.")
        if ai_type=="gemini":
            try:
                res = st.session_state.chat.send_message(first_prompt)
                st.session_state.messages.append({"role":"assistant","content":res.text})
            except Exception as e:
                st.warning(f"호출 오류: {e} → Mock으로 임시 전환")
                st.session_state.messages.append({"role":"assistant","content":mock_reply(first_prompt, st.session_state.initial_saju)})
        else:
            st.session_state.messages.append({"role":"assistant","content":mock_reply(first_prompt, st.session_state.initial_saju)})
        st.rerun()

# 대화
for m in st.session_state.messages[-10:]:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if st.session_state.initial_saju:
    if prompt := st.chat_input("질문을 입력하세요 (짧을수록 저렴)"):
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            q = f"[사주 데이터]\n{st.session_state.initial_saju}\n\n[사용자 질문]\n{prompt}"
            if ai_type=="gemini":
                try:
                    res = st.session_state.chat.send_message(q)
                    out = res.text
                except Exception as e:
                    st.warning(f"호출 오류: {e} → Mock으로 임시 전환")
                    out = mock_reply(prompt, st.session_state.initial_saju)
                    st.session_state.chat = None
            else:
                out = mock_reply(prompt, st.session_state.initial_saju)
            st.markdown(out)
            st.session_state.messages.append({"role":"assistant","content":out})
