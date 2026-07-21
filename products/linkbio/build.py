#!/usr/bin/env python3
"""Link-in-Bio Kit — build 50 self-contained "bio + links" pages.

Each output is a single .html file with everything inlined (CSS, an emoji
favicon, no JS needed) — no dependencies, no external requests, works offline
and on any static host. Mobile-first, themed, all text HTML-escaped.

    python build.py   ->  sites/<slug>.html  (x50)
"""
from __future__ import annotations

import html
import os
from string import Template

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sites")


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def socials_html(items):
    return "".join(
        f'<a class="soc" href="#" aria-label="{esc(l)}" title="{esc(l)}">{e}</a>'
        for e, l in items
    )


def links_html(items):
    out = []
    for e, label in items:
        out.append(
            f'<a class="link" href="#"><span class="le">{e}</span>'
            f'<span class="lt">{esc(label)}</span><span class="lg">›</span></a>'
        )
    return "".join(out)


PAGE = Template(
    """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$name — ссылки</title>
<meta name="description" content="$meta">
<meta property="og:title" content="$name">
<meta property="og:description" content="$meta">
<meta property="og:type" content="profile">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>$emoji</text></svg>">
<style>
:root{$vars --radius:16px; --maxw:520px}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  background:var(--bg);background-attachment:fixed;color:var(--text);
  display:flex;justify-content:center;padding:44px 18px 30px;-webkit-font-smoothing:antialiased}
.wrap{width:100%;max-width:var(--maxw);text-align:center}
.avatar{width:104px;height:104px;border-radius:50%;margin:0 auto 16px;display:grid;place-items:center;
  font-size:48px;background:var(--av);border:3px solid var(--ring);
  box-shadow:0 8px 30px rgba(0,0,0,.18)}
h1{font-size:1.5rem;margin:0 0 4px;letter-spacing:-.01em;display:flex;gap:6px;justify-content:center;align-items:center}
.badge{color:var(--accent);font-size:1.05rem}
.handle{color:var(--muted);margin:0 0 12px;font-weight:500}
.bio{color:var(--text);opacity:.92;margin:0 auto 22px;max-width:40ch;line-height:1.55}
.socials{display:flex;gap:12px;justify-content:center;margin-bottom:24px;flex-wrap:wrap}
.soc{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;font-size:20px;
  background:var(--soc);color:var(--text);text-decoration:none;transition:.15s;border:1px solid var(--border)}
.soc:hover{transform:translateY(-2px) scale(1.05)}
.links{display:flex;flex-direction:column;gap:14px}
.link{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--btn-text);
  background:var(--btn);border:var(--btn-border);border-radius:14px;padding:16px 18px;font-weight:600;
  box-shadow:0 4px 16px rgba(0,0,0,.10);transition:.15s;
  animation:rise .5s both}
.link:hover{transform:translateY(-2px);filter:brightness(1.03)}
.link .le{font-size:1.25rem;width:26px;text-align:center}
.link .lt{flex:1;text-align:center}
.link .lg{opacity:.5;font-size:1.2rem}
.links .link:nth-child(1){animation-delay:.05s}
.links .link:nth-child(2){animation-delay:.10s}
.links .link:nth-child(3){animation-delay:.15s}
.links .link:nth-child(4){animation-delay:.20s}
.links .link:nth-child(5){animation-delay:.25s}
.links .link:nth-child(6){animation-delay:.30s}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
footer{margin-top:30px;color:var(--muted);font-size:.82rem}
footer a{color:var(--muted)}
@media (prefers-reduced-motion:reduce){.link{animation:none}}
</style>
</head>
<body>
<main class="wrap">
  <div class="avatar">$emoji</div>
  <h1>$name $badge</h1>
  <p class="handle">$handle</p>
  <p class="bio">$bio</p>
  <div class="socials">$socials</div>
  <nav class="links">$links</nav>
  <footer>© $year $name</footer>
</main>
</body>
</html>
"""
)


def render(cfg: dict) -> str:
    badge = '<span class="badge" title="Verified">✔</span>' if cfg.get("verified") else ""
    return PAGE.substitute(
        name=esc(cfg["name"]),
        meta=esc(cfg["bio"]),
        emoji=cfg["emoji"],
        handle=esc(cfg["handle"]),
        bio=esc(cfg["bio"]),
        badge=badge,
        socials=socials_html(cfg["socials"]),
        links=links_html(cfg["links"]),
        vars=cfg["vars"],
        year="2026",
    )


def main():
    from configs import CONFIGS

    os.makedirs(OUT, exist_ok=True)
    for cfg in CONFIGS:
        with open(os.path.join(OUT, f"{cfg['slug']}.html"), "w", encoding="utf-8") as fh:
            fh.write(render(cfg))
    print(f"wrote {len(CONFIGS)} pages")


if __name__ == "__main__":
    main()
