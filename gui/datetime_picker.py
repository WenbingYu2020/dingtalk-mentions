"""
纯 tkinter 日期时间选择器。
用法：
    result = DateTimePicker.ask(parent, initial=datetime.now())
    # result 是 datetime 或 None（用户取消）
"""

from __future__ import annotations
import calendar
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

WEEK_HEADERS = ["一", "二", "三", "四", "五", "六", "日"]  # Monday-first


class DateTimePicker(tk.Toplevel):
    """弹窗式日期 + 时/分 选择器。"""

    def __init__(self, parent: tk.Misc, initial: datetime | None = None, title: str = "选择时间"):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._result: datetime | None = None
        now = initial or datetime.now()
        self._year = now.year
        self._month = now.month
        self._selected_day = now.day
        self._hour_var = tk.StringVar(value=f"{now.hour:02d}")
        self._minute_var = tk.StringVar(value=f"{now.minute:02d}")

        self._build_ui()
        self._render_calendar()

        # 弹到 parent 中间
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        except tk.TclError:
            pass

    # ---------- UI ----------
    def _build_ui(self):
        pad = 8
        outer = ttk.Frame(self, padding=pad)
        outer.pack()

        # 年月导航
        nav = ttk.Frame(outer)
        nav.pack(fill="x", pady=(0, 6))
        ttk.Button(nav, text="◀", width=3, command=self._prev_month).pack(side="left")
        self._title_label = ttk.Label(nav, text="", width=14, anchor="center", font=("Microsoft YaHei UI", 10, "bold"))
        self._title_label.pack(side="left", padx=6)
        ttk.Button(nav, text="▶", width=3, command=self._next_month).pack(side="left")
        ttk.Button(nav, text="今天", width=6, command=self._goto_today).pack(side="right")

        # 星期表头
        hdr = ttk.Frame(outer)
        hdr.pack()
        for i, name in enumerate(WEEK_HEADERS):
            fg = "#c0392b" if i >= 5 else "#333"
            lbl = tk.Label(hdr, text=name, width=4, fg=fg, font=("Microsoft YaHei UI", 9, "bold"))
            lbl.grid(row=0, column=i, padx=1, pady=1)

        # 日期网格容器
        self._grid_frame = tk.Frame(outer)
        self._grid_frame.pack()

        # 时分选择
        time_row = ttk.Frame(outer)
        time_row.pack(fill="x", pady=(8, 0))
        ttk.Label(time_row, text="时间:").pack(side="left")
        ttk.Spinbox(
            time_row, from_=0, to=23, width=4, textvariable=self._hour_var,
            format="%02.0f", wrap=True,
        ).pack(side="left", padx=(4, 2))
        ttk.Label(time_row, text=":").pack(side="left")
        ttk.Spinbox(
            time_row, from_=0, to=59, width=4, textvariable=self._minute_var,
            format="%02.0f", wrap=True,
        ).pack(side="left", padx=(2, 0))

        # 底部按钮
        btns = ttk.Frame(outer)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="确定", command=self._on_ok).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="取消", command=self._on_cancel).pack(side="right")

        self.bind("<Escape>", lambda e: self._on_cancel())
        self.bind("<Return>", lambda e: self._on_ok())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _render_calendar(self):
        # 清空
        for w in self._grid_frame.winfo_children():
            w.destroy()

        self._title_label.configure(text=f"{self._year} 年 {self._month} 月")

        cal = calendar.Calendar(firstweekday=0)  # Monday-first
        weeks = cal.monthdayscalendar(self._year, self._month)

        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                if day == 0:
                    ttk.Label(self._grid_frame, text="", width=4).grid(row=r, column=c, padx=1, pady=1)
                    continue

                is_selected = day == self._selected_day
                is_today = (
                    self._year == datetime.now().year
                    and self._month == datetime.now().month
                    and day == datetime.now().day
                )

                if is_selected:
                    bg, fg = "#1677ff", "white"
                elif is_today:
                    bg, fg = "#e6f4ff", "#1677ff"
                else:
                    bg, fg = "#f5f5f5", "#c0392b" if c >= 5 else "#333"

                btn = tk.Label(
                    self._grid_frame, text=str(day), width=4, height=1,
                    bg=bg, fg=fg, font=("Microsoft YaHei UI", 9),
                    relief="flat", cursor="hand2",
                )
                btn.grid(row=r, column=c, padx=1, pady=1)
                btn.bind("<Button-1>", lambda e, d=day: self._pick_day(d))

    # ---------- 交互 ----------
    def _pick_day(self, day: int):
        self._selected_day = day
        self._render_calendar()

    def _prev_month(self):
        first = datetime(self._year, self._month, 1)
        prev = first - timedelta(days=1)
        self._year, self._month = prev.year, prev.month
        # 校准选中日
        _, last = calendar.monthrange(self._year, self._month)
        self._selected_day = min(self._selected_day, last)
        self._render_calendar()

    def _next_month(self):
        _, last = calendar.monthrange(self._year, self._month)
        nxt = datetime(self._year, self._month, last) + timedelta(days=1)
        self._year, self._month = nxt.year, nxt.month
        _, last2 = calendar.monthrange(self._year, self._month)
        self._selected_day = min(self._selected_day, last2)
        self._render_calendar()

    def _goto_today(self):
        today = datetime.now()
        self._year, self._month, self._selected_day = today.year, today.month, today.day
        self._hour_var.set(f"{today.hour:02d}")
        self._minute_var.set(f"{today.minute:02d}")
        self._render_calendar()

    def _on_ok(self):
        try:
            h = int(self._hour_var.get())
            m = int(self._minute_var.get())
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
        except ValueError:
            return  # 忽略非法输入
        self._result = datetime(self._year, self._month, self._selected_day, h, m)
        self.destroy()

    def _on_cancel(self):
        self._result = None
        self.destroy()

    # ---------- API ----------
    @classmethod
    def ask(cls, parent: tk.Misc, initial: datetime | None = None, title: str = "选择时间") -> datetime | None:
        dlg = cls(parent, initial=initial, title=title)
        parent.wait_window(dlg)
        return dlg._result
