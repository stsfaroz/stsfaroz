#!/usr/bin/env python3
"""Regenerates assets/terminal.svg — the typed Ubuntu-terminal README banner.

Pulls live repo/follower counts from the GitHub API for the ./status.sh
line; everything else in the session is static copy. Run manually or via
.github/workflows/refresh-terminal.yml (weekly + on relevant pushes).
"""
import html
import json
import os
import sys
import urllib.request

GITHUB_USER = "stsfaroz"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "assets", "terminal.svg")

FONT_SIZE = 14.5
CHAR_W = 8.75
LINE_H = 25
PAD_X = 22
PAD_TOP = 50
TITLE_H = 38
WIDTH = 620

PROMPT_USER = "salman@ubuntu"
PROMPT_PATH = "~"

# classic Ubuntu (GNOME Terminal) palette
BG = "#300a24"
TITLEBAR = "#2c0722"
BORDER = "#4b1039"
FG = "#eeeeec"          # default foreground
GREEN = "#8ae234"       # bold bright green — user@host
BLUE = "#729fcf"        # bold bright blue — cwd

CHARS_PER_SEC = 42.0
PAUSE_AFTER_CMD = 0.18
OUTPUT_FADE = 0.22
PAUSE_AFTER_OUTPUT = 0.55
CURSOR_BLINK_BEFORE = 0.55
PROMPT_APPEAR = 0.06


def fetch_status_line():
    """Live repo/follower counts, falling back to a safe default on any error
    (rate limit, no network) so a bad fetch never breaks the SVG."""
    try:
        req = urllib.request.Request(
            f"https://api.github.com/users/{GITHUB_USER}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "gen-terminal-script"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        return f"{data['public_repos']} repos · {data['followers']} followers · still building."
    except Exception as exc:
        print(f"warning: GitHub API fetch failed ({exc}), keeping last-known status line", file=sys.stderr)
        return "33 repos · 48 followers · still building."


session = [
    ("whoami", ["salman-faroz — AI Researcher"]),
    ("cat role.txt", ["Deep Learning · Applied ML · research → production"]),
    ("ls stack/", [
        "python  pytorch  tensorflow  scikit-learn  opencv",
        "numpy   pandas   jupyter     docker        git   linux",
    ]),
    ("cat contact.txt", [
        ("portfolio   stsfaroz.github.io", "https://stsfaroz.github.io/"),
        ("linkedin    linkedin.com/in/salman-faroz", "https://www.linkedin.com/in/salman-faroz"),
        ("mail        stsfaroz@gmail.com", "mailto:stsfaroz@gmail.com"),
    ]),
    ("./status.sh", [fetch_status_line()]),
]


def esc(s):
    return html.escape(s, quote=False)


prompt_prefix = f'{PROMPT_USER}:{PROMPT_PATH}$ '
prompt_len = len(prompt_prefix)
cursor_x = PAD_X + prompt_len * CHAR_W


def prompt_tspans(begin_t, instant=False):
    """Render the coloured 'user@host:~$ ' prompt, fading in at begin_t."""
    if instant:
        anim = ''
    else:
        anim = f'<animate attributeName="opacity" from="0" to="1" begin="{begin_t:.2f}s" dur="{PROMPT_APPEAR:.2f}s" fill="freeze"/>'
    op = '1' if instant else '0'
    return (
        f'<tspan fill="{GREEN}" font-weight="600" opacity="{op}">{anim}{esc(PROMPT_USER)}</tspan>'
        f'<tspan fill="{FG}" opacity="{op}">{anim}:</tspan>'
        f'<tspan fill="{BLUE}" font-weight="600" opacity="{op}">{anim}{esc(PROMPT_PATH)}</tspan>'
        f'<tspan fill="{FG}" opacity="{op}">{anim}$ </tspan>'
    )


elements = []
defs = []
areas = []
t = 0.35
y = PAD_TOP

for cmd_i, (cmd, outputs) in enumerate(session):
    is_first = cmd_i == 0
    prompt_start = t
    elements.append(f'''
<text x="{PAD_X}" y="{y}" font-size="{FONT_SIZE}">{prompt_tspans(prompt_start, instant=is_first)}</text>''')
    t = prompt_start + (0 if is_first else PROMPT_APPEAR)

    # cursor blink while waiting to type this command
    blink_start = t
    elements.append(f'''
<rect x="{cursor_x:.1f}" y="{y-11:.1f}" width="{CHAR_W-1.5:.1f}" height="15" fill="{FG}" opacity="0">
  <animate attributeName="opacity" values="0;1;0;1;0;1;0" keyTimes="0;0.01;0.17;0.34;0.5;0.67;1"
           begin="{blink_start:.2f}s" dur="{CURSOR_BLINK_BEFORE:.2f}s" fill="freeze"/>
</rect>''')

    t += CURSOR_BLINK_BEFORE
    type_start = t
    cmd_len = len(cmd)
    type_dur = max(cmd_len / CHARS_PER_SEC, 0.05)
    clip_id = f"clip{cmd_i}"
    reveal_w = cmd_len * CHAR_W + 6

    defs.append(f'''
<clipPath id="{clip_id}">
  <rect x="{cursor_x:.1f}" y="{y-16:.1f}" width="0" height="22">
    <animate attributeName="width" from="0" to="{reveal_w:.1f}" begin="{type_start:.2f}s" dur="{type_dur:.2f}s" fill="freeze" calcMode="linear"/>
  </rect>
</clipPath>''')

    elements.append(f'''
<text x="{cursor_x:.1f}" y="{y}" font-size="{FONT_SIZE}" fill="{FG}" clip-path="url(#{clip_id})">{esc(cmd)}</text>''')

    t = type_start + type_dur + PAUSE_AFTER_CMD
    y += LINE_H

    for out_line in outputs:
        out_start = t

        if isinstance(out_line, tuple):
            text, href = out_line
            areas.append((PAD_X, y - 16, PAD_X + len(text) * CHAR_W, y + 6, href, text.strip()))
        else:
            text = out_line

        elements.append(f'''
<text x="{PAD_X}" y="{y}" font-size="{FONT_SIZE}" fill="{FG}" opacity="0">
  <animate attributeName="opacity" from="0" to="1" begin="{out_start:.2f}s" dur="{OUTPUT_FADE:.2f}s" fill="freeze"/>
  {esc(text)}
</text>''')
        t += OUTPUT_FADE * 0.35
        y += LINE_H

    t += PAUSE_AFTER_OUTPUT
    y += LINE_H * 0.25

# trailing idle prompt + blinking cursor, appears only after everything above finished
final_start = t
elements.append(f'''
<text x="{PAD_X}" y="{y}" font-size="{FONT_SIZE}">{prompt_tspans(final_start)}</text>
<rect x="{cursor_x:.1f}" y="{y-11:.1f}" width="{CHAR_W-1.5:.1f}" height="15" fill="{FG}" opacity="0">
  <animate attributeName="opacity" values="0;1;0;1;0;1;0" keyTimes="0;0.01;0.17;0.34;0.5;0.67;1"
           begin="{final_start+PROMPT_APPEAR:.2f}s" dur="10s" repeatCount="indefinite"/>
</rect>''')

y += 22
total_height = y + 14

svg = f'''<svg width="{WIDTH}" height="{total_height:.0f}" viewBox="0 0 {WIDTH} {total_height:.0f}" xmlns="http://www.w3.org/2000/svg">
<defs>
<style>
  text {{ font-family: "Ubuntu Mono","DejaVu Sans Mono","JetBrains Mono",Consolas,monospace; }}
</style>
{''.join(defs)}
</defs>

<rect width="{WIDTH}" height="{total_height:.0f}" fill="{BG}"/>

<rect width="{WIDTH}" height="{TITLE_H}" fill="{TITLEBAR}"/>
<line x1="0" y1="{TITLE_H}" x2="{WIDTH}" y2="{TITLE_H}" stroke="{BORDER}" stroke-width="1"/>
<text x="{WIDTH/2:.0f}" y="{TITLE_H/2+4:.0f}" text-anchor="middle" font-size="12.5" fill="{FG}" opacity="0.75">{esc(PROMPT_USER)}: {esc(PROMPT_PATH)}</text>

<!-- GNOME/Yaru-style window controls, right-aligned, monochrome pills -->
<g fill="#4a1338">
  <circle cx="{WIDTH-72:.1f}" cy="{TITLE_H/2:.0f}" r="11"/>
  <circle cx="{WIDTH-44:.1f}" cy="{TITLE_H/2:.0f}" r="11"/>
  <circle cx="{WIDTH-16:.1f}" cy="{TITLE_H/2:.0f}" r="11"/>
</g>
<g stroke="{FG}" stroke-opacity="0.7" stroke-width="1.4" fill="none" stroke-linecap="round">
  <line x1="{WIDTH-76:.1f}" y1="{TITLE_H/2:.0f}" x2="{WIDTH-68:.1f}" y2="{TITLE_H/2:.0f}"/>
  <rect x="{WIDTH-48:.1f}" y="{TITLE_H/2-4:.0f}" width="8" height="8" rx="1.5"/>
  <line x1="{WIDTH-20:.1f}" y1="{TITLE_H/2-4:.0f}" x2="{WIDTH-12:.1f}" y2="{TITLE_H/2+4:.0f}"/>
  <line x1="{WIDTH-20:.1f}" y1="{TITLE_H/2+4:.0f}" x2="{WIDTH-12:.1f}" y2="{TITLE_H/2-4:.0f}"/>
</g>

{''.join(elements)}
</svg>
'''

with open(OUTPUT_PATH, "w") as f:
    f.write(svg)

print(f"wrote {OUTPUT_PATH}")
print("contact.txt link areas (should match the <map> in README.md):")
for (x1, y1, x2, y2, href, alt) in areas:
    coords = f"{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}"
    print(f'  <area shape="rect" coords="{coords}" href="{href}" alt="{alt}" />')
