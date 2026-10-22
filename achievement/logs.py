"""运行日志：logs/app-YYYY-MM-DD.log（每天一个文件，保留天数看 config.ini 的 [log] keep_days，默认 30 天）。

- 启动资料、每次载入的文件数、读取失败的文件、手动调整保存、导出、所有错误都会记下来。
- 黑色窗口只显示警告和错误；--dev 时连每次网页请求也写进日志并显示。
- 程序开着过了午夜，会自动改写到新一天的文件。
- 启动时删掉超过保留天数的 app-YYYY-MM-DD.log（只删这种名字的文件，旧版的 app.log 不会动）。
- 程序意外崩溃时，错误内容也会写进日志，方便排查。
"""
from __future__ import annotations

import datetime as _dt
import logging
import re
import sys
import threading
from pathlib import Path

LOG_NAME = "achievement"
log = logging.getLogger(LOG_NAME)
_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
PREFIX = "app"
_DAILY = re.compile(rf"^{PREFIX}-(\d{{4}})-(\d{{2}})-(\d{{2}})\.log$")
LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING, "error": logging.ERROR}


def file_for(log_dir: Path, day: _dt.date) -> Path:
    return Path(log_dir) / f"{PREFIX}-{day:%Y-%m-%d}.log"


class DailyFileHandler(logging.FileHandler):
    """写进 logs/app-YYYY-MM-DD.log；日期变了就换到新一天的文件。"""

    def __init__(self, log_dir: Path, today=_dt.date.today):
        self.log_dir, self._today = Path(log_dir), today
        self.day = today()
        super().__init__(file_for(self.log_dir, self.day), encoding="utf-8", delay=True)

    def emit(self, record):
        d = self._today()
        if d != self.day:
            self.acquire()
            try:
                self.close()
                self.day = d
                self.baseFilename = str(file_for(self.log_dir, d).resolve())
            finally:
                self.release()
        super().emit(record)


def cleanup(log_dir: Path, keep_days: int, today: _dt.date | None = None) -> list[Path]:
    """删掉超过 keep_days 天的 app-YYYY-MM-DD.log，返回删掉的文件。其它文件一律不动。"""
    today = today or _dt.date.today()
    cutoff = today - _dt.timedelta(days=keep_days)
    removed = []
    for p in Path(log_dir).glob(f"{PREFIX}-*.log"):
        m = _DAILY.match(p.name)
        if not m:
            continue
        try:
            day = _dt.date(*map(int, m.groups()))
        except ValueError:
            continue
        if day < cutoff:
            try:
                p.unlink()
                removed.append(p)
            except OSError as e:
                log.warning("删不掉旧日志 %s：%s", p, e)
    return removed


def setup(log_dir: Path, dev: bool = False, level: str = "info", keep_days: int = 30) -> Path | None:
    """设置日志。返回今天的日志文件路径（无法写入时返回 None，程序照常运行）。"""
    file_level = logging.DEBUG if dev else LEVELS.get(level, logging.INFO)
    root = logging.getLogger()
    root.setLevel(min(file_level, logging.INFO if dev else logging.WARNING))
    for h in list(root.handlers):
        root.removeHandler(h)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO if dev else logging.WARNING)
    console.setFormatter(logging.Formatter(" [%(levelname)s] %(message)s"))
    root.addHandler(console)

    path, removed = None, []
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        removed = cleanup(log_dir, keep_days)
        fh = DailyFileHandler(log_dir)
        fh.setLevel(file_level)
        fh.setFormatter(logging.Formatter(_FMT, "%Y-%m-%d %H:%M:%S"))
        root.addHandler(fh)
        path = Path(fh.baseFilename)
    except OSError as e:   # 例：程序放在只读的位置
        log.warning("无法写入日志文件夹 %s：%s", log_dir, e)
        path = None
    if removed:
        log.info("已删除 %d 个超过 %d 天的旧日志", len(removed), keep_days)

    # 网页请求记录（werkzeug）：平时只记警告，--dev 或 level = debug 时每次请求都记
    logging.getLogger("werkzeug").setLevel(logging.INFO if dev or file_level <= logging.DEBUG else logging.WARNING)

    def _hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("程序意外出错", exc_info=(exc_type, exc, tb))

    sys.excepthook = _hook
    threading.excepthook = lambda a: _hook(a.exc_type, a.exc_value, a.exc_traceback)
    return path
