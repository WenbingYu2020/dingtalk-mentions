"""dws CLI 命令执行封装"""

import json
import subprocess
import sys
import time

from core.paths import DWS


def run_dws(logger, cmd_args, *, retry=1, context=""):
    """
    执行 dws 命令，返回 (ok, data_or_error)。
    ok=True 时 data 是剥壳后的 dict/list；
    ok=False 时 data 是 {code, message, reason, trace_id, raw} 字典。
    超时/网络类自动重试。
    """
    cmd = [DWS] + list(cmd_args) + ["--format", "json"]
    logger.debug(f"执行: {' '.join(cmd_args[:6])}...")

    for attempt in range(1 + retry):
        try:
            kwargs = dict(capture_output=True, text=True, encoding="utf-8", timeout=60)
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(cmd, **kwargs)
        except FileNotFoundError:
            err = {"code": "NOT_FOUND", "message": "找不到 dws.exe，请检查安装", "reason": "file_not_found", "trace_id": "", "raw": ""}
            logger.error(f"[{context}] ❌ 找不到 dws.exe")
            return False, err
        except subprocess.TimeoutExpired:
            if attempt < retry:
                logger.warning(f"[{context}] 命令超时，重试 ({attempt+1}/{retry})...")
                time.sleep(2)
                continue
            err = {"code": "TIMEOUT", "message": "命令执行超时（60s）", "reason": "timeout", "trace_id": "", "raw": ""}
            logger.error(f"[{context}] ❌ 命令超时")
            return False, err

        # 解析输出
        output = result.stdout.strip()
        if result.returncode != 0:
            err_info = _parse_error(output, result.stderr)
            # 可重试类
            if err_info.get("retryable") and attempt < retry and err_info.get("code") not in ("1001", "AUTH_PERMISSION_DENIED"):
                logger.warning(f"[{context}] ⚠ {err_info['reason']}: {err_info['message']}，重试...")
                time.sleep(2)
                continue
            logger.debug(f"[{context}] 错误原文: {err_info.get('raw','')}")
            logger.error(f"[{context}] ❌ {err_info['code']}: {err_info['message']} (trace={err_info.get('trace_id','')[:12]})")
            return False, err_info

        # 解析 JSON
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            err = {"code": "PARSE", "message": f"响应解析失败: {output[:300]}", "reason": "json_decode_error", "trace_id": "", "raw": output[:500]}
            logger.error(f"[{context}] ❌ 响应 JSON 解析失败")
            return False, err

        # 剥壳
        data = _unwrap(parsed)
        logger.debug(f"[{context}] 成功，数据 keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
        return True, data

    return False, {"code": "UNKNOWN", "message": "未知错误", "reason": "unknown", "trace_id": "", "raw": ""}


def _parse_error(stdout, stderr):
    """从 dws 错误输出中提取结构化信息（stdout 或 stderr 都可能包含 JSON）"""
    info = {"code": "", "message": "未知错误", "reason": "unknown", "trace_id": "", "raw": "", "retryable": False}

    obj = {}
    for src in (stdout, stderr):
        if not src:
            continue
        try:
            obj = json.loads(src)
            if obj.get("error"):
                break
        except json.JSONDecodeError:
            continue

    error = obj.get("error", {})
    if error:
        info["code"] = str(error.get("server_error_code") or error.get("code", ""))
        raw_msg = error.get("message", "未知错误")
        info["message"] = raw_msg.split("\n")[0].strip() if isinstance(raw_msg, str) else str(raw_msg)
        info["reason"] = error.get("reason", "unknown")
        info["trace_id"] = error.get("trace_id", "")
        info["retryable"] = error.get("retryable", False)
        info["raw"] = json.dumps(error, ensure_ascii=False)[:500]
    else:
        raw = (stderr or stdout or "")
        info["message"] = raw.split("\n")[0].strip()[:200] or "未知错误"
        info["raw"] = raw[:500]
    return info


def _unwrap(parsed):
    """剥离 dws 响应外壳"""
    if isinstance(parsed, dict):
        if "data" in parsed and "success" in parsed:
            return parsed.get("data") or {}
        if "result" in parsed and "success" in parsed:
            return parsed.get("result") or {}
    return parsed
