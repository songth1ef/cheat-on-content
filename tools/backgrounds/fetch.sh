#!/usr/bin/env bash
# 抓取「周一到周天」7 张 CC0 背景照片（Picsum，免费免署名）。
# text2video.py 按 weekday() 选 <0-6>-<day>.jpg 做 Ken Burns 背景。
# 幂等：已存在的跳过，缺的补。需要网络。
set -euo pipefail
cd "$(dirname "$0")"

# weekday(0=Mon..6=Sun) -> Picsum 固定 ID（偏风景/自然/建筑；换图改这里）
ids=(1018 1015 1016 1036 1039 1043 1037)
days=(0-mon 1-tue 2-wed 3-thu 4-fri 5-sat 6-sun)

for i in 0 1 2 3 4 5 6; do
  f="${days[$i]}.jpg"
  if [ -s "$f" ]; then echo "  skip $f"; continue; fi
  url="https://picsum.photos/id/${ids[$i]}/1188/2112"
  code=$(curl -sL -o "$f" -w "%{http_code}" --max-time 30 "$url" || echo 000)
  if file "$f" 2>/dev/null | grep -q -E 'JPEG|PNG'; then echo "  ✓ $f (id ${ids[$i]})"
  else echo "  ✗ $f HTTP $code"; rm -f "$f"; fi
done
echo "完成。手动换主题：把任意 1188x2112+ 的 CC0 图命名 <0-6>-*.jpg 放这里即可。"
