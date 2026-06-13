---
name: cheat-distribute
description: 把一篇博客文章分发成多平台/多形态原生稿（文字版/视频口播稿 × 中/英）。读内容项目的 platforms/registry.json 矩阵，每格注入{对应语言原文 + 该 form 的 profile（视频还读 script_patterns/rubric_notes）}产出 drafts/<slug>/<form>-<lang>.md。是「文章→多元文案」的生成动作，下游接 cheat-render（出片）和 cheat-score/predict（校准）。触发词："分发 [slug]"/"distribute [slug]"/"把这篇做成多平台稿"/"生成多元文案"/"一篇变多篇"。
argument-hint: <slug | 源文章路径> [--forms text,video] [--langs zh,en]
allowed-tools: Read, Glob, Grep, Write, Bash
---

# /cheat-distribute — 一篇博客 → N 份平台原生稿

把一篇文章按「形式 × 语言」矩阵分发成多份**平台原生底稿**。不是机械「1 变 7」水货——价值全在平台原生度，靠 `platforms/` 的 profile 注入。

## Overview

```
[用户：分发 2026-06-13-workspace-as-work-os]
  ↓
[读 platforms/registry.json → matrix 枚举启用的 (form,lang)]
  ↓  对每个组合：
[定位该语言原文] + [读 form profile(text.md/video.md)] + [video 还读 script_patterns+rubric_notes]
  ↓
[按 profile 第10节「skill 输出物」生成原生稿]
  ↓
[写 drafts/<slug>/<form>-<lang>.md（带 frontmatter）]
  ↓
[汇报：生成了哪几份 + 下一步(cheat-render 出片 / cheat-score 打分)]
```

## 前置：在内容项目目录跑

本 skill 在内容项目（有 `platforms/`、`drafts/`、`.cheat-state.json` 的仓，如 mycontent）里运行。先确认 `platforms/registry.json` 存在；不存在说明项目没建分发层，提示用户。

## 步骤

### 1. 解析输入 + 定位博客源

- 入参可以是 **slug**（如 `2026-06-13-workspace-as-work-os`）或**直接的源文章路径**。
- 博客仓是唯一母体，本地 checkout 路径**因机而异**（registry 里 `source.local_path` 是写它的那台机的值，别盲信）。动态解析：
  ```bash
  # ① 先信 registry 的 local_path（仅当本机真存在）；② 常见 checkout 位置；③ find 兜底（articles 在 ~ 下约 7 层深，maxdepth 给足）
  BLOG=$(python3 -c "import json,os;p=json.load(open('platforms/registry.json'))['source']['local_path'];print(p if os.path.isdir(p) else '')" 2>/dev/null)
  for c in ~/Desktop/code/github/blog ~/github/blog ~/code/blog ~/cy/blog; do
    [ -n "$BLOG" ] && break; [ -d "$c/src/content/articles" ] && BLOG="$c"
  done
  [ -n "$BLOG" ] || BLOG=$(find ~ -maxdepth 8 -type d -path '*/src/content/articles' -prune 2>/dev/null | head -1 | sed 's#/src/content/articles##')
  ```
  - 中文源：`$BLOG/<zh_glob 去掉 *>/<slug>.md`（默认 `src/content/articles/<slug>.md`）
  - 英文源：`$BLOG/src/content/articles/en/<slug>.md`
- 找不到源 → 报清楚缺哪个文件，不要硬编路径瞎猜。

### 2. 读矩阵

读 `platforms/registry.json` 的 `matrix`，取 `enabled:true` 的 `(form,lang)` 组合（默认 4 格：text-zh / text-en / video-zh / video-en）。`--forms` / `--langs` 可缩小范围。
每个 form 的 `profile` 字段指向 `platforms/<profile>`；`needs_script_patterns:true`（视频）的要多读两份 pattern。

### 3. 逐组合生成

对每个 `(form,lang)`：
1. 定位**该语言**原文（缺 en 源就跳过 en 组合，并在汇报里说明——en 是给 X/YouTube 的英文受众，不从中文机翻）。
2. 读 `platforms/<profile>`（如 `video.md` / `text.md`）。
3. 若 `needs_script_patterns` → **先读** `script_patterns.md` + `rubric_notes.md`，复用已沉淀写作 pattern，不另起炉灶。
4. 按 profile 的 **§10 skill 输出物** 生成那一份原生稿（text：titles/summary/body/tags；video：hooks/script/titles/tags/duration_est）。`lang:en` 取结构原则按英文受众适配，不要机翻腔。
5. **profile 是 toolbox 不是 mold**——内容本身最强属性和 profile 冲突时以内容为准（同 script_patterns 的 meta 原则）。

### 4. 写底稿

写到 `drafts/<slug>/<form>-<lang>.md`，frontmatter 固定：
```yaml
---
form: <text|video>
lang: <zh|en>
source_slug: <slug>
source_title: <取自源文 frontmatter 的 title>
generated: <今天日期 YYYY-MM-DD，用 `date +%F`>
status: draft
publish: <取自 matrix 该格的 publish>
---
```
正文随后接 profile §10 要求的字段。已存在同名 draft 时**先问**是否覆盖（别默默盖掉手改过的稿）。

### 5. 汇报 + 交接

列出生成了哪几份、跳过了哪些（及原因）。给下一步：
- 视频稿 → **`/cheat-render <video-draft>`** 出竖屏短视频成片。
- 任一稿 → **`/cheat-score`** 看 rubric 分，再决定是否 `/cheat-predict`。

## 可选：平台级微调（legacy）

矩阵默认只出「form 通用底稿」。要把某份底稿打磨成**特定平台**原生稿（知乎/微博/掘金/抖音/B站/X/公众号/YouTube），再拿 `registry.json._platforms_legacy` 里对应的 `platforms/<platform>.md` 注入二次改写。按需后置，不默认跑。

## 与其它 skill 的接缝

```
博客文章(songth1ef/blog)
   │  cheat-distribute  ← 本 skill
   ▼
drafts/<slug>/{text,video}-{zh,en}.md
   │  video 稿 → cheat-render → mp4 成片
   │  任一稿 → cheat-score → cheat-predict → cheat-publish → cheat-retro
   ▼
校准循环（rubric 反馈）
```
