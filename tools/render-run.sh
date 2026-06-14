#!/usr/bin/env bash
# render-run.sh — text2video.py 的跨平台启动器（Mac / Windows-GitBash / Linux / proot）。
#
# 为什么需要它：不同环境拿 Python 依赖（Pillow + edge-tts）的方式不一样——
#   - mac / windows：一般 `pip install --user` 直接可用 → 系统 python 就行。
#   - Debian/Ubuntu/魅族 proot：PEP668「externally-managed」禁止 pip 装系统包 → 必须用 venv。
# 本脚本统一解决：找一个「能 import PIL+edge_tts」的 python；找不到就地建 venv 装依赖再用。
# batch 脚本和 cheat-render skill 都调它，不再各自写死路径/布局。
#
# 用法：bash render-run.sh <script.md> <out_dir> [text2video.py 的其余参数...]
set -uo pipefail

SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$SCRIPT_DIR/text2video.py"
[ -f "$ENGINE" ] || { echo "✗ 找不到引擎 $ENGINE"; exit 1; }

have_deps() { "$1" -c "import PIL, edge_tts" >/dev/null 2>&1; }

# 一个 venv base 下，POSIX 用 bin/，Windows 用 Scripts/——都试
venv_py() {
  for p in "$1/bin/python" "$1/bin/python3" "$1/Scripts/python.exe"; do
    [ -x "$p" ] && { echo "$p"; return 0; }
  done
  return 1
}

PY=""

# 1) 已存在且带齐依赖的 venv（仓内 .venv 优先，其次历史/通用位置）
for base in "$SCRIPT_DIR/.venv" "$HOME/.venv-render" "/root/cy/.venv-render"; do
  cand="$(venv_py "$base" 2>/dev/null)" && have_deps "$cand" && { PY="$cand"; break; }
done

# 2) 系统 python 本身就带依赖（mac/win 常见）
if [ -z "$PY" ]; then
  for cand in python3 python py; do
    command -v "$cand" >/dev/null 2>&1 && have_deps "$cand" && { PY="$(command -v "$cand")"; break; }
  done
fi

# 3) 都没有依赖 → 在仓内 tools/.venv 建专用 venv 并安装（PEP668 机器走这条）
if [ -z "$PY" ]; then
  BASEPY=""
  for cand in python3 python py; do command -v "$cand" >/dev/null 2>&1 && { BASEPY="$cand"; break; }; done
  [ -z "$BASEPY" ] && { echo "✗ 未找到 python3/python/py，请先安装 Python 3"; exit 1; }
  echo "[setup] 首次运行：在 $SCRIPT_DIR/.venv 建专用 venv 并安装 Pillow/edge-tts ..."
  "$BASEPY" -m venv "$SCRIPT_DIR/.venv" || { echo "✗ venv 创建失败（Linux 需先 apt install python3-venv）"; exit 1; }
  PY="$(venv_py "$SCRIPT_DIR/.venv")" || { echo "✗ venv 里找不到 python"; exit 1; }
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet Pillow edge-tts || { echo "✗ 依赖安装失败（需联网）"; exit 1; }
  echo "[setup] 完成。"
fi

exec "$PY" "$ENGINE" "$@"
