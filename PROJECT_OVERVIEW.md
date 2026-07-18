# 项目梳理报告 — ding-mentions

> 生成时间: 2026-07-18
> 版本: v0.1.1
> 仓库: https://github.com/WenbingYu2020/dingtalk-mentions

---

## 一、项目概述

**定位：** 一键抓取钉钉群聊中 @我 的消息，自动汇总到钉钉 AI 表格。

**两种使用方式：**
- 桌面版 GUI（面向普通用户，下载 exe 即用）
- Claude Code Skill（面向开发者，自然语言触发）

**技术栈：** Python 3.8+ / tkinter / PyInstaller / GitHub Actions

---

## 二、文件结构与职责

### 总体统计

| 分类 | 文件数 | 总行数 |
| --- | --- | --- |
| 核心业务 (core/) | 7 | 694 |
| 桌面 GUI (gui/) | 3 | 606 |
| Skill 入口 (skills/) | 3 | 233 |
| 构建/脚本 (scripts/, spec, workflow) | 4 | 198 |
| 文档/配置 (.gitignore, README, LICENSE, requirements) | 5 | 205 |
| **合计** | **22** | **1936** |

---

### 2.1 核心业务层 — `core/`

这是整个项目的核心，被 GUI 和 Skill 两端共用。

| 文件 | 行数 | 作用 |
| --- | --- | --- |
| `__init__.py` | 4 | 包入口，导出 `fetch_mentions` 和 `setup_table` |
| `paths.py` | 33 | 统一路径常量（状态目录、日志、dws路径），支持环境变量覆盖 |
| `dws.py` | 107 | dws.exe 子进程封装：执行命令 → JSON 解析 → 错误处理 → 自动重试 |
| `state.py` | 21 | `state.json` 读写工具 |
| `logging_setup.py` | 76 | 日志初始化：文件(DEBUG) + stdout(INFO) + GUI 回调(INFO) 三通道 |
| `table_setup.py` | 135 | 建表逻辑：创建 Base → 重命名主字段为 group_name → 批量建业务字段 → 持久化 |
| `fetcher.py` | 318 | 抓取主逻辑：获取用户身份 → 遍历分组群聊 → 正则匹配 @我 → 去重 → 写入表格 |

**调用关系：**
```
fetcher.py ──→ dws.py ──→ subprocess(dws.exe)
     │──→ state.py
     │──→ paths.py
table_setup.py ──→ dws.py
     │──→ state.py
logging_setup.py（独立，被上层调用时传入）
```

---

### 2.2 桌面 GUI — `gui/`

| 文件 | 行数 | 作用 |
| --- | --- | --- |
| `app.py` | 261 | tkinter 主窗口：登录/登出/加载分组/更新按钮 + 日志区 |
| `dws_helper.py` | 146 | GUI 胶水层：登录/状态/分组走 subprocess；抓取/建表直接 import core |
| `dws_installer.py` | 199 | 首次运行自动下载 dws.exe（GitHub → Gitee 回退）+ 进度回调 |

**调用关系：**
```
app.py ──→ dws_helper.py ──→ core.fetcher / core.table_setup（同进程）
  │                      ──→ subprocess(dws.exe)（登录/状态/分组）
  │──→ dws_installer.py（首次启动检测 dws 是否存在）
```

---

### 2.3 Claude Code Skill — `skills/dingtalk-mentions/`

| 文件 | 行数 | 作用 |
| --- | --- | --- |
| `SKILL.md` | 133 | Skill 元数据 + 6 步执行流程说明 |
| `fetch_mentions.py` | 53 | CLI 瘦壳：解析 `--category-id` 参数 → 调用 `core.fetch_mentions` |
| `setup_table.py` | 47 | CLI 瘦壳：调用 `core.setup_table` |

**注册方式：** 通过 junction 链接到 `~/.claude/skills/dingtalk-mentions/`

---

### 2.4 构建与分发

| 文件 | 行数 | 作用 |
| --- | --- | --- |
| `DingTalkMentions.spec` | 63 | PyInstaller 配置：onefile + windowed + 图标 + hiddenimports |
| `.github/workflows/release.yml` | 55 | CI：push tag v* → windows-latest 打包 → 上传到 Release |
| `scripts/build.bat` | 38 | 本地打包脚本（检查 pyinstaller → 清理 → 打包） |
| `scripts/install-skill.ps1` | 42 | 开发者用：在 ~/.claude/skills/ 建 junction |

---

### 2.5 配置与文档

| 文件 | 行数 | 作用 |
| --- | --- | --- |
| `README.md` | 146 | 面向用户 + 开发者的完整使用说明 |
| `LICENSE` | 21 | MIT License |
| `.gitignore` | 36 | 排除 build/dist/_archive/缓存/敏感文件 |
| `requirements.txt` | 1 | `pyinstaller>=6.0` |
| `assets/icon.ico` | — | 蓝底 @ 符号图标（6 种尺寸） |

---

### 2.6 运行时目录（不在代码仓库中）

路径：`~/.dingtalk-mentions/`

| 文件/目录 | 作用 |
| --- | --- |
| `state.json` | 存 baseId、tableId、fieldId 映射、已处理消息 ID 集合 |
| `logs/` | 每次抓取的日志文件 |
| `downloads/` | 临时下载目录（dws 压缩包解压用） |

---

## 三、核心功能要点

### 3.1 消息抓取流程

1. 获取当前用户身份（nick）→ 构建 `@nick` 正则
2. 列出指定分组下的所有群聊
3. 逐群拉取近 2 天消息
4. 正则匹配包含 @我 的消息
5. 按 `openMessageId` 去重（对比 state.json 中已处理列表）
6. 新消息写入 AI 表格（一条一条 create record）
7. 更新 state.json 中的已处理 ID 集合

### 3.2 自动建表

首次运行时：
1. 创建 AI 表格 Base（名称：`钉钉@我消息汇总`）
2. 重命名 primaryDoc 主字段为 `group_name`
3. 批量创建 6 个业务字段（msg_id, sender, send_time, content, images, raw_json）
4. 所有 ID 持久化到 state.json

### 3.3 dws 自动安装

- 检测 `~/.local/bin/dws.exe` 是否存在
- 不存在 → GitHub API 查询最新版 → 下载 zip → 解压到目标路径
- GitHub 不可达时自动回退 Gitee 镜像
- 全程进度回调，GUI 实时展示

### 3.4 错误容忍

- `AUTH_PERMISSION_DENIED`：自动跳过该群，计入统计，不中断整体流程
- 命令超时：自动重试 1 次
- 已处理 ID 超 5000 条时自动 trim 到 3000

---

## 四、架构设计亮点

| 设计 | 好处 |
| --- | --- |
| core 业务层无 UI 依赖 | GUI / CLI / Skill 三端复用，可独立单测 |
| 同进程调用（抓取/建表）| 不依赖外部 Python，打包后零环境要求 |
| subprocess 仅用于 dws 登录/状态 | 这些是 dws CLI 独有能力，无法绕过 |
| GitHub → Gitee 自动回退 | 墙内墙外用户都能首次启动成功 |
| 环境变量覆盖所有路径 | 便于测试、排障、非标准部署 |
| tag → CI → Release 全自动 | 发版只需 `git tag + push` |

---

## 五、优化建议

### 高优先级（建议近期做）

| # | 建议 | 原因 | 预计工作量 |
| --- | --- | --- | --- |
| 1 | `gui/dws_helper._run()` 与 `core/dws.run_dws()` 逻辑重复 | 两处都在包装 subprocess 调用 dws.exe，应统一到 `core/dws.py` 暴露一个轻量版 | 1-2h |
| 2 | 加版本号常量 | 当前 exe 无法告诉用户自己是什么版本；应在一处定义，GUI 标题栏 + 日志 + Release 名共用 | 30min |
| 3 | 补 core/ 单元测试 | `fetcher.py` 318 行无测试，改动时无法自动验证回归 | 4-8h |
| 4 | `fetcher.py` 单条写入改批量 | 当前逐条 `create record`，50 条新消息就是 50 次 API 调用；dws 支持批量写入可大幅提速 | 2-3h |
| 5 | 进度条替代日志刷屏 | dws 下载时日志区刷 100+ 行进度文本，应用 tkinter 进度条组件 | 1-2h |

### 中优先级（有时间做）

| # | 建议 | 原因 | 预计工作量 |
| --- | --- | --- | --- |
| 6 | 图片抓取完善 | `images` 字段已建但逻辑未实现，README 标注"预留" | 4-8h |
| 7 | 日志轮转 | 当前每次 `logging_setup` 覆盖式建文件，无历史追溯 | 1h |
| 8 | 配置文件化 | LOOKBACK_DAYS=2、MAX_PROCESSED_IDS=5000 等硬编码，可提取到 config | 1h |
| 9 | 错误提示人性化 | `setup_table` 和 `fetcher` 的异常直接显示技术信息，对普通用户不友好 | 2h |
| 10 | `_archive/` 清理 | 已废弃的 Node 代码仍占磁盘，.gitignore 已排除但目录还在本地 | 5min |

### 低优先级（视需求）

| # | 建议 | 何时做 |
| --- | --- | --- |
| 11 | macOS 支持 | 有明确用户需求时 |
| 12 | 自动更新机制 | 用户量增长后 |
| 13 | 定时自动抓取 | 当前手动点"更新"够用 |
| 14 | 代码签名证书 | SmartScreen 持续成为用户流失点时（$200+/年） |

---

## 六、潜在风险

| 风险 | 影响 | 当前缓解措施 |
| --- | --- | --- |
| dws API 格式变化 | 抓取/建表可能 break | `_parse_error` + `_unwrap` 做了容错，但无版本兼容层 |
| 已处理 ID 集合丢失 | 重复写入表格 | state.json 是单点，无备份机制 |
| 大量群消息导致超时 | 单次抓取时间过长 | 有 60s 超时 + 重试，但无分页/增量策略上限 |
| SmartScreen 拦截 | 首次用户放弃 | README 有文字指引 |
| GitHub 和 Gitee 都不可达 | dws 下载失败 | 错误提示引导手动下载 |

---

## 七、模块依赖关系图

```
┌─────────────────────────────────────────────────┐
│                  用户入口                          │
├──────────────┬──────────────┬───────────────────┤
│  GUI (exe)   │  Skill (CLI) │  手动 python CLI  │
│  gui/app.py  │  skills/     │  skills/*.py      │
└──────┬───────┴──────┬───────┴──────┬────────────┘
       │              │              │
       ▼              ▼              ▼
┌──────────────────────────────────────────────────┐
│              gui/dws_helper.py                     │
│   (胶水层：登录/状态走subprocess, 抓取走core)       │
└──────────────────────┬───────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌────────────┐  ┌────────────┐  ┌────────────────┐
│core/fetcher│  │core/table_ │  │core/dws.py     │
│   .py      │  │  setup.py  │  │(subprocess封装)│
└─────┬──────┘  └─────┬──────┘  └───────┬────────┘
      │               │                  │
      ├───────────────┤                  │
      ▼               ▼                  ▼
┌────────────┐  ┌────────────┐    ┌───────────┐
│core/state  │  │core/paths  │    │ dws.exe   │
│   .py      │  │   .py      │    │ (钉钉CLI) │
└────────────┘  └────────────┘    └───────────┘
                                        │
                                        ▼
                                  ┌───────────┐
                                  │ 钉钉 API  │
                                  └───────────┘
```

---

## 八、发版流程

```bash
# 1. 改代码、提交
git add . && git commit -m "feat: ..."

# 2. 生成临时 token（repo + workflow scope），push
git push https://USER:TOKEN@github.com/WenbingYu2020/dingtalk-mentions.git main

# 3. 打 tag
git tag v0.2.0 -m "v0.2.0: ..."
git push https://USER:TOKEN@github.com/WenbingYu2020/dingtalk-mentions.git v0.2.0

# 4. 等 5 分钟，Release 页面自动出现新 exe
# 5. 删除 token
```

---

*本文档由项目梳理自动生成，后续随版本更新同步维护。*
