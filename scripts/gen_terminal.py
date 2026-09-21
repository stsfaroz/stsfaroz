#!/usr/bin/env python3
"""Regenerates assets/terminal.svg — the typed Ubuntu-terminal README banner.

Pulls live repo/follower counts from the GitHub API for the ./status.sh
line; everything else in the session is static copy. Run manually or via
.github/workflows/refresh-terminal.yml (weekly + on relevant pushes).
"""
import html
import json
import math
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

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


def now_ist_string():
    """Current time in IST (UTC+5:30), formatted like the real `date`
    command. Reflects the moment this script last ran — a quiet proof
    the daily cron is actually alive, not just a claim."""
    ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    return ist.strftime("%a %b %-d %H:%M IST %Y")


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


def fetch_activity_weeks(weeks=8):
    """Real weekly public-event counts (pushes, PRs, issues, ...) for the
    last `weeks` weeks, from /events/public. Returns None on any failure so
    the sparkline is simply skipped rather than showing fabricated data."""
    try:
        req = urllib.request.Request(
            f"https://api.github.com/users/{GITHUB_USER}/events/public?per_page=100",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "gen-terminal-script"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            events = json.load(resp)
        now = datetime.now(timezone.utc)
        buckets = [0] * weeks
        for e in events:
            ts = datetime.strptime(e["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age_days = (now - ts).days
            week_idx = weeks - 1 - (age_days // 7)
            if 0 <= week_idx < weeks:
                buckets[week_idx] += 1
        return buckets
    except Exception as exc:
        print(f"warning: activity fetch failed ({exc}), skipping sparkline", file=sys.stderr)
        return None


def _github_token():
    """A token for the GraphQL API (which requires auth even for public
    data). Prefers GITHUB_TOKEN (set by the Actions workflow), falls back
    to the local gh CLI's token for manual runs."""
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        return subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5, check=True
        ).stdout.strip()
    except Exception:
        return None


def fetch_join_year():
    """Account creation year, to know how far back to sum contributions.
    Falls back to the real join year (2018) on any failure."""
    try:
        req = urllib.request.Request(
            f"https://api.github.com/users/{GITHUB_USER}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "gen-terminal-script"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        return int(data["created_at"][:4])
    except Exception:
        return 2018


def fetch_total_commits(join_year):
    """Real all-time commit count, from GitHub's own contribution data
    (GraphQL contributionsCollection), summed year by year since join_year.
    This is de-duplicated per repo — unlike the commit search API, it
    doesn't count the same commit again in every unrelated fork that
    copied it. Returns None (label omitted) if no token is available or
    any call fails, rather than showing a wrong number."""
    token = _github_token()
    if not token:
        print("warning: no GitHub token available, omitting commit count", file=sys.stderr)
        return None

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          commitContributionsByRepository(maxRepositories: 100) {
            contributions { totalCount }
          }
        }
      }
    }
    """
    total = 0
    current_year = datetime.now(timezone.utc).year
    try:
        for year in range(join_year, current_year + 1):
            body = json.dumps({
                "query": query,
                "variables": {
                    "login": GITHUB_USER,
                    "from": f"{year}-01-01T00:00:00Z",
                    "to": f"{year}-12-31T23:59:59Z",
                },
            }).encode()
            req = urllib.request.Request(
                "https://api.github.com/graphql",
                data=body,
                headers={
                    "Authorization": f"bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "gen-terminal-script",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
            repos = data["data"]["user"]["contributionsCollection"]["commitContributionsByRepository"]
            total += sum(r["contributions"]["totalCount"] for r in repos)
        return total
    except Exception as exc:
        print(f"warning: commit count fetch failed ({exc}), omitting label", file=sys.stderr)
        return None


CONTRIBUTIONS = [
    ("ubuntu", "ubuntu/app-center"),
    ("ggml-org", "ggml-org/whisper.cpp"),
    ("crewAIInc", "crewAIInc/crewAI"),
    ("langchain-ai", "langchain-ai/langchain"),
    ("huggingface", "huggingface/sentence-transformers"),
    ("tensorflow", "tensorflow/probability"),
]
_LABEL_W = max(len(org) for org, _ in CONTRIBUTIONS) + 4
_contributions_outputs = [
    (f"{org.ljust(_LABEL_W)}{repo}", f"https://github.com/{repo}")
    for org, repo in CONTRIBUTIONS
]

_status_outputs = [fetch_status_line(), f"as of {now_ist_string()}"]
_weekly_activity = fetch_activity_weeks()
if _weekly_activity is not None:
    _status_outputs.append(("__spark__", _weekly_activity, fetch_total_commits(fetch_join_year())))

session = [
    ("whoami", ["salman-faroz — AI Researcher"]),
    ("cat role.txt", ["Deep Learning · Applied ML · research → production"]),
    ("./status.sh", _status_outputs),
    ("cat contributions.txt", _contributions_outputs),
    ("cat contact.txt", [
        ("portfolio   stsfaroz.github.io", "https://stsfaroz.github.io/"),
        ("linkedin    linkedin.com/in/salman-faroz", "https://www.linkedin.com/in/salman-faroz"),
        ("mail        stsfaroz@gmail.com", "mailto:stsfaroz@gmail.com"),
    ]),
    ("locate --self", [
        "Karur, Tamil Nadu, India",
        ("__radar__", "10.9600°N  78.0750°E"),
    ]),
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

        if isinstance(out_line, tuple) and out_line[0] == "__radar__":
            _, coords_label = out_line
            r = 19.0
            y += 4
            cx, cy = PAD_X + r, y + r

            sweep_len = 3.4  # seconds per full rotation
            glow_id = f"radar-glow{cmd_i}"
            defs.append(f'''
<filter id="{glow_id}" x="-60%" y="-60%" width="220%" height="220%">
  <feGaussianBlur stdDeviation="1.6" result="blur"/>
  <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>''')

            # blip position: fixed angle/radius inside the scope
            blip_angle = math.radians(-52)
            blip_r = r * 0.58
            blip_x = cx + blip_r * math.cos(blip_angle)
            blip_y = cy + blip_r * math.sin(blip_angle)

            # sweep wedge: a ~26° pie slice from center, rotated continuously
            wedge_deg = 26
            a1 = math.radians(-wedge_deg)
            x1, y1v = cx + r * math.cos(a1), cy + r * math.sin(a1)
            x2, y2v = cx + r, cy

            elements.append(f'''
<g opacity="0">
  <animate attributeName="opacity" from="0" to="1" begin="{out_start:.2f}s" dur="0.3s" fill="freeze"/>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{GREEN}" stroke-opacity="0.55" stroke-width="1"/>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r*0.66:.1f}" fill="none" stroke="{GREEN}" stroke-opacity="0.4" stroke-width="1"/>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r*0.33:.1f}" fill="none" stroke="{GREEN}" stroke-opacity="0.32" stroke-width="1"/>
  <line x1="{cx-r:.1f}" y1="{cy:.1f}" x2="{cx+r:.1f}" y2="{cy:.1f}" stroke="{GREEN}" stroke-opacity="0.22" stroke-width="1"/>
  <line x1="{cx:.1f}" y1="{cy-r:.1f}" x2="{cx:.1f}" y2="{cy+r:.1f}" stroke="{GREEN}" stroke-opacity="0.22" stroke-width="1"/>

  <g>
    <animateTransform attributeName="transform" type="rotate" from="0 {cx:.1f} {cy:.1f}" to="360 {cx:.1f} {cy:.1f}" dur="{sweep_len:.1f}s" begin="{out_start:.2f}s" repeatCount="indefinite"/>
    <path d="M{cx:.1f},{cy:.1f} L{x1:.1f},{y1v:.1f} A{r:.1f},{r:.1f} 0 0,1 {x2:.1f},{y2v:.1f} Z" fill="{GREEN}" opacity="0.16"/>
    <line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{y2v:.1f}" stroke="{GREEN}" stroke-width="1.2" stroke-opacity="0.85"/>
  </g>

  <circle cx="{blip_x:.1f}" cy="{blip_y:.1f}" r="2.6" fill="{GREEN}" filter="url(#{glow_id})"/>
  <circle cx="{blip_x:.1f}" cy="{blip_y:.1f}" r="2.6" fill="none" stroke="{GREEN}" stroke-width="1.2">
    <animate attributeName="r" values="2.6;{r*0.9:.1f}" dur="2.6s" begin="{out_start:.2f}s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.8;0" dur="2.6s" begin="{out_start:.2f}s" repeatCount="indefinite"/>
  </circle>

  <text x="{cx+r+14:.1f}" y="{cy+4:.1f}" font-size="11" fill="{FG}" opacity="0.6">{esc(coords_label)}</text>
</g>''')

            t = out_start + 0.35
            y = cy + r + LINE_H * 0.5
            continue

        if isinstance(out_line, tuple) and out_line[0] == "__spark__":
            counts = out_line[1]
            total_commits = out_line[2]
            n = len(counts)
            chart_w, chart_h = 220.0, 30.0
            max_v = max(max(counts), 1)
            xs = [i * (chart_w / (n - 1)) for i in range(n)] if n > 1 else [0.0]
            ys = [chart_h - (c / max_v) * chart_h for c in counts]

            caption_y = y + 8
            top = caption_y + 14
            pts = [(PAD_X + px, top + py) for px, py in zip(xs, ys)]
            draw_dur = 0.9

            poly_str = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
            baseline = top + chart_h
            area_str = poly_str + f" {pts[-1][0]:.1f},{baseline:.1f} {pts[0][0]:.1f},{baseline:.1f}"

            reveal_id = f"spark-clip{cmd_i}"
            glow_id = f"spark-glow{cmd_i}"
            defs.append(f'''
<clipPath id="{reveal_id}">
  <rect x="{PAD_X-2}" y="{top-4:.1f}" width="0" height="{chart_h+8:.1f}">
    <animate attributeName="width" from="0" to="{chart_w+4:.1f}" begin="{out_start:.2f}s" dur="{draw_dur:.2f}s" fill="freeze" calcMode="linear"/>
  </rect>
</clipPath>
<filter id="{glow_id}" x="-30%" y="-100%" width="160%" height="300%">
  <feGaussianBlur stdDeviation="2.2" result="blur"/>
  <feMerge>
    <feMergeNode in="blur"/>
    <feMergeNode in="blur"/>
    <feMergeNode in="SourceGraphic"/>
  </feMerge>
</filter>''')

            # radar/scope-style graticule behind the trace
            grid_rows = "".join(
                f'<line x1="{PAD_X}" y1="{top+chart_h*f:.1f}" x2="{PAD_X+chart_w:.1f}" y2="{top+chart_h*f:.1f}" stroke="{GREEN}" stroke-opacity="0.15" stroke-width="1"/>'
                for f in (0.0, 0.5, 1.0)
            )
            grid_cols = "".join(
                f'<line x1="{PAD_X+chart_w*f/4:.1f}" y1="{top:.1f}" x2="{PAD_X+chart_w*f/4:.1f}" y2="{top+chart_h:.1f}" stroke="{GREEN}" stroke-opacity="0.1" stroke-width="1"/>'
                for f in range(1, 4)
            )

            elements.append(f'''
<text x="{PAD_X}" y="{caption_y:.1f}" font-size="10.5" fill="{FG}" opacity="0"><animate attributeName="opacity" from="0" to="0.55" begin="{out_start:.2f}s" dur="0.3s" fill="freeze"/>public activity</text>
<g opacity="0">
  <animate attributeName="opacity" from="0" to="1" begin="{out_start:.2f}s" dur="0.3s" fill="freeze"/>
  {grid_rows}{grid_cols}
</g>
<g clip-path="url(#{reveal_id})">
  <polygon points="{area_str}" fill="{GREEN}" opacity="0.12"/>
  <polyline points="{poly_str}" fill="none" stroke="{GREEN}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" filter="url(#{glow_id})"/>
</g>
<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3" fill="{GREEN}" filter="url(#{glow_id})" opacity="0">
  <animate attributeName="opacity" from="0" to="1" begin="{out_start+draw_dur:.2f}s" dur="0.15s" fill="freeze"/>
</circle>''')

            if total_commits is not None:
                elements.append(
                    f'<text x="{pts[-1][0]+9:.1f}" y="{pts[-1][1]+3.5:.1f}" font-size="10.5" fill="{GREEN}" opacity="0">'
                    f'<animate attributeName="opacity" from="0" to="1" begin="{out_start+draw_dur:.2f}s" dur="0.15s" fill="freeze"/>'
                    f'{total_commits:,} commits, all-time</text>'
                )

            t = out_start + draw_dur + 0.25
            y = top + chart_h + LINE_H * 0.6
            continue

        if isinstance(out_line, tuple):
            text, href = out_line
            areas.append((PAD_X, y - 16, PAD_X + len(text) * CHAR_W, y + 6, href, text.strip()))
        else:
            text = out_line

        elements.append(
            f'<text x="{PAD_X}" y="{y}" font-size="{FONT_SIZE}" fill="{FG}" opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" begin="{out_start:.2f}s" dur="{OUTPUT_FADE:.2f}s" fill="freeze"/>'
            f'{esc(text)}</text>'
        )
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

svg = f'''<svg width="{WIDTH}" height="{total_height:.0f}" viewBox="0 0 {WIDTH} {total_height:.0f}" xmlns="http://www.w3.org/2000/svg" xml:space="preserve">
<defs>
<style>
  text {{ font-family: "Ubuntu Mono","DejaVu Sans Mono","JetBrains Mono",Consolas,monospace; white-space: pre; }}
</style>
<pattern id="scanlines" width="4" height="4" patternUnits="userSpaceOnUse">
  <rect width="4" height="1" fill="#000000" opacity="0.5"/>
</pattern>
{''.join(defs)}
</defs>

<rect width="{WIDTH}" height="{total_height:.0f}" fill="{BG}"/>

<rect width="{WIDTH}" height="{TITLE_H}" fill="{TITLEBAR}"/>
<line x1="0" y1="{TITLE_H}" x2="{WIDTH}" y2="{TITLE_H}" stroke="{BORDER}" stroke-width="1"/>
<text x="{WIDTH/2:.0f}" y="{TITLE_H/2+4:.0f}" text-anchor="middle" font-size="12.5" fill="{FG}" opacity="0.75">{esc(PROMPT_USER)}: {esc(PROMPT_PATH)}</text>
<circle cx="{WIDTH/2-70:.1f}" cy="{TITLE_H/2:.0f}" r="3" fill="{GREEN}">
  <animate attributeName="opacity" values="1;0.35;1" dur="2.4s" repeatCount="indefinite"/>
</circle>

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

<!-- CRT: faint scanlines sitting over everything, then a bright boot-flash that fades to reveal the session -->
<rect width="{WIDTH}" height="{total_height:.0f}" fill="url(#scanlines)" opacity="0.1"/>
<rect width="{WIDTH}" height="{total_height:.0f}" fill="#ffffff" opacity="0.85">
  <animate attributeName="opacity" from="0.85" to="0" begin="0s" dur="0.3s" fill="freeze" calcMode="linear"/>
</rect>
</svg>
'''

with open(OUTPUT_PATH, "w") as f:
    f.write(svg)

print(f"wrote {OUTPUT_PATH}")
print("contact.txt link areas (should match the <map> in README.md):")
for (x1, y1, x2, y2, href, alt) in areas:
    coords = f"{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}"
    print(f'  <area shape="rect" coords="{coords}" href="{href}" alt="{alt}" />')
