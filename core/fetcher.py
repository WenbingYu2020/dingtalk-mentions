"""抓取业务逻辑 — 供 GUI / CLI / skill 共用"""

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.dws import run_dws
from core.paths import STATE_DIR
from core.state import load_state, save_state

TZ_CN = timezone(timedelta(hours=8))
LOOKBACK_DAYS = 2
MAX_PROCESSED_IDS = 5000
TRIM_TO = 3000


class FetchError(Exception):
    """抓取失败异常"""
    pass


# ---------- 用户身份 ----------
def _ensure_user_identity(state: dict, logger: logging.Logger) -> str:
    """确保 state 里有 user_identity.nick，没有则从 dws 获取。返回 nick。"""
    identity = state.get("user_identity")
    if identity and identity.get("nick"):
        logger.info(f"当前用户: {identity['nick']}")
        return identity["nick"]

    logger.info("获取当前用户身份...")
    ok, data = run_dws(logger, ["contact", "user", "me"], context="用户身份")
    if not ok:
        raise FetchError(f"无法获取用户身份: {data.get('message')}")

    nick = ""
    user_id = ""
    if isinstance(data, list) and data:
        model = data[0].get("orgEmployeeModel", {})
        nick = model.get("orgUserName", "")
        user_id = model.get("userId", "")
    elif isinstance(data, dict):
        model = data.get("orgEmployeeModel", data)
        nick = model.get("orgUserName") or model.get("name", "")
        user_id = model.get("userId", "")

    if not nick:
        raise FetchError("无法从 dws contact user me 中解析出用户昵称")

    state["user_identity"] = {"nick": nick, "userId": user_id}
    save_state(state)
    logger.info(f"当前用户: {nick} (userId={user_id})")
    return nick


# ---------- @我 匹配 ----------
def _build_mention_pattern(nick: str) -> re.Pattern:
    """构建 @我 的正则：@nick 后跟分隔符或结尾"""
    escaped = re.escape(nick)
    return re.compile(r"@" + escaped + r"(?![A-Za-z0-9_])")


# ---------- 拉取 ----------
def _get_conversations_in_category(logger: logging.Logger, category_id: str) -> list:
    """拉取分组下所有会话"""
    ok, data = run_dws(
        logger,
        ["chat", "category", "list-conversations", "--category-id", str(category_id)],
        context="分组会话列表",
    )
    if not ok:
        logger.error(f"⚠ 加载分组会话失败: {data.get('message')}")
        return []
    convs = data.get("conversations") if isinstance(data, dict) else data
    return convs if isinstance(convs, list) else []


def _fetch_group_messages(logger: logging.Logger, group_id: str, start_time_str: str, stats: dict) -> list:
    """翻页拉取某群从 start_time 到现在的所有消息。返回消息列表。"""
    all_messages = []
    current_time = start_time_str
    page = 0

    while True:
        page += 1
        ok, data = run_dws(
            logger,
            ["chat", "message", "list",
             "--group", group_id,
             "--time", current_time,
             "--direction", "newer",
             "--limit", "200"],
            retry=1,
            context=f"群消息 page={page}",
        )
        if not ok:
            err_code = str(data.get("code", ""))
            err_msg = data.get("message", "")
            if (
                "RightsDenied" in err_code
                or "Forbidden" in err_code
                or "AUTH_PERMISSION_DENIED" in err_msg
                or err_code == "1001"
            ):
                stats["perm_skip"] += 1
                logger.warning("  ⚠ 权限不足，跳过该群")
            elif "TIMEOUT" in err_code:
                stats["timeout_skip"] += 1
                logger.warning("  ⚠ 超时，跳过该群")
            else:
                stats["other_errors"] += 1
                logger.warning(f"  ⚠ {err_msg[:120]}")
            break

        messages = data.get("messages") or []
        if not messages:
            break

        all_messages.extend(messages)

        has_more = data.get("hasMore", False)
        if not has_more:
            break

        last_time = messages[-1].get("createTime", "")
        if not last_time or last_time == current_time:
            break
        current_time = last_time
        time.sleep(0.3)

    return all_messages


# ---------- 写入 AI 表格 ----------
def _create_record(logger: logging.Logger, state: dict, record_data: dict, stats: dict) -> bool:
    """往 AI 表格写一条记录，返回 True/False"""
    base_id = state["base_id"]
    table_id = state["table_id"]
    fields = state["fields"]

    cells = {}
    for key, value in record_data.items():
        field_id = fields.get(key)
        if field_id and value is not None:
            cells[field_id] = value

    records_json = json.dumps([{"cells": cells}], ensure_ascii=False)
    tmp_file = STATE_DIR / "_tmp_record.json"
    tmp_file.write_text(records_json, encoding="utf-8")

    ok, data = run_dws(
        logger,
        ["aitable", "record", "create",
         "--base-id", base_id,
         "--table-id", table_id,
         "--records-file", str(tmp_file)],
        retry=1,
        context=f"写入记录 {record_data.get('msg_id','?')[:20]}",
    )

    try:
        tmp_file.unlink()
    except OSError:
        pass

    if ok:
        return True
    stats["failed"] += 1
    logger.warning(f"  写入失败: {data.get('message','')[:150]}")
    return False


# ---------- 内容 / 去重 ----------
def _extract_text_content(msg: dict) -> str:
    """提取消息的文本内容"""
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    return str(content) if content else ""


def _trim_processed_ids(state: dict) -> None:
    """如果超限则裁剪 processed_msg_ids 到 TRIM_TO 条"""
    ids = state.get("processed_msg_ids", [])
    if len(ids) > MAX_PROCESSED_IDS:
        state["processed_msg_ids"] = ids[-TRIM_TO:]


# ---------- 主流程 ----------
def fetch_mentions(
    category_id: str,
    logger: Optional[logging.Logger] = None,
) -> dict:
    """
    抓取指定分组内所有群的 @我 消息，去重后写入 AI 表格。
    返回 stats 字典。
    调用前需保证 state.json 已存在（即已运行 setup_table）。
    """
    log = logger or logging.getLogger("fetch")

    state = load_state()
    if state is None:
        raise FetchError("state.json 不存在，请先运行建表流程")

    log.debug(f"state 加载: base_id={state.get('base_id')}, fields={list(state.get('fields',{}).keys())}")

    # 用户身份 & @我 正则
    nick = _ensure_user_identity(state, log)
    mention_pattern = _build_mention_pattern(nick)

    # 时间窗口：最近 2 天
    now = datetime.now(TZ_CN)
    start_dt = now - timedelta(days=LOOKBACK_DAYS)
    start_time_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    log.info(f"时间窗口: {start_time_str} → {end_time_str}")

    # 分组会话
    conversations = _get_conversations_in_category(log, category_id)
    if not conversations:
        log.info("该分组下没有会话，结束。")
        return {"added": 0, "skipped_dup": 0, "failed": 0, "perm_skip": 0, "timeout_skip": 0, "other_errors": 0}

    # 筛选群（排除单聊）
    groups = []
    for conv in conversations:
        cid = conv.get("openConversationId") or conv.get("conversationId") or conv.get("id", "")
        name = conv.get("title") or conv.get("name") or conv.get("groupName") or ""
        is_single = conv.get("singleChat", False)
        if is_single or not cid:
            continue
        groups.append({"id": cid, "name": name})

    log.info(f"分组内共 {len(groups)} 个群聊")

    # 去重集合
    processed_ids = set(state.get("processed_msg_ids", []))
    new_processed = []

    stats = {
        "added": 0,
        "skipped_dup": 0,
        "skipped_not_me": 0,
        "failed": 0,
        "perm_skip": 0,
        "timeout_skip": 0,
        "other_errors": 0,
    }

    for idx, group in enumerate(groups, 1):
        group_id = group["id"]
        group_name = group["name"] or group_id[:12]
        log.info(f"\n[{idx}/{len(groups)}] 群: {group_name}")

        messages = _fetch_group_messages(log, group_id, start_time_str, stats)
        if not messages:
            log.info("  无消息")
            continue

        # 客户端筛选 @我
        mention_msgs = [m for m in messages if mention_pattern.search(_extract_text_content(m))]
        log.info(f"  拉到 {len(messages)} 条，命中 @我 {len(mention_msgs)} 条")

        if not mention_msgs:
            continue

        for msg in mention_msgs:
            msg_id = msg.get("openMessageId") or msg.get("messageId") or msg.get("id", "")
            if not msg_id:
                stats["failed"] += 1
                continue

            if msg_id in processed_ids:
                stats["skipped_dup"] += 1
                continue

            sender = msg.get("sender") or msg.get("senderNick") or ""
            send_time_raw = msg.get("createTime", "")
            text_content = _extract_text_content(msg)

            record_data = {
                "msg_id": msg_id,
                "group_name": group_name,
                "sender": sender,
                "send_time": send_time_raw if send_time_raw else None,
                "content": text_content,
                "raw_json": json.dumps(msg, ensure_ascii=False)[:2000],
            }

            if _create_record(log, state, record_data, stats):
                stats["added"] += 1
                processed_ids.add(msg_id)
                new_processed.append(msg_id)
                log.debug(f"  ✓ 写入: {msg_id[:20]}... from {sender}")

            time.sleep(0.2)

    # 更新 state
    all_ids = state.get("processed_msg_ids", []) + new_processed
    state["processed_msg_ids"] = all_ids
    _trim_processed_ids(state)
    state.setdefault("last_run_by_category", {})[str(category_id)] = end_time_str
    save_state(state)

    # 汇总
    log.info("")
    log.info("=" * 50)
    log.info("✅ 抓取完成!")
    log.info(f"  新增写入: {stats['added']} 条")
    log.info(f"  已存在跳过: {stats['skipped_dup']} 条")
    log.info(f"  权限跳过: {stats['perm_skip']} 群")
    log.info(f"  超时跳过: {stats['timeout_skip']} 群")
    log.info(f"  写入失败: {stats['failed']} 条")
    log.info(f"  表格: https://docs.dingtalk.com/i/nodes/{state['base_id']}")

    return stats
