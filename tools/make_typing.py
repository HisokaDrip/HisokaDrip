"""Builds assets/typing.svg from the lines in typing.txt (one line = one phrase)."""
from pathlib import Path

CHAR_W = 13.2          # width of one character at font-size 22
SLOT = 4.0             # seconds per phrase
X0 = 92                # where the typed text starts
root = Path(__file__).resolve().parent.parent
lines = [l.strip() for l in (root / "typing.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
n = len(lines)
dur = SLOT * n
font = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,'DejaVu Sans Mono',monospace"
BG, PANEL, Y, C, M = "#0b0b0f", "#111119", "#fcee0a", "#00f0ff", "#ff003c"
out = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="880" height="76" viewBox="0 0 880 76">',
    '<defs><filter id="gl" x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="2.2" result="b"/>'
    '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    '<pattern id="sl" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity="0.4"/></pattern></defs>',
    f'<rect width="880" height="76" fill="{BG}"/>',
    f'<polygon points="24,10 840,10 856,26 856,66 40,66 24,50" fill="{PANEL}" stroke="{C}" stroke-width="1.2" stroke-opacity="0.5"/>',
    f'<polygon points="24,10 140,10 134,15 24,15" fill="{Y}"/>',
    f'<rect x="24" y="22" width="3" height="32" fill="{Y}"/>',
    f'<text x="44" y="46" font-family="{font}" font-size="22" font-weight="bold" fill="{M}" filter="url(#gl)">&gt;_</text>',
    f'<rect x="780" y="61" width="60" height="3" fill="{C}" opacity="0.7"/>',
    f'<rect x="828" y="18" width="8" height="8" fill="{M}"><animate attributeName="opacity" values="1;0.15;1" dur="1.4s" repeatCount="indefinite"/></rect>',
]
for i, text in enumerate(lines):
    w = round(len(text) * CHAR_W)
    s = i / n
    kt = f"0;{s:.4f};{s + 0.07 / n * 4:.4f};{s + 0.22 / n * 4:.4f};{s + 0.221 / n * 4:.4f};1"
    if i == 0:
        kt = f"0;0;{0.07 / n * 4:.4f};{0.22 / n * 4:.4f};{0.221 / n * 4:.4f};1"
    vals_w = f"0;0;{w};{w};0;0"
    vals_x = f"{X0};{X0};{X0 + w + 2};{X0 + w + 2};{X0};{X0}"
    vals_o = "0;0;1;1;0;0"
    anim = lambda a, v: f'<animate attributeName="{a}" values="{v}" keyTimes="{kt}" dur="{dur:g}s" repeatCount="indefinite"/>'
    out.append(f'<clipPath id="c{i}"><rect x="{X0}" y="0" height="76" width="0">{anim("width", vals_w)}</rect></clipPath>')
    out.append(f'<text x="{X0}" y="46" font-family="{font}" font-size="22" fill="{Y}" filter="url(#gl)" clip-path="url(#c{i})">{text}</text>')
    out.append(f'<rect y="25" width="12" height="26" fill="{C}" opacity="0">{anim("x", vals_x)}{anim("opacity", vals_o)}</rect>')
out.append('<rect width="880" height="76" fill="url(#sl)"/>')
out.append("</svg>")
(root / "assets" / "typing.svg").write_text("\n".join(out), encoding="utf-8")
