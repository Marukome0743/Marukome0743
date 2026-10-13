"""Generate dynamic profile content from public GitHub data.

Usage:
  python3 profile.py oss <readme>        Update the OSS section in a README
  python3 profile.py terminal <out_dir>  Render terminal-dark/light.svg
  python3 profile.py commit <repo> <branch> <head> <message> <files...>
                                         Print a createCommitOnBranch body

Requires the GitHub CLI (`gh`) authenticated through GH_TOKEN.
"""

import base64
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from html import escape

USER = os.environ.get("PROFILE_USER", "Marukome0743")
# Organizations the user works in; listed separately from external OSS.
HOME_OWNERS = {USER, "OpenUp-LabTakizawa"}
STACK = "TypeScript, Python, Bash, Docker, OpenTofu"
SHELL = "zsh + mise + jj"


def gh(*args):
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def search_prs(query, limit=1000):
    """Return (total count, newest-first merged PRs) for a search query."""
    items, total = [], 0
    for page in range(1, -(-limit // 100) + 1):
        res = gh(
            "api", "-X", "GET", "search/issues",
            "-f", f"q=author:{USER} is:pr is:merged {query}",
            "-f", f"per_page={min(limit, 100)}", "-f", f"page={page}",
        )
        items += res["items"]
        total = res["total_count"]
        if len(res["items"]) < 100:
            break
    prs = []
    for item in items:
        repo = item["repository_url"].removeprefix("https://api.github.com/repos/")
        prs.append({
            "repo": repo,
            "title": item["title"],
            "url": item["html_url"],
            "closed": item["closed_at"][:10],
        })
    prs.sort(key=lambda p: p["closed"], reverse=True)
    return total, prs


def external_prs():
    """Merged PRs outside the user's own repositories and home organizations."""
    query = " ".join(
        f"-user:{owner}" for owner in sorted(HOME_OWNERS)
    )
    return search_prs(query)[1]


def stars(repo):
    return gh("api", f"repos/{repo}")["stargazers_count"]


def plural(n, word):
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def human(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def replace_section(text, name, body):
    pattern = re.compile(
        rf"(<!--START_SECTION:{name}-->).*?(<!--END_SECTION:{name}-->)", re.S
    )
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


def cmd_oss(readme):
    ext = external_prs()
    counts = Counter(p["repo"] for p in ext)
    lines = [
        "| | Repository | ⭐ Stars | Merged PRs |",
        "| :-: | :-- | --: | --: |",
    ]
    for repo, n in counts.most_common(8):
        owner = repo.split("/")[0]
        search = f"https://github.com/{repo}/pulls?q=is%3Apr+author%3A{USER}+is%3Amerged"
        lines.append(
            f'| <img src="https://github.com/{owner}.png?size=40" width="20" height="20"> '
            f"| [{repo}](https://github.com/{repo}) | {human(stars(repo))} | [{n}]({search}) |"
        )
    lines += ["", "<details>", "<summary><b>🆕 Latest merged pull requests</b></summary>", ""]
    seen = set()
    latest = [p for p in ext if not (p["repo"] in seen or seen.add(p["repo"]))]
    for p in latest[:8]:
        lines.append(f"- `{p['closed']}` **{p['repo']}** — [{escape(p['title'])}]({p['url']})")
    lines += [
        "",
        "</details>",
        "",
        f"<sub>{len(ext):,} merged PRs across {len(counts)} external repositories "
        f"· updated {datetime.now(timezone.utc):%Y-%m-%d} by GitHub Actions</sub>",
    ]
    with open(readme, encoding="utf-8") as f:
        text = f.read()
    with open(readme, "w", encoding="utf-8") as f:
        f.write(replace_section(text, "oss", "\n".join(lines)))


# --- terminal card ---------------------------------------------------------

ASCII = [
    "       .-''''''''-.",
    "     .'            '.",
    "    /   .-.    .-.   \\",
    "   |   ( o )  ( o )   |",
    "   |    '-'    '-'    |",
    "   |  ~~          ~~  |",
    "    \\    \\      /    /",
    "     '.   '----'   .'",
    "       '-.______.-'",
    "         /      \\",
]

THEMES = {
    "dark": {
        "bg": "#1a1b26", "bar": "#16161e", "border": "#2f334d", "fg": "#c0caf5",
        "dim": "#565f89", "accent": "#7aa2f7", "green": "#9ece6a",
        "yellow": "#e0af68", "magenta": "#bb9af7", "cyan": "#7dcfff",
        "red": "#f7768e",
    },
    "light": {
        "bg": "#ffffff", "bar": "#f3f4f6", "border": "#d0d7de", "fg": "#24292f",
        "dim": "#8c959f", "accent": "#0969da", "green": "#1a7f37",
        "yellow": "#9a6700", "magenta": "#8250df", "cyan": "#1b7c83",
        "red": "#cf222e",
    },
}


def terminal_data():
    user = gh("api", f"users/{USER}")
    repos = gh("api", "--paginate", "--slurp", f"users/{USER}/repos?per_page=100")
    repos = [r for page in repos for r in page]
    q = (
        "query($login:String!){user(login:$login){contributionsCollection"
        "{contributionCalendar{totalContributions}}}}"
    )
    contrib = gh("api", "graphql", "-f", f"query={q}", "-f", f"login={USER}")
    total = search_prs("", limit=1)[0]
    ext = external_prs()
    created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    months = (datetime.now(timezone.utc) - created).days // 30
    top = Counter(p["repo"] for p in ext).most_common(5)
    return {
        "login": user["login"].lower(),
        "location": user["location"] or "Earth",
        "company": user["company"] or "-",
        "bio": user["bio"] or "",
        "uptime": f"{plural(months // 12, 'year')}, {plural(months % 12, 'month')}",
        "since": created.strftime("%Y-%m-%d"),
        "prs": total,
        "contribs": contrib["data"]["user"]["contributionsCollection"]
        ["contributionCalendar"]["totalContributions"],
        "followers": user["followers"],
        "stars": sum(r["stargazers_count"] for r in repos),
        "top": [(repo, n, stars(repo)) for repo, n in top],
    }


def render_terminal(d, t):
    c = THEMES[t]
    lh, x0, y0, cw = 21, 24, 66, 8.43  # line height, padding, char width
    rows = []  # each row: list of (text, color, x_offset_chars)
    prompt = [(f"{d['login']}@github", c["green"], 0), (" ~ $ ", c["dim"], None)]

    def cmd(text):
        rows.append(prompt + [(text, c["fg"], None)])

    cmd("neofetch")
    info = [
        [(f"{d['login']}@github", c["accent"], None)],
        [("-" * (len(d["login"]) + 7), c["dim"], None)],
        [("Location  ", c["yellow"], None), (d["location"], c["fg"], None)],
        [("Org       ", c["yellow"], None), (d["company"], c["fg"], None)],
        [("Uptime    ", c["yellow"], None), (f"{d['uptime']} (since {d['since']})", c["fg"], None)],
        [("Shell     ", c["yellow"], None), (SHELL, c["fg"], None)],
        [("Stack     ", c["yellow"], None), (STACK, c["fg"], None)],
        [("Merged    ", c["yellow"], None), (f"{d['prs']:,} pull requests", c["fg"], None)],
        [("Commits   ", c["yellow"], None), (f"{d['contribs']:,} contributions this year", c["fg"], None)],
        [("Social    ", c["yellow"], None), (f"{plural(d['followers'], 'follower')}, {plural(d['stars'], 'star')}", c["fg"], None)],
    ]
    swatches = [c[k] for k in ("red", "green", "yellow", "accent", "magenta", "cyan", "fg")]
    for i in range(max(len(ASCII), len(info)) + 1):
        row = []
        if i < len(ASCII):
            row.append((ASCII[i], c["yellow"] if i < 9 else c["dim"], 0))
        if i < len(info):
            first = True
            for text, color, _ in info[i]:
                row.append((text, color, 26 if first else None))
                first = False
        if i == len(info):
            row.append(("swatch", swatches, 26))
        rows.append(row)
    cmd("ls ~/oss --sort=merged-prs")
    pad = max(len(repo) for repo, _, _ in d["top"]) + 2
    for repo, n, s in d["top"]:
        rows.append([
            (f"{n:>4}", c["green"], 0),
            (f"  {repo:<{pad}}", c["accent"], None),
            (f"★ {human(s)}", c["yellow"], None),
        ])
    cmd("echo $MOTTO")
    rows.append([(d["bio"], c["magenta"], 0)])
    rows.append(prompt + [("█", c["fg"], None)])

    width = 820
    height = y0 + lh * len(rows) + 10
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(d["login"])} neofetch">',
        "<style>",
        "text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;"
        "font-size:14px;white-space:pre}",
        ".r{opacity:0;animation:in .25s ease forwards}",
        "@keyframes in{to{opacity:1}}",
        ".cur{animation:blink 1s step-end infinite}",
        "@keyframes blink{50%{opacity:0}}",
        "@media (prefers-reduced-motion:reduce){.r{animation:none;opacity:1}.cur{animation:none}}",
        "</style>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="{c["bg"]}" stroke="{c["border"]}"/>',
        f'<path d="M0.5 36V10.5a10 10 0 0 1 10-10h{width - 21}a10 10 0 0 1 10 10V36z" fill="{c["bar"]}"/>',
        f'<line x1="0.5" y1="36" x2="{width - 0.5}" y2="36" stroke="{c["border"]}"/>',
    ]
    for i, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        out.append(f'<circle cx="{22 + i * 20}" cy="18" r="6" fill="{color}"/>')
    out.append(
        f'<text x="{width / 2}" y="23" fill="{c["dim"]}" text-anchor="middle">'
        f'{escape(d["login"])}@github: ~</text>'
    )
    for i, row in enumerate(rows):
        y = y0 + i * lh
        delay = i * 0.12
        out.append(f'<g class="r" style="animation-delay:{delay:.2f}s">')
        col = 0
        for text, color, at in row:
            if at is not None:
                col = at
            if text == "swatch":
                for j, sw in enumerate(color):
                    out.append(
                        f'<rect x="{x0 + (col + j * 3) * cw:.1f}" y="{y - 12}" '
                        f'width="{cw * 3:.1f}" height="16" fill="{sw}"/>'
                    )
                continue
            cls = ' class="cur"' if text == "█" else ""
            out.append(
                f'<text x="{x0 + col * cw:.1f}" y="{y}" fill="{color}"{cls}>{escape(text)}</text>'
            )
            col += len(text)
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def cmd_terminal(out_dir):
    data = terminal_data()
    os.makedirs(out_dir, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(out_dir, f"terminal-{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render_terminal(data, theme))


def cmd_commit(repo, branch, head, message, *files):
    with open(os.path.join(os.path.dirname(__file__), "..", "api", "createCommitOnBranch.gql")) as f:
        query = f.read()
    additions = []
    for path in files:
        with open(path, "rb") as f:
            additions.append({"path": path, "contents": base64.b64encode(f.read()).decode()})
    json.dump({
        "query": query,
        "variables": {
            "githubRepository": repo,
            "branchName": branch,
            "expectedHeadOid": head,
            "commitMessage": message,
            "files": additions,
        },
    }, sys.stdout)


if __name__ == "__main__":
    {"oss": cmd_oss, "terminal": cmd_terminal, "commit": cmd_commit}[sys.argv[1]](*sys.argv[2:])
