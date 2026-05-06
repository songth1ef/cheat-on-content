# Cheat on Content

> 做内容本质上就是作弊——谁先看穿规律，谁就拿走流量。
> 凭感觉发是**猜**，这套让你**算**。也叫**网红外挂**。
> 我用它一个月涨粉 100w —— 不是灵感，是系统。

[![Version](https://img.shields.io/badge/version-v0.1.0-orange)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🎬 它真正在干什么

90% 的创作者都活在同一个循环里：

> 凭感觉发 → 数据出来发现拉了 → 不知道为什么拉 → 下一条还是凭感觉

爆了不知道为啥爆，扑了学不到东西。一年发 200 条，水平和第一天一样——只是更累。

**网红外挂**把每一篇都强行变成一次校准实验：

📊 打分 → 🎯 盲预测 → 🚀 发布 → 📈 T+3 天复盘 → 🧬 进化你的评分公式

跑一个月 = 你有了一份**只属于你的爆款公式**。
跑三个月 = 你比刚开始的自己强 10 倍。

---

## ⚖️ 它和别的"创作工具"哪里不一样

| 别人 | 这个 |
|---|---|
| 给你"灵感" | 让你**自己的灵感被量化** |
| AI 帮你写 | AI 帮你**判**——稿子还是你的 |
| 一发发 10 个版本 A/B 测 | 一发就**赌**——把判断写下来，数据出来对账 |
| 静态数据看板 | **会进化的评分公式**——你三个月后的 rubric 已经不是初始版 |

一句话：别的工具帮你"产出更多"，这个工具帮你"判得更准"。

---

## 🤔 那 ChatGPT / 豆包 / DeepSeek 不是也能干这个？

那是**通用助手**——对所有人说同样的话。你问"我这条会爆吗"，它的答案是从全网平均经验拟合出来的，跟你的账号没关系。明天再问一遍，答案还是上次那个——**它不记得你，更不会因为你而变**。

这套是**你自己的运营专家**，只服务你这一个账号：

- 评分公式从**你的**历史数据反推，不是通用训练分布
- 每发一条它就更新一次对你账号的理解——三个月后判断准度比刚开始强 10 倍（**自动进化**）
- 它知道你的对标账号、你的发布 cadence、你最近三次为什么扑——这些 ChatGPT 第一句话就忘了

通用 LLM 帮所有人；这套帮你**这个**账号。

---

## 🛡️ 它怎么让循环真的能进化

📝 **每条都留底**：发布前打分、写预测，全程存档。三天后回来对账——你哪里准、哪里偏，**一目了然**，不再是模糊的"感觉这次没发好"。

🔁 **越用越准**：连续三次同方向偏差，工具自动催你升级评分公式。**你不主动它也催**。

🛡️ **升级有刹车**：换公式必须用新公式重判所有历史样本，能比旧公式更准才放行；还要跨模型独立审一次——**防你自己骗自己**。

🪒 **rubric 是工作台不是博物馆**：被推翻的观察删，被吸收的也删。永远只放当下最有用的。

---

## 📦 安装

### Claude Code

```bash
git clone https://github.com/XBuilderLAB/cheat-on-content.git
cd cheat-on-content
bash install.sh
```

13 个子 skill 软链接到 `~/.claude/skills/`。装一次，所有内容项目都能用。

### Codex

```bash
git clone https://github.com/XBuilderLAB/cheat-on-content.git
cd cheat-on-content
bash install.sh --codex
```

Codex 会安装根路由 skill `cheat-on-content` + 13 个子 skill 到 `~/.codex/skills/`。如果当前 Codex 会话看不到新 skill，重开一次会话。

> 同时安装 Claude Code + Codex：`bash install.sh --all`
>
> 冻结版本：`bash install.sh --copy` / `bash install.sh --codex --copy`
>
> 卸载：`bash uninstall.sh` / `bash uninstall.sh --codex`（不动你的内容数据）

---

## 🚀 第一次跑

在你的内容项目目录里开 Claude Code 或 Codex，说：

```
初始化 cheat-on-content
```

5 个 yes/no 搞定 onboarding。**强烈建议导对标账号**——5-10 条样本 → 工具立刻有 anchor，不然前 5 篇预测精度 ±50%。

---

## ⚡ 日常用法

```
打分这篇 scripts/<...>.md         → 评分
启动预测 scripts/<...>.md         → 盲预测 + 决策日志
拍了 scripts/<...>.md            → 建 video folder + buffer +1
已发布 https://...                → buffer -1
复盘 videos/<...>/                → T+3d 数据回收 + 复盘
状态 / 抓热点 / 找选题 / 升级 rubric / 找对标
```

Claude Code 每次开会话 hook 自动报告 buffer + 待复盘 + top 候选——你不用主动问。Codex 当前没有等价 hook 自动注入，直接说 `状态` 可获得同样看板。

完整工作流 + 子 skill 细节见 [SKILL.md](SKILL.md)。

---

## 📜 License

MIT。商用、改造、闭源接入都行。

---

*这是作弊吗？计算器也是。Google 也是。
未来不奖励努力——它奖励先看见规律的人。*
