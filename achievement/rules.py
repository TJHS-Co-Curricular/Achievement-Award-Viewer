"""履历表解析 + 手册计分规则。

所有「怎么算」的规则都集中在这个文件：
  - 类别标题识别（CATS）
  - 执委/职务标准化（classify_role / standard_roles）
  - 获奖识别（is_award）
  - 计分规则 R1~R4（compute_exclusions）
  - 统计（compute_stats）
要改规则，改这里即可。
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

# ---------------------------------------------------------------- 类别
CATS = [
    ("role", "执委/职务", r"^(执委层?/?中层管理/?联课处工委(/?会员)?|执委层?/?中层管理|执委层|学会职务|职务|中层管理|执委)"),
    ("comm", "筹委", r"^(筹委|担任活动筹委|活动筹委|活动职务)"),
    ("extComp", "校外比赛", r"^(参[与加]校外比赛(及|与|以及)奖项|参[与加]校外比赛|校外比赛(及|与|以及)奖项|校外比赛|曾参与社团比赛)"),
    ("intComp", "校内比赛", r"^(参[与加]校内比赛(及|与|以及)奖项|参[与加]校内比赛|校内比赛(及|与|/|以及)(奖项|荣誉)|校内比赛|校内奖项)"),
    ("extAct", "校外活动", r"^(参[与加]校外活动|观看校外活动|校外活动|参与校外/内活动)"),
    ("intAct", "校内活动", r"^(参与校内活动|校内活动)"),
    ("extSvc", "校外服务", r"^(校外服务)"),
    ("intSvc", "校内服务", r"^(校内服务|校内外服务)"),
    ("total", "总服务时数", r"^(总服务时数|服务总时数|服务时数)"),
    ("team", "团内工作/表演", r"^(团内活动的?工作人员(/表演)?|团内工作人员|团内活动|参与团内营会/活动|团内表演|校内演出|校内表演)"),
    ("badge", "考章", r"^(考章|专章)"),
    ("honor", "团内荣誉", r"^(团内荣誉|团内荣耀|学会奖项|荣誉|学术成就|体育奖项)"),
]
CATS_RE = [(k, lab, re.compile(rx)) for k, lab, rx in CATS]
CAT_LABEL = {k: lab for k, lab, _ in CATS}
CAT_LABEL["other"] = "其他（未注明类别）"

# 获奖的判断规则在 config/award.json
EMPTY_RE = re.compile(r"^[\s\-—－–_/无無nN/A.。、:：]*$")
_WS = re.compile(r"[\s 　​-‏⁠-⁯﻿]+")


def norm(s) -> str:
    return _WS.sub("", str(s))


# 职位常见的繁体字 → 简体（只用在认职位，不改学生写的原文；2024 校准：「副總務」）
_T2S = str.maketrans(
    "總務財賬帳書長員組會團課網頁衛紀導顧問監動無隊記錄攝體樂藝術設計傳聯絡處選學習練領幹級屆輔協調劃觀師歡節發備報為議規幫隊員種啟",
    "总务财账帐书长员组会团课网页卫纪导顾问监动无队记录摄体乐艺术设计传联络处选学习练领干级届辅协调划观师欢节发备报为议规帮队员种启")


def to_simplified(s) -> str:
    return str(s).translate(_T2S)


def match_header(text):
    t = norm(text)
    for key, _, rx in CATS_RE:
        m = rx.match(t)
        if not m:
            continue
        rest = t[m.end():]
        if re.match(r"^[：:]", rest):
            return key, re.sub(r"^[^：:]*[：:]", "", str(text), count=1).strip()
        if rest == "":
            return key, ""
        return None
    return None


_HOURS_ONLY = re.compile(r"\s*\d{2,}[.．]\d+\s*(小时|[Hh](ours?|rs?)?)?[。.]?\s*")


def strip_num(s) -> str:
    # 「26.5小时」这种两位数以上的小数是时数，不是编号「26.」（2026 校准：罗羽筒 26.5 被读成 5）；
    # 「1.18小时」「1.2026年……」仍当作编号 1. 处理（和以前一样）
    if _HOURS_ONLY.fullmatch(str(s)):
        return str(s).strip()
    return re.sub(r"^\s*(\d{1,2}\s*[.．、)）]|\d{1,2}\s+(?!小时|分|个|[HhMm])(?=\D)|[•·●▪\-–—]\s*(?=\S))\s*", "", str(s), count=1).strip()


_HOURS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:个)?\s*((?i:小时|hours?|hrs?|h\b))(?:\s*(\d+(?:\.\d+)?)\s*分钟?)?|(\d+(?:\.\d+)?)\s*(?:分钟|(?i:mins?\b)|M\b)")
# 「60M / 120M」这类写法只取斜线前的数字
_HOURS_DENOM = re.compile(r"/\s*\d+(?:\.\d+)?\s*(?:小时|分钟|mins?\b|M\b|hours?|hrs?|h\b)", re.I)


_CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_HOURS = re.compile(r"([零一二两三四五六七八九十]{1,4})(个半|个|)(小时|分钟)")


def _cn_to_int(w):
    if "十" in w:
        a, _, b = w.partition("十")
        return (_CN_NUM.get(a, 1) if a else 1) * 10 + (_CN_NUM.get(b, 0) if b else 0)
    n = 0
    for ch in w:
        n = n * 10 + _CN_NUM[ch]
    return n


def _cn_hours(s):
    """「四小时」「一个半小时」「三十分钟」→ 阿拉伯数字（2024 校准：汪威俊）"""
    def f(m):
        n = _cn_to_int(m.group(1)) + (0.5 if m.group(2) == "个半" else 0)
        return f"{n:g}{m.group(3)}"
    return _CN_HOURS.sub(f, s)


_MULT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(小时|[Hh](?:ours?|rs?)?)\s*[×xX*]\s*(\d+)\s*(?:天|次|日|场|晚)?(\s*[=＝]\s*(?=\d))?")


def _mult_hours(s):
    """「12小时×2天」→ 24小时；「8小时*3天=24小时」→ 只取等号后面的 24小时（2024 校准：舞蹈团）"""
    def f(m):
        if m.group(4):
            return ""
        return f"{float(m.group(1)) * int(m.group(3)):g}小时"
    return _MULT_RE.sub(f, s)


def parse_hours(s):
    s = _mult_hours(_cn_hours(str(s)))
    vals = []
    for m in _HOURS_RE.finditer(_HOURS_DENOM.sub("", str(s))):
        if m.group(1):
            vals.append(float(m.group(1)) + (float(m.group(3)) / 60 if m.group(3) else 0))
        elif m.group(4):
            vals.append(float(m.group(4)) / 60)
    if not vals:
        return None
    # 「11h，筹备6h，活动5h」：第一个是总数、后面是细分（加起来刚好等于总数）→ 只算总数
    if len(vals) > 2 and abs(vals[0] - sum(vals[1:])) < 0.02:
        return round(vals[0], 2)
    return round(sum(vals), 2)


def year_of(v):
    if v is None:
        return None
    if isinstance(v, (int, float)) and 2000 < v < 2100:
        return int(round(v))
    m = re.search(r"20\d\d", str(v))
    return int(m.group()) if m else None


def _s(v) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


# ---------------------------------------------------------------- 解析一张表
def _declared_total(parts):
    """「总服务时数」一格里有好几个数字时怎么算：
    - 同一个数字重复写（例：标题「总服务时数：168小时」下面又写「1. 168小时」）→ 只算一次
    - 第一个数字 = 后面几个相加（例：「总服务时数：168小时」下面写「校内 100小时」「校外 68小时」）→ 只算第一个
    - 其它情况（例：分开写校内、校外时数）→ 相加"""
    if len(parts) > 1 and all(abs(x - parts[0]) < 1e-6 for x in parts):
        return parts[0]
    if len(parts) > 2 and abs(parts[0] - sum(parts[1:])) < 1e-6:
        return parts[0]
    return sum(parts)


def parse_rows(rows, is_pdf=False):
    yi, hi = 0, -1
    for r in range(min(len(rows), 30)):
        row = rows[r] or []
        j = next((j for j, v in enumerate(row) if v is not None and norm(v) == "年份"), -1)
        if j >= 0:
            yi, hi = j, r
            break
    ci, ki, di = yi + 1, yi + 2, yi + 3
    meta = {}
    for r in range(hi if hi >= 0 else min(6, len(rows))):
        txt = " ".join(_s(v) for v in (rows[r] or []) if v is not None)
        m = re.search(r"姓名[：:]\s*([^\s班学]+(?:\s+[A-Za-z][A-Za-z \-]*)?)", txt)
        if m:
            meta["name"] = m.group(1).strip()
        m = re.search(r"班级[：:]\s*([A-Za-z0-9]+)", txt)
        if m:
            meta["cls"] = m.group(1)
        m = re.search(r"学号[：:]\s*(\d{4,6})", txt)
        if m:
            meta["sid"] = m.group(1)

    blocks = []
    st = {"blk": None, "cat": None, "last": None, "lastYear": None, "lastCls": None, "rowYear": False}

    def new_block(year, cls, club):
        st["blk"] = {"year": year, "cls": cls, "club": club, "cats": {}, "declaredTotal": None}
        blocks.append(st["blk"])
        st["cat"], st["last"] = None, None

    def add_item(text):
        t = strip_num(text)
        if not t or EMPTY_RE.match(t):
            st["last"] = None
            return
        if st["blk"] is None:
            new_block(st["lastYear"], st["lastCls"], "")
        if t == "0" or re.fullmatch(r"[（(]?(未入学|未入校|尚未入学)[）)]?", t):
            return
        if re.fullmatch(r"[^\d：:，,。]{1,8}[：:]", t):   # 不认识的小标题（例：「相关活动：」）只是标题，不是一项
            st["last"] = None
            return
        k = st["cat"] or "other"
        if k == "other":
            if re.search(r"执委|干部|主席|财政|秘书|总务|查账|^(会员|团员|队员)$", t) and "筹委" not in t:
                k = "role"
            elif re.search(r"筹委|筹主", t):
                k = "comm"
        blk = st["blk"]
        if k == "total":
            h = _total_value(t)
            # 「8.5小时」「6.0小时」：strip_num 会把「8.」当成编号 → 两种读法都留着，最后按逐项相加选比较接近的
            raw = _total_value(str(text).strip())
            alt = raw if raw is not None and h is not None and abs(raw - h) > 1e-9 else None
            if re.search(r"\d[.．]\d+\s*小时\s*\d+\s*分", str(text)):   # 「1.20小时 55分钟」= 编号 1. + 20小时55分钟
                alt = None
            if alt is not None and not re.match(r"^\s*1\s*[.．]", str(text)):
                h, alt = alt, h          # 预设：开头不是「1.」的当小数（1.18小时 仍当编号 1.）
            if h is not None:
                blk.setdefault("totalParts", []).append(h)
                blk.setdefault("totalAlts", []).append(alt)
                blk["declaredTotal"] = _declared_total(blk["totalParts"])
            st["last"] = None
            return
        blk["cats"].setdefault(k, []).append(t)
        st["last"] = (k, len(blk["cats"][k]) - 1)
        m = re.match(r"^\s*(\d{1,2})\s*[.．、)）]", str(text))
        st["lastNum"] = (id(blk), k, int(m.group(1))) if m else None

    def split_lines(s):
        return [x.strip() for x in re.split(r"\r?\n|\r", str(s)) if x.strip()]

    def handle_text(text):
        h = match_header(text)
        if h:
            blk = st["blk"]
            if blk is not None and not st["rowYear"] and h[0] == "role" and blk["cats"].get("role") and st["cat"] != "role":
                # 同一格局里栏目又从头出现、这一行却没写年份：可能是下一年的年份写在后面（李如意）。
                # 先开一个「暂定」格；等到年份行出现就归那一年，一直没有年份就并回上一格。
                new_block(None, blk["cls"], blk["club"])
                st["blk"]["provisional"] = True
            st["cat"], st["last"] = h[0], None
            if h[1]:
                for l in split_lines(h[1]):
                    handle_line(l)
            return True
        return False

    def handle_line(line):
        if match_header(line):
            handle_text(line)
            return
        if is_pdf and st["last"] and not re.match(r"^\s*\d{1,2}\s*[.．、]", line) and not EMPTY_RE.match(line):
            k, i = st["last"]
            st["blk"]["cats"][k][i] += line
            return
        add_item(line)

    if hi >= 0 and _is_table_layout(rows[hi]):
        return meta, _finish_blocks(_parse_table_layout(rows, hi, yi, handle_line, new_block, st, blocks))

    for r in range(hi + 1, len(rows)):
        row = rows[r] or []
        get = lambda i: row[i] if i < len(row) else None
        if hi < 0 and _is_meta_row(row):   # 没有「年份」表头时，标题行 / 姓名班级行不是资料
            continue
        y = year_of(get(yi))
        club = _s(get(ki)).strip() if get(ki) is not None and _s(get(ki)).strip() else None
        cls = _s(get(ci)).strip() if get(ci) is not None and _s(get(ci)).strip() else None
        blk = st["blk"]
        st["rowYear"] = bool(y)
        first = next((_s(v) for v in row[di:] if v is not None and _s(v).strip()), "")
        starts_cycle = bool(match_header(re.sub(r"[\r\n]+", "", first))) and match_header(re.sub(r"[\r\n]+", "", first))[0] == "role"
        if (not y and cls and blk is not None and blk.get("cls") and re.fullmatch(r"[JSjs]\d.*", cls)
                and norm(cls) != norm(blk["cls"]) and st["lastYear"] and blocks and blocks[-1]["year"]):
            # 没写年份、但班级换了（例：S3S1 → S2S1）：是上一年，年份按顺序往前推（2026 校准：罗羽筒）
            y = st["lastYear"] - 1
            st["rowYear"] = True
        if y and blk is not None and blk["year"] is None and not starts_cycle and (blk.get("provisional") or not any(b["year"] for b in blocks)):
            # 年份那一行写在中间（例：前面几栏先写，年份和班级、学会写在「校外服务」那一行）：
            # 前面没有年份的条目就属于这一年（2024 校准：李如意）
            st["lastYear"] = y
            st["lastCls"] = cls or st["lastCls"]
            blk.update(year=y, cls=cls, club=club or blk["club"])
            blk.pop("provisional", None)
        elif y:
            # 年份写在下一行（梁嘉谦）：年份那一行的内容其实是上一年的延续——
            # 例如上一年「总服务时数：」下面的数字，或上一年编号 1、2、3 之后的第 4 项 → 先放回上一年
            if blk is not None and st["cat"] and first and not match_header(re.sub(r"[\r\n]+", "", first)):
                m = re.match(r"^\s*(\d{1,2})\s*[.．、)）]", first)
                ln = st.get("lastNum")
                cont = (st["cat"] == "total" and blk.get("declaredTotal") is None and _total_value(strip_num(first)) is not None) or \
                       (m and ln and ln[0] == id(blk) and ln[1] == st["cat"] and int(m.group(1)) == ln[2] + 1)
                if cont:
                    for c2 in range(di, len(row)):
                        if row[c2] is not None and _s(row[c2]).strip():
                            for l in split_lines(_s(row[c2])):
                                handle_line(l)
                            break
                    row = list(row)
                    for c2 in range(di, len(row)):
                        if row[c2] is not None and _s(row[c2]).strip():
                            row[c2] = None
                            break
            st["lastYear"] = y
            st["lastCls"] = cls or st["lastCls"]
            new_block(y, cls, club or (blk["club"] if blk else ""))
        elif club and blk and club != blk["club"] and not re.fullmatch(r"学会|班级|年份", club):
            new_block(st["lastYear"], cls or st["lastCls"], club)
        row_item = None
        first_c = None
        for c in range(di, len(row)):
            v = row[c]
            if v is None or _s(v).strip() == "":
                continue
            if first_c is None:
                first_c = c
            s = _s(v)
            flat = re.sub(r"[\r\n]+", "", s)
            whole = match_header(flat)
            lines = split_lines(s)
            if c > first_c and ((whole and whole[0] == "total") or (lines and (match_header(lines[0]) or ("",))[0] == "total")):
                # 右边备注栏写的「总服务时数：82小时」：记下总数，但不要改变这一栏接下来的类别
                # （否则下一行的服务条目会被当成总数；2026：陈永祥、苏爱欣……）
                keep = st["cat"]
                for l in (lines if len(lines) > 1 else [flat]):
                    handle_line(l)
                st["cat"], st["last"] = keep, None
                continue
            if whole and (not whole[1] or not re.search(r"[\r\n]", s)):
                handle_text(flat)
                continue
            if len(lines) > 1 or match_header(lines[0]):
                for l in lines:
                    handle_line(l)
                continue
            if row_item and c > di:  # 同一行右边的格子 = 备注（例如奖项）
                if not EMPTY_RE.match(s):
                    k, i = row_item
                    cur, add = st["blk"]["cats"][k][i], s.strip()
                    # 同一段文字被复制到右边多个格子时（合并格/复制），不要重复接上去
                    if k != "total" and norm(strip_num(add)) not in norm(cur):
                        st["blk"]["cats"][k][i] += " —— " + add
                continue
            if st["cat"] == "total" and not EMPTY_RE.match(s):
                add_item(s)
                continue
            handle_line(s)
            if st["last"]:
                row_item = st["last"]

    return meta, _finish_blocks(blocks)


def _total_value(t):
    h = parse_hours(t)
    if h is None and re.fullmatch(r"\d+(\.\d+)?", norm(t)):
        h = float(norm(t))
    return h


def _pick_total(b, itemized):
    """总服务时数有两种读法（例「8.5小时」= 8.5 还是编号 8. + 5 小时）时，选和逐项相加最接近的那一种。"""
    parts, alts = b.get("totalParts") or [], b.get("totalAlts") or []
    idx = [i for i, a in enumerate(alts) if a is not None][:6]
    if not idx or itemized is None:
        return
    from itertools import product
    best = (abs(_declared_total(parts) - itemized), parts)
    for combo in product([0, 1], repeat=len(idx)):
        if not any(combo):
            continue
        cand = list(parts)
        for i, use in zip(idx, combo):
            if use:
                cand[i] = alts[i]
        d = abs(_declared_total(cand) - itemized)
        if d < best[0] - 1e-9 and d <= 0.5:   # 另一种读法要和逐项相加几乎一样才换
            best = (d, cand)
    b["totalParts"] = best[1]
    b["declaredTotal"] = _declared_total(best[1])


def _finish_blocks(blocks):
    merged = []
    for b in blocks:    # 暂定格一直没等到年份：并回上一格（只是同一格里栏目重复写）
        if b.pop("provisional", None) and b["year"] is None and merged:
            prev = merged[-1]
            for k, v in b["cats"].items():
                prev["cats"].setdefault(k, []).extend(v)
            if b.get("totalParts"):
                prev.setdefault("totalParts", []).extend(b["totalParts"])
                prev.setdefault("totalAlts", []).extend(b.get("totalAlts") or [None] * len(b["totalParts"]))
                prev["declaredTotal"] = _declared_total(prev["totalParts"])
            continue
        merged.append(b)
    blocks = merged
    out = []
    for b in blocks:
        for k in list(b["cats"]):
            b["cats"][k] = [x.strip() for x in b["cats"][k] if x.strip() and not EMPTY_RE.match(x.strip())]
            if not b["cats"][k]:
                del b["cats"][k]
        itemized, anyh = 0.0, False
        for k in ("extSvc", "intSvc"):
            for it in b["cats"].get(k, []):
                h = parse_hours(it)
                if h is not None:
                    itemized += h
                    anyh = True
        b["itemizedHours"] = round(itemized, 2) if anyh else None
        _pick_total(b, b["itemizedHours"])
        # 服务时数：优先用学生自填的「总服务时数」；该年没填才用逐项相加（上级 2026-09-24 定，对没逐项写时数的学生较公平）
        b["hours"] = round(b["declaredTotal"], 2) if b["declaredTotal"] is not None else b["itemizedHours"]
        b.pop("totalParts", None)
        b.pop("totalAlts", None)
        b["club"] = re.sub(r"\s+", " ", _s(b["club"] or "")).strip()
        if b["cats"] or b["hours"]:
            out.append(b)
    return out


def _is_meta_row(row) -> bool:
    txt = norm(" ".join(_s(v) for v in row if v is not None))
    return bool(re.search(r"姓名[：:]|学号[：:]|个人表现履历表$", txt))


def _is_table_layout(header_row) -> bool:
    """另一种履历表格式：年份 | 活动 | 身份 | 性质 | 服务时数 | 备注（每行一项，「性质」写栏目）"""
    vals = [norm(_s(v)) for v in (header_row or []) if v is not None]
    return "性质" in vals and "活动" in vals


def _parse_table_layout(rows, hi, yi, handle_line, new_block, st, blocks):
    """表格式履历表（2024 校准：谢咏恩）：把每一行转成「栏目：活动-身份（N小时）」再用一般流程处理。
    「性质」写了两个栏目时：有时数就放服务栏，没有就放第一个。"""
    hdr = {norm(_s(v)): j for j, v in enumerate(rows[hi] or []) if v is not None}
    ai, ri, ti = hdr.get("活动"), hdr.get("身份"), hdr.get("性质")
    hri = next((j for k, j in hdr.items() if "时数" in k), None)
    bi = hdr.get("备注")
    for r in range(hi + 1, len(rows)):
        row = rows[r] or []
        get = lambda i: (_s(row[i]).strip() if i is not None and i < len(row) and row[i] is not None else "")
        y = year_of(row[yi] if yi < len(row) else None)
        if y:
            st["lastYear"] = y
            new_block(y, None, "")
        act = get(ai)
        if not act:
            continue
        if match_header(act):          # 例：「总服务时数：260小时」写在最后 = 全部年份的总数，不是某一年的，不用
            continue
        if st["blk"] is None:
            new_block(st["lastYear"], None, "")
        # 「团内活动的工作人员/表演」本身含斜线：整格先试一次
        whole = match_header(get(ti))
        if whole:
            cats = [whole]
        else:
            parts = [x.strip() for x in re.split(r"[,，]", get(ti)) if x.strip()]
            cats = [c for c in (match_header(x) for x in parts) if c]
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", get(hri))]
        keys = [c[0] for c in cats]
        if nums:
            k = next((k for k in keys if k in ("intSvc", "extSvc")), keys[0] if keys else "other")
        else:
            k = keys[0] if keys else "other"
        text = act + (f"-{get(ri)}" if get(ri) else "")
        if get(bi):
            text += f"（{get(bi).replace(chr(10), ' ').strip()}）"
        if nums and k in ("intSvc", "extSvc"):
            text += f"（{sum(nums):g}小时）"
        st["cat"], st["last"] = k, None
        st["blk"]["cats"].setdefault(k, []).append(text)
    return blocks


def parse_filename(fn: str) -> dict:
    base = re.sub(r"\.(xlsx|pdf)$", "", fn, flags=re.I)
    out = {}
    m = re.match(r"^\s*([A-Z]\d{2}|0\d{2})[\s_\-]+", base, re.I)
    if m:
        out["code"] = m.group(1).upper()
    m = re.search(r"(?:^|[\s_\-])(\d{5})(?=[\s_\-成]|$)", base)
    if m:
        out["sid"] = m.group(1)
    who = base.split(" - ")[-1]
    m = re.match(r"^([㐀-鿿\U00020000-\U0002FFFF]+)-(.+)$", who)
    if m:
        out["cn"], out["en"] = m.group(1), re.sub(r"\(\d+\)$", "", m.group(2)).strip()
    else:
        out["en"] = re.sub(r"\(\d+\)$", "", who).strip()
    return out


# ---------------------------------------------------------------- 执委/职务标准化（手册）
# 「什么职位算什么」全部写在 config/member_rules.json（四、职位归类），这里只负责照表执行。
# 下面只保留文字处理的细节：判断正/副、去掉年份和学会名、把一条拆成几个职位等。
from . import member_rules as MR

_P = r"(?:^|(?<=[正副委会团队社·—\-：:（(]))"
# 标准职称的细节写法（名称来自 member_rules.json 的「标准职称」；这里补上「不要误认成 XX股 / XX小组」的细节）
# 标准职称后面不能接的字（避免把「秘书股」「主席团」当成职称）
_TITLE_AFTER = {"主席": r"(?![股团])", "秘书": r"(?!股|小组|组)", "事务": r"(?!股)", "财政": r"(?!股|小组|组)", "总学长": "", "查账": r"(?!股)"}
_TITLE_NOPREFIX = {"总学长", "查账"}   # 这两个前面接什么字都算


def _title_rx(name, R=None):
    """标准职称的比对方式；「同等写法」（member_rules.json）里的写法也算同一个职称，例：事物、总务 = 事务"""
    alts = (R.title_alias.get(name) if R else None) or [name]
    words = "(?:" + "|".join(map(re.escape, alts)) + ")"
    after = _TITLE_AFTER.get(name, r"(?!股)")
    pre = "" if name in _TITLE_NOPREFIX else _P
    return re.compile(pre + words + after), words


def _side(t, title):
    m = re.search(r"(正|副)(?:执委)?" + title, t)
    if m:
        return m.group(1)
    a = re.search(title + r"(?:股)?[（(](正|副)[）)]", t)
    return a.group(1) if a else ""


def _no_side(t):
    """没写正/副 → 当作正（做法 A）。保留函数名以便日后改规则。"""
    return "正"


def clean_role(t, club_name):
    club = re.sub(r"^[A-E]\d{2}", "", norm(club_name or ""))
    parts = []
    for p in re.split(r"——|--|—|－|–|-|：|:", t):
        p = re.sub(r"^担任", "", p)
        p = re.sub(r"\d{2,4}/\d{2,4}(年度|届|年)?", "", p)
        p = re.sub(r"20\d\d(年度|年|届)?", "", p)
        p = re.sub(r"循人中学|联课活动", "", p)
        if club:
            p = p.replace(club, "")
        p = re.sub(r"执委层|中层管理|中层干部", "", p).replace("执委", "")
        p = re.sub(r"^[A-E]\d{2}", "", p)
        p = re.sub(r"^(的|之)", "", p).strip().lstrip("，,、;；。.")
        if p and not re.fullmatch(r".{0,8}(学会|团|队|社)", p) and not re.fullmatch(r"[\d.、]+", p):
            parts.append(p)
    return "·".join(parts).strip("·")


MID_SPLIT = re.compile(r"[+＋、，,/]|兼")


def _mid_label(p, R):
    p = re.sub(r"^会员[（(](.*)[）)]$", r"\1", p.strip())
    m = re.search(r"(总|正|副|小|中|分)?队长", p)
    if m and not any(w in p.lower() for w in R.mid_words if w not in R.captain_words):
        return m.group(0).replace("正队长", "队长")
    return p


def _classify_mid(t, club_name, R):
    """含中层管理职位的一条：拆出中层管理部分；同一条里的其它职位照原规则分类。"""
    c = clean_role(t, club_name) or t
    c = re.sub(r"^会员[（(](.*)[）)]$", r"\1", c)
    full = c.strip("。.· ")
    c = re.sub(r"[（(][^）)]*[）)]", "", c).strip("。.· ") or c   # 去掉「（已取消，但有进行筹备工作）」这类备注
    if not R.has_mid(c):   # 中层字眼只在括号里，如「家族家长（小组组长）」→ 整条算一个
        return {"mid": [full]}
    for w in R.split_words:   # 规则表里标了「拆开」的，如「校内服务负责人：A、B」→ 每项各算 1 个
        if w in c.lower():
            head = c[c.lower().index(w):c.lower().index(w) + len(w)]
            items = [x.strip("·：: ") for x in re.split(r"[、，,；;/]", c[c.lower().index(w) + len(w):]) if x.strip("·：: ")]
            return {"mid": list(dict.fromkeys(f"{head}·{x}" for x in items)) or [head]}
    if re.match(r"(负责)?(监督|督导)", c):   # 「监督壁报股，多媒体，课程…」：整条都是监督的对象，不拆
        return {"mid": [c]}
    parts = [x for x in (p.strip("·").strip() for p in MID_SPLIT.split(c)) if x]
    mids = [_mid_label(p, R) for p in parts if R.has_mid(p)]
    rest = [p for p in parts if not R.has_mid(p)]
    if not mids:
        mids = [_mid_label(c, R)]
    out = {"mid": list(dict.fromkeys(mids))}
    if rest:
        r = classify_role(rest[0], club_name) if len(rest) == 1 else {"other": "、".join(rest)}
        if r:
            for k in ("std", "other"):
                if r.get(k):
                    out[k] = r[k]
    return out


_CTX_DROP = re.compile(r"^[（(]\d+[）)]|学会|执委|^第[一二三四五]$|【[^】]*】")


def _with_context(std, words, t, club_name):
    """标准职称前面还写了别的单位 / 活动（例：「联课处工委联课表扬大会——副总务」）→ 保留下来：
    执委(联课处工委联课表扬大会-事务(副))。用「+」「兼」连着的另一个职位 → 另外算一个执委(…)。"""
    c = re.sub(r"[。.；;，,]+$", "", clean_role(t, club_name) or t)
    m = re.search(r"(?:正|副)?(?:执委)?(?:正|副)?" + words + r"(?:股)?(?:[（(](?:正|副)[）)])?", c)
    if not m:
        return {"std": std}
    before, after = c[:m.start()], c[m.end():]
    clean = lambda x: _CTX_DROP.sub("", x).strip("·-—–－:：+＋、，, ")
    before, after = clean(before), clean(after)
    if not before and not after:
        return {"std": std}
    if re.search(r"[+＋]|兼", c):   # 「财政+联课处工委」：两个职位
        return {"std": std, "other": "、".join(x for x in (before, after) if x)}
    return {"other": "-".join(x for x in (before, std, after) if x)}


def classify_role(raw, club_name=""):
    """执委栏的一条 → {'std': 标准写法} / {'other': 其它职位名} / {'mid': [中层管理职位…]}（可同时有）或 None。
    按 member_rules.json「四、职位归类」从上往下找第一条符合的规则。"""
    R = MR.get()
    t = to_simplified(norm(raw))
    t = re.sub(r"^\d{1,2}[，,、.．]", "", t)
    t = re.sub(r"[。；;，,.]+$", "", t)
    if not t or EMPTY_RE.match(t) or re.fullmatch(r"[（(]?无[）)]?", t):
        return None
    # 「执委层（查账）」：整条写在括号里 → 拿掉外壳；「29/5-31/5」这类日期不是职位的一部分（2024 / 2025 校准）
    t = re.sub(r"^(执委层?|中层管理|执委)[（(](.+)[）)]$", r"\2", t)
    t = re.sub(r"(?<!\d)\d{1,2}/(?:0?[1-9]|1[0-2])(?:\s*[-–~至]\s*\d{1,2}/(?:0?[1-9]|1[0-2]))?(?!\d)", "", t)
    # 年度写在最前面（「2023/2024财政」）、学会名称本身含「小组」（「E02编辑小组——副主席」）：
    # 先拿掉再认标准职称（2024 校准）
    t = re.sub(r"^(\d{2,4}\s*[/／]\s*\d{2,4}|20\d\d)(年度|年|届)?", "", t) or t
    club_n = re.sub(r"^[A-E]\d{2}", "", norm(club_name or ""))
    t_title = t.replace(club_n, "") if len(club_n) >= 2 else t
    rule = R.role_rule(t, club_name)
    kind = rule.get("归类") if rule else None
    if kind == "执委":
        return {"std": rule.get("写法") or rule.name}
    if kind == "主席级":
        w = rule.hit_first(t) or "主席"
        return {"std": f"主席({_side(t, re.escape(w)) or _no_side(t)})"}
    if kind == "中层管理":
        r = _classify_mid(t, club_name, R)
        # 显示成「校内服务负责人-新春快闪」（用「-」连接，不用「·」）
        r["mid"] = list(dict.fromkeys(re.sub(r"\s*·\s*", "-", m) for m in r["mid"]))
        return r
    if kind == "会员":
        return {"std": "会员"}
    if not any(w in t_title.lower() for w in R.not_title):
        for name in R.titles_side + R.titles_plain:
            rx, side_rx = _title_rx(name, R)
            if rx.search(t_title) or rx.search(re.sub(r"^[A-E]\d{2}", "", t_title).lstrip("-—–－:：")):
                std = name if name in R.titles_plain else f"{name}({_side(t, side_rx) or _no_side(t)})"
                return _with_context(std, side_rx, t, club_name)
    c = clean_role(t, club_name)
    if not c or c in ("执委", "执委层"):
        return {"std": "执委"}
    return {"other": c}


def standard_roles_from(classified):
    """同一年同一学会的职务 → (执委标准写法清单, 职务数, 中层清单)。
    其它职位合并成一个「执委(A,B)」（计 A、B 两个）；会员不计职务数；
    中层（助理类、授课人类、队长类）另列，中层数 = 不同中层职位的个数。"""
    std, other, mid = [], [], []
    for r in classified:
        if not r:
            continue
        if r.get("other") and r["other"] not in other:
            other.append(r["other"])
        if r.get("std") and r["std"] not in std:
            std.append(r["std"])
        for m in r.get("mid") or []:
            if m not in mid:
                mid.append(m)
    out = [x for x in std if x != "执委" or not other]
    merged = f"执委({','.join(other)})" if other else None
    if merged:
        out.append(merged)
    if len(out) > 1:
        out = [x for x in out if x != "会员"]
    count = sum(len(other) if x == merged else (0 if x == "会员" else 1) for x in out)
    return out, count, mid


# ---------------------------------------------------------------- 获奖识别
def is_award(s) -> bool:
    """比赛条目算不算获奖 → 规则在 award.json"""
    from . import award_rules
    return award_rules.get().why(s) is not None


# ---------------------------------------------------------------- 计分规则（手册）
# R1 以班级为单位的内容/服务/活动/比赛不计 → 见 member_rules.json「一、不计」
# R2 B 类（体育、学术培训队）整年不计；A/C/D/E 类照算
B_NAME_RE = re.compile(r"培训队|篮球|排球|羽球|足球|乒乓|田径|游泳|辩论|口才|时事常识|数学培训")
# R4 比赛须代表本学会 → 各学会关键词写在 award.json「五、比赛是否代表本学会」


def block_class(b) -> str:
    code = b.get("clubCode") or ""
    if code.startswith("B"):
        return "B"
    if not code and B_NAME_RE.search(b.get("clubName") or b.get("club") or ""):
        return "B"
    return code[:1]


def comp_judge(text, code):
    """比赛是否代表本学会（规则在 award.json）：None=计入；"unsure"=待确认；其它字串=不计原因"""
    from . import award_rules
    return award_rules.get().comp_judge(text, code)


def _work_key(t):
    """判断「同一项服务写了两次」用：去掉时数、日期、括号内容"""
    t = re.sub(r"[（(][^）)]*[）)]", "", str(t))
    t = re.sub(r"\d+(\.\d+)?\s*(小时|个小时|分钟|h|H|hrs?)", "", t)
    t = re.sub(r"\d{1,4}\s*[/.-]\s*\d{1,2}(\s*[/.-]\s*\d{2,4})?", "", t)
    t = re.sub(r"20\d\d\s*年?", "", t)
    t = _simp(t)
    return re.sub(r"(服务|工作)$", "", t)


def _mark_svc(b, seen):
    """资料总览「服务（数量）」（维护者 2026-09-28 定）：b["sc"][栏][i] = 1 算、0 例常不算、2 同一年已算过；
    说明放在 b["wr"]（个人页「详细」显示）。规则在 config/work.json「服务（数量）」。"""
    from . import work_rules
    W = work_rules.get()
    b["sc"] = {}
    for k in ("intSvc", "extSvc"):
        arr = b["cats"].get(k) or []
        if not arr:
            continue
        sc, wr = [], []
        exl = b["ex"].get(k) or [None] * len(arr)
        for i, t in enumerate(arr):
            why = W.svc_routine_why(t)
            if why:
                sc.append(0)
                wr.append(why)
                continue
            v = 1
            if not exl[i] and not b["exBlock"]:
                grp = W.svc_group(t)
                key = f"{b['year']}|{'类:' + grp if grp else _work_key(t)}"
                if len(key) > 6:
                    if key in seen:
                        v, why = 2, (f"同一年「{grp}」已算过，服务数量只算 1 个" if grp else "同一年同一项服务已算过，服务数量只算 1 个")
                    seen[key] = k
            sc.append(v)
            wr.append(why)
        b["sc"][k] = sc
        b["wr"][k] = wr


def _mark_work(b, seen=None):
    """资料总览的「活动 / 工作」（维护者 2026-09-28 定，取代之前所有条件）：
    服务栏的条目 = 工作；除了比赛和服务，其它栏目（活动、团内工作/表演、考章、团内荣誉）一律 = 活动。
    b["wk"][栏][i] = 1 工作 / 3 活动。不计的条目（班级、B 类……）在 compute_stats 里本来就不算。
    算哪几栏在 config/work.json。"""
    from . import work_rules
    W = work_rules.get()
    b["wk"], b["wr"] = {}, {}
    for k, arr in b["cats"].items():
        v = W.kind(k)
        if v and arr:
            b["wk"][k] = [v] * len(arr)
            b["wr"][k] = [None] * len(arr)


def _simp(t):
    t = norm(t)
    t = re.sub(r"^[\d.、，,]+", "", t)
    t = re.sub(r"[。．.，,；;！!“”\"《》()（）\-—–:：]", "", t)
    return re.sub(r"^(参加|参与|代表\S{0,6}参加)", "", t)


# ---------------------------------------------------------------- 执委栏 ↔ 筹委栏 的移动
# 什么要移、什么不计，写在 member_rules.json 的「一、不计」「二、执委栏移到筹委栏」「三、筹委栏移到执委栏」。


def _split_grade_parts(arr):
    """一条里同时写了学会职位和毕联会职位（用逗号隔开）时，拆成两条，只让毕联会那部分不计。"""
    R = MR.get()
    out = []
    for t in arr:
        parts = [p.strip() for p in re.split(r"[，,；;]", t) if p.strip()]
        if len(parts) > 1 and any(R.is_grade(p) for p in parts) and not all(R.is_grade(p) for p in parts):
            out.append("，".join(p for p in parts if not R.is_grade(p)))
            out.extend(p for p in parts if R.is_grade(p))
        else:
            out.append(t)
    return out


def special_label(text, cat=None):
    """特别标记（member_rules.json「五、特别标记」）——只做标记，不改变计分"""
    return MR.get().special_label(norm(text), cat)


def _split_supervise(arr):
    """「执委主席监督成果汇报主席监督《弈德杯》…主席」这种连在一起的，拆成「执委主席」+ 各个「监督…主席」。"""
    out = []
    for t in arr:
        n = norm(t)
        parts = [p for p in re.split(r"(?=监督|督导)", n) if p]
        if len(parts) > 1 and re.fullmatch(r"(执委)?(正|副)?主席|执委(正|副)主席", parts[0]):
            out.extend(parts)
        else:
            out.append(t)
    return out


def _split_mixed_comm(arr, R, col="role"):
    """「A 兼 B」两个职位该放不同栏（一个是筹委、一个是执委 / 中层管理）→ 拆成两条，各自移到该去的栏。
    连接词见 member_rules.json「二」的「拆开连接词」。"""
    if not R.comm_joiners:
        return arr
    rx = re.compile("|".join(map(re.escape, R.comm_joiners)))
    test = R.moves_to_comm if col == "role" else R.moves_to_role
    out = []
    for t in arr:
        parts = [p.strip(" 　。.") for p in rx.split(t) if p.strip(" 　。.")]
        if len(parts) > 1:
            mv = [test(p) for p in parts]
            if any(mv) and not all(mv):
                out.extend(parts)
                continue
        out.append(t)
    return out


def move_event_roles(s):
    R = MR.get()
    for b in s["blocks"]:
        for k in ("role", "comm"):
            if k in b["cats"]:
                b["cats"][k] = _split_grade_parts(b["cats"][k])
        if "role" in b["cats"]:
            b["cats"]["role"] = _split_mixed_comm(_split_supervise(b["cats"]["role"]), R, "role")
        if "comm" in b["cats"]:
            b["cats"]["comm"] = _split_mixed_comm(b["cats"]["comm"], R, "comm")
        roles, comms = b["cats"].get("role", []), b["cats"].get("comm", [])
        team = b["cats"].get("team", [])
        to_comm = [t for t in roles if R.moves_to_comm(t)]
        to_role = [t for t in comms if R.moves_to_role(t)]
        team_role = [t for t in team if R.team_to_role_match(t)]   # 例：礼仪小组组员（上级 2026-09-28）
        if not to_comm and not to_role and not team_role:
            continue
        new_role = [t for t in roles if t not in to_comm] + to_role + team_role
        new_comm = [t for t in comms if t not in to_role] + to_comm
        if team_role:
            new_team = [t for t in team if t not in team_role]
            if new_team:
                b["cats"]["team"] = new_team
            else:
                b["cats"].pop("team", None)
            b["movedTeam"] = team_role
        for k, arr in (("role", new_role), ("comm", new_comm)):
            if arr:
                b["cats"][k] = arr
            else:
                b["cats"].pop(k, None)
        b["movedComm"], b["movedRole"] = to_comm, to_role


def compute_exclusions(s):
    R = MR.get()
    for b in s["blocks"]:
        b["exBlock"] = "B类（体育/学术培训队）不计" if block_class(b) == "B" else None
        b["ex"], b["unsure"] = {}, {}
        for k, arr in b["cats"].items():
            # member_rules.json「一、不计」：班级、毕联会/高三年级组、班级运动会、感恩聚会、运动会义卖……
            b["ex"][k] = [R.exclusion(t, k) for t in arr]

            if k in ("extComp", "intComp"):
                for i, t in enumerate(arr):
                    if b["ex"][k][i]:
                        continue
                    js = [comp_judge(t, c) for c in (b.get("clubCodes") or [b.get("clubCode", "")])] or [comp_judge(t, "")]
                    j = None if None in js else ("unsure" if "unsure" in js else js[0])
                    if j == "unsure":
                        b["unsure"][f"{k}#{i}"] = 1
                    elif j:
                        b["ex"][k][i] = j
    # R3 同年同一比赛写在两个学会 → 只计一次
    seen = {}
    for b in s["blocks"]:
        for k in ("extComp", "intComp"):
            for i, t in enumerate(b["cats"].get(k, [])):
                st = _simp(t)
                if len(st) < 4:
                    continue
                key = f"{b['year']}|{st}"
                if key not in seen:
                    seen[key] = (b, k, i)
                    continue
                p = seen[key]
                if p[0] is b and p[1] == k:
                    # 同一学会同一栏里重复出现（例：不同比赛底下都写「自选南棍—第一名」）→ 各自计算，不当重复
                    continue
                from . import award_rules
                A = award_rules.get()
                own_new = A.own(b.get("clubCode"), t)
                own_old = A.own(p[0].get("clubCode"), t)
                drop, keep = (p, (b, k, i)) if (own_new and not own_old) else ((b, k, i), p)
                db, dk, di = drop
                if not db["exBlock"] and not db["ex"][dk][di]:
                    db["ex"][dk][di] = (f"同一年重复写（{CAT_LABEL.get(keep[1], keep[1])}已有），只计一次" if keep[0] is db
                                        else f"双学会重复，只计入 {keep[0].get('clubCode', '')}{keep[0].get('clubName', '')}")
                seen[key] = keep
    # 预先计算每条的属性，供网页即时重算用
    svc_seen = {}
    for b in s["blocks"]:
        b["aw"] = {k: [is_award(t) for t in b["cats"].get(k, [])] for k in ("extComp", "intComp") if k in b["cats"]}
        b["hr"] = {k: [parse_hours(t) for t in b["cats"].get(k, [])] for k in ("extSvc", "intSvc") if k in b["cats"]}
        _mark_work(b)
        _mark_svc(b, svc_seen)
        b["rc"] = [classify_role(t, b.get("clubName") or b.get("club")) for t in b["cats"].get("role", [])]
        b["nk"] = {k: [norm(t) for t in arr] for k, arr in b["cats"].items()}
        mc, mr = set(b.get("movedComm") or []), set(b.get("movedRole") or [])
        b["mv"] = {}
        sp = {k: [special_label(t, k) for t in arr] for k, arr in b["cats"].items()}
        b["sp"] = {k: v for k, v in sp.items() if any(v)}
        if mc:
            b["mv"]["comm"] = [t in mc for t in b["cats"].get("comm", [])]
        mt = set(b.get("movedTeam") or [])
        if mr or mt:
            b["mv"]["role"] = ["team" if t in mt else (t in mr) for t in b["cats"].get("role", [])]


def item_key(s, b, k, t):
    """手动调整的识别键（网页端用同样的规则，见 template.html 的 itemKey）"""
    return "|".join([str(s["sid"] or s["file"]), str(b["year"] or ""), str(b.get("clubCode") or b.get("clubName") or ""), k, norm(t)])


def item_state(s, b, k, i, ov):
    t = b["cats"][k][i]
    auto = b["exBlock"] or (b["ex"].get(k) or [None] * (i + 1))[i]
    m = (ov or {}).get(item_key(s, b, k, t))
    inc = False if b["exBlock"] else (m == "in" if m else not auto)
    return {"inc": inc, "auto": auto, "manual": None if b["exBlock"] else m,
            "reason": b["exBlock"] or ("手动设为不计" if m == "out" else None if m == "in" else auto),
            "unsure": bool(b["unsure"].get(f"{k}#{i}")) and not m}


def mid_by_block(s, ov=None, year=None):
    bl = [b for b in s["blocks"] if not year or b["year"] == year]
    return [standard_roles_from([b["rc"][i] for i in range(len(b["cats"].get("role", []))) if item_state(s, b, "role", i, ov)["inc"]])[2] for b in bl]


def compute_stats(s, ov=None, year=None):
    bl = [b for b in s["blocks"] if not year or b["year"] == year]
    c = Counter()
    hours = 0.0
    roles_by_block = []
    for b in bl:
        for k, arr in b["cats"].items():
            for i, _ in enumerate(arr):
                x = item_state(s, b, k, i, ov)
                if x["unsure"]:
                    c["unsure"] += 1
                if x["inc"]:
                    c[k] += 1
                    sc = (b.get("sc") or {}).get(k)
                    if sc and sc[i] == 1:
                        c["svcN"] += 1
                    wk = (b.get("wk") or {}).get(k)
                    if wk and wk[i] == 1:
                        c["work"] += 1
                    elif wk and wk[i] == 3:
                        c["acts"] += 1
                    if k in ("extComp", "intComp") and b["aw"][k][i]:
                        c["extAwards" if k == "extComp" else "intAwards"] += 1
        rl, rc, ml = standard_roles_from([b["rc"][i] for i in range(len(b["cats"].get("role", []))) if item_state(s, b, "role", i, ov)["inc"]])
        roles_by_block.append(rl)
        c["roles"] += rc
        c["mid"] += len(ml)
        if b["exBlock"]:
            continue
        # 服务时数 = 该年采用的时数（自填总数优先），再扣掉不计入的服务项的时数
        h = b["hours"] or 0
        for k in ("extSvc", "intSvc"):
            for i, _ in enumerate(b["cats"].get(k, [])):
                if not item_state(s, b, k, i, ov)["inc"] and b["hr"][k][i]:
                    h -= b["hr"][k][i]
        hours += max(0.0, h)
    out = {k: c[k] for k in ("roles", "mid", "comm", "extComp", "intComp", "extAct", "intAct", "extSvc", "intSvc", "team", "badge", "honor", "unsure", "extAwards", "intAwards", "work", "acts", "svcN")}
    out["awards"] = out["extAwards"] + out["intAwards"]
    out["hours"] = round(hours, 2)
    return out, roles_by_block


# ---------------------------------------------------------------- 学生记录
def build_student(file, meta, blocks):
    fn = parse_filename(file)
    blocks.sort(key=lambda b: -(b["year"] or 0))
    latest = blocks[0] if blocks else {}
    code = fn.get("code")
    if not code or code in ("099", "2026"):
        m = re.match(r"^([A-E]\d{2})", latest.get("club") or "")
        if m:
            code = m.group(1)
    cls = next((b["cls"] for b in blocks if b["year"] == latest.get("year") and b["cls"]), None) or meta.get("cls") or ""
    issues = []
    if not blocks:
        issues.append("未能读取任何年份资料")
    if any("other" in b["cats"] for b in blocks):
        issues.append("有未归类的条目")
    return {
        "file": file, "sid": fn.get("sid") or meta.get("sid") or "",
        "cn": fn.get("cn") or (meta.get("name") or "").split(" ")[0], "en": fn.get("en") or "",
        "code": code or "", "club": latest.get("club") or "", "cls": _s(cls).upper(),
        "years": [b["year"] for b in blocks if b["year"]], "blocks": blocks, "issues": issues,
    }


def _richness(s):
    return sum(len(a) for b in s["blocks"] for a in b["cats"].values())


def dedupe(students):
    by = defaultdict(list)
    for s in students:
        by[s["sid"] or s["file"]].append(s)
    out = []
    for arr in by.values():
        arr.sort(key=lambda s: (-_richness(s), len(s["file"])))
        main = arr[0]
        main["otherFiles"] = [x["file"] for x in arr[1:]]
        if len(arr) > 1:
            main["issues"].append(f"有 {len(arr)} 个版本，已采用内容最多的一个")
        out.append(main)
    return out


def finalize(students):
    """统一学会代号/名称，套用计分规则，算出统计。"""
    split = lambda c: (lambda m: (m.group(1), m.group(2).strip()) if m else (None, str(c or "").strip()))(re.match(r"^([A-E]\d{2})\s*(.*)$", str(c or "")))
    code_name, name_code = defaultdict(Counter), defaultdict(Counter)
    for s in students:
        for b in s["blocks"]:
            c, n = split(b["club"])
            code = c or (s["code"] if s["code"] and b is s["blocks"][0] else None)
            if code and n:
                code_name[code][n] += 1
                name_code[n][code] += 1
    top = lambda cnt: cnt.most_common(1)[0][0] if cnt else None
    for s in students:
        for b in s["blocks"]:
            c, n = split(b["club"])
            if not c and n:
                c = top(name_code.get(n, Counter()))
            if c and not n:
                n = top(code_name.get(c, Counter()))
            if not c and n:
                for cc, nn in code_name.items():
                    t = top(nn)
                    if t and len(t) >= 2 and (t in n or n in t):
                        c = cc
                        break
            if not c and not n and re.fullmatch(r"[A-E]\d{2}", s["code"] or ""):
                c = s["code"]
            b["clubCode"] = c or ""
            b["clubName"] = n or b["club"] or (top(code_name.get(c, Counter())) if c else "") or ""
            # 一格写了两个学会（「合唱团/学长团」）：比赛是否代表本学会时两个都算（2024-2026 校验）
            codes = [b["clubCode"]] if b["clubCode"] else []
            for part in re.split(r"[/、+＋，,&]", str(b["club"] or "")):
                pc, pn = split(part)
                if not pc and pn:
                    pc = top(name_code.get(pn, Counter()))
                    if not pc:
                        for cc, nn in code_name.items():
                            t = top(nn)
                            if t and len(t) >= 2 and len(pn) >= 2 and (t in pn or pn in t):
                                pc = cc
                                break
                if pc and pc not in codes:
                    codes.append(pc)
            b["clubCodes"] = codes
        if not re.fullmatch(r"[A-E]\d{2}", s["code"] or ""):
            s["code"] = s["blocks"][0]["clubCode"] if s["blocks"] else ""
        move_event_roles(s)
        compute_exclusions(s)
        s["special"] = sorted({x for b in s["blocks"] for v in b["sp"].values() for x in v if x})
        st, rbb = compute_stats(s)
        for b, rl in zip(s["blocks"], rbb):
            b["roleStd"] = rl
        s["stats"] = st
        s["roleLatest"] = next(("、".join(rl) for rl in rbb if rl), "")
        s["club"] = top(code_name.get(s["code"], Counter())) or (s["blocks"][0]["clubName"] if s["blocks"] else "")
        seen = []
        for b in s["blocks"]:
            x = ((b["clubCode"] + " ") if b["clubCode"] else "") + b["clubName"]
            if x.strip() and x not in seen:
                seen.append(x)
        s["clubs"] = seen
    students.sort(key=lambda s: (s["code"], s["sid"]))
    return students
