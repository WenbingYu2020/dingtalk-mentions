#!/usr/bin/env python3
"""
skill 入口 — 增量抓取指定分组内所有群的 @我 消息，去重后写入 AI 表格。
用法: python fetch_mentions.py --category-id <id>

业务逻辑在 core.fetcher，此文件仅负责：
1. 把项目根目录加入 sys.path
2. 解析 CLI 参数
3. 初始化日志
4. 调用 core.fetch_mentions 并处理异常
"""

import argparse
import sys
from pathlib import Path

# 项目根 = 本文件往上 2 级
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 强制 UTF-8 输出 + 行缓冲
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True, errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True, errors="replace")
except Exception:
    pass

from core.logging_setup import setup_logging
from core.fetcher import fetch_mentions, FetchError


def main():
    parser = argparse.ArgumentParser(description="抓取分组内 @我 的消息")
    parser.add_argument("--category-id", required=True, help="会话分组 ID")
    args = parser.parse_args()

    logger, log_file = setup_logging(logger_name="fetch")
    print(f"📄 日志文件: {log_file}", flush=True)

    logger.info("=" * 50)
    logger.info("钉钉 @我 消息抓取 启动")
    logger.info("=" * 50)

    try:
        stats = fetch_mentions(category_id=args.category_id, logger=logger)
    except FetchError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
