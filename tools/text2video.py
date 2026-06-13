#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text2video.py v2 — 把 video-zh.md 风格分段脚本（[口播]/[画面]/[屏幕字]）
渲染成带动效的竖屏短视频。

动效：逐字弹出字幕 + 段间淡入淡出 + 周轮值照片背景(Ken Burns 慢推+模糊+压暗) / 纯色时漂移光晕。
音频：edge-tts 神经网络中文配音(4 音色每日轮值，跨平台) + ffmpeg 合成极简环境配乐(压低混入)。
       edge-tts 失败时仅 macOS 回退本地 say。
依赖：edge-tts、ffmpeg、Pillow（跨平台 Mac/Win/Linux）。

用法：python3 text2video.py <script.md> <out_dir> [--themes dark,gradient,light] [--fps 25]
      [--voice zh-CN-XxxNeural] [--no-bg | --bg-day 0..6 | --bg-dir <path>] [--kicker <text>]
"""
import os, re, sys, math, glob, datetime, platform, subprocess, tempfile, shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

_SYS = platform.system()  # Darwin / Windows / Linux

W, H = 1080, 1920
FPS = 25
PAD = 0.5  # 段尾留白（含淡出）

# 4 个 edge-tts 音色，每日轮值（用户 2026-06-13 定）
VOICES = ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural",
          "zh-CN-YunyangNeural", "zh-CN-XiaoyiNeural"]
def todays_voice():
    return VOICES[datetime.date.today().toordinal() % len(VOICES)]

# 跨平台中文字体候选（按平台挑，找不到逐个回退，最后用 PIL 默认）
if _SYS == "Darwin":
    FONT_BOLD = [("/System/Library/Fonts/Hiragino Sans GB.ttc", 1),
                 ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
                 ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0)]
    FONT_REG  = [("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
                 ("/System/Library/Fonts/STHeiti Light.ttc", 0)]
elif _SYS == "Windows":
    FONT_BOLD = [("C:/Windows/Fonts/msyhbd.ttc", 0),   # 微软雅黑 Bold
                 ("C:/Windows/Fonts/msyh.ttc", 0),
                 ("C:/Windows/Fonts/simhei.ttf", 0)]   # 黑体
    FONT_REG  = [("C:/Windows/Fonts/msyh.ttc", 0),
                 ("C:/Windows/Fonts/simsun.ttc", 0)]
else:  # Linux
    FONT_BOLD = [("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
                 ("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf", 0),
                 ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0)]
    FONT_REG  = [("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
                 ("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf", 0),
                 ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0)]
_font_cache = {}
def font(size, bold=False):
    key = (size, bold)
    if key in _font_cache: return _font_cache[key]
    for path, idx in (FONT_BOLD if bold else FONT_REG):
        if os.path.exists(path):
            try: f = ImageFont.truetype(path, size, index=idx)
            except Exception:
                try: f = ImageFont.truetype(path, size)
                except Exception: continue
            _font_cache[key] = f; return f
    f = ImageFont.load_default(); _font_cache[key] = f; return f

def clean(text):
    text = text.replace("**", "").strip()
    out = []
    for ch in text:
        o = ord(ch)
        if o < 128 or 0x2010 <= o <= 0x206F or 0x2190 <= o <= 0x21FF \
           or 0x3000 <= o <= 0x303F or 0x4E00 <= o <= 0x9FFF or 0xFF00 <= o <= 0xFFEF:
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()

def parse_segments(md_path):
    raw = open(md_path, encoding="utf-8").read()
    m = re.search(r"##\s*script.*?\n(.*?)(?:\n##\s|\Z)", raw, re.S)
    body = m.group(1) if m else raw
    segs, cur = [], None
    for line in body.splitlines():
        line = line.strip()
        if "[口播]" in line:
            if cur: segs.append(cur)
            cur = {"oral": clean(line.split("[口播]")[-1]), "cap": "", "diagram": ""}
        elif "[屏幕字]" in line and cur is not None:
            cur["cap"] = clean(line.split("[屏幕字]")[-1])
        elif "[图示]" in line and cur is not None:
            cur["diagram"] = line.split("[图示]")[-1].replace("**", "").strip()
    if cur: segs.append(cur)
    return [s for s in segs if s["oral"]]

def parse_diagram(raw):
    raw = re.sub(r"^\s*flow\s*:", "", raw, flags=re.I)
    return [clean(x) for x in raw.split("->") if x.strip()]

def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == " " and not cur: continue
        t = cur + ch
        if draw.textlength(t, font=fnt) > max_w and cur:
            lines.append(cur); cur = ch if ch != " " else ""
        else: cur = t
    if cur.strip(): lines.append(cur)
    return lines

def take_chars(lines, k):
    """从 wrap 好的行里取前 k 个字符，返回 (整行..., 末行部分)"""
    out, rem = [], k
    for ln in lines:
        if rem <= 0: break
        if len(ln) <= rem:
            out.append(ln); rem -= len(ln)
        else:
            out.append(ln[:rem]); rem = 0
    return out

THEMES = {
    "dark":     dict(bg=(14,17,22),  grad=None,                 kicker=(120,130,145),
                     cap=(255,212,0), oral=(240,242,245), bar=(255,212,0),
                     glow=(255,212,0), dia_text=(245,245,245), dia_fill=(30,34,40)),
    "gradient": dict(bg=None, grad=((26,18,64),(8,10,28)),      kicker=(150,200,255),
                     cap=(255,255,255), oral=(200,212,228), bar=(110,231,255),
                     glow=(110,231,255), dia_text=(245,245,245), dia_fill=(34,30,66)),
    "light":    dict(bg=(245,243,236), grad=None,               kicker=(150,120,90),
                     cap=(24,24,24), oral=(70,70,70), bar=(229,72,69),
                     glow=(229,72,69), dia_text=(30,30,30), dia_fill=(255,255,255)),
}

def draw_chrome(d, theme, kicker_text):
    """画 kicker + 进度条底槽（两种背景模式共用）"""
    kf = font(40, True); kw = d.textlength(kicker_text, font=kf)
    d.text(((W-kw)/2, 188), kicker_text, font=kf, fill=theme["kicker"],
           stroke_width=2, stroke_fill=(0,0,0,170))
    d.rounded_rectangle([90, 1720, W-90, 1730], radius=5, fill=(255,255,255,40))

def base_layer(theme, kicker_text):
    """纯色/渐变静态层：背景 + chrome（每主题算一次，无照片时用）"""
    if theme["grad"]:
        top, bot = theme["grad"]; img = Image.new("RGB", (W, H)); px = img.load()
        for y in range(H):
            t = y/(H-1)
            px_row = (int(top[0]+(bot[0]-top[0])*t), int(top[1]+(bot[1]-top[1])*t),
                      int(top[2]+(bot[2]-top[2])*t))
            for x in range(W): px[x, y] = px_row
        img = img.convert("RGBA")
    else:
        img = Image.new("RGBA", (W, H), theme["bg"] + (255,))
    draw_chrome(ImageDraw.Draw(img, "RGBA"), theme, kicker_text)
    return img

# ---------- 照片背景（周一到周天轮值，Ken Burns 慢推 + 模糊 + 压暗，不抢文案）----------
def _cover(img, tw, th):
    w, h = img.size; sc = max(tw/w, th/h)
    img = img.resize((int(w*sc+0.5), int(h*sc+0.5)), Image.LANCZOS)
    nw, nh = img.size; x = (nw-tw)//2; y = (nh-th)//2
    return img.crop((x, y, x+tw, y+th))

BG_OVER = int(W*1.1), int(H*1.1)  # 比成片略大，留 Ken Burns 平移/缩放余量
def load_bg_base(bg_dir, day_override=None):
    """取今日(或指定)星期的背景照片 → cover + 模糊 + 压暗。无则 None。"""
    if not bg_dir or not os.path.isdir(bg_dir):
        return None
    wd = day_override if day_override is not None else datetime.date.today().weekday()  # 0=Mon
    exts = ("jpg", "jpeg", "png", "JPG", "JPEG", "PNG")
    # ① 优先按 <weekday>-* 命名精确选今天那张
    cand = []
    for ext in exts:
        cand += glob.glob(os.path.join(bg_dir, f"{wd}-*.{ext}"))
    if cand:
        pick = sorted(cand)[0]
    else:
        # ② 没有星期前缀 → 把目录里所有图按名排序，用 weekday 取模轮值（任意张数都能转）
        allimg = []
        for ext in exts:
            allimg += glob.glob(os.path.join(bg_dir, f"*.{ext}"))
        allimg = sorted(set(allimg))
        if not allimg:
            return None
        pick = allimg[wd % len(allimg)]
    img = Image.open(pick).convert("RGB")
    img = _cover(img, *BG_OVER)
    img = img.filter(ImageFilter.GaussianBlur(2))       # 极轻模糊，几乎无感；照片满亮度，不加任何暗罩（用户 2026-06-13 定）
    img = ImageEnhance.Color(img).enhance(1.06)         # 仅极轻提饱和；可读性全靠文字黑描边
    return img.convert("RGBA"), os.path.basename(pick)

def ken_burns(base, t, T):
    """从略大的背景底图里缓慢推近+平移裁出 1080x1920 当帧背景"""
    bw, bh = base.size; p = (t/T) if T > 0 else 0.0
    s = 1.0 + 0.06*p                                    # 慢推近
    cw, ch = min(int(W/s), bw), min(int(H/s), bh)
    mx, my = bw-cw, bh-ch
    cx = int(mx*(0.5 + 0.4*math.sin(p*math.pi)))        # 缓慢横移
    cy = int(my*(0.5 - 0.3*math.cos(p*math.pi*0.7)))
    return base.crop((cx, cy, cx+cw, cy+ch)).resize((W, H), Image.LANCZOS).convert("RGBA")

def glow_sprite(color):
    """半透明径向光晕精灵，用作背景轻动效"""
    R = 520; s = Image.new("RGBA", (R*2, R*2), (0,0,0,0)); px = s.load()
    cr, cg, cb = color
    for y in range(R*2):
        for x in range(R*2):
            dx, dy = x-R, y-R; dist = math.hypot(dx, dy)/R
            if dist < 1:
                a = int(46 * (1-dist)**2)
                if a: px[x, y] = (cr, cg, cb, a)
    return s

def render_diagram(d, nodes, frac, theme, a):
    """竖向流程图：方框 + 下箭头，随 frac 逐个出现。a=段透明度(0..1)"""
    n = len(nodes)
    if n == 0: return
    shown = max(1, math.ceil(n*frac))
    box_w = 860; x1 = (W-box_w)//2; x2 = x1+box_w
    gap = 46
    box_h = int(min(120, (720 - gap*(n-1))/n))
    fsize = max(26, min(40, box_h-44))
    total_h = n*box_h + (n-1)*gap
    y0 = 580 + (720-total_h)//2
    br,bgc,bb = theme["bar"]; tr,tg,tb = theme["dia_text"]; fr,fg,fb = theme["dia_fill"]
    bf = font(fsize, True)
    for i in range(shown):
        by1 = y0 + i*(box_h+gap); by2 = by1+box_h
        d.rounded_rectangle([x1,by1,x2,by2], radius=22,
                            fill=(fr,fg,fb,255),
                            outline=(br,bgc,bb,255), width=3)
        lines = wrap(d, nodes[i], bf, box_w-52)
        lh = int(fsize*1.24); th = len(lines)*lh
        ty = by1 + (box_h-th)//2
        for k, ln in enumerate(lines):
            lw = d.textlength(ln, font=bf)
            d.text(((W-lw)/2, ty+k*lh), ln, font=bf, fill=(tr,tg,tb,int(245*a)))
        if i < shown-1 and i < n-1:
            ax = W//2; ay2 = by2+gap-6
            d.line([ax, by2+6, ax, ay2-8], fill=(br,bgc,bb,int(235*a)), width=4)
            d.polygon([(ax-13,ay2-13),(ax+13,ay2-13),(ax,ay2)],
                      fill=(br,bgc,bb,int(235*a)))

def pop_line(img, text, fnt, cy, rgb, e, seg_a):
    """整行一次性「弹出」：缩放(0.72→1)+淡入，e=本行入场进度(0..1)。不是逐字打字。"""
    if e <= 0: return
    ease = 1-(1-e)**2
    scale = 0.72 + 0.28*ease
    alpha = ease*seg_a
    if alpha <= 0: return
    m = ImageDraw.Draw(img)
    tw = int(m.textlength(text, font=fnt)); asc, desc = fnt.getmetrics(); th = asc+desc
    pad = 16
    sp = Image.new("RGBA", (tw+2*pad, th+2*pad), (0,0,0,0))
    ImageDraw.Draw(sp).text((pad, pad), text, font=fnt, fill=rgb+(255,),
                            stroke_width=5, stroke_fill=(0,0,0,255))  # 黑描边：亮风景上也清晰
    if scale < 0.999:
        sp = sp.resize((max(1,int(sp.width*scale)), max(1,int(sp.height*scale))), Image.LANCZOS)
    if alpha < 0.999:
        sp.putalpha(sp.split()[3].point(lambda v: int(v*alpha)))
    img.paste(sp, (int(W/2 - sp.width/2), int(cy + (th - sp.height)/2)), sp)

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(" ".join(map(str,cmd))+"\n"+r.stderr[-1000:]+"\n"); raise SystemExit(1)
    return r

def dur(path):
    return float(run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","csv=p=0", path]).stdout.strip())

def main():
    md, out_dir = sys.argv[1], sys.argv[2]
    themes = ["dark","gradient","light"]
    fps = FPS
    if "--themes" in sys.argv: themes = sys.argv[sys.argv.index("--themes")+1].split(",")
    if "--fps" in sys.argv: fps = int(sys.argv[sys.argv.index("--fps")+1])
    voice = sys.argv[sys.argv.index("--voice")+1] if "--voice" in sys.argv else todays_voice()
    kicker = sys.argv[sys.argv.index("--kicker")+1] if "--kicker" in sys.argv else "AI 文章 · 看完不费劲"
    # 照片背景（周轮值）：默认引擎同目录 backgrounds/；--no-bg 关闭；--bg-day 0..6 钉星期
    bg_dir = sys.argv[sys.argv.index("--bg-dir")+1] if "--bg-dir" in sys.argv \
             else os.path.join(os.path.dirname(os.path.abspath(__file__)), "backgrounds")
    bg_day = int(sys.argv[sys.argv.index("--bg-day")+1]) if "--bg-day" in sys.argv else None
    bg_loaded = None if "--no-bg" in sys.argv else load_bg_base(bg_dir, bg_day)
    bg_base = bg_loaded[0] if bg_loaded else None
    os.makedirs(out_dir, exist_ok=True)
    print(f"[voice] 今日值班音色: {voice}")
    print(f"[bg] 背景照片: {bg_loaded[1] if bg_loaded else '无（用纯色/渐变）'}")

    segs = parse_segments(md); n = len(segs)
    for s in segs:
        s["dnodes"] = parse_diagram(s["diagram"]) if s.get("diagram") else None
    print(f"[parse] {n} 段")
    work = tempfile.mkdtemp(prefix="t2v_")

    # 1) TTS（edge-tts 神经网络音色）一次，复用；同时建 voice.wav（含段尾留白）
    seg_meta = []  # (start, voicedur, segdur)
    wavs, t0 = [], 0.0
    for i, s in enumerate(segs):
        mp3 = os.path.join(work, f"a{i}.mp3")
        try:
            run([sys.executable,"-m","edge_tts","--voice",voice,"--rate","+8%",
                 "--text", s["oral"], "--write-media", mp3])
        except SystemExit:           # edge-tts 失败（网络/未装）→ 平台兜底
            if _SYS == "Darwin":     # 仅 macOS 有本地 say
                aiff = os.path.join(work, f"a{i}.aiff")
                run(["say","-v","Tingting","-o",aiff, s["oral"]])
                mp3 = aiff
            else:
                sys.stderr.write("edge-tts 失败，且本平台无本地 TTS 兜底（仅 macOS 有 say）。"
                                 "请检查网络或 `pip install edge-tts`。\n")
                raise
        vd = dur(mp3); sd = vd + PAD
        wav = os.path.join(work, f"a{i}.wav")
        run(["ffmpeg","-y","-loglevel","error","-i",mp3,"-t",f"{sd:.3f}",
             "-af","apad","-ar","44100","-ac","2", wav])
        wavs.append(wav); seg_meta.append((t0, vd, sd)); t0 += sd
        print(f"[tts] 段{i+1} 语音{vd:.1f}s")
    T = t0
    listf = os.path.join(work, "vlist.txt")
    open(listf,"w").write("".join(f"file '{w}'\n" for w in wavs))
    voice = os.path.join(work, "voice.wav")
    run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",listf,
         "-c","copy", voice])

    # 2) 极简环境配乐（合成，低音量），长度 = T
    music = os.path.join(work, "music.wav")
    run(["ffmpeg","-y","-loglevel","error",
         "-f","lavfi","-i",f"sine=frequency=220:duration={T:.2f}",
         "-f","lavfi","-i",f"sine=frequency=164.81:duration={T:.2f}",
         "-f","lavfi","-i",f"sine=frequency=110:duration={T:.2f}",
         "-filter_complex",
         "[0][1][2]amix=inputs=3:normalize=0,tremolo=f=0.12:d=0.6,"
         "lowpass=f=520,volume=0.10,aecho=0.8:0.5:90:0.25,afade=t=in:d=2,"
         f"afade=t=out:st={max(0,T-2):.2f}:d=2",
         "-ar","44100","-ac","2", music])

    def seg_at(t):
        for i,(st,vd,sd) in enumerate(seg_meta):
            if t < st+sd: return i, t-st, vd, sd
        i = n-1; st,vd,sd = seg_meta[-1]; return i, t-st, vd, sd

    glow_cache = {}
    nframes = int(T*fps)
    for theme_name in themes:
        theme = THEMES[theme_name]
        base = base_layer(theme, kicker)
        # 照片背景只用于深色主题（浅色主题深字压在暗照片上会看不清）
        use_photo = (bg_base is not None) and (theme_name != "light")
        if theme["glow"] not in glow_cache:
            glow_cache[theme["glow"]] = glow_sprite(theme["glow"])
        glow = glow_cache[theme["glow"]]
        # 预算每段 caption / oral 的 wrap（用临时 draw 量）
        td = ImageDraw.Draw(base)
        seg_lines = []
        for s in segs:
            cap = s["cap"] or s["oral"]
            for size in (96,84,72,62):
                cf = font(size, True); cl = wrap(td, cap, cf, 900)
                if len(cl)*int(size*1.32) <= 720: break
            of = font(50, False); ol = wrap(td, s["oral"], of, 920)
            seg_lines.append((cap, cf, cl, size, of, ol))

        fdir = os.path.join(work, theme_name); os.makedirs(fdir, exist_ok=True)
        for fr in range(nframes):
            t = fr/fps
            i, local, vd, sd = seg_at(t)
            cap, cf, clines, csize, of, olines = seg_lines[i]
            if use_photo:
                # 照片背景：Ken Burns 慢推 + chrome（kicker/进度槽每帧画）
                img = ken_burns(bg_base, t, T)
                d = ImageDraw.Draw(img, "RGBA")
                draw_chrome(d, theme, kicker)
            else:
                img = base.copy()
                d = ImageDraw.Draw(img, "RGBA")
                # 纯色背景才加漂移光晕（照片背景本身已有质感，不叠）
                gx = int(W/2 + 280*math.sin(t*0.5) - 520)
                gy = int(H*0.42 + 200*math.cos(t*0.37) - 520)
                img.paste(glow, (gx, gy), glow)

            # 段淡入淡出
            fin = min(local/0.35, 1.0)
            fout = min((sd-local)/0.3, 1.0)
            a = max(0.0, min(fin, fout))

            # 逐字弹出（字幕领先语音一点）
            frac = max(0.0, min(local/(vd*0.9), 1.0)) if vd>0 else 1.0

            cr,cg,cb = theme["cap"]; calpha = int(255*a)
            if segs[i].get("dnodes"):
                # 配图段：小标题(屏幕字) + 流程图配图
                htxt = segs[i]["cap"]
                if htxt:
                    hf = font(48, True); hw = d.textlength(htxt, font=hf)
                    d.text(((W-hw)/2, 492), htxt, font=hf, fill=(cr,cg,cb,calpha),
                           stroke_width=3, stroke_fill=(0,0,0,calpha))
                render_diagram(d, segs[i]["dnodes"], frac, theme, a)
            else:
                # 大字幕：整行「弹出」（不是逐字打字）；多行时一行接一行整条弹
                lh = int(csize*1.32); nlines = len(clines)
                block_h = nlines*lh; y0 = 560 + (760-block_h)//2
                POP = 0.30                                   # 单行入场时长(s)
                span = max(vd*0.45, 0.4)                     # 多行入场铺开的总时长
                for k, ln in enumerate(clines):
                    line_start = (k/nlines)*span if nlines > 1 else 0.0
                    e = max(0.0, min((local-line_start)/POP, 1.0))
                    pop_line(img, ln, cf, y0+k*lh, (cr,cg,cb), e, a)

            # 底部口播字幕
            olh = int(50*1.34); total_o = sum(len(l) for l in olines)
            oshown = take_chars(olines, math.ceil(total_o*frac))
            oy = 1640 - len(olines)*olh
            orr,org,orb = theme["oral"]; oalpha = int(235*a)
            for k, ln in enumerate(oshown):
                lw = d.textlength(ln, font=of)
                d.text(((W-lw)/2, oy+k*olh), ln, font=of, fill=(orr,org,orb,oalpha),
                       stroke_width=3, stroke_fill=(0,0,0,oalpha))

            # 进度条（全局连续）
            br,bg_,bb = theme["bar"]
            fillw = 90 + (W-180)*min(t/T,1.0)
            d.rounded_rectangle([90,1720,fillw,1730], radius=5, fill=(br,bg_,bb,255))
            nf = font(34, True)
            d.text((90,1756), f"{i+1} / {n}", font=nf, fill=theme["kicker"])

            img.convert("RGB").save(os.path.join(fdir, f"f{fr:05d}.jpg"), quality=90)
            if fr % 200 == 0: print(f"[{theme_name}] 帧 {fr}/{nframes}")

        out_mp4 = os.path.join(out_dir, f"video-{theme_name}.mp4")
        run(["ffmpeg","-y","-loglevel","error",
             "-framerate",str(fps),"-i",os.path.join(fdir,"f%05d.jpg"),
             "-i",voice,"-i",music,
             "-filter_complex","[1:a][2:a]amix=inputs=2:weights=1 0.5:normalize=0:duration=first[a]",
             "-map","0:v","-map","[a]",
             "-c:v","libx264","-r",str(fps),"-pix_fmt","yuv420p",
             "-c:a","aac","-b:a","192k","-movflags","+faststart", out_mp4])
        print(f"[done] {out_mp4}  {dur(out_mp4):.1f}s")

    shutil.rmtree(work, ignore_errors=True)
    print("\n=== 产出 ===")
    for tn in themes:
        print(f"{out_dir}/video-{tn}.mp4")

if __name__ == "__main__":
    main()
