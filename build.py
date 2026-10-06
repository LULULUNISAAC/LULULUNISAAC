#!/usr/bin/env python3
"""Black-and-grey GitHub profile panels (rounded cards, subtle motion).

    python build.py             # live data (GH_TOKEN / GITHUB_TOKEN)
    python build.py --offline   # sample data, no network
    python build.py --snake     # post-process dist/snake.svg into a dark rounded card
"""
import os, re, sys, json, html, random, pathlib, datetime as dt
from zoneinfo import ZoneInfo
import yaml

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "dist"
OFFLINE = "--offline" in sys.argv
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

CFG = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
USER = CFG["github_user"]
TZ = ZoneInfo(CFG.get("timezone", "UTC"))

PANEL, LINE, INK = "#0a0a0a", "#262626", "#000000"
DIM, MUT, SOFT, FG = "#555555", "#777777", CFG.get("accent", "#9a9a9a"), "#ffffff"
RAMP = ["#141414", "#333333", "#5e5e5e", "#9a9a9a", "#e8e8e8"]
FONT = ('ui-monospace,"SF Mono",Menlo,Consolas,"DejaVu Sans Mono",'
        '"PingFang TC","Microsoft JhengHei","Noto Sans CJK TC",monospace')
M = 6  # outer margin: gives every card its own rounded edge and a gap to its neighbour

CSS = """
text{font-family:%FONT%;fill:%FG%}
.m{fill:%MUT%}.s{fill:%SOFT%}.d{fill:%DIM%}.k{fill:%INK%}.b{font-weight:700}
.blink{animation:blink 1.1s steps(1) infinite}
.sweep{animation:sweep 9s linear infinite}
.fade{opacity:0;animation:fade .6s ease forwards}
.grow{transform-box:fill-box;transform-origin:left center;transform:scaleX(0);animation:grow .7s cubic-bezier(.2,.8,.2,1) forwards}
.pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2.2s ease-out infinite}
@keyframes blink{50%{opacity:0}}
@keyframes sweep{from{transform:translateX(0)}to{transform:translateX(1120px)}}
@keyframes fade{to{opacity:1}}
@keyframes grow{to{transform:scaleX(1)}}
@keyframes pulse{from{transform:scale(1);opacity:.75}to{transform:scale(3.4);opacity:0}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;opacity:1!important;transform:none!important}}
""".replace("%FONT%", FONT).replace("%FG%", FG).replace("%MUT%", MUT)\
   .replace("%SOFT%", SOFT).replace("%DIM%", DIM).replace("%INK%", INK)

# ───────────────────────── helpers ─────────────────────────
def esc(s): return html.escape(str(s), quote=True)
def cw(ch): return 1.0 if ord(ch) >= 0x2E80 else 0.6
def tw(s, size): return sum(cw(c) for c in s) * size

def wrap(s, size, maxw, maxlines=2):
    toks = re.findall(r"[\u2E80-\uffff]|[^\s\u2E80-\uffff]+\s*|\s+", s)
    lines, cur = [], ""
    for t in toks:
        if not cur or tw(cur + t, size) <= maxw: cur += t
        else: lines.append(cur.rstrip()); cur = t.lstrip()
    if cur: lines.append(cur.rstrip())
    if len(lines) > maxlines:
        lines = lines[:maxlines]; lines[-1] = lines[-1][:-1].rstrip() + "…"
    return lines

def T(x, y, s, size=16, cls="", anchor="start", extra=""):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    c = f' class="{cls}"' if cls else ""
    return f'<text x="{x}" y="{y}" font-size="{size}"{a}{c} {extra}>{esc(s)}</text>'

def R(x, y, w, h, fill="none", stroke="", extra="", rx=0):
    st = f' stroke="{stroke}"' if stroke else ""
    r = f' rx="{rx}"' if rx else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"{st}{r} {extra}/>'

def svg(w, h, body, css="", defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<style>{CSS}{css}</style><defs>{defs}</defs>{body}</svg>')

def card_bg(w, h, rx=20, fill=PANEL):
    return R(M + .5, M + .5, w - 2 * M - 1, h - 2 * M - 1, fill, LINE, rx=rx)

def short_date(iso):
    try:
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ).strftime("%Y-%m-%d")
    except Exception:
        return "—"

# ───────────────────────── data ─────────────────────────
def http(url, payload=None):
    import urllib.request as ur
    req = ur.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-builder"})
    if TOKEN: req.add_header("Authorization", f"Bearer {TOKEN}")
    if payload is not None:
        req.data = json.dumps(payload).encode(); req.add_header("Content-Type", "application/json")
    with ur.urlopen(req, timeout=30) as r:
        return json.load(r)

def sample_data(featured):
    rnd = random.Random(7)
    today = dt.date.today()
    days = []
    for i in range(364, -1, -1):
        d = today - dt.timedelta(days=i)
        n = 0 if rnd.random() < .35 else int(rnd.random() ** 2 * 12)
        days.append((d.isoformat(), n))
    now = dt.datetime.now(TZ)
    pushes = []
    for _ in range(160):
        hr = int(min(23, max(0, rnd.gauss(15, 5))))
        d = now - dt.timedelta(days=rnd.randint(0, 89))
        pushes.append(d.replace(hour=hr, minute=rnd.randint(0, 59)))
    repos = {r: dict(stars=rnd.randint(0, 9), forks=rnd.randint(0, 3), lang="Python",
                     pushed=(now - dt.timedelta(days=rnd.randint(1, 60))).isoformat()) for r in featured}
    recent = [dict(name=r, lang="Python", stars=repos[r]["stars"], pushed=repos[r]["pushed"]) for r in featured]
    return dict(ok=dict(cal=True, push=True, repos=True), followers=4, public_repos=7,
                days=days, pushes=pushes, repos=repos, recent=recent)

def live_data(featured):
    out = dict(ok=dict(cal=False, push=False, repos=False), followers=0, public_repos=0,
               days=[], pushes=[], repos={}, recent=[])
    try:
        u = http(f"https://api.github.com/users/{USER}")
        out["followers"], out["public_repos"] = u.get("followers", 0), u.get("public_repos", 0)
    except Exception as e: print("warn user:", e)
    try:
        q = ("query($l:String!){user(login:$l){contributionsCollection{contributionCalendar{"
             "weeks{contributionDays{date contributionCount}}}}}}")
        g = http("https://api.github.com/graphql", {"query": q, "variables": {"l": USER}})
        weeks = g["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        out["days"] = [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]]
        out["ok"]["cal"] = bool(out["days"])
    except Exception as e: print("warn calendar:", e)
    try:
        for page in (1, 2, 3):
            ev = http(f"https://api.github.com/users/{USER}/events/public?per_page=100&page={page}")
            if not ev: break
            for e in ev:
                if e.get("type") == "PushEvent":
                    out["pushes"].append(dt.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")).astimezone(TZ))
        out["ok"]["push"] = True
    except Exception as e: print("warn events:", e)
    try:
        lst = http(f"https://api.github.com/users/{USER}/repos?sort=pushed&per_page=12&type=owner")
        out["recent"] = [dict(name=r["name"], lang=r.get("language") or "—", stars=r["stargazers_count"],
                              pushed=r["pushed_at"]) for r in lst if not r.get("fork")]
        out["ok"]["repos"] = True
    except Exception as e: print("warn repos:", e)
    for name in featured:
        try:
            r = http(f"https://api.github.com/repos/{USER}/{name}")
            out["repos"][name] = dict(stars=r["stargazers_count"], forks=r["forks_count"],
                                      lang=r.get("language") or "—", pushed=r["pushed_at"])
        except Exception as e: print(f"warn repo {name}:", e)
    return out

# ───────────────────────── panels ─────────────────────────
def hero(L, D):
    w, h, ui = 1200, 430, L["ui"]
    defs = ('<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
            '<circle cx="2" cy="2" r="1" fill="#1b1b1b"/></pattern>'
            '<radialGradient id="glow" cx="85%" cy="0%" r="70%">'
            '<stop offset="0" stop-color="#ffffff" stop-opacity=".09"/>'
            '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient>')
    b = [card_bg(w, h, 26),
         R(M + 1, M + 1, w - 2 * M - 2, h - 2 * M - 2, "url(#dots)", rx=25),
         R(M + 1, M + 1, w - 2 * M - 2, h - 2 * M - 2, "url(#glow)", rx=25),
         f'<line x1="{M}" y1="52" x2="{w-M}" y2="52" stroke="{LINE}"/>',
         f'<circle cx="44" cy="31" r="4" fill="{SOFT}"/><circle cx="44" cy="31" r="4" fill="{SOFT}" class="pulse"/>',
         T(60, 36, f"{USER.lower()}@github", 14, "m"),
         T(w - 40, 36, f'{ui["rendered"]} {dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")}', 14, "m", "end")]
    name = L["name"]
    b.append(T(40, 142, name, 64, "b"))
    b.append(R(40 + tw(name, 64) + 18, 96, 26, 48, SOFT, extra='class="blink"', rx=4))
    b.append(T(40, 184, L["role"], 20, "s", extra='letter-spacing="2"'))
    y = 240
    for lab, txt in L["rows"]:
        b.append(T(40, y, lab, 15, "s", extra='letter-spacing="2"'))
        b.append(T(170, y, wrap(txt, 19, 980, 1)[0], 19))
        y += 34
    days = D["days"]
    if days:
        weekly = [sum(c for _, c in days[i:i + 7]) for i in range(0, len(days), 7)]
        m = max(weekly) or 1
        x0, x1, yb, ht = 40, 1160, 386, 58
        pts = [(x0 + (x1 - x0) * i / max(1, len(weekly) - 1), yb - ht * v / m) for i, v in enumerate(weekly)]
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        b.append(f'<polygon points="{x0},{yb} {line} {x1},{yb}" fill="#171717"/>')
        b.append(f'<polyline points="{line}" fill="none" stroke="{FG}" stroke-width="1.6" stroke-linejoin="round"/>')
        b.append(f'<line x1="{x0}" y1="{yb}" x2="{x1}" y2="{yb}" stroke="{LINE}"/>')
        b.append(R(x0, yb - ht - 8, 2, ht + 8, SOFT, extra='class="sweep"', rx=1))
        ex, ey = pts[-1]
        b.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="{FG}"/>'
                 f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="none" stroke="{FG}" class="pulse"/>')
        total = sum(c for _, c in days)
        streak = 0
        for _, c in reversed(days[:-1] if days[-1][1] == 0 else days):
            if c > 0: streak += 1
            else: break
        b.append(T(40, 412, f'{ui["contrib"]} {total}', 13, "m"))
        b.append(T(1160, 412, f'{ui["streak"]} {streak}{ui["days"]}', 13, "m", "end"))
    return svg(w, h, "".join(b), defs=defs)

def ticker(L):
    ui, w, h = L["ui"], 1200, 56
    items = [t for t, _ in CFG["tools"]] + [r["repo"] for r in L["repos"]] + [L["rows"][-1][1]]
    text = "   ·   ".join(items) + "   ·   "
    tl = round(tw(text, 15))
    css = f"@keyframes tick{{from{{transform:translateX(0)}}to{{transform:translateX(-{tl}px)}}}}.tick{{animation:tick 38s linear infinite}}"
    clip = f'<clipPath id="c"><rect x="{M+14}" y="{M}" width="{w-2*M-28}" height="{h-2*M}"/></clipPath>'
    g = (f'<g clip-path="url(#c)"><g class="tick">'
         f'<text x="{M+20}" y="34" font-size="15" class="s" textLength="{tl}" lengthAdjust="spacing">{esc(text)}</text>'
         f'<text x="{M+20+tl}" y="34" font-size="15" class="s" textLength="{tl}" lengthAdjust="spacing">{esc(text)}</text>'
         f'</g></g>')
    return svg(w, h, card_bg(w, h, 22) + g, css=css, defs=clip)

def key(L, i, D):
    w, h = 400, 120
    k = L["keys"][i]
    sub = k["sub"].replace("{followers}", str(D["followers"])).replace("{repos}", str(D["public_repos"]))
    return svg(w, h, card_bg(w, h, 22) + T(30, 40, f"0{i+1}", 13, "m")
               + f'<circle cx="{w-42}" cy="40" r="15" fill="none" stroke="{LINE}"/>'
               + T(w - 42, 46, "↗", 16, "s", "middle")
               + T(30, 80, k["label"], 26, "b", extra='letter-spacing="2"')
               + T(30, 102, sub, 13, "m"))

def strip(num, title):
    w, h = 1200, 64
    x = 98 + tw(title, 18) + 6 * len(title) + 24
    return svg(w, h, card_bg(w, h, 26, "#070707")
               + R(24, 17, 48, 30, "none", SOFT, rx=15) + T(48, 37, num, 14, "s", "middle")
               + T(98, 40, title, 18, "b", extra='letter-spacing="6"')
               + f'<line x1="{x}" y1="35" x2="{w-36}" y2="35" stroke="{LINE}"/>')

def work_card(L, r, st):
    w, h, ui = 600, 250, L["ui"]
    b = [card_bg(w, h, 24), R(30, 28, tw(r["tag"], 13) + 26, 28, "none", SOFT, rx=14),
         T(43, 47, r["tag"], 13, "s", extra='letter-spacing="2"'),
         f'<circle cx="{w-46}" cy="42" r="15" fill="none" stroke="{LINE}"/>', T(w - 46, 48, "↗", 16, "s", "middle"),
         T(30, 110, r["repo"], 30, "b")]
    y = 148
    lines = wrap(r["pitch"], 17, 530, 2)
    for ln in lines:
        b.append(T(30, y, ln, 17)); y += 24
    b.append(T(30, y + 2, wrap(r["sub"], 14, 530, 1)[0], 14, "m"))
    b.append(f'<line x1="30" y1="{h-52}" x2="{w-30}" y2="{h-52}" stroke="{LINE}"/>')
    if st:
        b.append(T(30, h - 28, f'{ui["stars"]} {st["stars"]} · {ui["forks"]} {st["forks"]} · {st["lang"]} · {ui["updated"]} {short_date(st["pushed"])}', 13, "s"))
    else:
        b.append(T(30, h - 28, ui["private"], 13, "d"))
    return svg(w, h, "".join(b))

def lab(L):
    ui, tools = L["ui"], CFG["tools"]
    rows = max(len(tools), len(L["repos"]))
    w, h = 1200, 110 + rows * 42
    b = [card_bg(w, h, 26), T(44, 52, ui["tools"], 14, "s", extra='letter-spacing="3"'),
         T(704, 52, ui["projects"], 14, "s", extra='letter-spacing="3"'),
         f'<line x1="640" y1="34" x2="640" y2="{h-34}" stroke="{LINE}"/>']
    for i, (name, lvl) in enumerate(tools):
        y = 104 + i * 42
        b.append(T(44, y, name, 18))
        for j in range(5):
            on = j < lvl
            b.append(R(270 + j * 60, y - 15, 52, 14, FG if on else "#1a1a1a", rx=7,
                       extra=f'class="grow" style="animation-delay:{(i*5+j)*0.06:.2f}s"' if on else ""))
    for i, r in enumerate(L["repos"]):
        y = 104 + i * 42
        b.append(T(704, y, r["repo"], 18))
        tw_ = tw(r["tag"], 12) + 24
        b.append(R(1160 - tw_, y - 18, tw_, 24, "none", LINE, rx=12))
        b.append(T(1160 - tw_ / 2, y - 1, r["tag"], 12, "m", "middle", 'letter-spacing="2"'))
    return svg(w, h, "".join(b))

def activity(L, D):
    ui, w = L["ui"], 1200
    grid = [[0] * 24 for _ in range(7)]
    for t in D["pushes"]: grid[t.weekday()][t.hour] += 1
    mx = max(max(r) for r in grid) or 1
    cw_, ch_, gap, x0, y0 = 38, 26, 4, 130, 90
    h = y0 + 7 * (ch_ + gap) + 84
    b = [card_bg(w, h, 26), T(44, 54, ui["activity"], 14, "s", extra='letter-spacing="2"')]
    n = 0
    for d in range(7):
        y = y0 + d * (ch_ + gap)
        b.append(T(44, y + 18, ui["weekdays"][d], 13, "m"))
        for hr in range(24):
            v = grid[d][hr]
            lvl = 0 if v == 0 else min(4, 1 + int(3 * v / mx))
            ex = f'class="fade" style="animation-delay:{(n%40)*0.03:.2f}s"' if v else ""
            n += 1 if v else 0
            b.append(R(x0 + hr * (cw_ + gap), y, cw_, ch_, RAMP[lvl], rx=7, extra=ex))
    yl = y0 + 7 * (ch_ + gap) + 16
    for hr in range(0, 24, 3):
        b.append(T(x0 + hr * (cw_ + gap), yl, f"{hr:02d}", 12, "m"))
    tot = [sum(grid[d][hr] for d in range(7)) for hr in range(24)]
    if any(tot):
        pk = tot.index(max(tot))
        b.append(T(44, h - 30, f'{ui["peak"]} {pk:02d}:00 – {pk+1:02d}:00', 13, "m"))
    lx = 1160 - (5 * 20 + 100 + 80)
    b.append(T(lx, h - 30, ui["less"], 12, "m"))
    for i, c in enumerate(RAMP):
        b.append(R(lx + 52 + i * 20, h - 42, 15, 15, c, rx=5))
    b.append(T(lx + 52 + 5 * 20 + 6, h - 30, ui["more"], 12, "m"))
    return svg(w, h, "".join(b))

def recent(L, D):
    ui, w = L["ui"], 1200
    items = D["recent"][:6]
    h = 100 + len(items) * 42 + 20
    b = [card_bg(w, h, 26), T(44, 54, ui["recent"], 14, "s", extra='letter-spacing="3"')]
    for i, r in enumerate(items):
        y = 104 + i * 42
        b.append(f'<line x1="44" y1="{y+16}" x2="{w-44}" y2="{y+16}" stroke="{LINE}"/>')
        b.append(T(44, y, r["name"], 20))
        b.append(T(560, y, r["lang"], 14, "m"))
        b.append(T(800, y, f'{ui["stars"]} {r["stars"]}', 14, "m"))
        b.append(T(1156, y, short_date(r["pushed"]), 14, "m", "end"))
    return svg(w, h, "".join(b))

def switch_btn(label, active):
    w, h = 120, 44
    fill, txt = (FG, "k") if active else (PANEL, "m")
    return svg(w, h, R(M, M, w - 2 * M, h - 2 * M, fill, LINE, rx=16) + T(w / 2, 28, label, 14, txt + " b", "middle", 'letter-spacing="2"'))

def fix_snake():
    p = DIST / "snake.svg"
    if not p.exists(): print("no snake.svg to patch"); return
    s = p.read_text(encoding="utf-8")
    if "<!--patched-->" in s: return
    m = re.search(r"<svg\b[^>]*>", s)
    vb = re.search(r'viewBox="([^"]+)"', m.group(0)) if m else None
    if not m or not vb: print("snake.svg: no viewBox, left as is"); return
    x, y, w, h = [float(v) for v in vb.group(1).split()]
    pad = 26
    x, y, w, h = x - pad, y - pad, w + 2 * pad, h + 2 * pad
    tag = re.sub(r'viewBox="[^"]+"', f'viewBox="{x:g} {y:g} {w:g} {h:g}"', m.group(0))
    tag = re.sub(r'\s(?:width|height)="[^"]*"', "", tag)
    bg = f'<!--patched--><rect x="{x+M:g}" y="{y+M:g}" width="{w-2*M:g}" height="{h-2*M:g}" rx="26" fill="{PANEL}" stroke="{LINE}"/>'
    p.write_text(s.replace(m.group(0), tag + bg, 1), encoding="utf-8")
    print("snake.svg patched")

# ───────────────────────── main ─────────────────────────
def put(path, content, skip_if_exists=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if skip_if_exists and path.exists():
        print("kept previous:", path.name); return
    path.write_text(content, encoding="utf-8")

def main():
    if "--snake" in sys.argv: return fix_snake()
    featured = []
    for L in CFG["languages"].values():
        for r in L["repos"]:
            if r["repo"] not in featured: featured.append(r["repo"])
    D = sample_data(featured) if OFFLINE else live_data(featured)
    ok = D["ok"]
    for code, label in (("en", "EN"), ("zh", "繁中")):
        put(DIST / f"sw-{code}-on.svg", switch_btn(label, True))
        put(DIST / f"sw-{code}-off.svg", switch_btn(label, False))
    for L in CFG["languages"].values():
        out, ui = DIST / L["dir"], L["ui"]
        put(out / "strip-info.svg", strip("01", ui["info"]))
        put(out / "hero.svg", hero(L, D), skip_if_exists=not ok["cal"])
        put(out / "ticker.svg", ticker(L))
        for i in range(len(L["keys"])): put(out / f"key-{i}.svg", key(L, i, D))
        put(out / "strip-work.svg", strip("02", ui["work"]))
        put(out / "strip-lab.svg", strip("03", ui["lab"]))
        put(out / "strip-flow.svg", strip("04", ui["flow"]))
        for i, r in enumerate(L["repos"]):
            put(out / f"work-{i}.svg", work_card(L, r, D["repos"].get(r["repo"])))
        put(out / "lab.svg", lab(L))
        put(out / "activity.svg", activity(L, D), skip_if_exists=not ok["push"])
        put(out / "recent.svg", recent(L, D), skip_if_exists=not ok["repos"])
    print("done ->", DIST)

if __name__ == "__main__":
    main()
