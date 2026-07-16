# ding-mentions

Claude Code skill：抓取钉钉指定会话分组内所有群聊中 **@我** 的消息（含图片），去重后写入钉钉 AI 表格。

## 依赖

- **Claude Code**（CLI 或 VSCode 扩展）— skill 运行环境
- **[dws.exe](https://github.com/dingtalk/dingtalk-workspace)** — 钉钉官方 CLI，默认路径 `~/.local/bin/dws.exe`
- **Python 3.8+** — 运行 skill 的两个脚本
- **钉钉账号** — 已通过 `dws auth login` 完成扫码授权

## 目录结构

```text
ding-mentions/
├── skills/
│   └── dingtalk-mentions/          # skill 真身
│       ├── SKILL.md                # skill 描述与执行流程
│       ├── setup_table.py          # 首次运行：创建 AI 表格
│       └── fetch_mentions.py       # 增量抓取入库
├── scripts/
│   └── install-skill.ps1           # 在 ~/.claude/skills 建 junction 的一键脚本
├── _archive/
│   └── node-legacy/                # 早期 Node 版实现（已弃用，保留仅供参考）
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
