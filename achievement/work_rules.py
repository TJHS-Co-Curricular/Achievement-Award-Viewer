"""读取 config/work.json：资料总览「活动/工作/比赛」里的「工作」怎么算。

- 「一、算工作的栏目」里的条目（已计入的）算工作，除非符合「二、例常」
- 「三、活动栏里算工作」：写在活动栏但其实是工作的（例：接待、演出 / 表演）改算工作、不算活动
- 「四、同一类算一个」：同一年同一项 / 同一类工作写了好几次只算 1 个
文件改了会自动重新读取。
"""
from __future__ import annotations

import json

from .member_rules import Rule
from .paths import find_config

FILE_NAME = "work.json"
COL_KEYS = {"团内工作/表演": "team", "团内工作": "team", "校内服务": "intSvc", "校外服务": "extSvc",
            "校内活动": "intAct", "校外活动": "extAct"}
ACT_COLS = ("extAct", "intAct")


def path():
    return find_config(FILE_NAME, "ACHIEVEMENT_WORK_RULES")


class WorkRules:
    def __init__(self, d: dict):
        cols = (d.get("一、算工作的栏目") or {}).get("栏目") or ["团内工作/表演", "校内服务", "校外服务"]
        self.cols = [COL_KEYS[c] for c in cols if c in COL_KEYS]
        self.routine = [Rule(x) for x in d.get("二、例常（不算工作）") or []]
        self.act_work = [Rule(x) for x in d.get("三、活动栏里算工作") or []]
        self.groups = [Rule(x) for x in d.get("四、同一类算一个") or []]

    def group(self, text: str):
        """「四、同一类算一个」：属于哪一类（同一年同一类只算 1 个工作）"""
        for r in self.groups:
            if r.match(text):
                return r.name
        return None

    def judge(self, text: str, cat: str):
        """返回 (是否算工作, 说明)。说明：例常的规则名称 / 活动栏改算工作的规则名称 / None"""
        if cat in ACT_COLS and cat not in self.cols:
            for r in self.act_work:
                if r.match(text):
                    return True, f"{r.name} → 算工作（不算活动）"
            return False, None
        if cat not in self.cols:
            return False, None
        for r in self.routine:
            if r.match(text):
                return False, f"例常（{r.name}），不算工作"
        return True, None


_cache = {"mtime": None, "path": None, "rules": None}


def get() -> WorkRules:
    try:
        p = path()
    except FileNotFoundError:          # 没有 work.json：团内工作 + 服务全部算工作
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
