#!/usr/bin/env python3
"""
skill 入口 — 首次运行：创建 AI 表格 Base、数据表、字段，保存 state.json。

业务逻辑在 core.table_setup，此文件仅负责：
1. 把项目根目录加入 sys.path（因为脚本通过 junction 从 ~/.claude/skills 调用）
2. 初始化日志
3. 调用 core.setup_table 并处理异常
"""

import sys
from pathlib import Path

# junction 让本文件的 __file__ 指向 skills/dingtalk-mentions/setup_table.py，
# 项目根 = 本文件往上 2 级
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 强制 UTF-8 输出，避免 Windows GBK 无法输出 emoji
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True, errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True, errors="replace")
except Exception:
    pass

from core.logging_setup import setup_logging
from core.table_setup import setup_table, SetupError


def main():
    logger, log_file = setup_logging(logger_name="setup")
    print(f"📄 日志文件: {log_file}", flush=True)

    try:
        state = setup_table(logger)
    except SetupError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)

    logger.info("")
    logger.info("✅ 初始化完成!")
    logger.info(f"  Base URL: https://docs.dingtalk.com/i/nodes/{state['base_id']}")


if __name__ == "__main__":
    main()
