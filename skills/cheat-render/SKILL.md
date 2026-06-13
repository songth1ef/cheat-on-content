---
name: cheat-render
description: 把分段视频口播稿（[口播]/[屏幕字]/[图示]）渲染成竖屏短视频成片（.mp4）。逐字弹出字幕 + 段间淡入淡出 + 流程图配图 + edge-tts 神经配音（4 音色每日轮值）+ 极简配乐。跨平台（Mac/Win/Linux）。触发词："出片 [path]"/"渲染视频 [path]"/"render [path]"/"把这稿子做成视频"/"生成短视频"。是 cheat-distribute 产出口播稿之后的「文案→视频」末端动作。
argument-hint: <script.md> [--themes dark] [--voice zh-CN-XxxNeural]
allowed-tools: Read, Bash, Glob, Grep
---

# /cheat-render — 文案稿 → 竖屏短视频成片

把一份分段口播稿渲染成可投稿的竖屏 mp4。核心目标：**把枯燥长文换成「刷得下去」的视频形式**，提高 AI 内容的消费率。

## Overview

```
[用户：出片 video-zh-full.md]
  ↓
[定位引擎 tools/text2video.py（本仓内）]
  ↓
[解析稿子：[口播]→配音 / [屏幕字]→大字幕 / [图示]→流程图]
  ↓
[edge-tts 配音（今日轮值音色）+ 逐帧渲染 + ffmpeg 合成]
  ↓
[out_dir/video-<theme>.mp4 — 成片落本地，不入 git]
```

## 输入稿格式

分段脚本，`## script` 段内每段用标注：

- `**[口播]**` 逐字稿 → 转配音 + 底部字幕（逐字弹出）
- `**[屏幕字]**` 关键词 → 屏幕中央大字幕
- `**[图示]**` `flow: A -> B -> C` → 竖向流程图（方框+下箭头，逐个弹出），可选

> 这正是 `platforms/video.md` / `cheat-distribute` 产出的口播稿形态，直接喂入即可。`video-zh.md`（60s 狠砍版）和 `video-zh-full.md`（全文完整版）都支持。

## 运行

1. **定位引擎**：本 skill 同仓的 `tools/text2video.py`。解析 skill 真实路径找到仓根，例如：
   ```bash
   ENGINE="$(cd "$(dirname "$(readlink "$HOME/.claude/skills/cheat-render/SKILL.md" 2>/dev/null || echo "$HOME/.claude/skills/cheat-render/SKILL.md")")/../tools" && pwd)/text2video.py"
   # 兜底：find ~ -path '*/cheat-on-content/tools/text2video.py' 2>/dev/null | head -1
   ```
2. **跑**：
   ```bash
   python3 "$ENGINE" <script.md> <out_dir> [--themes dark] [--voice zh-CN-XiaoxiaoNeural]
   ```
   - 默认 `--themes dark`（主风格）。可选 `gradient` / `light`，逗号分隔多出几版。
   - 不传 `--voice` → 自动用**今日轮值音色**。
3. **验收**：抽 1-2 帧确认（`ffmpeg -ss <t> -i out.mp4 -frames:v 1 chk.png` 后 Read），重点看流程图和字幕。
4. **交付**：`open <out_dir>`（Mac）/ 直接给路径。**提醒用户成片不入 git**（见下）。

## 配音：4 音色每日轮值

`VOICES = [Xiaoxiao(暖女声), Yunxi(阳光男声), Yunyang(新闻男声), Xiaoyi(活泼女声)]`，
按 `date.toordinal() % 4` **每天自动换一个**（用户 2026-06-13 定）。`--voice` 可手动钉某个。
全部走 edge-tts（免费、无需 key、神经网络音色），断网时仅 macOS 回退本地 `say`。

## 依赖（首次/新机器）

```bash
pip install --user Pillow edge-tts      # 跨平台
# ffmpeg：mac `brew install ffmpeg` / win `winget install ffmpeg` / linux `apt install ffmpeg`
```
中文字体：Mac 自带 Hiragino；Win 自带微软雅黑；Linux 需 `fonts-noto-cjk`（`apt install fonts-noto-cjk`）。
引擎按平台自动挑字体，找不到逐级回退。

## ⚠️ 成片不入 git

mp4 体积大（完整版 ~15M），**不进版本库**。在内容项目里加 `.gitignore`：
```
drafts/**/video-out*/
```
入 git 的只是「稿子（.md）+ 引擎（本仓 tools/）」这些 KB 级可复用资产；成片本地留存 / 投稿用。

## 与其它 skill 的接缝

- 上游：`cheat-distribute`（文章 → 多平台口播稿）→ 产出本 skill 的输入。
- 评分：出片前可先 `/cheat-score` 看稿子 rubric 分。
- 下游：成片走 `/cheat-shoot`（登记已拍）→ `/cheat-predict` → `/cheat-publish`。
