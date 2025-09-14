# saju_rules.py
from __future__ import annotations
import datetime as dt
import requests
import xml.etree.ElementTree as ET

# KASI: 음양력 정보제공 서비스 (운영)
# ※ 반드시 http 사용 (가이드가 http이며, https는 SSL 오류가 납니다)
#   예: http://apis.data.go.kr/B090041/openapi/service/LrsrCldInfoService/getLunCalInfo
KASI_ENDPOINT = "http://apis.data.go.kr/B090041/openapi/service/LrsrCldInfoService/getLunCalInfo"

STEMS = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
BRANCHES = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
STEM_TO_ELEM = {'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水'}
BRANCH_TO_ELEM = {'子':'水','丑':'土','寅':'木','卯':'木','辰':'土','巳':'火','午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'}

# ─────────────────────────────────────────────────────────
# 1) KASI에서 년/월/일 간지 가져오기
#    응답 예시 필드: lunSecha(간지/세차), lunWolgeon(간지/월), lunIljin(간지/일)
# ─────────────────────────────────────────────────────────
def _extract_hanja(text: str) -> str:
    """예: '갑오(甲午)' -> '甲午'; '신축(辛丑)' -> '辛丑'"""
    if not text:
        return ""
    s = text.strip()
    if '(' in s and ')' in s:
        return s[s.find('(')+1:s.find(')')]
    # 한자만 남기기(안전장치)
    return "".join(ch for ch in s if '\u4e00' <= ch <= '\u9fff') or s

def fetch_ganzhi_from_kasi(sol_y: int, sol_m: int, sol_d: int, service_key: str) -> dict:
    params = {
        "solYear": sol_y, "solMonth": f"{sol_m:02d}", "solDay": f"{sol_d:02d}",
        "ServiceKey": service_key
    }
    r = requests.get(KASI_ENDPOINT, params=params, timeout=6)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    item = root.find(".//item")
    if item is None:
        raise RuntimeError("KASI 응답에 item이 없습니다.")
    # 년/월/일 간지
    year_gz = _extract_hanja((item.findtext("lunSecha") or "").strip())    # 예: 甲午
    month_gz = _extract_hanja((item.findtext("lunWolgeon") or "").strip()) # 예: 丙子
    day_gz = _extract_hanja((item.findtext("lunIljin") or "").strip())     # 예: 辛丑
    if len(year_gz) != 2 or len(month_gz) != 2 or len(day_gz) != 2:
        raise RuntimeError("간지 파싱 실패 (year/month/day).")
    return {"year": year_gz, "month": month_gz, "day": day_gz}

# ─────────────────────────────────────────────────────────
# 2) 교재 규칙: 시지(地支) = 2시간 간격 + 한국표준시 30분 보정
#    방법: 시각에 +30분 → 23:00 기준으로 2시간 슬라이스 하여 지지 산출
# ─────────────────────────────────────────────────────────
def time_to_branch(hour: int, minute: int) -> str:
    """한국표준시 +30분 보정 후 지지(子~亥) 반환"""
    t = (hour * 60 + minute + 30) % (24 * 60)
    base = 23 * 60  # 23:00을 기준
    idx = ((t - base) % (24*60)) // 120  # 120분 단위
    return BRANCHES[int(idx)]

# ─────────────────────────────────────────────────────────
# 3) 교재 시두법으로 시(時)의 천간 계산
#    규칙(표준):
#      甲己日 → 甲子 기시, 乙庚日 → 丙子, 丙辛日 → 戊子,
#      丁壬日 → 庚子, 戊癸日 → 壬子
#    자시 야/조 처리:
#      - 자시 & '야자'(전날 23~24시대) → "다음날 일간"으로 시두법 적용
#      - 자시 & '조자'(당일 00~01시대) → "당일 일간"으로 시두법 적용
# ─────────────────────────────────────────────────────────
def _start_stem_for_day_gan(day_gan: str) -> str:
    if day_gan in ('甲','己'): return '甲'
    if day_gan in ('乙','庚'): return '丙'
    if day_gan in ('丙','辛'): return '戊'
    if day_gan in ('丁','壬'): return '庚'
    if day_gan in ('戊','癸'): return '壬'
    raise ValueError("알 수 없는 일간")

def stem_for_time(day_gan_for_rule: str, branch: str) -> str:
    start = _start_stem_for_day_gan(day_gan_for_rule)
    start_idx = STEMS.index(start)
    offset = BRANCHES.index(branch)  # 子=0, 丑=1, ...
    return STEMS[(start_idx + offset) % 10]

# ─────────────────────────────────────────────────────────
# 4) 외부 API + 규칙 합쳐서 최종 사주 반환
#    - 필요할 때(야자시)만 다음날 일간을 KASI에서 한 번 더 조회
# ─────────────────────────────────────────────────────────
def get_pillars(y:int, m:int, d:int, hh:int, mm:int, service_key:str) -> dict:
    base = fetch_ganzhi_from_kasi(y, m, d, service_key)
    day_gz = base["day"]          # 예: 辛丑
    year_gz = base["year"]
    month_gz = base["month"]

    # 시지
    b = time_to_branch(hh, mm)    # 子~亥
    # 자시 야/조 판정(보정 전 '실제 시각' 기준):
    is_ya = (b == '子' and hh >= 23)     # 23시대 → 야자 / 0시대 → 조자

    # 시간 계산용 일간
    day_gan_used = day_gz[0]
    if b == '子' and is_ya:
        # 다음날 일간을 KASI에서 받아서 사용
        dt0 = dt.date(y, m, d) + dt.timedelta(days=1)
        next_gz = fetch_ganzhi_from_kasi(dt0.year, dt0.month, dt0.day, service_key)
        day_gan_used = next_gz["day"][0]

    time_stem = stem_for_time(day_gan_used, b)
    time_gz = time_stem + b  # 時柱

    return {
        "year_gz": year_gz,   # 年柱
        "month_gz": month_gz, # 月柱
        "day_gz": day_gz,     # 日柱
        "time_gz": time_gz,   # 時柱
        "is_ya": is_ya,       # True=야자, False=조자(자시가 아니면 의미 없음)
    }

# ─────────────────────────────────────────────────────────
# 5) 오행 카운트
# ─────────────────────────────────────────────────────────
def five_element_counts(pillars: dict) -> dict:
    s = pillars["year_gz"] + pillars["month_gz"] + pil_]()_]()
