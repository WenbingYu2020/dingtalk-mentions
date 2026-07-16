# ding-mentions

抓取钉钉指定会话分组内所有群聊中 **@我** 的消息，去重后写入钉钉 AI 表格。提供两种用法：

- **桌面版（推荐给普通用户）**：下载一个 `.exe` 双击运行，图形界面操作
- **Claude Code skill（推荐给开发者）**：在 Claude Code 里用自然语言触发

---

## 🖥️ 普通用户：桌面版

### 下载

打开 [Releases 页面](https://github.com/WenbingYu2020/dingtalk-mentions/releases/latest)，下载最新版的 `DingTalkMentions-vX.Y.Z-windows-amd64.exe`。

### 使用流程

1. 双击运行下载的 `.exe`
   - 首次运行 Windows SmartScreen 可能拦截 → 点 **更多信息 → 仍要运行**
   - 因为 exe 没有代码签名证书，属于正常提示
2. 首次启动时程序会**自动下载 dws.exe**（钉钉官方 CLI，~8MB）到 `~/.local/bin/`，等进度条走完
3. 点 **登录 / 扫码** → 用钉钉扫码授权
4. 点 **加载分组** → 从下拉框选一个会话分组
5. 点 **更新（抓取 @我 消息）**
   - 首次会自动创建一张钉钉 AI 表格（叫 `钉钉 @我 消息`）
   - 之后每次点"更新"只会追加新的 @我 消息，已经抓过的会跳过
6. 日志区会显示表格链接，点开就能看到所有 @我 消息

### 系统要求

- Windows 10 / 11（64 位）
- 联网（首次要下载 dws，之后要连钉钉 API）
- 不需要装 Python

### 数据存哪

- 表格：在你自己的钉钉账号下（Base 归你所有，其他人看不到）
- 本地状态：`~/.dingtalk-mentions/state.json`（保存表格 ID、已处理消息 ID）
- 日志：`~/.dingtalk-mentions/logs/`

### 卸载

- 删除 exe
- 删除 `~/.dingtalk-mentions/` 目录
- 删除 `~/.local/bin/dws.exe`

---

## 🧑‍💻 开发者：Claude Code skill

### 依赖

- **Claude Code**（CLI 或 VSCode 扩展）— skill 运行环境
- **[dws.exe](https://github.com/DingTalk-Real-AI/dingtalk-workspace-cli/releases)** — 钉钉官方 CLI，默认路径 `~/.local/bin/dws.exe`
- **Python 3.8+** — 运行 skill 的两个脚本
- **钉钉账号** — 已通过 `dws auth login` 完成扫码授权

## 目录结构

```text
ding-mentions/
├── .github/workflows/release.yml   # CI：tag 触发自动构建 Release
├── core/                           # 核心业务逻辑（GUI 和 skill 共用）
├── gui/                            # 桌面版 GUI（tkinter）
│   ├── app.py                      # 主窗口
│   ├── dws_helper.py               # dws CLI 包装
│   └── dws_installer.py            # 首次运行自动下载 dws
├── skills/
│   └── dingtalk-mentions/          # Claude Code Skill 入口
│       ├── SKILL.md
│       ├── setup_table.py
│       └── fetch_mentions.py
├── scripts/
│   ├── install-skill.ps1           # junction 安装（开发者用）
│   └── build.bat                   # 本地打包
├── DingTalkMentions.spec           # PyInstaller 配置
└── README.md
```

**运行时状态目录**（不在项目内）：`~/.dingtalk-mentions/`

- `state.json` — baseId / tableId / fieldId 映射 / 已处理消息 ID
- `logs/` — 每次抓取的日志（skill 自行清理旧日志）
- `downloads/` — 抓取的图片附件

## 安装

首次在本机使用（或 clone 到新机器后）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-skill.ps1
```

脚本会在 `~/.claude/skills/dingtalk-mentions` 建一个 junction 指向本项目的 `skills/dingtalk-mentions/`。这样：

- Claude Code 可以正常发现并加载 skill
- skill 代码跟着项目走，方便版本管理

## 使用

在 Claude Code 里说下面任一句话即可触发 skill：

- "抓取钉钉 @我 的消息"
- "同步 mentions"
- "更新"（在 @消息抓取的上下文中）

执行流程：

1. 检查 `dws` 登录状态，未登录时提示扫码
2. 列出钉钉分组，让用户选一个
3. 首次运行 → 自动建 AI 表格（`setup_table.py`），保存 baseId / fieldId
4. 抓取该分组下所有群，过滤 `@我`，按 `openMessageId` 去重，写入 AI 表格
5. 输出表格 URL 和统计（新增 / 跳过 / 权限失败）

## AI 表格字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `group_name` | 主字段（primaryDoc） | 群聊名称 |
| `msg_id` | 文本 | `openMessageId`，去重键 |
| `sender` | 文本 | 发送者昵称 |
| `send_time` | 日期 | 发送时间 |
| `content` | 文本 | 消息正文 |
| `images` | 附件 | 图片（预留，抓取待完善） |
| `raw_json` | 文本 | 完整原始 payload（截断至 2000 字符） |

## 常见问题

**Q: 报 `AUTH_PERMISSION_DENIED`（错误码 1001）？**
A: 该群的消息读取权限不足。skill 会自动跳过并计入 "权限跳过" 统计；有时候是间歇性的，重试即可命中。

**Q: 想手动跑一次抓取？**
```bash
python skills/dingtalk-mentions/fetch_mentions.py --category-id <分组ID>
```
分组 ID 从 `dws chat category list --format json` 拿。

**Q: state.json 坏了想重建？**
删除 `~/.dingtalk-mentions/state.json` 后，下次 skill 触发时会自动跑 `setup_table.py` 重建（会新建一个 Base，旧的表格数据不会自动迁移）。
