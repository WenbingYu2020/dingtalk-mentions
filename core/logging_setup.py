"""
日志初始化，支持:
- 文件输出（DEBUG 及以上，写到 ~/.dingtalk-mentions/logs/fetch_YYYYMMDD_HHMMSS.log）
- stdout 输出（INFO 及以上，供 skill / CLI 场景使用）
- 回调（INFO 及以上，供 GUI 场景使用，每行日志作为字符串回调）

清理策略：每次初始化都会清空旧日志（只保留本次），符合"日志只保留更新抓取时间内的"需求。
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.paths import LOGS_DIR


def setup_logging(
    on_line: Optional[Callable[[str], None]] = None,
    logger_name: str = "fetch",
) -> tuple[logging.Logger, Path]:
    """
    初始化日志。返回 (logger, log_file_path)。

    Args:
        on_line: 可选回调函数，每条 INFO 及以上级别的日志会调用一次，参数为格式化后的字符串。
                GUI 传入此参数以实时接收日志。
        logger_name: logger 名称，默认 "fetch"，setup 场景传 "setup"。
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # 清理历史日志
    for old_log in LOGS_DIR.glob("*.log"):
        try:
            old_log.unlink()
        except OSError:
            pass

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"{logger_name}_{ts}.log"

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    # 文件 handler
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # stdout handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # 回调 handler（供 GUI 使用）
    if on_line is not None:
        class CallbackHandler(logging.Handler):
            def emit(self, record):
                try:
                    on_line(self.format(record))
                except Exception:
                    pass

        ch = CallbackHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger, log_file
