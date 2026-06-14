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

1. **定位启动器**：用跨平台启动器 `tools/render-run.sh`，它自己解析引擎路径 + 跨平台选/建 Python（见「依赖」节），**不要**直接 `python3 text2video.py`（PEP668 机器会失败）。cheat-render 是「目录符号链接」(SKILL.md 本身不是链接)，用 `cd -P` 物理穿透找仓根：
   ```bash
   # 仓内布局: cheat-on-content/{skills/cheat-render, tools/render-run.sh} → 从 skill 目录上跳两级
   RUN="$(cd -P "$HOME/.claude/skills/cheat-render" 2>/dev/null && cd ../../tools 2>/dev/null && pwd)/render-run.sh"
   # 兜底(copy 安装模式等)：[ -f "$RUN" ] || RUN="$(find "$HOME/.claude" "$HOME" -path '*/cheat-on-content/tools/render-run.sh' 2>/dev/null | head -1)"
   ```
2. **跑**（启动器透传参数给 text2video.py；首次在 PEP668 机器上会自动建 venv 装依赖）：
   ```bash
   bash "$RUN" <script.md> <out_dir> [--themes dark] [--voice zh-CN-XiaoxiaoNeural]
   ```
   - 默认 `--themes dark`（主风格）。可选 `gradient` / `light`，逗号分隔多出几版。
   - 不传 `--voice` → 自动用**今日轮值音色**。
   - Windows 原生无 bash → 用 Git Bash 跑 `bash render-run.sh ...`，或手动 `<venv>\Scripts\python.exe text2video.py ...`。
3. **验收**：抽 1-2 帧确认（`ffmpeg -ss <t> -i out.mp4 -frames:v 1 chk.png` 后 Read），重点看流程图和字幕。
4. **交付**：`open <out_dir>`（Mac）/ 直接给路径。**提醒用户成片不入 git**（见下）。

## 背景：周一到周天照片轮值（Ken Burns + 压暗模糊）

默认给视频铺一张**循环慢移的照片背景**：`tools/backgrounds/<0-6>-<day>.jpg` 按 `weekday()` 选今天那张，做 Ken Burns 慢推 + 高斯模糊 + 压暗到 ~34% → **ambient，绝不抢文案注意力**。深色主题专用（light 主题自动跳过用纯色）。

- 选项：`--no-bg` 关掉用纯色；`--bg-day 0..6` 钉某天（0=周一）；`--bg-dir <path>` 换图库。
- 换/补图：跑 `tools/backgrounds/fetch.sh`（Picsum CC0，免费免署名，幂等），或把任意 1188×2112+ 的 CC0 图命名 `<0-6>-*.jpg` 丢进 `tools/backgrounds/`。
- 默认 7 张是风景/自然/建筑向；要人文/逛街等主题自行换图即可，文件名定星期。

## 配音：4 音色每日轮值

`VOICES = [Xiaoxiao(暖女声), Yunxi(阳光男声), Yunyang(新闻男声), Xiaoyi(活泼女声)]`，
按 `date.toordinal() % 4` **每天自动换一个**（用户 2026-06-13 定）。`--voice` 可手动钉某个。
全部走 edge-tts（免费、无需 key、神经网络音色），断网时仅 macOS 回退本地 `say`。

## 依赖（跨平台，启动器自动处理）

Python 依赖 = **Pillow + edge-tts**。**正常不用手动装**——`render-run.sh` 会按平台自动选/建：
- **mac / Windows**：一般系统 python 已能 `pip install --user Pillow edge-tts`，启动器探测到就直接用。
- **PEP668 系统（Debian/Ubuntu/魅族 proot 等，pip 报 externally-managed）**：启动器**自动**在 `tools/.venv` 建专用 venv 装依赖（已 gitignore）。别用 `--break-system-packages` 污染系统 python。
- 想手动预建也行：`python3 -m venv <dir> && <dir>/bin/pip install Pillow edge-tts`（Win 是 `<dir>\Scripts\pip`）；启动器会探测 `tools/.venv` / `$HOME/.venv-render` / `/root/cy/.venv-render`。

系统级依赖（启动器**不**代装，缺了要自己装）：
- **ffmpeg**：mac `brew install ffmpeg` / win `winget install ffmpeg` / linux `apt install ffmpeg`。
- **python3-venv**：部分 Debian/Ubuntu 建 venv 需 `apt install python3-venv`。
- **联网**：edge-tts 配音要联网；断网仅 macOS 回退本地 `say`。

中文字体**无需安装**：引擎自带可商用 Noto Sans SC（`tools/fonts/NotoSansSC.ttf`），跨平台一致。仅当该字体缺失才回退系统字体（Mac Hiragino / Win 微软雅黑 / Linux Noto CJK）。

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
