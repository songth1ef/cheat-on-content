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
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

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
# bundled 可商用字体（Noto Sans SC, SIL OFL）—— 优先用它，跨平台一致 + 可商用嵌入
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTO = os.path.join(_ENGINE_DIR, "fonts", "NotoSansSC.ttf")
FONT_SCALE = 1.2  # 所有字体 ×1.2（用户 2026-06-13 定）
_font_cache = {}
def font(size, bold=False):
    size = int(round(size * FONT_SCALE))
    key = (size, bold)
    if key in _font_cache: return _font_cache[key]
    f = None
    if os.path.exists(NOTO):                       # 可变字体：wght 700=Bold / 400=Regular
        try:
            f = ImageFont.truetype(NOTO, size)
            try: f.set_variation_by_axes([700 if bold else 400])
            except Exception: pass
        except Exception:
            f = None
    if f is None:                                  # 回退系统字体（无 bundled 字体时）
        for path, idx in (FONT_BOLD if bold else FONT_REG):
            if os.path.exists(path):
                try: f = ImageFont.truetype(path, size, index=idx); break
                except Exception:
                    try: f = ImageFont.truetype(path, size); break
                    except Exception: continue
    if f is None: f = ImageFont.load_default()
    _font_cache[key] = f; return f

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
            txt = clean(line.split("[口播]")[-1])
            # 连续 [口播] 合并进同一段（到出现 [屏幕字]/[图示] 才算该段完成）→ 避免没屏幕字的口播被当大字幕
            if cur is not None and not cur["cap"] and not cur["diagram"]:
                cur["oral"] = (cur["oral"] + " " + txt).strip()
            else:
                if cur: segs.append(cur)
                cur = {"oral": txt, "cap": "", "diagram": ""}
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
                     cap=(255,255,255), oral=(245,245,245), bar=(255,255,255),
                     glow=(255,255,255), dia_text=(245,245,245), dia_fill=(30,34,40)),
    "gradient": dict(bg=None, grad=((26,18,64),(8,10,28)),      kicker=(150,200,255),
                     cap=(255,255,255), oral=(200,212,228), bar=(110,231,255),
                     glow=(110,231,255), dia_text=(245,245,245), dia_fill=(34,30,66)),
    "light":    dict(bg=(245,243,236), grad=None,               kicker=(150,120,90),
                     cap=(24,24,24), oral=(70,70,70), bar=(229,72,69),
                     glow=(229,72,69), dia_text=(30,30,30), dia_fill=(255,255,255)),
}

NICK = "歌贼王"
AVATAR_FILE = os.path.join(_ENGINE_DIR, "brand", "avatar.jpg")  # 默认；main 按内容项目/--avatar 改
_AVATAR = None
def avatar_img():
    """圆形头像（无白圈，纯圆形剪裁），算一次缓存。无则 False。"""
    global _AVATAR
    if _AVATAR is not None: return _AVATAR
    if not AVATAR_FILE or not os.path.exists(AVATAR_FILE):
        _AVATAR = False; return False
    sz = 88
    im = Image.open(AVATAR_FILE).convert("RGBA").resize((sz, sz), Image.LANCZOS)
    mask = Image.new("L", (sz, sz), 0); ImageDraw.Draw(mask).ellipse([0, 0, sz-1, sz-1], fill=255)
    out = Image.new("RGBA", (sz, sz), (0, 0, 0, 0)); out.paste(im, (0, 0), mask)
    _AVATAR = out; return out                                  # 无白圈（用户 2026-06-14）

def draw_chrome(img, theme, kicker_text):
    """画 kicker + 右上角头像昵称 + 进度条底槽（两种背景模式共用）"""
    d = ImageDraw.Draw(img, "RGBA")
    # 顶部描述行已去掉（用户 2026-06-14：极简，不要 "AI 文章·看完不费劲"）
    # 右上角：头像 + 昵称「歌贼王」
    av = avatar_img(); nf = font(30, True); nw = d.textlength(NICK, font=nf)
    if av:
        ax, ay = W - av.width - 40, 150
        img.paste(av, (ax, ay), av)
        tx, ty = ax - nw - 16, ay + (av.height - 36) // 2
        d.text((tx, ty), NICK, font=nf, fill=(255, 255, 255, 240))      # 纯白无阴影
    else:
        d.text((W-nw-40, 158), NICK, font=nf, fill=(255, 255, 255, 240))
    # 进度条底槽已去掉（改消耗式：见帧循环里的 draining 白条）

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
    draw_chrome(img, theme, kicker_text)
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
    img = Image.open(pick)
    img = ImageOps.exif_transpose(img)                  # 按 EXIF 自动摆正——不手动翻转用户照片（用户 2026-06-14 定）
    img = img.convert("RGB")
    img = _cover(img, W, H)                             # 直接裁到成片尺寸，静态；不模糊，保清晰度
    img = ImageEnhance.Color(img).enhance(1.04)         # 仅极轻提饱和；可读性全靠文字黑描边
    return img.convert("RGBA"), os.path.basename(pick)

def ken_burns(base, t, T):
    """静态背景：去掉 Ken Burns 慢移/缩放（用户 2026-06-14 觉得晃动不舒服）。base 已是 WxH。"""
    return base.copy()

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

def render_diagram(img, nodes, frac, theme, a):
    """竖向流程图：半透明白磨砂卡片 + 深灰无描边字 + 白连接箭头，随 frac 逐个出现。
    极简白风（用户 2026-06-14：纯黑底不好看、文字不要黑毛边）。a=段透明度(0..1)。"""
    d = ImageDraw.Draw(img, "RGBA")
    n = len(nodes)
    if n == 0: return
    shown = max(1, math.ceil(n*frac))
    box_w = 860; x1 = (W-box_w)//2
    gap = 46
    box_h = int(min(120, (720 - gap*(n-1))/n))
    fsize = max(26, min(40, box_h-44))
    total_h = n*box_h + (n-1)*gap
    y0 = 580 + (720-total_h)//2
    bf = font(fsize, True)
    panel_a = int(160*a)                                  # 更浅的半透明白磨砂底（用户 2026-06-14：再浅一点）
    for i in range(shown):
        by1 = y0 + i*(box_h+gap); by2 = by1+box_h
        # 真·alpha 合成的圆角白卡（不是实色填充）
        tile = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        ImageDraw.Draw(tile).rounded_rectangle([0, 0, box_w-1, box_h-1], radius=24,
                                               fill=(255, 255, 255, panel_a))
        img.alpha_composite(tile, (x1, by1))
        # 深灰字，无描边（白底上够清晰）
        lines = wrap(d, nodes[i], bf, box_w-52)
        lh = int(fsize*1.24); th = len(lines)*lh
        ty = by1 + (box_h-th)//2
        for k, ln in enumerate(lines):
            lw = d.textlength(ln, font=bf)
            d.text(((W-lw)/2, ty+k*lh), ln, font=bf, fill=(34, 38, 45, int(248*a)))
        if i < shown-1 and i < n-1:                       # 白色连接箭头（配极简白）
            ax = W//2; ay2 = by2+gap-6; aw = (255, 255, 255, int(235*a))
            d.line([ax, by2+6, ax, ay2-8], fill=aw, width=5)
            d.polygon([(ax-13, ay2-13), (ax+13, ay2-13), (ax, ay2)], fill=aw)

def pop_line(img, text, fnt, cy, rgb, e, seg_a):
    """整行一次性「弹出」：缩放(0.72→1)+淡入，e=本行入场进度(0..1)。不是逐字打字。"""
    if e <= 0: return
    ease = 1-(1-e)**2
    scale = 0.72 + 0.28*ease
    alpha = ease*seg_a
    if alpha <= 0: return
    m = ImageDraw.Draw(img)
    tw = int(m.textlength(text, font=fnt)); asc, desc = fnt.getmetrics(); th = asc+desc
    pad = 10
    # 纯白文字，无描边、无阴影、无边框（用户 2026-06-14：极简到极致）
    sp = Image.new("RGBA", (tw+2*pad, th+2*pad), (0,0,0,0))
    ImageDraw.Draw(sp).text((pad, pad), text, font=fnt, fill=rgb+(255,))
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
    # 头像/背景默认从「内容项目」assets/ 读（私人素材放私有内容仓，不进公开工具仓）：
    #   优先级 = 命令行参数 > 当前内容项目 assets/ > 引擎自带 tools/。
    global AVATAR_FILE
    _cwd_av = os.path.join(os.getcwd(), "assets", "brand", "avatar.jpg")
    if "--avatar" in sys.argv: AVATAR_FILE = sys.argv[sys.argv.index("--avatar")+1]
    elif os.path.exists(_cwd_av): AVATAR_FILE = _cwd_av
    # 照片背景（周轮值）：--bg-dir > 内容项目 assets/backgrounds/ > 引擎自带 tools/backgrounds/
    _cwd_bg = os.path.join(os.getcwd(), "assets", "backgrounds")
    if "--bg-dir" in sys.argv:   bg_dir = sys.argv[sys.argv.index("--bg-dir")+1]
    elif os.path.isdir(_cwd_bg): bg_dir = _cwd_bg
    else: bg_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backgrounds")
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
            cap = s["cap"]                       # 没屏幕字就不画大字幕（不再拿口播兜底成字墙）
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
                draw_chrome(img, theme, kicker)
                d = ImageDraw.Draw(img, "RGBA")
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
                    d.text(((W-hw)/2, 492), htxt, font=hf, fill=(cr,cg,cb,calpha))  # 纯白无阴影无描边
                render_diagram(img, segs[i]["dnodes"], frac, theme, a)
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

            # 底部口播字幕：最多 4 行（滑动窗口，只显示最近几行）+ 底部锚定，绝不压上方内容区
            olh = int(50*1.34); MAX_ORAL = 4
            total_o = sum(len(l) for l in olines)
            oshown = take_chars(olines, math.ceil(total_o*frac))[-MAX_ORAL:]
            oy = 1648 - len(oshown)*olh             # 满 4 行时 top≈1380，内容区到 ~1320，留 60px 不重叠
            orr,org,orb = theme["oral"]; oalpha = int(235*a)
            for k, ln in enumerate(oshown):
                lw = d.textlength(ln, font=of)
                d.text(((W-lw)/2, oy+k*olh), ln, font=of, fill=(orr,org,orb,oalpha))  # 纯白无阴影无描边

            # 进度条：消耗式——初始整条纯白，播过的部分变透明，白色逐渐缩短到全消失（用户 2026-06-14）
            fillw = 90 + (W-180)*min(t/T,1.0)
            if fillw < W-90:
                d.rounded_rectangle([fillw,1720,W-90,1730], radius=5, fill=(255,255,255,235))
            nf = font(34, True)
            d.text((90,1756), f"{i+1} / {n}", font=nf, fill=(255,255,255,235))  # 纯白无阴影

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
