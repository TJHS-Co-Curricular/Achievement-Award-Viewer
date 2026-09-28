"""读取 config/work.json：资料总览「活动/工作/比赛」里的「活动」和「工作」怎么算。

维护者 2026-09-28 定（取代之前所有条件）：比赛照原本的判断；服务栏 = 工作；
除了比赛和服务，其他栏目一律算活动。算哪几栏写在 work.json，文件改了会自动重新读取。
「服务（数量）」栏：服务栏条数，但例常（周会等）不算、同一年同一项只算 1 个（work.json「服务（数量）」）。
"""
from __future__ import annotations

import json

from .member_rules import Rule
from .paths import find_config

FILE_NAME = "work.json"
COL_KEYS = {"团内工作/表演": "team", "团内工作": "team", "校内服务": "intSvc", "校外服务": "extSvc",
            "校内活动": "intAct", "校外活动": "extAct", "考章": "badge", "团内荣誉": "honor"}
DEFAULT_WORK = ["校内服务", "校外服务"]
DEFAULT_ACT = ["校内活动", "校外活动", "团内工作/表演", "考章", "团内荣誉"]


def path():
    return find_config(FILE_NAME, "ACHIEVEMENT_WORK_RULES")


class WorkRules:
    def __init__(self, d: dict):
        self.work_cols = [COL_KEYS[c] for c in (d.get("工作的栏目") or DEFAULT_WORK) if c in COL_KEYS]
        self.act_cols = [COL_KEYS[c] for c in (d.get("活动的栏目") or DEFAULT_ACT)
                         if c in COL_KEYS and COL_KEYS[c] not in self.work_cols]
        sv = d.get("服务（数量）") or {}
        self.svc_routine = [Rule(x) for x in sv.get("例常（不算）") or []]
        self.svc_groups = [Rule(x) for x in sv.get("同一类算一个") or []]

    def svc_routine_why(self, text: str):
        """「服务（数量）」：例常的不算 → 返回说明；不是例常 → None"""
        for r in self.svc_routine:
            if r.match(text):
                return r.get("原因") or f"例常（{r.name}），不算服务数量"
        return None

    def svc_group(self, text: str):
        """「服务（数量）」：属于哪一类（同一年同一类只算 1 个）"""
        for r in self.svc_groups:
            if r.match(text):
                return r.name
        return None

    def kind(self, cat: str):
        """这一栏的条目算什么：1 = 工作，3 = 活动，0 = 都不是（比赛、执委、筹委……另外算）"""
        if cat in self.work_cols:
            return 1
        if cat in self.act_cols:
            return 3
        return 0


_cache = {"mtime": None, "path": None, "rules": None}


def get() -> WorkRules:
    try:
        p = path()
    except FileNotFoundError:          # 没有 work.json：服务 = 工作，其它 = 活动
        return WorkRules({})
    m = p.stat().st_mtime_ns
    if _cache["rules"] is None or _cache["path"] != p or _cache["mtime"] != m:
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"work.json 格式有误（第 {e.lineno} 行第 {e.colno} 个字附近）：{e.msg}。"
                             "常见原因：少了逗号、多了最后一个逗号、用了中文引号。") from None
        _cache.update(rules=WorkRules(data), path=p, mtime=m)
    return _cache["rules"]


def fingerprint() -> str:
    try:
        p = path()
        st = p.stat()
        return f"{p}|{st.st_mtime_ns}|{st.st_size}"
    except OSError:
        return ""
