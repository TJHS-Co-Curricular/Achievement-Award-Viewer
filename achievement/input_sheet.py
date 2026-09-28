"""「资料总览」页：把学生列表的统计，按学校「高三最高成就奖评审」Google 表格的格式排列，
方便复制贴到 Google 表格。

- 栏位：序、学号、班级、姓名，然后每个年份一组：执委（数量）、中层管理（数量）、筹委（数量）、
  服务（小时）、活动/工作/比赛（例 4/6/2；活动 = 比赛和服务以外的栏目，工作 = 服务栏，见 config/work.json）
- 数字由系统计算，已套用「计入 / 不计」手动调整；该年没有履历的格子放 0，并用红色标出。
- 年份栏预设自动：Result 里最新的年份 = 高三，往前推高二、高一……（config/config.ini 的 [input_sheet] 可改）。
"""
from __future__ import annotations

from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import rules

FIELDS = [
    {"k": "role", "t": "执委", "u": "数量"},
    {"k": "mid", "t": "中层管理", "u": "数量"},
    {"k": "comm", "t": "筹委", "u": "数量"},
    {"k": "hours", "t": "服务", "u": "小时"},
    {"k": "svc", "t": "服务", "u": "数量"},       # 维护者 2026-09-28：例常不算、同一年同一项只算 1 个
    {"k": "awc", "t": "活动/工作/比赛", "u": ""},
]
INFO_COLS = ["序", "学号", "班级", "姓名(中)"]


class _Missing(int):
    """没有资料的年份：值是 0，但要标红"""


MISSING = _Missing(0)


class _MissingText(str):
    """没有资料的年份（活动/工作/比赛那一格）"""


MISSING_AWC = _MissingText("0/0/0")


def newest_year(students) -> int:
    """Result 里最新的年份（= 这一届的高三）；没有资料时用今年"""
    ys = [int(b["year"]) for s in students or [] for b in s.get("blocks", []) if str(b.get("year", "")).isdigit()]
    return max(ys) if ys else date.today().year


def year_columns(settings, students) -> list[tuple[str, str, str]]:
    """[(年份, 显示的年级, 年级)]。自动：最新年份 = 第一个年级（高三），往前推；特别标注（例 2022:MCO）接在后面。"""
    if settings.sheet_years is not None:
        return [(y, lab, lab.split()[0] if lab else "") for y, lab in settings.sheet_years]
    top = newest_year(students)
    out = []
    for i, grade in enumerate(settings.sheet_grades):
        y = str(top - i)
        note = settings.sheet_notes.get(y, "")
        out.append((y, f"{grade} {note}".strip(), grade))
    return out


def sheet_config(settings, students=None) -> dict:
    return {"title": settings.sheet_title, "auto": settings.sheet_years is None,
            "years": [{"y": y, "label": lab, "optional": y in settings.sheet_optional or grade in settings.sheet_optional_grades}
                      for y, lab, grade in year_columns(settings, students)],
            "fields": FIELDS}


def ordered_students(students: list) -> list:
    """和网页同一个顺序：学会代号 → 学号（同一学号只列一次）"""
    seen, out = set(), []
    for s in sorted(students, key=lambda s: (s.get("code") or "~", s.get("sid") or "")):
        sid = s.get("sid") or ""
        if sid and sid not in seen:
            seen.add(sid)
            out.append(s)
    return out


def _field(st: dict, k: str):
    if k == "role":
        return st["roles"]
    if k == "svc":
        return st["svcN"]
    if k == "awc":   # 活动/工作/比赛，例 4/6/2（工作的定义在 config/work.json）
        return f'{st["acts"]}/{st["work"]}/{st["extComp"] + st["intComp"]}'
    v = st[k]
    return int(v) if isinstance(v, float) and v.is_integer() else v


def row_values(s: dict, ov: dict, cfg: dict) -> list:
    years = {str(b["year"]) for b in s["blocks"]}
    out = []
    for y in cfg["years"]:
        if str(y["y"]) not in years:          # 该年没有履历 → 放 0（Excel 里红色标出；留级等可选年份不标红）
            out += [("0/0/0" if f["k"] == "awc" else 0) if y.get("optional") else
                    (MISSING_AWC if f["k"] == "awc" else MISSING) for f in cfg["fields"]]
            continue
        st, _ = rules.compute_stats(s, ov, int(y["y"]))
        out += [_field(st, f["k"]) for f in cfg["fields"]]
    return out


def write_xlsx(students: list, ov: dict, cfg: dict, out) -> int:
    wb = Workbook()
    ws = wb.active
    ws.title = "评审表"
    thin = Side(style="thin", color="999999")
    thick = Side(style="medium", color="000000")
    head_fill = PatternFill("solid", fgColor="FFF2CC")
    miss_fill = PatternFill("solid", fgColor="FDE2E2")
    bold = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    nf = len(cfg["fields"])
    ni = len(INFO_COLS)

    ws["A1"] = cfg["title"]
    ws["A1"].font = Font(bold=True, size=14)
    for i, t in enumerate(INFO_COLS, start=1):
        ws.merge_cells(start_row=2, start_column=i, end_row=3, end_column=i)
        c = ws.cell(row=2, column=i, value=t)
        c.font, c.alignment = bold, center
    col = ni + 1
    for y in cfg["years"]:
        ws.merge_cells(start_row=2, start_column=col, end_row=2, end_column=col + nf - 1)
        c = ws.cell(row=2, column=col, value=f"{y['y']}({y['label']})" if y["label"] else y["y"])
        c.font, c.alignment, c.fill = bold, center, head_fill
        for j, f in enumerate(cfg["fields"]):
            c = ws.cell(row=3, column=col + j, value=f["t"] + (f"\n({f['u']})" if f["u"] else ""))
            c.font, c.alignment, c.fill = Font(bold=True, size=9), center, head_fill
            c.border = Border(left=thick if j == 0 else thin, right=thin, top=thin, bottom=thick)
        col += nf

    rows = ordered_students(students)
    for n, s in enumerate(rows, start=1):
        r = 3 + n
        sid = s.get("sid") or ""
        vals = [n, int(sid) if sid.isdigit() else sid, s.get("cls") or "", s.get("cn") or s.get("en") or ""]
        nums = row_values(s, ov, cfg)
        vals += nums
        req = [v for i, v in enumerate(nums) if not cfg["years"][i // nf].get("optional")]
        none = bool(req) and all(v is MISSING or v is MISSING_AWC for v in req)
        for ci, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=ci, value=int(v) if v is MISSING else str(v) if v is MISSING_AWC else v)
            c.alignment = Alignment(vertical="center", horizontal="left" if ci == 4 else "center")
            if v is MISSING or v is MISSING_AWC or (none and ci <= ni):
                c.fill, c.font = miss_fill, Font(color="C62828", bold=True)
            k = ci - ni - 1
            c.border = Border(left=thick if k >= 0 and k % nf == 0 else thin, right=thin, top=thin, bottom=thin)

    for i, w in enumerate([5, 8, 7, 10], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for i in range(ni + 1, col):
        ws.column_dimensions[get_column_letter(i)].width = 9 if (i - ni - 1) % nf == nf - 1 else 7
    ws.row_dimensions[3].height = 34
    ws.freeze_panes = ws.cell(row=4, column=ni + 1)
    wb.save(out)
    return len(rows)
