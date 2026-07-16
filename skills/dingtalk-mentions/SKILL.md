---
name: dingtalk-mentions
description: 抓取钉钉指定会话分组内被 @ 我的消息（含图片）并写入 AI 表格，运行时选分组，增量抓取，自动去重。当用户说"更新"、"抓取 @ 我的消息"、"同步钉钉 mentions"、"抓取群里艾特我的消息"时使用。
cli_version: ">=1.0.15"
---

# 钉钉 @ 我消息抓取器

用 `dws` 命令抓取钉钉指定会话分组内所有群聊中 @ 我的消息，写入 AI 表格。

## 用户触发

用户说以下任一即触发本 skill：
- "更新"（在明确 @ 消息抓取上下文时）
- "抓取钉钉 @ 我的消息"
- "同步 mentions"
- "拉群里艾特我的消息"

## 执行流程

**必须严格按以下顺序执行，不要跳步、不要发挥。**

### Step 1: 检查登录状态

```bash
dws auth status --format json
```

如果 `authenticated: false`，停下来提示用户先执行 `dws auth login`，然后 skill 结束。**不要**代替用户扫码。

### Step 2: 让用户选分组

拉分组列表：
```bash
dws chat category list --format json
```

从返回中提取每个分组的 `categoryId` 和 `title`，编号呈现给用户（1/2/3…），让用户回复编号选择目标分组。**不要**自动挑一个。

若返回空数组：告知用户"钉钉侧未设置任何自定义会话分组，请先在钉钉客户端创建分组并把目标群拖进去"，skill 结束。

### Step 3: 加载运行时配置

配置文件：`C:\Users\13328\.dingtalk-mentions\state.json`

结构示例：
```json
{
  "base_id": "xxx",
  "table_id": "xxx",
  "fields": {
    "msg_id": "fldXxx",
    "group_name": "fldXxx",
    "sender": "fldXxx",
    "send_time": "fldXxx",
    "content": "fldXxx",
    "images": "fldXxx",
    "raw_json": "fldXxx"
  },
  "last_run_by_category": {
    "<categoryId>": "2026-07-15T10:30:00+08:00"
  }
}
```

用 Python/Bash 读取。文件不存在 → 走 Step 4 初始化；存在 → 跳到 Step 5。

### Step 4: 首次运行 — 创建 AI 表格

调用：
```bash
python "<skill-dir>/setup_table.py"
```

`<skill-dir>` 指本 SKILL.md 所在目录。日常安装路径为 `~/.claude/skills/dingtalk-mentions/`（junction 或真实目录皆可）。

脚本会：
1. 创建名为「钉钉@我消息汇总」的 Base
2. 在默认数据表里建以下字段：
   - `msg_id`（文本，去重键）
   - `group_name`（文本）
   - `sender`（文本）
   - `send_time`（日期）
   - `content`（文本）
   - `images`（附件）
   - `raw_json`（文本，保留原始 payload）
3. 把 baseId / tableId / fieldId 写回 `state.json`
4. stdout 输出 baseId 和文档 URI，展示给用户

### Step 5: 抓取并写入

调用：
```bash
python "<skill-dir>/fetch_mentions.py" --category-id <用户选的categoryId>
```

脚本负责：
1. 从 `state.json` 读取该分组上次运行时间（无则默认 7 天前）
2. 拉该分组下所有会话：`dws chat category list-conversations --category-id <id>`
3. 逐群跑 `dws chat message list-mentions --group <openConversationId> --start <ISO> --end <now>` 翻页
4. 对每条消息：
   - 提取 `openMessageId` 作为去重 key
   - 查 AI 表格是否已存在（`record query --filters` on `msg_id`）
   - 已存在 → 跳过
   - 不存在 → 若有图片，`chat message download-media` 下到 `~/.dingtalk-mentions/downloads/`，再走 `upload_attachment.py` 转成 fileToken；组装 record 写入
5. 全部完成后，把该分组的 `last_run_by_category[categoryId]` 更新为本次抓取的开始时间戳
6. 输出汇总：新增 N 条、跳过 M 条、失败 K 条

### Step 6: 汇报结果

告诉用户：
- 表格 URI（`https://alidocs.dingtalk.com/i/nodes/<baseId>`）
- 本次新增记录数、跳过（去重命中）数
- 若有失败，列出失败群和原因

## 严格禁止

- **不要**在没有登录时代替用户扫码
- **不要**自作主张替用户选分组
- **不要**跳过去重检查直接批量插入
- **不要**在 skill 里手写抓取循环，全部走脚本
- **不要**修改脚本中的字段名（`msg_id` 等），它们是 state 结构约定

## 错误恢复

- 脚本非零退出：读 stderr 展示给用户，不要静默重试
- 单个群拉取失败：脚本内部会记录并继续，不影响其他群
- 消息数量为 0：正常告知用户"本次无新增 @ 我的消息"

## 相关文件

- [setup_table.py](setup_table.py) — 首次运行建表
- [fetch_mentions.py](fetch_mentions.py) — 增量抓取入库
