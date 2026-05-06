# Changelog

All notable changes to cheat-on-content will be documented here.

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### Added — v2 预测重判系统（拍后改稿场景）

- **append-only v2 prediction**：cheat-shoot 检测拍摄稿与 `scripts/<id>.md` 行级 diff ≥ 30%（`V2_TRIGGER_THRESHOLD`）→ 自动调用 `/cheat-predict — mode: v2 — prediction-file: <path>` → 在原 prediction 文件 `## 复盘` 之前 append `## 预测 v2 (replaces v1)` 段。**v1 段绝不修改**（hook 物理强制），v2 才进 cheat-retro 的偏差计算
- **immutability hook awk 升级**：单个 `## 预测` 改为可识别多个 `## 预测 vN` 段（v1 / v2 / 任意 vN 一起锁），同时兼容 v0.1.0 的 legacy 裸 `## 预测` 写法。端到端 5 场景验证通过（编辑 v1 / 编辑 v2 / 编辑 legacy 都 BLOCK；append 新段、改 ## 复盘 都 ALLOW）
- **cheat-predict 加 Phase 0.7 模式判定**：检测目标 prediction 文件已含 `## 预测...` 段 → 自动切 v2 模式（Edit 在 `## 复盘` 边界 append，不 Write 覆盖）
- **cheat-retro 升级**：识别多个 `## 预测 vN`，取最后一段作校准依据；预测段哈希校验扩展为"全部 v? 段合并哈希"，任一被改即报错回滚
- **prediction header 新字段 `Prediction Basis`**：`pre_shoot`（v1 默认）/ `post_shoot_pre_publish`（v2）。score-curve 与 cheat-bump 据此区分两条数据线避免混样
- **shoots[] 项 schema 扩展**：新增 `scripts_path` / `script_consistency` / `script_diff_pct` / `v2_prediction_written` / `script_hash_at_shoot`（详见 [migrations/1.1-to-1.2.md](migrations/1.1-to-1.2.md)）

### Changed — schema 1.1 → 1.2（MINOR）

- 升级 [migrations/registry.md](migrations/registry.md) `LATEST_SCHEMA` 标记 + 版本链表
- cheat-init 新建 state 写 `"schema_version": "1.2"`
- SessionStart hook `LATEST_SCHEMA="1.2"` —— 老用户 git pull + 跑会话 → hook 提示 schema mismatch → 用户跑 `/cheat-migrate` 5 秒升上来。MINOR 兼容，不强制（skills 用 `state.get(field, default)` 兜底）

### Why now

用户实际工作流：写完草稿 → **常常拍摄时即兴改文案** → 草稿和实际播出版本脱节。原"拍前预测，拍后只登记"的严格盲预测让"预测对的稿子"与"实际播出的稿子"不是同一份——校准失真。

v2 系统让"拍后改稿"成为一等公民：v1 留作档案，v2 基于实际拍摄稿重判，diff(v1, v2) 本身成为 rubric 升级的强证据（用户改稿改高了 ER → 工具学到这个用户的 ER 阈值跟当前公式不一致）。盲预测原则保留：v2 仍在发布前完成，没有播放数据可"作弊"。

### Added — Codex 安装兼容（@songth1ef [#6](https://github.com/XBuilderLAB/cheat-on-content/pull/6)）

- **`install.sh --codex`**：安装根路由 skill `cheat-on-content` 和 13 个子 skill 到 `~/.codex/skills/`
- **`install.sh --all`**：同时安装 Claude Code 和 Codex skill
- **`uninstall.sh --codex` / `--all`**：对称卸载 Codex 或双端安装
- **Codex 路由说明**：Codex 用自然语言触发同一套流程，不依赖 Claude Code 的 `/cheat-*` slash-command harness

### Added — Migration 系统（让长期迭代不打断老用户）

- **`/cheat-migrate` skill**：把老用户 `.cheat-state.json` 从旧 `schema_version` 升级到当前 `LATEST_SCHEMA`。幂等、不跳版、失败停在断点
- **`migrations/` 目录**：版本演进单一来源
  - `registry.md`：`LATEST_SCHEMA` 标记 + 完整版本链表
  - `<from>-to-<to>.md`：每步迁移 4 段（WHAT changed / WHY / HOW Claude steps / Manual fallback）
- **`shared-references/migration-protocol.md`**：演进哲学 + maintainer checklist（bump schema 必做的 4 件事）
- **SessionStart hook 增强**：检测 `state.schema_version != LATEST_SCHEMA` → 输出非阻塞警告，建议跑 `/cheat-migrate`
- **`install.sh --reinstall-hooks <project>`**：git pull 后重写用户项目 `.cheat-hooks/` 的脚本（不动 state / rubric / predictions）
- **state-management.md 升级**：所有 schema 升级文档指向 cheat-migrate；明确 MINOR / MAJOR 边界

### Why now

v0.1.0 用户的 state 是 schema 1.1。后续如果改字段语义、删字段、重命名等 → 没有迁移系统的话老用户 git pull 后会卡住。这套系统让"长期迭代不打断老用户"成为常态。

### Fixed

- **cheat-init `content_form` 存成字母 bug**：Phase 3 state JSON 模板用 `<Q1>` 抽象占位，导致 Claude 字面把 `"a"` 写进 state 文件而不是 enum `"opinion-video"`。修复：Q1/Q3/Q4/Q5 各加明确字母→enum 映射表 + Phase 3 模板加粗 warning。同时补全 7 个缺失的 `last_*` init 字段（之前靠 `state.get(field, default)` 兜底）+ `enabled_perf_adapters` 派生 + 强制 `initialized_at` 用本地 `+08:00` 时区不用 UTC `Z`

### Changed — README 重写（v0.1.0 ship 后的定位调整）

- 标题：英文 `Cheat on Content`，副标 `网红外挂`（之前 `网红作弊器`）
- Tagline 直面"作弊"框架：「做内容本质上就是作弊——谁先看穿规律，谁就拿走流量」
- 新增"那 ChatGPT / 豆包 / DeepSeek 不是也能干这个？"段——核心定位为"你自己的运营专家 + 自动进化"
- 删早期产品警示段（badge + 本 CHANGELOG 已经在传达，重复就是不自信）
- 砍 ARIS attribution（保留多 adapter 设计思路，去掉外部归功）
- README 总长 330 行 → 90 行
- cheat-init Phase 1 首屏文案同步重写：删方法论哲学，2 条 caveats（早期不准 + 强烈建议导对标）

### 余项

- Step B：软化更多硬编码规则
- 完整 reference-implementation 脱敏快照

---

## [0.1.0] — 2026-05-05

> ⚠️ **早期产品（v0.x）—— state schema 仍可能 breaking**
>
> 在 v1.0 之前，每次升级可能改变 `.cheat-state.json` 的字段结构。**升级前建议 backup 你的整个 `<your-channel>/` 目录**。重大 breaking 改动会在本 CHANGELOG 标 `BREAKING`，并在可能的情况下给手动迁移步骤。

### Added

- **方法论 + 12 个子 skill**：完整闭环 init → learn-from → seed → score → predict → shoot → publish → retro → bump，加 status / recommend / trends 辅助
- **3 条不可妥协原则**：盲预测 + 升级=全量重打 + rubric 是工作台不是博物馆（详见 `shared-references/`）
- **`/cheat-learn-from` 对标账号导入**：5-10 条对标样本派生 base rubric 信号 + script patterns。两种 input 方式（粘文本 默认 / whisper 转录）+ 两种 data 方式（手填 / adapter 自动抓）
- **Buffer 警戒系统**（cadence-protocol）：按发布频率派生颜色阈值，断更预警
- **统一预测格式 + confidence 等级**：所有阶段同一 7 组件预测，header 显示 🔴/🟠/🟡/🟢/🔵 信心等级
- **prediction-immutability hook**：harness 层强制原则 #1（端到端验证 5/5 通过）
- **SessionStart auto-report hook**：每次开会话自动渲染状态报告
- **跨模型 bump 审核**（mcp__llm-chat__chat）：rubric 升级时调外部 LLM 独立判定
- **douyin-session adapter**（Playwright）：自动抓抖音视频 + 评论数据
- **whisper adapter**：转录视频文件为 transcript
- **9 份 templates** + **2 份 starter rubrics**（opinion-video v2 校准 / opinion-video-zero v0 等权）
- **score-curve.py**：预测精度收敛曲线诊断工具

### 软规则（Claude 判断为主，非死磕门槛）

下面规则**有默认参考值**但 Claude 可基于强信号软违反：

- bump 触发样本数（默认 ≥5，可基于强反例破例）
- 同向偏差触发（默认连续 ≥3 次，可基于 1 次极端偏差破例）
- benchmark 影响淡出（默认 calibration_samples ≥10，可基于"用户数据 vs benchmark 差异度"破例）
- observation 升格门槛（默认 ≥2 样本，可基于强信号破例）

软违反时 Claude 必须显式标注 `judgment-driven` 让用户审视。

### 硬约束（不可软违反）

- bump 验证 `THRESHOLD = 4/5`（统计刚性）
- prediction immutability hook（binary）
- `RETRO_WINDOW_DAYS = 3` 默认（用户可配置 1/7）
- 必须有 ≥3 条 benchmark 样本才能拆 pattern
- 必须 ≥20 top 评论才能完成 manual paste 复盘

### 已知 limitations

- **v0.x 无自动 migration**：升级时若 state schema 变了，老用户需手动 wipe + 重 init
- **adapter fragility**：抖音 / 小红书 adapter 依赖反爬绕过，平台改版时可能 break，需要持续维护
- **whisper 中文准确度**：medium 模型够用，long-form 准确度一般，关键稿子建议 manual review

---

## 升级指南（pre-v1.0）

每次 git pull 之后：

1. **Symlink 模式装（推荐）**：直接生效，无需重装
2. **Copy 模式装**：重跑 `bash install.sh --copy`
3. **如果 CHANGELOG 标了 `BREAKING`**：照 manual migration steps 操作。无 steps 时建议 wipe + 重 init
