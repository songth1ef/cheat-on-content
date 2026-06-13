#!/usr/bin/env bash
# 抓取「周一到周天」7 张真实壮景照片（Wikimedia Commons，CC 授权，多数需署名）。
# text2video.py 按 weekday() 选 <0-6>-<day>.jpg 做 Ken Burns 背景。
# 幂等：已存在的跳过。需要网络。换主题改下面 Q 里的搜索词即可。
# ⚠️ 许可：Commons 多为 CC-BY/CC-BY-SA → 公开发布时需在简介署名作者；要免署名改用 Unsplash/Pexels(需 key) 或 CC0。
set -euo pipefail
cd "$(dirname "$0")"

# weekday(0=Mon..6=Sun) -> 主题搜索词（具名地标偏向真实照片，避免画作/地图）
Q=(
 "0-mon|Himalaya mountain lake reflection"
 "1-tue|Aurora borealis Iceland"
 "2-wed|Grand Canyon Arizona"
 "3-thu|Niagara Falls Horseshoe"
 "4-fri|Sahara desert dunes"
 "5-sat|Moraine Lake Banff"
 "6-sun|Zhangjiajie mountains"
)
api="https://commons.wikimedia.org/w/api.php"
for item in "${Q[@]}"; do
  day="${item%%|*}"; q="${item#*|}"
  [ -s "$day.jpg" ] && { echo "  skip $day.jpg"; continue; }
  enc=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]+' filetype:bitmap'))" "$q")
  url=$(curl -sL --max-time 30 "$api?action=query&format=json&generator=search&gsrsearch=$enc&gsrnamespace=6&gsrlimit=1&prop=imageinfo&iiprop=url&iiurlwidth=2400" 2>/dev/null \
       | python3 -c "import sys,json;d=json.load(sys.stdin);ps=list(d.get('query',{}).get('pages',{}).values());print(ps[0]['imageinfo'][0]['thumburl'] if ps else '')" 2>/dev/null)
  if [ -n "$url" ] && curl -sL -o "$day.jpg" --max-time 50 "$url" 2>/dev/null && \
     python3 -c "from PIL import Image;import sys;w=Image.open('$day.jpg').size[0];sys.exit(0 if w>=1600 else 1)" 2>/dev/null; then
    echo "  ✓ $day.jpg [$q]"
  else echo "  ✗ $day [$q] 失败/过小"; rm -f "$day.jpg"; fi
done
echo "完成。换主题：改 Q 里的搜索词；或把任意 1600px+ 宽的图命名 <0-6>-*.jpg 放这里。"
