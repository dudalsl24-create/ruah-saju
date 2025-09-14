# saju_rules.py
# 교재 규칙(입춘/12절입일/야자시·조자시/한국표준 보정/시두법)만으로 4주 계산
from dataclasses import dataclass
from datetime import date, datetime, timedelta

STEMS = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
BRANCHES = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']

# 월 경계 (교재 고정 날짜, ±1~2일 오차 허용)
MONTH_BOUNDARIES = [
    ('丑', (1, 6)), ('寅', (2, 4)), ('卯', (3, 5)), ('辰', (4, 5)),
    ('巳', (5, 5)), ('午', (6, 6)), ('未', (7, 7)), ('申', (8, 7)),
    ('酉', (9, 8)), ('戌', (10, 8)), ('亥', (11, 7)), ('子', (12, 7)),
]

# 寅월의 시작 천간(연간별)
START_STEM_FOR_YIN_BY_YEAR_STEM = {
    '甲':'丙','己':'丙','乙':'戊','庚':'戊','丙':'庚','辛':'庚','丁':'壬','壬':'壬','戊':'甲','癸':'甲'
}

# 時干(시두법): 日干별 子시 시작 천간
HOUR_START_STEM_BY_DAY_STEM = {
    '甲':'甲','己':'甲','乙':'丙','庚':'丙','丙':'戊','辛':'戊','丁':'庚','壬':'庚','戊':'壬','癸':'壬'
}

# 오행 매핑(앱에서 재사용)
CHEONGAN_TO_ELEM = {'甲':'목','乙':'목','丙':'화','丁':'화','戊':'토','己':'토','庚':'금','辛':'금','壬':'수','癸':'수'}
JIJI_TO_ELEM     = {'子':'수','丑':'토','寅':'목','卯':'목','辰':'토','巳':'화','午':'화','未':'토','申':'금','酉':'금','戌':'토','亥':'수'}

@dataclass
class Pillars:
    year: str   # '甲子'
    month: str  # '丙寅'
    day: str    # '庚辰'
    hour: str   # '丁亥'
    note: str   # '야자시/조자시, +30분 보정, 일간보정 …'

def _stem_index(ch: str) -> int: return STEMS.index(ch)
def _branch_index(ch: str) -> int: return BRANCHES.index(ch)
def _add_stem(stem: str, n: int) -> str: return STEMS[(_stem_index(stem)+n) % 10]
def _add_branch(branch: str, n: int) -> str: return BRANCHES[(_branch_index(branch)+n) % 12]

def _jdn(y: int, m: int, d: int) -> int:
    a = (14 - m)//2
    y2 = y + 4800 - a
    m2 = m + 12*a - 3
    return d + (153*m2 + 2)//5 + 365*y2 + y2//4 - y2//100 + y2//400 - 32045

def ganzhi_of_day(y: int, m: int, d: int) -> str:
    # 1984-02-02 = 甲子(day) 기준 → (JDN+37)%60
    j = _jdn(y,m,d)
    idx = (j + 37) % 60
    return STEMS[idx % 10] + BRANCHES[idx % 12]

# 年柱: 입춘(2/4) 기준
def year_pillar_by_lichun(dt: date) -> str:
    lichun = date(dt.year, 2, 4)
    y = dt.year if dt >= lichun else dt.year - 1
    return STEMS[(y - 4) % 10] + BRANCHES[(y - 4) % 12]

# 月柱: 12절입일 고정 경계
def month_branch_and_startdate(dt: date) -> tuple[str, date]:
    y = dt.year
    boundaries = [(br, date(y, mm, dd)) for br, (mm, dd) in MONTH_BOUNDARIES]
    latest = None
    for br, start in sorted(boundaries, key=lambda x: x[1]):
        if dt >= start: latest = (br, start)
    if latest is None: latest = ('子', date(y-1, 12, 7))  # 1/1~1/5
    return latest

def month_pillar_by_rules(dt: date, year_stem: str) -> str:
    br, _ = month_branch_and_startdate(dt)
    order_from_yin = ['寅','卯','辰','巳','午','未','申','酉','戌','亥','子','丑']
    offset = order_from_yin.index(br)
    start_stem = START_STEM_FOR_YIN_BY_YEAR_STEM[year_stem]
    return _add_stem(start_stem, offset) + br

# 時支 + 야/조자시 + 일자보정(한국표준 +30분)
def hour_branch_kst_adjusted(hh: int, mm: int) -> tuple[str, str, int]:
    total_local = hh*60 + mm
    total = (total_local + 30) % (24*60)  # +30분 보정
    if total >= 23*60 or total < 1*60:
        label = '야자시' if total_local < 30 else '조자시'
        day_corr = -1 if total_local < 30 else 0
        return '子', label, day_corr
    starts = [
        ('丑', 1*60), ('寅', 3*60), ('卯', 5*60), ('辰', 7*60),
        ('巳', 9*60), ('午',11*60), ('未',13*60), ('申',15*60),
        ('酉',17*60), ('戌',19*60), ('亥',21*60),
    ]
    for br, start in starts:
        if total >= start and total < start+120:
            return br, '일반', 0
    return '亥', '일반', 0

def hour_pillar_by_shidu(day_stem: str, hour_branch: str) -> str:
    start = HOUR_START_STEM_BY_DAY_STEM[day_stem]
    order = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
    return _add_stem(start, order.index(hour_branch)) + hour_branch

def five_element_counts(gy, gm, gd, gh) -> dict:
    cnt = {"목":0,"화":0,"토":0,"금":0,"수":0}
    for p in [gy, gm, gd, gh]:
        if not p: continue
        tg, dz = p[0], p[1]
        cnt[CHEONGAN_TO_ELEM[tg]] += 1
        cnt[JIJI_TO_ELEM[dz]] += 1
    return cnt

@dataclass
class Pillars:
    year: str; month: str; day: str; hour: str; note: str

def get_pillars_by_textbook_rules(y: int, m: int, d: int, hh: int, mm: int) -> Pillars:
    base = date(y, m, d)
    y_p = year_pillar_by_lichun(base)
    m_p = month_pillar_by_rules(base, y_p[0])
    h_branch, label, d_corr = hour_branch_kst_adjusted(hh, mm)
    base_for_day = base + timedelta(days=d_corr)
    d_p = ganzhi_of_day(base_for_day.year, base_for_day.month, base_for_day.day)
    h_p = hour_pillar_by_shidu(d_p[0], h_branch)
    note = f"{label}, 한국표준 +30분, 일자보정 {d_corr:+d}일"
    return Pillars(y_p, m_p, d_p, h_p, note)
