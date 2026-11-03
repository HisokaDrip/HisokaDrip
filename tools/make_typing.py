"""Builds assets/typing.svg from the lines in typing.txt (one line = one phrase)."""
from pathlib import Path

CHAR_W = 13.2          # width of one character at font-size 22
SLOT = 4.0             # seconds per phrase
X0 = 92                # where the typed text starts
root = Path(__file__).resolve().parent.parent
lines = [l.strip() for l in (root / "typing.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
n = len(lines)
dur = SLOT * n
font = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,'DejaVu Sans Mono','Yu Gothic','Meiryo','Hiragino Sans','Noto Sans CJK JP',monospace"
BG, PANEL, Y, C, M = "#07080a", "#14171c", "#ffd400", "#ffd400", "#ffd400"
STEEL, TXT = "#2a2f38", "#f4f5f7"
BAT = ("M0,-11 L3,-11 L5,-18 L6.5,-9 C12,-8 16,-12 18,-17 C30,-14 40,-6 40,4 C36,-1 30,-1 27,3 C24,-2 18,-2 15,4 "
       "C11,0 4,4 0,14 C-4,4 -11,0 -15,4 C-18,-2 -24,-2 -27,3 C-30,-1 -36,-1 -40,4 C-40,-6 -30,-14 -18,-17 "
       "C-16,-12 -12,-8 -6.5,-9 L-5,-18 L-3,-11 Z")
out = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="880" height="76" viewBox="0 0 880 76">',
    '<defs><filter id="gl" x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="2.2" result="b"/>'
    '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    '<pattern id="sl" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity="0.4"/></pattern></defs>',
    f'<rect width="880" height="76" fill="{BG}"/>',
    f'<polygon points="24,10 840,10 856,26 856,66 40,66 24,50" fill="{PANEL}" stroke="{STEEL}" stroke-width="1.5"/>',
    f'<path d="{BAT}" fill="{STEEL}" opacity="0.6" transform="translate(790 40) scale(0.9)"/>',
    f'<polygon points="24,10 140,10 134,15 24,15" fill="{Y}"/>',
    f'<rect x="24" y="22" width="3" height="32" fill="{Y}"/>',
    f'<text x="44" y="46" font-family="{font}" font-size="22" font-weight="bold" fill="{Y}" filter="url(#gl)">&gt;_</text>',
    f'<rect x="780" y="61" width="60" height="3" fill="{Y}" opacity="0.6"/>',
    f'<rect x="828" y="18" width="8" height="8" fill="#d61f33"><animate attributeName="opacity" values="1;0.15;1" dur="1.4s" repeatCount="indefinite"/></rect>',
]
for i, text in enumerate(lines):
    import unicodedata
    w = round(sum(1.72 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text) * CHAR_W)
    s = i / n
    kt = f"0;{s:.4f};{s + 0.07 / n * 4:.4f};{s + 0.22 / n * 4:.4f};{s + 0.221 / n * 4:.4f};1"
    if i == 0:
        kt = f"0;0;{0.07 / n * 4:.4f};{0.22 / n * 4:.4f};{0.221 / n * 4:.4f};1"
    vals_w = f"0;0;{w};{w};0;0"
    vals_x = f"{X0};{X0};{X0 + w + 2};{X0 + w + 2};{X0};{X0}"
    vals_o = "0;0;1;1;0;0"
    anim = lambda a, v: f'<animate attributeName="{a}" values="{v}" keyTimes="{kt}" dur="{dur:g}s" repeatCount="indefinite"/>'
    out.append(f'<clipPath id="c{i}"><rect x="{X0}" y="0" height="76" width="0">{anim("width", vals_w)}</rect></clipPath>')
    out.append(f'<text x="{X0}" y="46" font-family="{font}" font-size="22" fill="{TXT}" clip-path="url(#c{i})">{text}</text>')
    out.append(f'<rect y="25" width="12" height="26" fill="{Y}" opacity="0">{anim("x", vals_x)}{anim("opacity", vals_o)}</rect>')
out.append('<rect width="880" height="76" fill="url(#sl)"/>')
out.append("</svg>")
(root / "assets" / "typing.svg").write_text("\n".join(out), encoding="utf-8")
