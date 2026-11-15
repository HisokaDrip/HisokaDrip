#!/usr/bin/env python3
"""Regenerate project cards, section headings, crime stats, and README links
from the GitHub API. Banner, typing, skills, snake, and footer are left alone.

Daily / from-scratch projects are public, non-fork Python repos created on or
after 2026-10-23, excluding the profile repo and a small denylist. The newest
MAIN_LIMIT of those go in the projects grid; the rest keep CASE-### labels in
Other Cases, followed by a fixed list of featured older repos.
"""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
README = ROOT / "README.md"
OWNER = "HisokaDrip"
DAILY_START = datetime(2026, 10, 23, tzinfo=timezone.utc)
MAIN_LIMIT = 12
NOT_DAILY = {
    "HisokaDrip",
    "leetcode-solutions",
}
FEATURED_OTHER = [
    "side-projects",
    "leetcode-solutions",
    "TourismAi",
    "The-Bridge",
    "Ai-Scavenger-Hunt",
    "ML-Mini-Project",
    "Algorithm-Lab",
]
FEATURED_META = {
    "side-projects": {
        "desc": ["small one-folder projects (go, rust)"],
        "lang": "Go / Rust",
    },
    "leetcode-solutions": {
        "desc": ["my accepted leetcode solutions in python"],
        "lang": "Python",
    },
    "TourismAi": {"desc": ["python project"], "lang": "Python"},
    "The-Bridge": {"desc": ["python project"], "lang": "Python"},
    "Ai-Scavenger-Hunt": {"desc": ["python project"], "lang": "Python"},
    "ML-Mini-Project": {"desc": ["notebook project"], "lang": "Jupyter"},
    "Algorithm-Lab": {"desc": ["python project"], "lang": "Python"},
}

# Batman theme primitives (same values as the original generator).
F = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,'DejaVu Sans Mono',monospace"
BG, PANEL, STEEL = "#07080a", "#14171c", "#2a2f38"
Y, W_ = "#ffd400", "#ffffff"
TXT, DIM, MUTED = "#f4f5f7", "#b3b9c4", "#5d6470"
CW = 0.6
BAT = (
    "M0,-11 L3,-11 L5,-18 L6.5,-9 C12,-8 16,-12 18,-17 C30,-14 40,-6 40,4 "
    "C36,-1 30,-1 27,3 C24,-2 18,-2 15,4 C11,0 4,4 0,14 C-4,4 -11,0 -15,4 "
    "C-18,-2 -24,-2 -27,3 C-30,-1 -36,-1 -40,4 C-40,-6 -30,-14 -18,-17 "
    "C-16,-12 -12,-8 -6.5,-9 L-5,-18 L-3,-11 Z"
)
LANG_BAR_COLORS = {
    "Python": Y,
    "HTML": "#f4f5f7",
    "Go": "#a7afbc",
    "Rust": "#6b7280",
    "JavaScript": "#c99a00",
    "CSS": "#8b93a1",
    "Jupyter": "#c99a00",
    "C": "#6b7280",
    "other": "#3d434e",
}

# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

def _token() -> str | None:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
    try:
        return subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    except Exception:
        return None


def _api(path: str, token: str, retries: int = 3) -> object:
    url = path if path.startswith("http") else f"https://api.github.com{path}"
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "HisokaDrip-profile-updater",
                "X-GitHub-Api-Version": "2022-11-28",
                "Authorization": f"Bearer {token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as resp:
                body = resp.read()
                link = resp.headers.get("Link", "")
                data = json.loads(body.decode("utf-8"))
                return data, link
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (502, 503, 429) and attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise last_err


def _pages(path: str, token: str) -> list:
    items = []
    url = path
    while url:
        data, link = _api(url, token)
        if not isinstance(data, list):
            raise RuntimeError(f"expected a list from {url}, got {type(data)}")
        items.extend(data)
        nxt = None
        for part in link.split(","):
            if 'rel="next"' in part:
                nxt = part.split(";")[0].strip().strip("<>")
        url = nxt
    return items


def fetch_public_repos(token: str) -> list[dict]:
    raw = _pages(f"/users/{OWNER}/repos?per_page=100&type=public&sort=created&direction=desc", token)
    repos = []
    for r in raw:
        if r.get("private") or r.get("fork"):
            continue
        created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        lang = r.get("language")
        repos.append(
            {
                "name": r["name"],
                "description": (r.get("description") or "").strip(),
                "language": lang,
                "created": created,
            }
        )
    return repos


def fetch_languages(names: list[str], token: str) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    failures = 0
    for name in names:
        try:
            data, _ = _api(f"/repos/{OWNER}/{name}/languages", token)
            if not isinstance(data, dict):
                raise RuntimeError(f"bad languages payload for {name}")
            for lang, bytes_ in data.items():
                totals[lang] += int(bytes_)
        except Exception as e:
            failures += 1
            print(f"warn: languages for {name}: {e}", file=sys.stderr)
            if failures > max(3, len(names) // 3):
                raise RuntimeError("too many language API failures; aborting") from e
    return dict(totals)


# ---------------------------------------------------------------------------
# Classification and copy
# ---------------------------------------------------------------------------

def is_daily(repo: dict) -> bool:
    if repo["name"] in NOT_DAILY:
        return False
    if repo["created"] < DAILY_START:
        return False
    if not repo["description"]:
        return False
    # Daily repos are from-scratch Python projects.
    if repo["language"] and repo["language"] != "Python":
        return False
    return True


def wrap_desc(text: str, width: int = 52, max_lines: int = 2) -> list[str]:
    text = " ".join(text.split())
    if text.endswith(".") and not text.endswith("..."):
        text = text[:-1]
    for art in ("A ", "An "):
        if text.startswith(art):
            text = text[len(art):]
            text = text[0].upper() + text[1:]
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = w if not cur else f"{cur} {w}"
        if len(trial) <= width:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = w
    if cur:
        lines.append(cur)
    if not lines:
        return [""]
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    # fold leftover words into the last line, then ellipsize
    extra = " ".join(lines[max_lines:])
    last = kept[-1] + " " + extra
    if len(last) > width:
        last = last[: width - 1].rstrip()
        last = last.rsplit(" ", 1)[0] if " " in last else last
        last = last.rstrip(" ,;:-") + "…"
    kept[-1] = last
    return kept


def xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def lang_label(name: str | None, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    if not name:
        return "Code"
    if name == "Jupyter Notebook":
        return "Jupyter"
    return name


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def bat(cx, cy, s, fill, extra=""):
    return f'<path d="{BAT}" fill="{fill}" transform="translate({cx:g} {cy:g}) scale({s:g})" {extra}/>'


def scan(id="sl", op=0.08):
    return (
        f'<pattern id="{id}" width="4" height="3" patternUnits="userSpaceOnUse">'
        f'<rect width="4" height="1" fill="#000" opacity="{op * 4:.2f}"/></pattern>'
    )


def glow(id="gl", sd=2.2, x="-20%", w="140%"):
    return (
        f'<filter id="{id}" x="{x}" y="-60%" width="{w}" height="220%">'
        f'<feGaussianBlur stdDeviation="{sd}" result="b"/>'
        f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    )


def cham(x, y, w, h, c1=0, c2=0, c3=0, c4=0):
    p = [
        (x + c1, y),
        (x + w - c2, y),
        (x + w, y + c2),
        (x + w, y + h - c3),
        (x + w - c3, y + h),
        (x + c4, y + h),
        (x, y + h - c4),
        (x, y + c1),
    ]
    out = []
    for q in p:
        if not out or out[-1] != q:
            out.append(q)
    return " ".join(f"{a:g},{b:g}" for a, b in out)


def flick(attr, a, b, dur, begin=0):
    return (
        f'<animate attributeName="{attr}" values="{a};{a};{b};{a};{a};{b};{a};{a}" '
        f'keyTimes="0;0.62;0.63;0.65;0.86;0.87;0.88;1" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>'
    )


def shine_text(x, y, s, size, fill, weight="bold", ls=0, anchor="start", extra=""):
    return (
        f'<text x="{x}" y="{y}" font-family="{F}" font-size="{size}" font-weight="{weight}" '
        f'letter-spacing="{ls}" text-anchor="{anchor}" fill="{fill}" {extra}>{s}</text>'
    )


def brackets(x, y, w, h, l, col, sw=2, op=1):
    d = (
        f"M{x},{y + l} V{y} H{x + l} M{x + w - l},{y} H{x + w} V{y + l} "
        f"M{x + w},{y + h - l} V{y + h} H{x + w - l} M{x + l},{y + h} H{x} V{y + h - l}"
    )
    return f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{sw}" opacity="{op}"/>'


def ticks(x, y, n, step, h, col, op=1):
    return "".join(
        f'<rect x="{x + i * step}" y="{y}" width="1" height="{h if i % 5 else h * 2}" fill="{col}" opacity="{op}"/>'
        for i in range(n)
    )


def svg(w, h, body, defs=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f"<defs>{defs}</defs><rect width=\"{w}\" height=\"{h}\" fill=\"{BG}\"/>{body}</svg>\n"
    )


def write(name: str, s: str) -> None:
    (ASSETS / name).write_text(s, encoding="utf-8")


def card(name: str, idx: int, tag: str, acc: str, title_col: str, desc: list[str], lang: str) -> str:
    W, H = 430, 116
    begin = round(idx * 0.7 % 6, 1)
    poly = cham(2, 2, W - 4, H - 4, 0, 16, 0, 16)
    defs = (
        scan()
        + glow("gl", 2)
        + f'<clipPath id="cp"><polygon points="{poly}"/></clipPath>'
        + '<linearGradient id="pg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#191c22"/><stop offset="1" stop-color="#0e1014"/></linearGradient>'
    )
    b = [f'<polygon points="{poly}" fill="url(#pg)"/>']
    b.append(
        f'<g clip-path="url(#cp)">{bat(W - 70, H / 2 + 10, 2.2, STEEL, "opacity=\"0.35\"")}'
        f'<rect width="{W}" height="{H}" fill="url(#sl)"/>'
        f'<rect x="-120" y="0" width="80" height="{H}" fill="{W_}" opacity="0.035" transform="skewX(-20)">'
        f'<animate attributeName="x" values="-120;-120;{W + 80}" keyTimes="0;0.7;1" dur="8s" begin="{begin}s" repeatCount="indefinite"/>'
        f"</rect></g>"
    )
    b.append(
        f'<polygon points="{poly}" fill="none" stroke="{acc}" stroke-width="1.2" stroke-opacity="0.35">'
        + flick("stroke-opacity", 0.35, 0.9, 7, begin)
        + "</polygon>"
    )
    b.append(
        f'<polygon points="2,2 130,2 124,6 2,6" fill="{acc}"/>'
        f'<rect x="134" y="2" width="16" height="2" fill="{acc}" opacity="0.5"/>'
    )
    b.append(f'<rect x="2" y="20" width="3" height="58" fill="{acc}"/>')
    b.append(bat(W - 34, 18, 0.26, acc))
    b.append(
        f'<text x="{W - 50}" y="22" font-family="{F}" font-size="10" fill="{MUTED}" '
        f'text-anchor="end" letter-spacing="1">{tag}-{idx + 1:03d}</text>'
    )
    b.append(shine_text(22, 36, xml(name), 16, title_col))
    for i, line in enumerate(desc):
        b.append(
            f'<text x="22" y="{60 + i * 17}" font-family="{F}" font-size="12" fill="{DIM}">{xml(line)}</text>'
        )
    lang_u = lang.upper()
    lw = round(len(lang_u) * 10 * CW + 30)
    lx = W - 30 - lw
    b.append(
        f'<polygon points="{cham(lx, H - 30, lw, 18, 5, 0, 5, 0)}" fill="{STEEL}" '
        f'stroke="{acc}" stroke-width="1" stroke-opacity="0.7"/>'
    )
    b.append(
        f'<circle cx="{lx + 12}" cy="{H - 21}" r="3" fill="{acc}">'
        f'<animate attributeName="opacity" values="1;0.3;1" dur="2.2s" begin="{begin}s" repeatCount="indefinite"/>'
        f"</circle>"
    )
    b.append(
        f'<text x="{lx + 21}" y="{H - 17.5}" font-family="{F}" font-size="10" fill="{TXT}" letter-spacing="1">{xml(lang_u)}</text>'
    )
    b.append(ticks(24, H - 20, 24, 4, 4, MUTED, 0.6))
    b.append(brackets(W - 14, H - 14, 8, 8, 8, acc, 1.5))
    return svg(W, H, "".join(b), defs)


def heading(fname: str, title: str, label: str) -> None:
    W, H = 880, 64
    defs = glow("gl", 2.5) + scan()
    b = [f'<polygon points="{cham(24, 13, 64, 36, 0, 10, 0, 10)}" fill="{Y}"/>', bat(56, 31, 0.62, BG)]
    b.append(
        f'<polygon points="{cham(24, 13, 64, 36, 0, 10, 0, 10)}" fill="#fff" opacity="0">'
        f'<animate attributeName="opacity" values="0;0;0.35;0;0" keyTimes="0;0.9;0.92;0.95;1" dur="6s" repeatCount="indefinite"/>'
        f"</polygon>"
    )
    t = f"// {title}"
    size, ls = 21, 2
    b.append(shine_text(104, 39, t, size, TXT, ls=ls))
    tw = 104 + len(t) * (size * CW + ls) + 22
    lw = len(label) * 11 * CW + 2 * len(label)
    lx = 856 - lw - 20
    b.append(f'<line x1="{tw:.0f}" y1="31" x2="{lx - 14:.0f}" y2="31" stroke="{STEEL}" stroke-width="2"/>')
    b.append(
        f'<line x1="{tw:.0f}" y1="31" x2="{tw + 50:.0f}" y2="31" stroke="{Y}" stroke-width="2" filter="url(#gl)">'
        f'<animate attributeName="x2" values="{tw + 50:.0f};{lx - 14:.0f};{tw + 50:.0f}" dur="6s" repeatCount="indefinite"/>'
        f"</line>"
    )
    b.append(f'<polygon points="{lx - 14:.0f},27 {lx - 6:.0f},31 {lx - 14:.0f},35" fill="{Y}"/>')
    b.append(
        f'<text x="856" y="35" font-family="{F}" font-size="11" fill="{Y}" text-anchor="end" letter-spacing="2">{xml(label)}</text>'
    )
    b.append('<line x1="24" y1="58" x2="856" y2="58" stroke="#1a1d23" stroke-width="1"/>')
    b.append(f'<rect x="24" y="57" width="64" height="3" fill="{Y}"/>')
    b.append(ticks(780, 55, 16, 5, 2, MUTED))
    write(fname, svg(W, H, "".join(b), defs))


def largest_remainder(parts: list[tuple[str, float]], n: int = 100) -> list[tuple[str, int]]:
    raw = [(name, n * share) for name, share in parts]
    floors = [(name, int(v)) for name, v in raw]
    leftover = n - sum(v for _, v in floors)
    order = sorted(range(len(raw)), key=lambda i: raw[i][1] - floors[i][1], reverse=True)
    counts = [v for _, v in floors]
    for i in order[:leftover]:
        counts[i] += 1
    return [(floors[i][0], counts[i]) for i in range(len(floors)) if counts[i] > 0]


def stats_svg(public_count: int, daily_count: int, lang_bytes: dict[str, int]) -> str:
    W, H = 880, 214
    defs = (
        scan()
        + glow("gl", 3)
        + glow("gs", 1.6)
        + '<linearGradient id="pg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#191c22"/><stop offset="1" stop-color="#0e1014"/></linearGradient>'
    )
    b = []
    boxes = [
        (str(public_count), "PUBLIC REPOS"),
        (str(daily_count), "FROM-SCRATCH BUILDS"),
        ("1 / day", "NEW PROJECT CADENCE"),
    ]
    for i, (num, lab) in enumerate(boxes):
        bx = 24 + i * 282
        bw = 268
        b.append(
            f'<polygon points="{cham(bx, 14, bw, 96, 0, 14, 0, 14)}" fill="url(#pg)" stroke="{Y}" '
            f'stroke-width="1.2" stroke-opacity="0.35">'
            + flick("stroke-opacity", 0.35, 0.9, 6, i)
            + "</polygon>"
        )
        b.append(bat(bx + bw - 50, 70, 1.3, STEEL, 'opacity="0.45"'))
        b.append(f'<polygon points="{bx},14 {bx + 80},14 {bx + 74},18 {bx},18" fill="{Y}"/>')
        b.append(
            f'<text x="{bx + 14}" y="34" font-family="{F}" font-size="9" fill="{MUTED}" letter-spacing="1">FILE.{i + 1:02d}</text>'
        )
        b.append(shine_text(bx + bw / 2, 68, xml(num), 34, Y, anchor="middle", extra='filter="url(#gs)"'))
        b.append(
            f'<text x="{bx + bw / 2}" y="93" font-family="{F}" font-size="11" fill="{DIM}" '
            f'text-anchor="middle" letter-spacing="2">{lab}</text>'
        )

    total = sum(lang_bytes.values()) or 1
    # Keep the bar readable: top languages, then "other".
    items = sorted(lang_bytes.items(), key=lambda kv: -kv[1])
    named = []
    other = 0
    for name, bytes_ in items:
        label = "Jupyter" if name == "Jupyter Notebook" else name
        share = bytes_ / total
        if len(named) < 4 and share >= 0.008 and label not in ("Procfile",):
            named.append((label, share))
        else:
            other += share
    parts = named + ([("other", other)] if other > 0 else [])
    langs = [(name, pct, LANG_BAR_COLORS.get(name, "#3d434e")) for name, pct in largest_remainder(parts)]

    b.append(f'<text x="24" y="136" font-family="{F}" font-size="10" fill="{MUTED}" letter-spacing="2">// LANGUAGE ANALYSIS</text>')
    b.append(f'<text x="856" y="136" font-family="{F}" font-size="10" fill="{MUTED}" text-anchor="end" letter-spacing="2">100%</text>')
    bx, bw, by = 24, 832, 144
    b.append(f'<polygon points="{cham(bx, by, bw, 16, 0, 0, 6, 0)}" fill="{PANEL}" stroke="{STEEL}"/>')
    x = bx + 3
    for name, p, col in langs:
        w = (bw - 6) * p / 100
        b.append(f'<rect x="{x:.1f}" y="{by + 3}" width="{max(w - 2, 1):.1f}" height="10" fill="{col}"/>')
        x += w
    b.append(
        "".join(
            f'<rect x="{bx + 3 + i * 8 + 6}" y="{by + 3}" width="2" height="10" fill="{PANEL}" opacity="0.85"/>'
            for i in range(103)
        )
    )
    b.append(
        f'<rect x="{bx}" y="{by + 3}" width="24" height="10" fill="#fff" opacity="0.25">'
        f'<animate attributeName="x" values="{bx};{bx + bw - 24}" dur="4s" repeatCount="indefinite"/></rect>'
    )
    x = 24
    for name, p, col in langs:
        lab = f"{name} {p}%"
        b.append(
            f'<rect x="{x}" y="{by + 34}" width="10" height="10" fill="{col}" stroke="{STEEL}"/>'
            f'<text x="{x + 16}" y="{by + 43}" font-family="{F}" font-size="12" fill="{DIM}">{xml(lab)}</text>'
        )
        x += 16 + len(lab) * 12 * CW + 30
    b.append(f'<rect width="{W}" height="{H}" fill="url(#sl)"/>')
    return svg(W, H, "".join(b), defs), langs


def card_links(names: list[str]) -> str:
    lines = ['<p align="center">']
    for n in names:
        lines.append(
            f'<a href="https://github.com/{OWNER}/{n}"><img src="assets/card-{n}.svg" width="49%" alt="{xml(n)}"/></a>'
        )
    lines.append("</p>")
    return "\n".join(lines)


def update_readme(main: list[str], other: list[str]) -> None:
    text = README.read_text(encoding="utf-8")
    # Replace the two card grids, leaving headings and everything else intact.
    import re

    pattern = re.compile(
        r'(<p align="center"><img src="assets/h-projects\.svg"[^>]*>\s*</p>\s*)'
        r'<p align="center">.*?</p>'
        r'(.*?<!--STATSPLIT-->)?'
        r'(.*?\<p align="center"><img src="assets/h-stack\.svg")',
        re.S,
    )
    # Simpler: split on known heading markers.
    start_proj = text.find('<p align="center"><img src="assets/h-projects.svg"')
    start_stack = text.find('<p align="center"><img src="assets/h-stack.svg"')
    start_other = text.find('<p align="center"><img src="assets/h-other.svg"')
    start_footer = text.find('<p align="center"><img src="assets/footer.svg"')
    if min(start_proj, start_stack, start_other, start_footer) < 0:
        raise RuntimeError("README is missing an expected section marker; refusing to rewrite it")
    # from h-projects through just before h-stack: heading + cards
    proj_head_end = text.find("</p>", start_proj) + 4
    new_proj = text[start_proj:proj_head_end] + "\n" + card_links(main) + "\n\n"
    # from h-other through just before footer
    other_head_end = text.find("</p>", start_other) + 4
    new_other = text[start_other:other_head_end] + "\n" + card_links(other) + "\n\n"
    updated = text[:start_proj] + new_proj + text[start_stack:start_other] + new_other + text[start_footer:]
    README.write_text(updated, encoding="utf-8")


def main() -> int:
    token = _token()
    if not token:
        print("no GitHub token (GITHUB_TOKEN / gh auth token)", file=sys.stderr)
        return 1
    repos = fetch_public_repos(token)
    if not repos:
        print("GitHub returned no public repos", file=sys.stderr)
        return 1
    public_count = len(repos)
    daily = [r for r in repos if is_daily(r)]
    daily.sort(key=lambda r: r["created"], reverse=True)
    if not daily:
        print("no daily repos matched; aborting so we don't wipe the grid", file=sys.stderr)
        return 1

    by_name = {r["name"]: r for r in repos}
    main_repos = daily[:MAIN_LIMIT]
    overflow = daily[MAIN_LIMIT:]
    other_names = [r["name"] for r in overflow] + [n for n in FEATURED_OTHER if n in by_name]
    main_names = [r["name"] for r in main_repos]

    lang_bytes = fetch_languages([r["name"] for r in repos], token)
    if not lang_bytes:
        print("language totals were empty; aborting", file=sys.stderr)
        return 1

    ASSETS.mkdir(exist_ok=True)
    used = set()

    def emit(name: str, idx: int, tag: str, acc: str, title_col: str) -> None:
        repo = by_name[name]
        meta = FEATURED_META.get(name, {})
        if meta.get("desc"):
            desc = meta["desc"]
        else:
            desc = wrap_desc(repo["description"] or name)
        lang = meta.get("lang") or lang_label(repo["language"])
        write(f"card-{name}.svg", card(name, idx, tag, acc, title_col, desc, lang))
        used.add(name)
        print(f"  {tag}-{idx + 1:03d}  {name:40}  {desc}")

    print(f"public={public_count}  from-scratch={len(daily)}  main={len(main_names)}  other={len(other_names)}")
    for i, n in enumerate(main_names):
        emit(n, i, "CASE", Y, W_)
    # Overflow dailies keep CASE labels with a continuing index.
    for i, n in enumerate(overflow):
        emit(n["name"], len(main_names) + i, "CASE", Y, W_)
    cold = [n for n in other_names if n not in {r["name"] for r in overflow}]
    for i, n in enumerate(cold):
        emit(n, i, "COLD", "#8b93a1", Y)

    heading("h-projects.svg", "BAT-COMPUTER: PROJECTS", f"[ {len(main_names):02d} FILES ]")
    heading("h-other.svg", "OTHER CASES", "[ COLD FILES ]")
    svg_text, langs = stats_svg(public_count, len(daily), lang_bytes)
    write("stats.svg", svg_text)
    print("languages:", ", ".join(f"{n} {p}%" for n, p, _ in langs))

    update_readme(main_names, other_names)

    # Drop generated cards that are no longer referenced (leave non-card assets).
    keep_prefixes = ("card-",)
    referenced = {f"card-{n}.svg" for n in (main_names + other_names)}
    for path in ASSETS.glob("card-*.svg"):
        if path.name not in referenced:
            path.unlink()
            print(f"removed stale {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
