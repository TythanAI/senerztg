#!/usr/bin/env python3
"""OnePage Kit — build 10 self-contained one-page website templates.

Each output is a single .html file with everything inlined (CSS + a few lines of
vanilla JS, a system-font stack, an emoji favicon as a data URI). No build step,
no dependencies, no external requests — open it in any browser or drop it on any
static host. Responsive, light/dark aware, SEO/OpenGraph meta included.

    python build.py      ->  sites/<slug>.html  (x10)
"""
from __future__ import annotations

import html
import os
from string import Template

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sites")


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


# --------------------------- fragment renderers ---------------------------
def nav_html(items):
    return "".join(f'<a href="{esc(h)}">{esc(t)}</a>' for t, h in items)


def stats_html(items):
    return "".join(
        f'<div class="stat"><div class="stat-n">{esc(n)}</div>'
        f'<div class="stat-l">{esc(l)}</div></div>'
        for n, l in items
    )


def features_html(items):
    return "".join(
        f'<article class="card"><div class="ico">{esc(e)}</div>'
        f'<h3>{esc(t)}</h3><p>{esc(d)}</p></article>'
        for e, t, d in items
    )


def steps_html(items):
    out = []
    for i, (t, d) in enumerate(items, 1):
        out.append(
            f'<li class="step"><span class="step-n">{i}</span>'
            f'<div><h4>{esc(t)}</h4><p>{esc(d)}</p></div></li>'
        )
    return "".join(out)


def pricing_html(items):
    out = []
    for name, price, period, feats, hot, cta in items:
        badge = '<span class="badge">Популярный</span>' if hot else ""
        feat_li = "".join(f"<li>{esc(f)}</li>" for f in feats)
        out.append(
            f'<div class="plan{" hot" if hot else ""}">{badge}'
            f'<h3>{esc(name)}</h3>'
            f'<div class="price">{esc(price)}<span>{esc(period)}</span></div>'
            f'<ul>{feat_li}</ul>'
            f'<a class="btn {"btn-primary" if hot else "btn-outline"}" href="#contact">{esc(cta)}</a>'
            f"</div>"
        )
    return "".join(out)


def faq_html(items):
    return "".join(
        f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>"
        for q, a in items
    )


# ------------------------------ page template ------------------------------
PAGE = Template(
    """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<meta name="description" content="$meta">
<meta property="og:title" content="$title">
<meta property="og:description" content="$meta">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>$emoji</text></svg>">
<style>
:root{
  --accent:$accent; --accent-2:$accent2;
  --bg:#ffffff; --bg-soft:#f6f7fb; --card:#ffffff; --border:#e6e8ef;
  --text:#12141a; --muted:#5b6172; --shadow:0 10px 30px rgba(20,22,40,.08);
  --radius:16px; --maxw:1120px;
}
@media (prefers-color-scheme:dark){
  :root{--bg:#0d0f16;--bg-soft:#12151f;--card:#151926;--border:#232838;
        --text:#eef1f7;--muted:#a3abbd;--shadow:0 10px 30px rgba(0,0,0,.35);}
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
img{max-width:100%}
.container{max-width:var(--maxw);margin:0 auto;padding:0 20px}
.btn{display:inline-block;padding:12px 22px;border-radius:12px;font-weight:600;
  cursor:pointer;transition:.15s;border:1px solid transparent;white-space:nowrap}
.btn-primary{background:linear-gradient(135deg,var(--accent),var(--accent-2));color:#fff;box-shadow:var(--shadow)}
.btn-primary:hover{filter:brightness(1.06);transform:translateY(-1px)}
.btn-outline{border-color:var(--border);background:var(--card)}
.btn-outline:hover{border-color:var(--accent)}
.btn-ghost{background:transparent}
/* header */
header{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--border)}
.nav{display:flex;align-items:center;justify-content:space-between;height:66px;gap:16px}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:1.15rem}
.brand .logo{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;
  background:linear-gradient(135deg,var(--accent),var(--accent-2));color:#fff;font-size:18px}
.nav .links{display:flex;gap:22px;align-items:center}
.nav .links a{color:var(--muted);font-weight:500}
.nav .links a:hover{color:var(--text)}
.nav-cta{display:flex;gap:10px;align-items:center}
#burger{display:none;background:none;border:0;font-size:26px;color:var(--text);cursor:pointer}
/* hero */
.hero{position:relative;overflow:hidden}
.hero::before{content:"";position:absolute;inset:0;z-index:-1;
  background:radial-gradient(60% 60% at 75% 10%,color-mix(in srgb,var(--accent) 22%,transparent),transparent 70%)}
.hero .container{display:grid;grid-template-columns:1.1fr .9fr;gap:40px;align-items:center;
  padding-top:70px;padding-bottom:70px}
.eyebrow{display:inline-block;font-weight:600;color:var(--accent);
  background:color-mix(in srgb,var(--accent) 14%,transparent);padding:6px 12px;border-radius:999px;font-size:.85rem}
.hero h1{font-size:clamp(2rem,4.5vw,3.4rem);line-height:1.08;margin:16px 0 12px;letter-spacing:-.02em}
.hero p.sub{font-size:1.15rem;color:var(--muted);max-width:34ch}
.hero .cta{display:flex;gap:12px;flex-wrap:wrap;margin-top:26px}
.mock{aspect-ratio:4/3;border-radius:22px;border:1px solid var(--border);background:var(--card);
  box-shadow:var(--shadow);position:relative;overflow:hidden}
.mock::before{content:"";position:absolute;inset:0;background:
  linear-gradient(135deg,color-mix(in srgb,var(--accent) 30%,transparent),color-mix(in srgb,var(--accent-2) 30%,transparent))}
.mock .glyph{position:absolute;inset:0;display:grid;place-items:center;font-size:5rem;filter:saturate(1.1)}
/* generic section */
section{padding:74px 0}
.section-head{max-width:640px;margin:0 auto 44px;text-align:center}
.section-head h2{font-size:clamp(1.6rem,3vw,2.3rem);margin:0 0 10px;letter-spacing:-.02em}
.section-head p{color:var(--muted);margin:0}
/* stats */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:18px;
  background:var(--bg-soft);border:1px solid var(--border);border-radius:var(--radius);padding:26px}
.stat{text-align:center}
.stat-n{font-size:2rem;font-weight:800;color:var(--accent)}
.stat-l{color:var(--muted);font-size:.95rem}
/* cards grid */
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:26px;box-shadow:var(--shadow);transition:.15s}
.card:hover{transform:translateY(-3px)}
.card .ico{font-size:1.8rem;margin-bottom:10px}
.card h3{margin:0 0 6px;font-size:1.15rem}
.card p{margin:0;color:var(--muted)}
/* steps */
.steps{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:22px}
.step{display:flex;gap:14px;align-items:flex-start}
.step-n{flex:0 0 auto;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;
  font-weight:700;color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent-2))}
.step h4{margin:2px 0 4px}
.step p{margin:0;color:var(--muted)}
/* pricing */
.pricing{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px;align-items:start}
.plan{position:relative;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:28px;box-shadow:var(--shadow)}
.plan.hot{border-color:var(--accent);transform:scale(1.03)}
.plan .badge{position:absolute;top:-12px;left:50%;transform:translateX(-50%);
  background:var(--accent);color:#fff;font-size:.75rem;font-weight:700;padding:4px 12px;border-radius:999px}
.plan h3{margin:0 0 8px}
.plan .price{font-size:2.2rem;font-weight:800}
.plan .price span{font-size:1rem;font-weight:500;color:var(--muted)}
.plan ul{list-style:none;padding:0;margin:16px 0 22px}
.plan li{padding:7px 0 7px 26px;position:relative;color:var(--muted)}
.plan li::before{content:"✓";position:absolute;left:0;color:var(--accent);font-weight:700}
.plan .btn{width:100%;text-align:center}
/* testimonial */
.quote{max-width:760px;margin:0 auto;text-align:center}
.quote blockquote{font-size:1.5rem;line-height:1.4;margin:0 0 18px;letter-spacing:-.01em}
.quote .who{color:var(--muted)}
/* faq */
.faq{max-width:760px;margin:0 auto}
details{border:1px solid var(--border);border-radius:12px;padding:4px 18px;margin-bottom:12px;background:var(--card)}
summary{cursor:pointer;font-weight:600;padding:14px 0;list-style:none}
summary::-webkit-details-marker{display:none}
summary::after{content:"+";float:right;color:var(--accent);font-weight:700}
details[open] summary::after{content:"–"}
details p{margin:0 0 14px;color:var(--muted)}
/* cta band */
.cta-band{background:linear-gradient(135deg,var(--accent),var(--accent-2));color:#fff;
  border-radius:24px;padding:52px 30px;text-align:center;box-shadow:var(--shadow)}
.cta-band h2{font-size:clamp(1.6rem,3vw,2.3rem);margin:0 0 10px}
.cta-band p{margin:0 0 22px;opacity:.92}
.cta-band .btn{background:#fff;color:var(--text)}
/* footer */
footer{border-top:1px solid var(--border);padding:40px 0;color:var(--muted)}
.foot{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;align-items:center}
.foot a{color:var(--muted)}.foot a:hover{color:var(--text)}
/* responsive */
@media(max-width:820px){
  .hero .container{grid-template-columns:1fr;padding-top:44px}
  .mock{order:-1}
  .nav .links{display:none;position:absolute;top:66px;left:0;right:0;flex-direction:column;
    background:var(--bg);border-bottom:1px solid var(--border);padding:14px 20px;gap:14px}
  .nav .links.open{display:flex}
  #burger{display:block}
  .plan.hot{transform:none}
}
</style>
</head>
<body>
<header>
  <div class="container nav">
    <a class="brand" href="#"><span class="logo">$emoji</span>$brand</a>
    <nav class="links" id="menu">$nav</nav>
    <div class="nav-cta">
      <a class="btn btn-primary" href="#contact">$cta1</a>
      <button id="burger" aria-label="Меню">☰</button>
    </div>
  </div>
</header>

<main>
  <section class="hero">
    <div class="container">
      <div>
        <span class="eyebrow">$eyebrow</span>
        <h1>$h1</h1>
        <p class="sub">$sub</p>
        <div class="cta">
          <a class="btn btn-primary" href="#pricing">$cta1</a>
          <a class="btn btn-outline" href="#features">$cta2</a>
        </div>
      </div>
      <div class="mock"><div class="glyph">$emoji</div></div>
    </div>
  </section>

  <section style="padding-top:0">
    <div class="container"><div class="stats">$stats</div></div>
  </section>

  <section id="features">
    <div class="container">
      <div class="section-head"><h2>$features_title</h2><p>$features_sub</p></div>
      <div class="grid">$features</div>
    </div>
  </section>

  <section id="how" style="background:var(--bg-soft)">
    <div class="container">
      <div class="section-head"><h2>$steps_title</h2></div>
      <ol class="steps">$steps</ol>
    </div>
  </section>

  <section id="pricing">
    <div class="container">
      <div class="section-head"><h2>$pricing_title</h2><p>$pricing_sub</p></div>
      <div class="pricing">$pricing</div>
    </div>
  </section>

  <section style="background:var(--bg-soft)">
    <div class="container quote">
      <blockquote>“$quote”</blockquote>
      <div class="who">$quote_who</div>
    </div>
  </section>

  <section id="faq">
    <div class="container">
      <div class="section-head"><h2>$faq_title</h2></div>
      <div class="faq">$faq</div>
    </div>
  </section>

  <section id="contact">
    <div class="container">
      <div class="cta-band">
        <h2>$cta_title</h2>
        <p>$cta_sub</p>
        <a class="btn" href="mailto:$contact">$cta_btn</a>
      </div>
    </div>
  </section>
</main>

<footer>
  <div class="container foot">
    <div class="brand"><span class="logo">$emoji</span>$brand</div>
    <div>$footer_note</div>
    <div>© $year $brand</div>
  </div>
</footer>

<script>
  // Mobile menu toggle (the only JS on the page).
  var b=document.getElementById('burger'),m=document.getElementById('menu');
  if(b&&m){b.addEventListener('click',function(){m.classList.toggle('open');});
    m.addEventListener('click',function(e){if(e.target.tagName==='A')m.classList.remove('open');});}
</script>
</body>
</html>
"""
)


def render(cfg: dict) -> str:
    return PAGE.substitute(
        title=esc(cfg["title"]),
        meta=esc(cfg["meta"]),
        emoji=cfg["emoji"],
        brand=esc(cfg["brand"]),
        accent=cfg["accent"],
        accent2=cfg["accent2"],
        nav=nav_html(cfg["nav"]),
        eyebrow=esc(cfg["eyebrow"]),
        h1=esc(cfg["h1"]),
        sub=esc(cfg["sub"]),
        cta1=esc(cfg["cta1"]),
        cta2=esc(cfg["cta2"]),
        stats=stats_html(cfg["stats"]),
        features_title=esc(cfg["features_title"]),
        features_sub=esc(cfg["features_sub"]),
        features=features_html(cfg["features"]),
        steps_title=esc(cfg["steps_title"]),
        steps=steps_html(cfg["steps"]),
        pricing_title=esc(cfg["pricing_title"]),
        pricing_sub=esc(cfg["pricing_sub"]),
        pricing=pricing_html(cfg["pricing"]),
        quote=esc(cfg["quote"]),
        quote_who=esc(cfg["quote_who"]),
        faq_title=esc(cfg["faq_title"]),
        faq=faq_html(cfg["faq"]),
        cta_title=esc(cfg["cta_title"]),
        cta_sub=esc(cfg["cta_sub"]),
        cta_btn=esc(cfg["cta_btn"]),
        contact=esc(cfg["contact"]),
        footer_note=esc(cfg["footer_note"]),
        year="2026",
    )


def main():
    from configs import CONFIGS  # local module with the 10 template configs

    os.makedirs(OUT, exist_ok=True)
    for cfg in CONFIGS:
        path = os.path.join(OUT, f"{cfg['slug']}.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render(cfg))
        print("wrote", path)
    print(f"total: {len(CONFIGS)} templates")


if __name__ == "__main__":
    main()
