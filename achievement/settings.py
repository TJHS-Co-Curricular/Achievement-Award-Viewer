"""读取 config/config.ini（网站设定：只限本机 / 局域网、端口、自动开浏览器、Result / 导出位置）。

找不到文件或某一项没写，就用预设值；写错的值会在启动时提示，并改用预设值。
查找位置和规则表一样：exe 旁边的 config/ → exe 旁边 → 打包在 exe 里的 config/（开发时：项目的 config/）。
"""
from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path

from .paths import find_config as find_file

FILE_NAME = "config.ini"


@dataclass
class Settings:
    access: str = "local"          # local / lan
    port: int = 5000
    port_fallback: bool = True
    open_browser: bool = True
    lan_allow_edit: bool = False
    result_folder: str = "Result"
    output_folder: str = "output"
    # 「资料总览」页的年份栏：预设自动（Result 里最新的年份 = 第一个年级，往前推）
    sheet_title: str = "最高成就奖评审"
    sheet_years: list | None = None     # None = 自动；手动时是 [(年份, 年级), ...]
    sheet_grades: list = field(default_factory=lambda: ["高三", "高二", "高一", "初三", "初二", "初一", "留级"])
    sheet_notes: dict = field(default_factory=lambda: {"2022": "MCO"})   # 年份的特别标注，接在年级后面
    sheet_optional: list = field(default_factory=list)                    # 没资料放 0 但不标红的年份
    sheet_optional_grades: list = field(default_factory=lambda: ["留级"])  # 同上，用年级指定（自动时用这个）
    source: Path | None = None
    warnings: list = field(default_factory=list)


def _bool(v, default, name, warn):
    s = str(v).strip().lower()
    if s in ("yes", "y", "true", "1", "on", "是", "开"):
        return True
    if s in ("no", "n", "false", "0", "off", "否", "关"):
        return False
    warn.append(f"{name} = {v} 看不懂（要写 yes 或 no），改用 {'yes' if default else 'no'}")
    return default


def load() -> Settings:
    st = Settings()
    try:
        p = find_file(FILE_NAME, "ACHIEVEMENT_CONFIG")
    except FileNotFoundError:
        return st
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"), interpolation=None)
    try:
        cp.read(p, encoding="utf-8-sig")   # utf-8-sig：记事本存档时加的 BOM 也读得懂
    except configparser.Error as e:
        st.warnings.append(f"config.ini 格式有误，全部改用预设值：{e}")
        return st
    st.source = p
    srv = cp["server"] if cp.has_section("server") else {}
    data = cp["data"] if cp.has_section("data") else {}
    w = st.warnings
    a = str(srv.get("access", st.access)).strip().lower()
    if a in ("local", "lan"):
        st.access = a
    else:
        w.append(f"access = {a} 看不懂（要写 local 或 lan），改用 local")
    try:
        port = int(str(srv.get("port", st.port)).strip())
        if not 1024 <= port <= 65535:
            raise ValueError
        st.port = port
    except ValueError:
        w.append(f"port = {srv.get('port')} 不是 1024~65535 的数字，改用 5000")
    st.port_fallback = _bool(srv.get("port_fallback", "yes"), True, "port_fallback", w)
    st.open_browser = _bool(srv.get("open_browser", "yes"), True, "open_browser", w)
    st.lan_allow_edit = _bool(srv.get("lan_allow_edit", "no"), False, "lan_allow_edit", w)
    st.result_folder = str(data.get("result_folder", st.result_folder)).strip() or "Result"
    st.output_folder = str(data.get("output_folder", st.output_folder)).strip() or "output"
    sh = cp["input_sheet"] if cp.has_section("input_sheet") else {}
    st.sheet_title = str(sh.get("title", st.sheet_title)).strip() or st.sheet_title
    if str(sh.get("years", "auto")).strip().lower() in ("", "auto", "自动"):
        st.sheet_years = None
    else:
        ys = []
        for part in str(sh.get("years")).split(","):
            part = part.strip()
            if not part:
                continue
            y, _, lab = part.partition(":")
            if not y.strip().isdigit():
                w.append(f"input_sheet 的 years 里「{part}」看不懂（要写 年份:年级，例 2026:高三），已略过")
                continue
            ys.append((y.strip(), lab.strip()))
        st.sheet_years = ys or None
    split = lambda v: [x.strip() for x in str(v).replace("，", ",").split(",") if x.strip()]
    if sh.get("grades"):
        st.sheet_grades = split(sh.get("grades"))
    if "year_notes" in sh:
        st.sheet_notes = {}
        for part in split(sh.get("year_notes")):
            y, _, note = part.partition(":")
            if y.strip().isdigit() and note.strip():
                st.sheet_notes[y.strip()] = note.strip()
            else:
                w.append(f"input_sheet 的 year_notes 里「{part}」看不懂（要写 年份:标注，例 2022:MCO），已略过")
    if "optional_years" in sh:
        st.sheet_optional = split(sh.get("optional_years"))
    if "optional_grades" in sh:
        st.sheet_optional_grades = split(sh.get("optional_grades"))
    return st
