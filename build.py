#!/usr/bin/env python3
"""Black-and-grey GitHub profile panels, written from scratch.

Usage:
    python build.py             # live data (uses GH_TOKEN / GITHUB_TOKEN if set)
    python build.py --offline   # sample data, no network (for previewing)

Writes SVG panels to dist/<lang>/ for every language in config.yml.
"""
import os, re, sys, json, html, random, pathlib, datetime as dt
import urllib.request, urllib.error
from zoneinfo import ZoneInfo
import yaml

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "dist"
OFFLINE = "--offline" in sys.argv
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

CFG = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
USER = CFG["github_user"]
TZ = ZoneInfo(CFG.get("timezone", "UTC"))

BG, PANEL, LINE = "#000000", "#0a0a0a", "#222222"
DIM, MUT, SOFT, FG = "#555555", "#777777", CFG.get("accent", "#9a9a9a"), "#ffffff"
RAMP = ["#141414", "#333333", "#5e5e5e", "#9a9a9a", "#e8e8e8"]
FONT = ('ui-monospace,"SF Mono",Menlo,Consolas,"DejaVu Sans Mono",'
        '"PingFang TC","Microsoft JhengHei","Noto Sans CJK TC",monospace')

CSS = """
text{font-family:%FONT%;fill:%FG%}
.m{fill:%MUT%}.s{fill:%SOFT%}.d{fill:%DIM%}.b{font-weight:700}
.blink{animation:blink 1.1s steps(1) infinite}
.sweep{animation:sweep 9s linear infinite}
.fade{opacity:0;animation:fade .6s ease forwards}
@keyframes blink{50%{opacity:0}}
@keyframes sweep{from{transform:translateX(0)}to{transform:translateX(1120px)}}
@keyframes fade{to{opacity:1}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;opacity:1!important}}
""".replace("%FONT%", FONT).replace("%FG%", FG).replace("%MUT%", MUT)\
   .replace("%SOFT%", SOFT).replace("%DIM%", DIM)

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

def R(x, y, w, h, fill="none", stroke="", extra=""):
    st = f' stroke="{stroke}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"{st} {extra}/>'

def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<style>{CSS}</style>{R(0,0,w,h,BG)}{body}</svg>')

def frame(w, h):  # panel with 1px border, tiles cleanly next to its neighbours
    return R(0.5, 0.5, w - 1, h - 1, PANEL, LINE)

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
    pushes = []
    now = dt.datetime.now(TZ)
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
                    t = dt.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")).astimezone(TZ)
                    out["pushes"].append(t)
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
    w, h, ui = 1200, 400, L["ui"]
    b = [frame(w, h), f'<line x1="0" y1="44" x2="{w}" y2="44" stroke="{LINE}"/>',
         T(40, 28, f"{USER.lower()}@github", 14, "m"),
         T(w - 40, 28, f'{ui["rendered"]} {dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M")} {TZ.key.split("/")[-1].upper()}',
           14, "m", "end")]
    name = L["name"]
    b.append(T(40, 132, name, 64, "b"))
    b.append(R(40 + tw(name, 64) + 18, 88, 26, 48, SOFT, extra='class="blink"'))
    b.append(T(40, 174, L["role"], 20, "s", extra='letter-spacing="2"'))
    y = 226
    for lab, txt in L["rows"]:
        b.append(T(40, y, lab, 15, "s", extra='letter-spacing="2"'))
        b.append(T(170, y, wrap(txt, 19, 980, 1)[0], 19))
        y += 34
    days = D["days"]
    if days:
        weekly = [sum(c for _, c in days[i:i + 7]) for i in range(0, len(days), 7)]
        m = max(weekly) or 1
        x0, x1, yb, ht = 40, 1160, 374, 62
        pts = [(x0 + (x1 - x0) * i / max(1, len(weekly) - 1), yb - ht * v / m) for i, v in enumerate(weekly)]
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        b.append(f'<polygon points="{x0},{yb} {line} {x1},{yb}" fill="#161616"/>')
        b.append(f'<polyline points="{line}" fill="none" stroke="{FG}" stroke-width="1.5"/>')
        b.append(f'<line x1="{x0}" y1="{yb}" x2="{x1}" y2="{yb}" stroke="{LINE}"/>')
        b.append(R(x0, yb - ht - 6, 2, ht + 6, SOFT, extra='class="sweep"'))
        total = sum(c for _, c in days)
        streak = 0
        for _, c in reversed(days[:-1] if days[-1][1] == 0 else days):
            if c > 0: streak += 1
            else: break
        b.append(T(40, 392, f'{ui["contrib"]} {total}', 13, "m"))
        b.append(T(1160, 392, f'{ui["streak"]} {streak}{ui["days"]}', 13, "m", "end"))
    return svg(w, h, "".join(b))

def key(L, i, D):
    w, h = 400, 110
    k = L["keys"][i]
    sub = k["sub"].replace("{followers}", str(D["followers"])).replace("{repos}", str(D["public_repos"]))
    return svg(w, h, frame(w, h) + T(24, 34, f"0{i+1}", 13, "m")
               + T(w - 24, 38, "↗", 20, "s", "end")
               + T(24, 72, k["label"], 26, "b", extra='letter-spacing="2"')
               + T(24, 96, sub, 13, "m"))

def strip(num, title):
    w, h = 1200, 64
    x = 84 + tw(title, 18) + 6 * len(title) + 24
    return svg(w, h, T(40, 40, num, 14, "s") + T(84, 40, title, 18, "b", extra='letter-spacing="6"')
               + f'<line x1="{x}" y1="35" x2="1160" y2="35" stroke="{LINE}"/>')

def card(L, r, st):
    w, h, ui = 600, 240, L["ui"]
    b = [frame(w, h), R(32, 28, tw(r["tag"], 13) + 24, 26, "none", SOFT),
         T(44, 46, r["tag"], 13, "s", extra='letter-spacing="2"'),
         T(32, 106, r["repo"], 30, "b")]
    y = 144
    for ln in wrap(r["pitch"], 17, 536, 2):
        b.append(T(32, y, ln, 17)); y += 24
    b.append(T(32, 196, wrap(r["sub"], 14, 536, 1)[0], 14, "m"))
    if st:
        b.append(T(32, 224, f'{ui["stars"]} {st["stars"]} · {ui["forks"]} {st["forks"]} · {st["lang"]} · {ui["updated"]} {short_date(st["pushed"])}', 13, "s"))
    else:
        b.append(T(32, 224, ui["private"], 13, "d"))
    return svg(w, h, "".join(b))

def lab(L):
    ui, tools = L["ui"], CFG["tools"]
    rows = max(len(tools), len(L["repos"]))
    w, h = 1200, 96 + rows * 42
    b = [frame(w, h), T(40, 44, ui["tools"], 14, "s", extra='letter-spacing="3"'),
         T(700, 44, ui["projects"], 14, "s", extra='letter-spacing="3"'),
         f'<line x1="640" y1="24" x2="640" y2="{h-24}" stroke="{LINE}"/>']
    for i, (name, lvl) in enumerate(tools):
        y = 96 + i * 42
        b.append(T(40, y, name, 18))
        for j in range(5):
            on = j < lvl
            b.append(R(260 + j * 56, y - 15, 48, 14, FG if on else "#1a1a1a",
                       extra=f'class="fade" style="animation-delay:{(i*5+j)*0.05:.2f}s"' if on else ""))
    for i, r in enumerate(L["repos"]):
        y = 96 + i * 42
        b.append(T(700, y, r["repo"], 18))
        b.append(T(1160, y, r["tag"], 13, "m", "end", 'letter-spacing="2"'))
    return svg(w, h, "".join(b))

def activity(L, D):
    ui, w = L["ui"], 1200
    grid = [[0] * 24 for _ in range(7)]
    for t in D["pushes"]: grid[t.weekday()][t.hour] += 1
    mx = max(max(r) for r in grid) or 1
    cw_, ch_, gap, x0, y0 = 38, 26, 4, 130, 76
    h = y0 + 7 * (ch_ + gap) + 74
    b = [frame(w, h), T(40, 44, ui["activity"], 14, "s", extra='letter-spacing="2"')]
    for d in range(7):
        y = y0 + d * (ch_ + gap)
        b.append(T(40, y + 18, ui["weekdays"][d], 13, "m"))
        for hr in range(24):
            v = grid[d][hr]
            lvl = 0 if v == 0 else min(4, 1 + int(3 * v / mx))
            b.append(R(x0 + hr * (cw_ + gap), y, cw_, ch_, RAMP[lvl]))
    yl = y0 + 7 * (ch_ + gap) + 16
    for hr in range(0, 24, 3):
        b.append(T(x0 + hr * (cw_ + gap), yl, f"{hr:02d}", 12, "m"))
    tot = [sum(grid[d][hr] for d in range(7)) for hr in range(24)]
    if any(tot):
        pk = tot.index(max(tot))
        b.append(T(40, h - 20, f'{ui["peak"]} {pk:02d}:00 – {pk+1:02d}:00', 13, "m"))
    lx = 1160 - (5 * 18 + 90 + 90)
    b.append(T(lx, h - 20, ui["less"], 12, "m"))
    for i, c in enumerate(RAMP):
        b.append(R(lx + 50 + i * 18, h - 32, 14, 14, c))
    b.append(T(lx + 50 + 5 * 18 + 6, h - 20, ui["more"], 12, "m"))
    return svg(w, h, "".join(b))

def recent(L, D):
    ui, w = L["ui"], 1200
    items = D["recent"][:6]
    h = 76 + len(items) * 40 + 20
    b = [frame(w, h), T(40, 44, ui["recent"], 14, "s", extra='letter-spacing="3"')]
    for i, r in enumerate(items):
        y = 90 + i * 40
        b.append(f'<line x1="40" y1="{y+14}" x2="1160" y2="{y+14}" stroke="{LINE}"/>')
        b.append(T(40, y, r["name"], 20))
        b.append(T(560, y, r["lang"], 14, "m"))
        b.append(T(800, y, f'{ui["stars"]} {r["stars"]}', 14, "m"))
        b.append(T(1160, y, short_date(r["pushed"]), 14, "m", "end"))
    return svg(w, h, "".join(b))

# ───────────────────────── main ─────────────────────────
def put(path, content, skip_if_exists=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if skip_if_exists and path.exists():
        print("kept previous:", path.name); return
    path.write_text(content, encoding="utf-8")

def main():
    featured = []
    for L in CFG["languages"].values():
        for r in L["repos"]:
            if r["repo"] not in featured: featured.append(r["repo"])
    D = sample_data(featured) if OFFLINE else live_data(featured)
    ok = D["ok"]
    for L in CFG["languages"].values():
        out, ui = DIST / L["dir"], L["ui"]
        put(out / "hero.svg", hero(L, D), skip_if_exists=not ok["cal"])
        for i in range(len(L["keys"])): put(out / f"key-{i}.svg", key(L, i, D))
        put(out / "strip-work.svg", strip("02", ui["work"]))
        put(out / "strip-lab.svg", strip("03", ui["lab"]))
        put(out / "strip-flow.svg", strip("04", ui["flow"]))
        for i, r in enumerate(L["repos"]):
            put(out / f"work-{i}.svg", card(L, r, D["repos"].get(r["repo"])))
        put(out / "lab.svg", lab(L))
        put(out / "activity.svg", activity(L, D), skip_if_exists=not ok["push"])
        put(out / "recent.svg", recent(L, D), skip_if_exists=not ok["repos"])
    print("done ->", DIST)

if __name__ == "__main__":
    main()
