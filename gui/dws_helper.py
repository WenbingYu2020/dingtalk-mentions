"""
dws 命令包装层 — 为 GUI 提供登录 / 状态检查 / 登出 / 抓取 调用。

抓取和建表直接调用 core 模块（同进程），不再走 subprocess + 外部 python.exe。
登录 / 状态 / 分组列表仍走 dws.exe（这些是钉钉官方 CLI 提供的能力）。
"""

import json
import subprocess
import sys
from pathlib import Path

# 让 gui 目录能作为顶层运行时，也能找到 core/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
# PyInstaller 打包后
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _meipass = str(sys._MEIPASS)
    if _meipass not in sys.path:
        sys.path.insert(0, _meipass)

from core.paths import DWS  # noqa: E402
from core.logging_setup import setup_logging  # noqa: E402
from core.fetcher import fetch_mentions, FetchError  # noqa: E402
from core.table_setup import setup_table, SetupError  # noqa: E402


# ---------- dws.exe 直接调用（登录 / 状态 / 分组） ----------
def _run(args, timeout=120):
    """执行 dws 命令，返回 (success: bool, data: dict | str)"""
    cmd = [DWS] + args + ["--format", "json"]
    try:
        kwargs = dict(
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(cmd, **kwargs)
    except FileNotFoundError:
        return False, "找不到 dws.exe，请先安装 DingTalk Workspace CLI"
    except subprocess.TimeoutExpired:
        return False, "命令执行超时"

    output = result.stdout.strip()
    if result.returncode != 0:
        err = result.stderr.strip() or output or "未知错误"
        return False, err

    try:
        return True, json.loads(output)
    except json.JSONDecodeError:
        return True, output


def check_status():
    """检查登录状态，返回 (logged_in: bool, message: str)"""
    ok, data = _run(["auth", "status"])
    if not ok:
        return False, str(data)
    if isinstance(data, dict):
        authed = data.get("authenticated", False)
        msg = data.get("message", "")
        nick = data.get("nick") or data.get("name") or ""
        if authed:
            return True, f"已登录: {nick}" if nick else "已登录"
        return False, msg or "未登录"
    return False, str(data)


def login():
    """
    启动 dws auth login — 需要浏览器交互，返回 subprocess.Popen 对象。
    """
    cmd = [DWS, "auth", "login"]
    try:
        kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(cmd, **kwargs)
        return proc
    except FileNotFoundError:
        return None


def logout():
    """登出"""
    ok, data = _run(["auth", "logout"])
    return ok, str(data) if not ok else "已退出登录"


def list_categories():
    """获取会话分组列表，返回 (success, list[dict] | str)"""
    ok, data = _run(["chat", "category", "list"])
    if not ok:
        return False, str(data)
    if isinstance(data, list):
        return True, data
    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, dict):
            cats = result.get("categories") or []
            return True, cats
        if isinstance(result, list):
            return True, result
        cats = data.get("categories") or []
        return True, cats
    return True, []


# ---------- 抓取 / 建表（同进程直接调 core） ----------
def run_fetch(category_id, on_output=None):
    """
    直接调用 core.fetch_mentions（同进程），返回 (returncode, stderr_text)。
    on_output 每收到一条日志会被调用一次，用于 GUI 实时显示。
    """
    logger, _log_file = setup_logging(on_line=on_output, logger_name="fetch")
    try:
        fetch_mentions(category_id=str(category_id), logger=logger)
        return 0, ""
    except FetchError as e:
        return 1, str(e)
    except Exception as e:
        logger.exception("抓取过程发生未预期异常")
        return 1, f"未预期异常: {e}"


def run_setup(on_output=None):
    """直接调用 core.setup_table（同进程），返回 (returncode, stderr_text)。"""
    logger, _log_file = setup_logging(on_line=on_output, logger_name="setup")
    try:
        setup_table(logger=logger)
        return 0, ""
    except SetupError as e:
        return 1, str(e)
    except Exception as e:
        logger.exception("建表过程发生未预期异常")
        return 1, f"未预期异常: {e}"
