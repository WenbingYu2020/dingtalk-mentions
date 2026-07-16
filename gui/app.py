"""
钉钉 @我 消息抓取器 — 桌面应用
功能：登录/登出 dws、查看状态、选择分组、一键抓取 @我 消息写入 AI 表格
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
import json
import time

# 保证 core 模块可被 import：开发模式下项目根在 gui/.. ，打包后 PyInstaller 会把
# core/ 作为 datas 放到 sys._MEIPASS。两种情况都尝试加入 sys.path。
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent  # 开发模式：ding-mentions/
for p in (_PROJECT_ROOT, _HERE):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
# PyInstaller 打包后的临时解压目录（存放 datas）
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    meipass = str(sys._MEIPASS)
    if meipass not in sys.path:
        sys.path.insert(0, meipass)

import dws_helper
import dws_installer

STATE_FILE = Path.home() / ".dingtalk-mentions" / "state.json"

# ---------- 颜色 / 字体 ----------
BG = "#f5f5f5"
FG = "#333333"
ACCENT = "#1677ff"
FONT = ("Microsoft YaHei UI", 10)
FONT_TITLE = ("Microsoft YaHei UI", 14, "bold")
FONT_SMALL = ("Microsoft YaHei UI", 9)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("钉钉 @我 消息抓取器")
        self.geometry("620x520")
        self.configure(bg=BG)
        self.resizable(False, False)

        self._build_ui()
        # 先自检 dws.exe，缺失则自动下载；下载成功后再刷新登录状态
        self.after(300, self._ensure_dws_then_status)

    # --------- UI 构建 ---------
    def _build_ui(self):
        # 顶部标题
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(header, text="钉钉 @我 消息抓取器", font=FONT_TITLE, bg=BG, fg=FG).pack(side="left")

        # 状态栏
        status_frame = tk.Frame(self, bg=BG)
        status_frame.pack(fill="x", padx=20, pady=4)
        tk.Label(status_frame, text="登录状态:", font=FONT, bg=BG, fg=FG).pack(side="left")
        self.status_label = tk.Label(status_frame, text="检查中...", font=FONT, bg=BG, fg="#999")
        self.status_label.pack(side="left", padx=8)
        self.btn_refresh = ttk.Button(status_frame, text="刷新", command=self._refresh_status)
        self.btn_refresh.pack(side="left", padx=4)

        # 操作按钮行
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=8)

        self.btn_login = ttk.Button(btn_frame, text="登录 / 扫码", command=self._do_login)
        self.btn_login.pack(side="left", padx=(0, 8))

        self.btn_logout = ttk.Button(btn_frame, text="退出登录", command=self._do_logout)
        self.btn_logout.pack(side="left", padx=(0, 8))

        self.btn_fetch = ttk.Button(btn_frame, text="更新（抓取 @我 消息）", command=self._do_fetch)
        self.btn_fetch.pack(side="left", padx=(0, 8))

        # 分组选择
        cat_frame = tk.LabelFrame(self, text="选择会话分组", font=FONT, bg=BG, fg=FG)
        cat_frame.pack(fill="x", padx=20, pady=8)

        self.cat_combo = ttk.Combobox(cat_frame, state="readonly", width=40, font=FONT)
        self.cat_combo.pack(side="left", padx=8, pady=8)

        self.btn_load_cats = ttk.Button(cat_frame, text="加载分组", command=self._load_categories)
        self.btn_load_cats.pack(side="left", padx=4, pady=8)

        self.categories = []  # [{categoryId, title}]

        # 日志区
        log_frame = tk.LabelFrame(self, text="运行日志", font=FONT, bg=BG, fg=FG)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(8, 16))

        self.log_box = scrolledtext.ScrolledText(
            log_frame, height=12, font=FONT_SMALL, wrap="word", state="disabled"
        )
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)

    # --------- 日志 ---------
    def _log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # --------- dws 首次自动下载 ---------
    def _ensure_dws_then_status(self):
        """启动时确保 dws 存在，缺失则后台下载。完成后再刷新登录状态。"""
        from pathlib import Path as _P
        from core.paths import DWS as _DWS
        if _P(_DWS).exists():
            self._refresh_status()
            return

        self._log("检测到 dws.exe 未安装，正在自动下载...")

        def on_progress(pct, text):
            self.after(0, lambda p=pct, t=text: self._log(f"[dws 安装 {p if p>=0 else '?'}%] {t}"))

        def task():
            ok, msg = dws_installer.ensure_dws(on_progress=on_progress)
            self.after(0, lambda: self._log(msg))
            if ok:
                self.after(0, self._refresh_status)
            else:
                self.after(0, lambda: messagebox.showerror(
                    "dws 安装失败",
                    f"{msg}\n\n请手动下载 dws 并放到 ~/.local/bin/dws.exe，或设置环境变量 DINGTALK_MENTIONS_DWS 指向可执行文件。"
                ))

        threading.Thread(target=task, daemon=True).start()

    # --------- 登录状态 ---------
    def _refresh_status(self):
        def task():
            logged_in, msg = dws_helper.check_status()
            self.after(0, lambda: self._update_status_ui(logged_in, msg))

        threading.Thread(target=task, daemon=True).start()

    def _update_status_ui(self, logged_in, msg):
        if logged_in:
            self.status_label.configure(text=msg, fg="#52c41a")
        else:
            self.status_label.configure(text=msg or "未登录", fg="#ff4d4f")

    # --------- 登录 ---------
    def _do_login(self):
        self._log("正在启动登录（将打开浏览器扫码）...")
        self.btn_login.configure(state="disabled")

        def task():
            proc = dws_helper.login()
            if proc is None:
                self.after(0, lambda: self._log("[错误] 找不到 dws.exe"))
                self.after(0, lambda: self.btn_login.configure(state="normal"))
                return
            # 等待进程结束（用户扫码完成）
            proc.wait()
            stdout = proc.stdout.read() if proc.stdout else ""
            stderr = proc.stderr.read() if proc.stderr else ""
            self.after(0, lambda: self._log(f"登录流程结束 (code={proc.returncode})"))
            if stdout.strip():
                self.after(0, lambda: self._log(stdout.strip()))
            if stderr.strip():
                self.after(0, lambda: self._log(stderr.strip()))
            self.after(0, lambda: self.btn_login.configure(state="normal"))
            self.after(500, self._refresh_status)

        threading.Thread(target=task, daemon=True).start()

    # --------- 登出 ---------
    def _do_logout(self):
        ok, msg = dws_helper.logout()
        self._log(msg)
        self._refresh_status()

    # --------- 加载分组 ---------
    def _load_categories(self):
        self._log("加载会话分组...")
        self.btn_load_cats.configure(state="disabled")

        def task():
            ok, data = dws_helper.list_categories()
            self.after(0, lambda: self._on_categories_loaded(ok, data))

        threading.Thread(target=task, daemon=True).start()

    def _on_categories_loaded(self, ok, data):
        self.btn_load_cats.configure(state="normal")
        if not ok:
            self._log(f"[错误] 加载分组失败: {data}")
            return
        if not data:
            self._log("钉钉侧无自定义会话分组，请先在钉钉客户端创建分组。")
            return
        self.categories = data
        names = []
        for cat in data:
            cid = cat.get("categoryId") or cat.get("id", "")
            title = cat.get("title") or cat.get("name") or str(cid)
            names.append(f"{title} (ID:{cid})")
        self.cat_combo["values"] = names
        if names:
            self.cat_combo.current(0)
        self._log(f"已加载 {len(names)} 个分组")

    # --------- 抓取 ---------
    def _do_fetch(self):
        # 检查分组
        idx = self.cat_combo.current()
        if idx < 0 or not self.categories:
            messagebox.showwarning("提示", "请先加载并选择一个分组")
            return

        cat = self.categories[idx]
        category_id = cat.get("categoryId") or cat.get("id", "")
        cat_name = cat.get("title") or cat.get("name") or str(category_id)

        self._log(f"\n{'='*40}")
        self._log(f"开始抓取 — 分组: {cat_name}")

        self.btn_fetch.configure(state="disabled")

        def task():
            # 检查 state.json 是否存在，不存在则先建表
            if not STATE_FILE.exists():
                self.after(0, lambda: self._log("首次运行，正在创建 AI 表格..."))
                code, stderr = dws_helper.run_setup(
                    on_output=lambda line: self.after(0, lambda l=line: self._log(l))
                )
                if code != 0:
                    self.after(0, lambda: self._log(f"[错误] 建表失败: {stderr}"))
                    self.after(0, lambda: self.btn_fetch.configure(state="normal"))
                    return

            # 执行抓取
            code, stderr = dws_helper.run_fetch(
                category_id,
                on_output=lambda line: self.after(0, lambda l=line: self._log(l)),
            )
            if code != 0 and stderr:
                self.after(0, lambda: self._log(f"[错误] {stderr}"))
            self.after(0, lambda: self.btn_fetch.configure(state="normal"))

        threading.Thread(target=task, daemon=True).start()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
