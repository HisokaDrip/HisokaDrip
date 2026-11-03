"""Builds assets/typing.svg from the lines in typing.txt (one line = one phrase)."""
from pathlib import Path

CHAR_W = 13.2          # width of one character at font-size 22
SLOT = 4.0             # seconds per phrase
root = Path(__file__).resolve().parent.parent
lines = [l.strip() for l in (root / "typing.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
n = len(lines)
dur = SLOT * n
font = "'JetBrains Mono','Fira Code',Consolas,monospace"
out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="70" viewBox="0 0 880 70"><rect width="880" height="70" fill="#0a0510"/>']
for i, text in enumerate(lines):
    w = round(len(text) * CHAR_W)
    s = i / n
    kt = f"0;{s:.4f};{s + 0.07 / n * 4:.4f};{s + 0.22 / n * 4:.4f};{s + 0.221 / n * 4:.4f};1"
    if i == 0:
        kt = f"0;0;{0.07 / n * 4:.4f};{0.22 / n * 4:.4f};{0.221 / n * 4:.4f};1"
    vals_w = f"0;0;{w};{w};0;0"
    vals_x = f"40;40;{40 + w};{40 + w};40;40"
    vals_o = "0;0;1;1;0;0"
    anim = lambda a, v: f'<animate attributeName="{a}" values="{v}" keyTimes="{kt}" dur="{dur:g}s" repeatCount="indefinite"/>'
    out.append(f'<clipPath id="c{i}"><rect x="40" y="0" height="70" width="0">{anim("width", vals_w)}</rect></clipPath>')
    out.append(f'<text x="40" y="42" font-family="{font}" font-size="22" fill="#f2e6ff" clip-path="url(#c{i})">{text}</text>')
    out.append(f'<rect y="20" width="3" height="28" fill="#a855f7" opacity="0">{anim("x", vals_x)}{anim("opacity", vals_o)}</rect>')
out.append("</svg>")
(root / "assets" / "typing.svg").write_text("\n".join(out), encoding="utf-8")
