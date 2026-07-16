"""
dws.exe 自动下载与安装器 — 首次运行 GUI 时使用。

策略：
  1. 检查 core.paths.DWS 指向的路径是否已存在 → 存在则直接返回
  2. 查询 GitHub Releases API 获取最新版本的对应平台资源
  3. 下载到 STATE_DIR/downloads/ ，解压 dws 可执行文件到 DWS 目标路径
  4. 支持 Gitee 镜像（DWS_GITEE_REPO=1 或 GitHub 不可达时自动回退）
  5. 支持进度回调，供 GUI 显示进度条

调用示例（非 GUI）：
    from gui.dws_installer import ensure_dws
    ok, msg = ensure_dws(on_progress=lambda pct,text: print(pct, text))
"""

import io
import os
import platform
import shutil
import stat
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional, Tuple

# 让本文件既能在 gui 目录内直接跑，也能在 PyInstaller 打包后正常 import core
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
for _p in (_PROJECT_ROOT, _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _mp = str(sys._MEIPASS)
    if _mp not in sys.path:
        sys.path.insert(0, _mp)

from core.paths import DWS, DOWNLOADS_DIR, STATE_DIR  # noqa: E402


GITHUB_LATEST_API = (
    "https://api.github.com/repos/DingTalk-Real-AI/dingtalk-workspace-cli/releases/latest"
)
GITEE_LATEST_API = (
    "https://gitee.com/api/v5/repos/DingTalk-Real-AI/dingtalk-workspace-cli/releases/latest"
)

ProgressCB = Optional[Callable[[int, str], None]]


def _emit(cb: ProgressCB, pct: int, text: str) -> None:
    if cb:
        try:
            cb(pct, text)
        except Exception:
            pass


def _detect_platform_asset() -> str:
    """根据当前系统 / 架构返回 release asset 文件名"""
    sysname = platform.system().lower()      # 'windows' | 'darwin' | 'linux'
    machine = platform.machine().lower()     # 'amd64' | 'x86_64' | 'arm64' | 'aarch64'

    if machine in ("x86_64", "amd64"):
        arch = "amd64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        raise RuntimeError(f"暂不支持的 CPU 架构: {machine}")

    if sysname == "windows":
        return f"dws-windows-{arch}.zip"
    if sysname == "darwin":
        return f"dws-darwin-{arch}.tar.gz"
    if sysname == "linux":
        return f"dws-linux-{arch}.tar.gz"
    raise RuntimeError(f"暂不支持的操作系统: {sysname}")


def _http_get_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "DingTalkMentions/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        import json
        return json.loads(resp.read().decode("utf-8"))


def _find_asset_url(asset_name: str, cb: ProgressCB) -> Tuple[str, str]:
    """
    返回 (tag_name, download_url)。
    先试 GitHub，失败自动切 Gitee。
    """
    _emit(cb, 5, "查询最新版本（GitHub）...")
    try:
        data = _http_get_json(GITHUB_LATEST_API)
        for a in data.get("assets", []):
            if a.get("name") == asset_name:
                return data.get("tag_name", ""), a.get("browser_download_url", "")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        _emit(cb, 8, f"GitHub 不可达（{e}），改用 Gitee 镜像 ...")

    _emit(cb, 10, "查询最新版本（Gitee 镜像）...")
    data = _http_get_json(GITEE_LATEST_API)
    tag = data.get("tag_name", "")
    for a in data.get("assets", []):
        if a.get("name") == asset_name:
            return tag, a.get("browser_download_url", "")
    raise RuntimeError(f"在 releases 中未找到资源: {asset_name}")


def _download(url: str, dest: Path, cb: ProgressCB, base_pct: int = 15, span_pct: int = 60) -> None:
    """流式下载，进度百分比映射到 [base_pct, base_pct+span_pct]。"""
    _emit(cb, base_pct, f"下载 {url.split('/')[-1]} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "DingTalkMentions/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        dest.parent.mkdir(parents=True, exist_ok=True)
        got = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if total > 0:
                    pct = base_pct + int(span_pct * got / total)
                    _emit(cb, pct, f"下载中 {got // 1024 // 1024}MB / {total // 1024 // 1024}MB")
    _emit(cb, base_pct + span_pct, "下载完成")


def _extract(archive: Path, target_exe: Path, cb: ProgressCB) -> None:
    """从下载的压缩包中提取 dws 可执行文件到目标路径。"""
    _emit(cb, 80, "解压中...")
    target_exe.parent.mkdir(parents=True, exist_ok=True)

    name = archive.name
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive, "r") as zf:
            exe_names = [n for n in zf.namelist() if n.endswith(("dws.exe", "dws"))]
            if not exe_names:
                raise RuntimeError(f"压缩包中未找到 dws 可执行文件: {zf.namelist()}")
            with zf.open(exe_names[0]) as src, open(target_exe, "wb") as dst:
                shutil.copyfileobj(src, dst)
    elif name.endswith(".tar.gz") or name.endswith(".tgz"):
        with tarfile.open(archive, "r:gz") as tf:
            members = tf.getnames()
            exe_names = [n for n in members if n.endswith(("dws.exe", "/dws", "dws"))]
            if not exe_names:
                raise RuntimeError(f"压缩包中未找到 dws 可执行文件: {members}")
            member = tf.getmember(exe_names[0])
            src = tf.extractfile(member)
            if src is None:
                raise RuntimeError(f"无法读取: {exe_names[0]}")
            with open(target_exe, "wb") as dst:
                shutil.copyfileobj(src, dst)
    else:
        raise RuntimeError(f"不支持的压缩格式: {name}")

    if sys.platform != "win32":
        target_exe.chmod(target_exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)

    _emit(cb, 90, f"已安装到 {target_exe}")


def ensure_dws(on_progress: ProgressCB = None) -> Tuple[bool, str]:
    """
    确保 dws 可执行文件存在。
    返回 (success, message)。
    on_progress(percent: int, text: str) 被调用用于报告进度（0~100）。
    """
    dws_path = Path(DWS)
    if dws_path.exists():
        _emit(on_progress, 100, "dws 已就绪")
        return True, "dws 已就绪"

    _emit(on_progress, 1, "dws 未安装，准备自动下载...")
    try:
        asset_name = _detect_platform_asset()
        tag, url = _find_asset_url(asset_name, on_progress)
        if not url:
            return False, "未能获取下载链接"

        dest_archive = DOWNLOADS_DIR / asset_name
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

        _download(url, dest_archive, on_progress)
        _extract(dest_archive, dws_path, on_progress)

        # 清理下载的压缩包
        dest_archive.unlink(missing_ok=True)

        _emit(on_progress, 100, f"dws {tag} 安装完成")
        return True, f"dws {tag} 安装完成 → {dws_path}"

    except Exception as e:
        _emit(on_progress, -1, f"安装失败: {e}")
        return False, f"安装失败: {e}"
