# app.py — KASI 공공데이터(한국천문연)로 연/월/일 간지, 시주는 시두법 계산
import os, urllib.parse, requests, json
import xmltodict
import pandas as pd
import streamlit as st
from datetime import date, timedelta

st.set_page_config(page_title="사주명리코치 루아", page_icon="🔮")
st.title("🔮 사주명리코치 루아")
st.markdown("---")

# ===== 간지/오행 기본표 =====
STEMS     = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
BRANCHES  = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
HOUR_START_STEM_BY_DAY_STEM = {
    '甲':'甲','己':'甲','乙':'丙','庚':'丙','丙':'戊','辛':'戊','丁':'庚','壬':'庚','戊':'壬','癸':'壬'
}
ELEM_GAN = {'甲':'목','乙':'목','丙':'화','丁':'화','戊':'토','己':'토','庚':'금','辛':'금','壬':'수','癸':'수'}
ELEM_BRANCH = {'子':'수','丑':'토','寅':'목','卯':'목','辰':'토','巳':'화','午':'화','未':'토','申':'금','酉':'금','戌':'토','亥':'수'}

# ===== 시간대 선택(한국표준 +30분 기준) =====
SLOTS = [
    ("23:30–01:30 (子)", 0,30), ("01:30–03:30 (丑)", 2,30), ("03:30–05:30 (寅)", 4,30), ("05:30–07:30 (卯)", 6,30),
    ("07:30–09:30 (辰)", 8,30), ("09:30–11:30 (巳)",10,30), ("11:30–13:30 (午)",12,30), ("13:30–15:30 (未)",14,30),
    ("15:30–17:30 (申)",16,30), ("17:30–19:30 (酉)",18,30), ("19:30–21:30 (戌)",20,30), ("21:30–23:30 (亥)",22,30),
]

# ===== 공공데이터 호출 유틸 =====
BASE = "https://apis.data.go.kr/B090041/openapi/service/LrsrCldInfoService"

def _kasi_key():
    key = st.secrets.get("DATA_GO_KR_KEY") or os.getenv("DATA_GO_KR_KEY")
    if not key:
        raise RuntimeError("DATA_GO_KR_KEY가 없습니다. Streamlit Secrets에 넣어주세요.")
    return key

def _get_json(url, params):
    """
    _type=json 지원하면 JSON으로 받고,
    아니면 XML을 받아서 dict로 변환합니다.
    """
    key = _kasi_key()
    # Decoding키면 그대로, Encoding키면 그대로 넣어도 됩니다(요청 라이브러리가 인코딩 처리).
    params = {**params, "serviceKey": key}
    # 1) JSON 시도
    try:
        r = requests.get(url, params={**params, "_type":"json"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        return ("json", data)
    except Exception:
        # 2) XML fallback
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = xmltodict.parse(r.text)
        return ("xml", data)

def _extract_item(tagged, flavor):
    """
    KASI 응답에서 item을 dict로 뽑아 key를 소문자화하여 반환.
    flavor=json/xml
    """
    try:
        if flavor == "json":
            item = (tagged["response"]["body"]["items"]["item"])
        else:
            item = (tagged["response"]["body"]["items"]["item"])
    except Exception as e:
        raise RuntimeError(f"KASI 응답 파싱 실패: {e}\n원문: {str(tagged)[:400]}")

    # XML일 때 OrderedDict → dict
    if not isinstance(item, dict):
        raise RuntimeError(f"KASI item 형식이 예상과 다릅니다: {type(item)}")

    # key를 소문자로 통일
    out = {k.lower(): (v.get("#text") if isinstance(v, dict) and "#text" in v else v) for k,v in item.items()}
    return out

def get_sol_ganji(y, m, d):
    """양력 입력 → (년간지, 월간지, 일간지)와 부가정보 반환"""
    url = f"{BASE}/getSolCalInfo"
    flavor, raw = _get_json(url, {"solYear": y, "solMonth": f"{m:02d}", "solDay": f"{d:02d}"})
    it = _extract_item(raw, flavor)
    # 필드명이 API 버전에 따라 다를 수 있어 넓게 탐색
    yg = it.get("secha") or it.get("ganjiyear") or it.get("ganji_year") or it.get("szyear")
    mg = it.get("wolji") or it.get("ganjimonth") or it.get("ganji_month") or it.get("szmonth")
    dg = it.get("iljin") or it.get("ganjiday") or it.get("ganji_day") or it.get("szday")
    if not (yg and mg and dg):
        raise RuntimeError(f"간지 필드를 찾지 못했습니다. 응답 확인 필요: {it}")
    # 한글 '갑자' 형태로 올 수도 있어요 → 한자 10천간/12지지 조합일 때만 그대로 사용
    return str(yg), str(mg), str(dg), it

def get_lun_to_sol(lun_y, lun_m, lun_d, leap_yn=0):
    """음력 입력 → 같은 날의 양력 날짜(년,월,일)와 간지들"""
    url = f"{BASE}/getLunCalInfo"
    flavor, raw = _get_json(url, {
        "lunYear": lun_y, "lunMonth": f"{lun_m:02d}", "lunDay": f"{lun_d:02d}", "leapMonth": int(leap_yn)
    })
    it = _extract_item(raw, flavor)
    sy = int(it.get("solyear") or it.get("syear"))
    sm = int(it.get("solmonth") or it.get("smonth"))
    sd = int(it.get("solday") or it.get("sday"))
    return sy, sm, sd, it

# ===== 시두법(+30분/야·조자시) =====
def hour_branch_and_day_correction(hh:int, mm:int):
    """
    한국표준 +30분 경계. 자시(23:30~01:30)는 야/조자시를 구분하여
    야자시(23:30~00:30)는 '전날' 일간지로 계산해야 하므로 corr=-1.
    """
    local = hh*60 + mm
    kst   = (local + 30) % (24*60)
    if kst >= 23*60 or kst < 60:  # 子
        label = "야자시" if local < 30 else "조자시"
        corr  = -1 if local < 30 else 0
        return '子', label, corr
    bands=[('丑',90),('寅',210),('卯',330),('辰',450),('巳',570),
           ('午',690),('未',810),('申',930),('酉',1050),('戌',1170),('亥',1290)]
    for br,stt in bands:
        if stt <= kst < stt+120:
            return br,"일반",0
    return '亥',"일반",0

def hour_stem(day_stem:str, hour_branch:str):
    start = HOUR_START_STEM_BY_DAY_STEM[day_stem]
    order = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
    stem  = STEMS[(STEMS.index(start)+order.index(hour_branch))%10]
    return stem

def five_counts(gy, gm, gd, gh):
    c={"목":0,"화":0,"토":0,"금":0,"수":0}
    for p in [gy,gm,gd,gh]:
        c[ELEM_GAN[p[0]]] += 1
        c[ELEM_BRANCH[p[1]]] += 1
    return c

# ===== UI =====
with st.form("frm"):
    c1,c2,c3 = st.columns(3)
    y = c1.number_input("연도", 1901, 2099, 1971)
    m = c2.number_input("월", 1, 12, 7)
    d = c3.number_input("일", 1, 31, 7)
    cal = st.radio("달력", ["양력","음력"], horizontal=True)
    slot = st.selectbox("시간대", [s[0] for s in SLOTS], index=4)  # 07:30–09:30 기본
    ok = st.form_submit_button("만세력 확인하기")

if ok:
    try:
        # 1) 날짜 기준(양/음력) 정리
        if cal == "음력":
            sy, sm, sd, _ = get_lun_to_sol(int(y), int(m), int(d), leap_yn=0)
        else:
            sy, sm, sd = int(y), int(m), int(d)

        # 2) 연/월/일 간지: KASI 공식값
        y_g, m_g, d_g, _ = get_sol_ganji(sy, sm, sd)

        # 3) 시지/일간 보정(야자시면 하루 전 일간 사용)
        hh, mm = next((h, mn) for label, h, mn in SLOTS if label == slot)
        h_branch, h_label, corr = hour_branch_and_day_correction(hh, mm)
        if corr == -1:
            prev = date(sy, sm, sd) + timedelta(days=-1)
            _, _, d_g, _ = get_sol_ganji(prev.year, prev.month, prev.day)

        h_stem = hour_stem(d_g[0], h_branch)
        h_g    = h_stem + h_branch

        # 4) 결과 표시
        st.success(f"{y_g}년 {m_g}월 {d_g}일 {h_g}시")
        st.caption(f"{'음력→양력 변환, ' if cal=='음력' else ''}{h_label}(+30분), 일자보정 {corr:+d}일")

        # 5) 오행 카운트
        counts = five_counts(y_g, m_g, d_g, h_g)
        col1,col2 = st.columns([2,1])
        with col1:
            st.bar_chart(pd.DataFrame.from_dict(counts, orient="index", columns=["개수"]))
        with col2:
            top = max(counts, key=counts.get)
            st.info(f"가장 많은 오행: **{top}**")

    except Exception as e:
        st.error(f"오류: {e}")
