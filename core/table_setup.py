"""建表业务逻辑 — 供 GUI / CLI / skill 共用"""

import json
import logging
from typing import Optional

from core.dws import run_dws
from core.paths import STATE_DIR, STATE_FILE
from core.state import save_state

BASE_NAME = "钉钉@我消息汇总"

# 需要建立的业务字段（group_name 复用主字段 primaryDoc，不在这里创建）
FIELDS_CONFIG = [
    {"fieldName": "msg_id", "type": "text"},
    {"fieldName": "sender", "type": "text"},
    {"fieldName": "send_time", "type": "date", "config": {"formatter": "YYYY-MM-DD HH:mm:ss"}},
    {"fieldName": "content", "type": "text"},
    {"fieldName": "images", "type": "attachment"},
    {"fieldName": "raw_json", "type": "text"},
]

# group_name 通过重命名主字段得到，也需要记录 fieldId
TARGET_NAMES = {f["fieldName"] for f in FIELDS_CONFIG} | {"group_name"}


class SetupError(Exception):
    """建表失败异常"""
    pass


def setup_table(logger: Optional[logging.Logger] = None) -> dict:
    """
    创建 AI 表格 Base、重命名主字段、创建业务字段、保存 state.json。
    返回创建后的 state dict。
    失败抛 SetupError。
    """
    log = logger or logging.getLogger("setup")

    # 1. 创建 Base
    log.info("[1/4] 创建 AI 表格 Base...")
    ok, data = run_dws(log, ["aitable", "base", "create", "--name", BASE_NAME], context="创建 Base")
    if not ok:
        raise SetupError(f"创建 Base 失败: {data.get('message', '')}")
    base_id = data.get("baseId") or data.get("id")
    if not base_id:
        raise SetupError(f"创建 Base 失败，未返回 baseId: {json.dumps(data, ensure_ascii=False)}")
    log.info(f"  Base ID: {base_id}")

    # 2. 获取默认数据表
    log.info("[2/4] 获取默认数据表...")
    ok, data = run_dws(log, ["aitable", "table", "get", "--base-id", base_id], context="获取数据表")
    if not ok:
        raise SetupError(f"获取数据表失败: {data.get('message', '')}")
    tables = data.get("tables") if isinstance(data, dict) else data
    if not tables:
        raise SetupError("Base 创建后无默认数据表")
    table_id = tables[0].get("tableId") or tables[0].get("id")
    log.info(f"  Table ID: {table_id}")

    # 3. 把主字段重命名为 group_name
    log.info("[3/4] 重命名主字段 -> group_name...")
    ok, data = run_dws(log, ["aitable", "field", "list", "--base-id", base_id, "--table-id", table_id], context="字段列表")
    if not ok:
        raise SetupError(f"获取字段列表失败: {data.get('message', '')}")
    field_list = data.get("fields") if isinstance(data, dict) else data
    primary_id = None
    for f in field_list or []:
        if (f.get("type") or "").lower() == "primarydoc":
            primary_id = f.get("fieldId") or f.get("id")
            break
    if not primary_id:
        raise SetupError("未找到 primaryDoc 主字段")

    ok, _ = run_dws(
        log,
        ["aitable", "field", "update",
         "--base-id", base_id,
         "--table-id", table_id,
         "--field-id", primary_id,
         "--name", "group_name"],
        context="重命名主字段",
    )
    if not ok:
        raise SetupError("重命名主字段失败")
    log.info(f"  主字段 ID: {primary_id}")

    # 4. 批量创建其余字段
    log.info("[4/4] 创建业务字段...")
    fields_json = json.dumps(FIELDS_CONFIG, ensure_ascii=False)
    ok, data = run_dws(
        log,
        ["aitable", "field", "create",
         "--base-id", base_id,
         "--table-id", table_id,
         "--fields", fields_json],
        context="创建字段",
    )
    if not ok:
        raise SetupError(f"创建字段失败: {data.get('message', '')}")

    # 拉一次字段列表，拿到 fieldId 映射
    ok, data = run_dws(log, ["aitable", "field", "list", "--base-id", base_id, "--table-id", table_id], context="确认字段")
    if not ok:
        raise SetupError(f"确认字段列表失败: {data.get('message', '')}")
    field_list = data.get("fields") if isinstance(data, dict) else data
    if not isinstance(field_list, list):
        field_list = []

    fields_map = {}
    for f in field_list:
        name = f.get("fieldName") or f.get("name", "")
        fid = f.get("fieldId") or f.get("id")
        if name in TARGET_NAMES and fid:
            fields_map[name] = fid

    missing = TARGET_NAMES - set(fields_map.keys())
    if missing:
        log.warning(f"以下字段未拿到 fieldId: {missing}")

    # 保存 state.json
    state = {
        "base_id": base_id,
        "table_id": table_id,
        "fields": fields_map,
        "last_run_by_category": {},
    }
    save_state(state)

    log.info("")
    log.info("✅ 初始化完成!")
    log.info(f"  Base URL: https://docs.dingtalk.com/i/nodes/{base_id}")
    log.info(f"  state.json: {STATE_FILE}")

    return state
