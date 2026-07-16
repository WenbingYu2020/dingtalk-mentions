"""state.json 读写"""

import json

from core.paths import STATE_DIR, STATE_FILE


def load_state():
    """
    加载 state.json，不存在则返回 None。
    调用方负责处理 None（跳转到 setup_table 流程）。
    """
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict):
    """保存 state.json"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
