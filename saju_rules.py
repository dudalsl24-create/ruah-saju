# saju_rules.py  (KASI + 교재 규칙)
import datetime as dt
import requests
import xml.etree.ElementTree as ET

# KASI OpenAPI (HTTP 사용: https는 SSL 오류 유발)
KASI_ENDPOINT = "http://apis.data.go.kr/B090041/openapi/service/LrsrCldInfoService/getLunCalInfo"

STEMS = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
BRANCHES = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']

STEM_TO_ELEM = {'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水'}
BRANCH_TO_ELEM = {'子':'水','丑':'土','寅':'木','卯':'木','辰':'土','巳':'火','午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'}

def _extract_hanja(s):
    if not s:
        return ""
    s = s.strip()
    if '(' in s and ')' in s:
        return s[s.find('(')+1:s.find(')')]
    return "".join(ch for ch in s if '\u4e00' <= ch <= '\u9fff') or s

def fetch_ganzhi_from_kasi(sol_y, sol_m, sol_d, service_key):
    params = {
        "solYear": sol_y,
        "solMonth": f"{sol_m:02d}",
        "solDay": f"{sol_d:02d}",
        "serviceKey": service_key,   # 소문자 키
    }
    r = requests.get(KASI_ENDPOINT, params=params, timeout=8)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    item = root.find(".//item")
    if item is None:
        # 키가 잘못되었거나 쿼터 초과시 item이 비어있을 수 있음
        snippet = r.text[:200].replace("\n"," ")
        raise RuntimeError("KASI 응답에 item 없음: " + snippet)

    year_gz = _extract_hanja((item.findtext("lunSecha") or "").strip())
    month_gz = _extract_hanja((item.findtext("lunWolgeon") or "").strip())
    day_gz = _extract_hanja((item.findtext("lunIljin") or "").strip())
    if len(year_gz) != 2 or len(month_gz) != 2 or len(day_gz) != 2:
        raise RuntimeError("간지 파싱 실패(year/month/day).")

    return {"year": year_gz, "month": month_gz, "day": day_gz}

def time_to_branch(hour, minute):
    # 한국표준시 +30분 보정 후 2시간 슬라이스
    t = (hour * 60 + minute + 30) % (24 * 60)
    base = 23 * 60  # 23:00 기준
    idx = ((t - base) % (24*60)) // 120
    return BRANCHES[int(idx)]

def _start_stem_for_day_gan(day_gan):
    if day_gan in ('甲','己'): return '甲'
    if day_gan in ('乙','庚'): return '丙'
    if day_gan in ('丙','辛'): return '戊'
    if day_gan in ('丁','壬'): return '庚'
    if day_gan in ('戊','癸'): return '壬'
    raise ValueError("알 수 없는 일간")

def stem_for_time(day_gan_for_rule, branch):
    start = _start_stem_for_day_gan(day_gan_for_rule)
    start_idx = STEMS.index(start)
    offset = BRANCHES.index(branch)  # 子=0
    return STEMS[(start_idx + offset) % 10]

def get_pillars(y, m, d, hh, mm, service_key):
    base = fetch_ganzhi_from_kasi(y, m, d, service_key)
    year_gz = base["year"]
    month_gz = base["month"]
    day_gz = base["day"]

    b = time_to_branch(hh, mm)   # 時支
    is_ya = (b == '子' and hh >= 23)  # 자시 야/조 판정

    day_gan_used = day_gz[0]
    if b == '子' and is_ya:
        # 야자시: 다음날 일간으로 시두법 적용
        dt0 = dt.date(y, m, d) + dt.timedelta(days=1)
        nx = fetch_ganzhi_from_kasi(dt0.year, dt0.month, dt0.day, service_key)
        day_gan_used = nx["day"][0]

    time_stem = stem_for_time(day_gan_used, b)
    time_gz = time_stem + b

    return {
        "year_gz": year_gz,
        "month_gz": month_gz,
        "day_gz": day_gz,
        "time_gz": time_gz,
        "is_ya": is_ya,
    }

def five_element_counts(pillars):
    s = pillars["year_gz"] + pillars["month_gz"] + pillars["day_gz"] + pillars["time_gz"]
    cnt = {"木":0,"火":0,"土":0,"金":0,"水":0}
    for ch in s:
        if ch in STEM_TO_ELEM:
            cnt[STEM_TO_ELEM[ch]] += 1
        elif ch in BRANCH_TO_ELEM:
            cnt[BRANCH_TO_ELEM[ch]] += 1
    return cnt
