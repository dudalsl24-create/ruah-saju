# saju_rules.py
# 교재 규칙(절입일, +30분 보정, 야/조자시)만 사용하여 4주(년/월/일/시) 계산
from datetime import date, datetime, timedelta

# 간지/오행 테이블
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEM_ELEM = { "甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土","庚":"金","辛":"金","壬":"水","癸":"水" }
BR_ELEM   = { "子":"水","丑":"土","寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土","申":"金","酉":"金","戌":"土","亥":"水" }

def _stem_idx(ch):   return STEMS.index(ch)
def _branch_idx(ch): return BRANCHES.index(ch)

def _gz_by_index(idx60:int)->str:
    return STEMS[idx60%10] + BRANCHES[idx60%12]

# ── (1) 절입일(고정 근사치) : 각 월의 첫 절기(12절) 기준
# ※ 교재 표(±1~2일 오차 허용)과 일반 실무 관행을 절충한 고정값.
#    -> 첫 절기에 들어가면 ‘그 달(지지)’로 간주
SOLAR_BOUNDARIES = [
    (1,  6, "丑"),  # 小寒 1/6  → 12월(丑) 시작
    (2,  4, "寅"),  # 立春 2/4   → 1월(寅)
    (3,  6, "卯"),  # 驚蟄 3/6   → 2월(卯)
    (4,  5, "辰"),  # 淸明 4/5   → 3월(辰)
    (5,  6, "巳"),  # 立夏 5/6   → 4월(巳)
    (6,  6, "午"),  # 芒種 6/6   → 5월(午)
    (7,  7, "未"),  # 小暑 7/7   → 6월(未)
    (8,  8, "申"),  # 立秋 8/8   → 7월(申)
    (9,  8, "酉"),  # 白露 9/8   → 8월(酉)
    (10, 8, "戌"),  # 寒露 10/8  → 9월(戌)
    (11, 7, "亥"),  # 立冬 11/7  → 10월(亥)
    (12, 7, "子"),  # 大雪 12/7  → 11월(子)
]
# 寅(月)~丑(月) 순서(1~12)
MONTH_BRANCH_ORDER = "寅卯辰巳午未申酉戌亥子丑"

def _solar_month_branch(y:int, m:int, d:int) -> tuple[str,int]:
    """절입일 근사치로 해당 날짜의 월지와 寅=1 … 丑=12 ‘월순번’을 구함."""
    today = date(y,m,d)
    # 직전 경계 찾기
    current_branch = "丑"  # 1/1~1/5까지는 이전 해 11월(子) 계속이지만, 실제 월순번은 12(丑)로 본다.
    for mon, day, br in SOLAR_BOUNDARIES:
        bd = date(y, mon, day)
        if today >= bd:
            current_branch = br
    # 월지 → 월순번
    month_no = MONTH_BRANCH_ORDER.index(current_branch) + 1  # 1..12
    return current_branch, month_no

def _year_gz(y:int, m:int, d:int) -> str:
    """입춘(2/4) 기준 연주. 1984甲子 기준."""
    # 입춘 이전이면 전년으로 본다
    if date(y,m,d) < date(y,2,4):
        y -= 1
    idx = (y - 1984) % 60
    return _gz_by_index(idx)

def _month_gz(y:int, m:int, d:int, year_stem:str) -> str:
    """월주: 월지(절입) + 연간 기반 월간 계산."""
    br, month_no = _solar_month_branch(y,m,d)  # 寅=1 … 丑=12
    ys = year_stem
    # 寅월의 천간(월간) 시작 규칙 (연간 5그룹)
    # 甲/己→丙, 乙/庚→戊, 丙/辛→庚, 丁/壬→壬, 戊/癸→甲
    start_map = {0:2, 5:2, 1:4, 6:4, 2:6, 7:6, 3:8, 8:8, 4:0, 9:0}
    s0 = start_map[_stem_idx(ys)]              # 寅월(1월)의 간 인덱스
    s  = (s0 + (month_no-1)) % 10              # 해당 월의 간
    return STEMS[s] + br

def _day_gz(y:int, m:int, d:int) -> str:
    """일주: 1984-02-02(甲子) 기준."""
    anchor = date(1984,2,2)  # 甲子
    delta  = date(y,m,d) - anchor
    idx = delta.days % 60
    return _gz_by_index(idx)

def _time_gz(day_stem:str, hh:int, mm:int) -> tuple[str,bool]:
    """시주(+30분 보정, 子시 야/조 분리).
       반환: (時柱간지, is_ya)  is_ya=True → 야자시(전날 子)"""
    # +30분 보정(교재 규칙)
    dt = datetime(2000,1,1,hh,mm) + timedelta(minutes=30)
    H  = dt.hour

    # 子(23~01) 분리: 23:30~00:29 → 야자, 00:30~01:29 → 조자
    is_ya = False
    if   23 <= H or H < 1: br = "子"
    elif 1 <= H < 3:       br = "丑"
    elif 3 <= H < 5:       br = "寅"
    elif 5 <= H < 7:       br = "卯"
    elif 7 <= H < 9:       br = "辰"
    elif 9 <= H < 11:      br = "巳"
    elif 11 <= H < 13:     br = "午"
    elif 13 <= H < 15:     br = "未"
    elif 15 <= H < 17:     br = "申"
    elif 17 <= H < 19:     br = "酉"
    elif 19 <= H < 21:     br = "戌"
    else:                  br = "亥"

    # 야/조자시 플래그
    if br == "子":
        # +30 적용된 시각 기준으로 23≤H<24 → 야자, 0≤H<1 → 조자
        is_ya = (H >= 23)

    # 시간: (일간 인덱스*2 + ‘시지 인덱스’) % 10
    s_idx = (_stem_idx(day_stem)*2 + _branch_idx(br)) % 10
    return STEMS[s_idx] + br, is_ya

def get_pillars(y:int, m:int, d:int, hh:int, mm:int, is_lunar:bool=False):
    """양력 입력만 지원. (음력→양력 변환은 외부 만세력/천문 API 필요)"""
    if is_lunar:
        raise ValueError("지금 버전은 음력 입력을 지원하지 않습니다. (양력으로 입력해주세요)")

    y_gz = _year_gz(y,m,d)
    m_gz = _month_gz(y,m,d, y_gz[0])
    d_gz = _day_gz(y,m,d)
    t_gz, is_ya = _time_gz(d_gz[0], hh, mm)

    return {
        "year_gz":  y_gz,
        "month_gz": m_gz,
        "day_gz":   d_gz,
        "time_gz":  t_gz,
        "is_ya":    is_ya,
    }

def five_element_counts(pillars:dict)->dict:
    """4주(년/월/일/시)의 간·지 8글자를 오행으로 환산해 합계."""
    counts = {"木":0,"火":0,"土":0,"金":0,"水":0}
    for key in ("year_gz","month_gz","day_gz","time_gz"):
        gz = pillars[key]
        s, b = gz[0], gz[1]
        counts[STEM_ELEM[s]] += 1
        counts[BR_ELEM[b]]   += 1
    return counts
