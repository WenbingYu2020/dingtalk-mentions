"""路径常量 — 支持环境变量覆盖，方便打包后重定向"""

import os
from pathlib import Path


def _resolve_state_dir() -> Path:
    """
    运行时状态目录，默认 ~/.dingtalk-mentions
    可通过 DINGTALK_MENTIONS_STATE_DIR 环境变量覆盖
    """
    env = os.environ.get("DINGTALK_MENTIONS_STATE_DIR")
    if env:
        return Path(env)
    return Path.home() / ".dingtalk-mentions"


def _resolve_dws_path() -> Path:
    """
    dws.exe 路径，默认 ~/.local/bin/dws.exe
    可通过 DINGTALK_MENTIONS_DWS 环境变量覆盖
    """
    env = os.environ.get("DINGTALK_MENTIONS_DWS")
    if env:
        return Path(env)
    return Path.home() / ".local" / "bin" / "dws.exe"


STATE_DIR = _resolve_state_dir()
STATE_FILE = STATE_DIR / "state.json"
LOGS_DIR = STATE_DIR / "logs"
DOWNLOADS_DIR = STATE_DIR / "downloads"
DWS = str(_resolve_dws_path())
