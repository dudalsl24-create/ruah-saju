# saju_rules.py — 외부 CSV 없이 동작(내장 DB 자동 로딩)
from dataclasses import dataclass
from datetime import date, timedelta
import os, csv, gzip

# ───── 기본 표 ─────
STEMS     = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
BRANCHES  = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
MONTH_BOUNDARIES = [  # 규칙식 백업용(절입 "날짜"만)
    ('丑',(1,6)),('寅',(2,4)),('卯',(3,5)),('辰',(4,5)),('巳',(5,5)),('午',(6,6)),
    ('未',(7,7)),('申',(8,7)),('酉',(9,8)),('戌',(10,8)),('亥',(11,7)),('子',(12,7)),
]
HOUR_START_STEM_BY_DAY_STEM = {
    '甲':'甲','己':'甲','乙':'丙','庚':'丙','丙':'戊','辛':'戊','丁':'庚','壬':'庚','戊':'壬','癸':'壬'
}
START_STEM_FOR_YIN_BY_YEAR_STEM = {
    '甲':'丙','己':'丙','乙':'戊','庚':'戊','丙':'庚','辛':'庚','丁':'壬','壬':'壬','戊':'甲','癸':'甲'
}
CHEONGAN_TO_ELEM={'甲':'목','乙':'목','丙':'화','丁':'화','戊':'토','己':'토','庚':'금','辛':'금','壬':'수','癸':'수'}
JIJI_TO_ELEM    ={'子':'수','丑':'토','寅':'목','卯':'목','辰':'토','巳':'화','午':'화','未':'토','申':'금','酉':'금','戌':'토','亥':'수'}

# ───── 결과 타입 ─────
@dataclass
class Pillars:
    year:str; month:str; day:str; hour:str; note:str

# ───── 메모리 DB ─────
_DB_SOLAR = {}   # "Y-M-D" -> {'gy','gm','gd'}
_DB_LUNAR = {}   # "Y-M-D-L" -> {'y','m','d'}

def _load_manse_db():
    """① data/ → ② sajupy 패키지 내장 CSV 순으로 탐색"""
    global _DB_SOLAR, _DB_LUNAR
    if _DB_SOLAR or _DB_LUNAR:
        return
    path = None
    # ① 저장소 data/
    if os.path.exists("data/manse_utf8.csv"):
        path = "data/manse_utf8.csv"
    elif os.path.exists("data/manse_utf8.csv.gz"):
        path = "data/manse_utf8.csv.gz"
    # ② sajupy 패키지 내장
    if path is None:
        try:
            import importlib.resources as ir, sajupy
            base = ir.files('sajupy') / 'data'
            if (base/'manse_utf8.csv').exists():
                path = str(base/'manse_utf8.csv')
            elif (base/'manse_utf8.csv.gz').exists():
                path = str(base/'manse_utf8.csv.gz')
        except Exception:
            path = None
    if path is None:
        return  # DB 없이도 규칙식으로 동작

    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        r = csv.reader(f)
        for row in r:
            if not row or row[0].startswith("#"): 
                continue
            try:
                y,m,d = int(row[0]), int(row[1]), int(row[2])
                gy, gm, gd = row[7].strip(), row[8].strip(), row[9].strip()
                _DB_SOLAR[f"{y}-{m}-{d}"] = {"gy":gy, "gm":gm, "gd":gd}
                if len(row)>6 and row[4] and row[5] and row[6]:
                    ly,lm,ld = int(row[4]), int(row[5]), int(row[6])
                    _DB_LUNAR[f"{ly}-{lm}-{ld}-L"] = {"y":y, "m":m, "d":d}
            except Exception:
                continue

# ───── 백업 규칙(로컬 DB 없을 때) ─────
def _jdn(y,m,d):
    a=(14-m)//2; y2=y+4800-a; m2=m+12*a-3
    return d+(153*m2+2)//5+365*y2+y2//4-y2//100+y2//400-32045

def _ganzhi_of_day(y,m,d):
    idx = (_jdn(y,m,d) + 37) % 60  # 1984-02-02=甲子
    return STEMS[idx%10] + BRANCHES[idx%12]

def _year_by_lichun(dt:date):
    y = dt.year if dt >= date(dt.year,2,4) else dt.year-1
    return STEMS[(y-4)%10] + BRANCHES[(y-4)%12]

def _month_branch_and_start(dt:date):
    y=dt.year; latest=None
    for br,(mm,dd) in sorted(MONTH_BOUNDARIES, key=lambda x:x[1]):
        if dt >= date(y,mm,dd): latest=(br, date(y,mm,dd))
    if latest is None: latest=('子', date(y-1,12,7))
    return latest

def _month_by_rules(dt:date, year_stem:str):
    br,_=_month_branch_and_start(dt)
    order=['寅','卯','辰','巳','午','未','申','酉','戌','亥','子','丑']
    start = START_STEM_FOR_YIN_BY_YEAR_STEM[year_stem]
    stem  = STEMS[(STEMS.index(start)+order.index(br))%10]
    return stem + br

def _hour_branch_kst(hh:int, mm:int):
    """한국표준 +30분. 子시간은 야/조자시 보정."""
    local = hh*60 + mm
    kst   = (local + 30) % (24*60)
    if kst >= 23*60 or kst < 60:   # 子
        label = '야자시' if local < 30 else '조자시'
        corr  = -1 if local < 30 else 0
        return '子', label, corr
    starts=[('丑',90),('寅',210),('卯',330),('辰',450),('巳',570),
            ('午',690),('未',810),('申',930),('酉',1050),('戌',1170),('亥',1290)]
    for br,st in starts:
        if st <= kst < st+120:
            return br,'일반',0
    return '亥','일반',0

def _hour_by_shidu(day_stem:str, hour_branch:str):
    start = HOUR_START_STEM_BY_DAY_STEM[day_stem]
    order=['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
    stem  = STEMS[(STEMS.index(start)+order.index(hour_branch))%10]
    return stem + hour_branch

# ───── 공개 API (모듈 레벨로 "반드시" 노출) ─────
def five_element_counts(gy,gm,gd,gh)->dict:
    c={"목":0,"화":0,"토":0,"금":0,"수":0}
    for p in [gy,gm,gd,gh]:
        c[CHEONGAN_TO_ELEM[p[0]]] += 1
        c[JIJI_TO_ELEM[p[1]]]     += 1
    return c

def get_pillars(y:int,m:int,d:int, hh:int,mm:int, is_lunar:bool=False)->Pillars:
    """DB가 있으면 DB 기준(연/월/일), 없으면 규칙식 사용"""
    _load_manse_db()

    # 음력 → 양력 (DB 매핑이 있을 때만)
    if is_lunar and _DB_LUNAR:
        t = _DB_LUNAR.get(f"{y}-{m}-{d}-L")
        if t: y,m,d = t["y"], t["m"], t["d"]

    base = date(y,m,d)

    # 1) DB 우선
    rec = _DB_SOLAR.get(f"{y}-{m}-{d}") if _DB_SOLAR else None
    if rec:
        gy, gm, gd = rec["gy"], rec["gm"], rec["gd"]
        hbr,label,corr = _hour_branch_kst(hh,mm)
        base2 = base + timedelta(days=corr)
        rec2  = _DB_SOLAR.get(f"{base2.year}-{base2.month}-{base2.day}")
        if rec2: gd = rec2["gd"]  # 야자시 전날 일주
        gh = _hour_by_shidu(gd[0], hbr)
        note = f"{'음력→양력, ' if is_lunar else ''}DB기반, {label}, +30분, 일자보정 {corr:+d}일"
        return Pillars(gy,gm,gd,gh,note)

    # 2) 백업 규칙
    yp = _year_by_lichun(base)
    mp = _month_by_rules(base, yp[0])
    hbr,label,corr = _hour_branch_kst(hh,mm)
    base2 = base + timedelta(days=corr)
    dp = _ganzhi_of_day(base2.year, base2.month, base2.day)
    gh = _hour_by_shidu(dp[0], hbr)
    note = f"{'음력→양력, ' if is_lunar else ''}규칙식, {label}, +30분, 일자보정 {corr:+d}일"
    return Pillars(yp,mp,dp,gh,note)
def get_pillars_by_textbook_rules(y, m, d, hh, mm, is_lunar=False):
    # 기존 get_pillars의 래퍼(동일한 동작)
    return get_pillars(y, m, d, hh, mm, is_lunar=is_lunar)

