# MrSOLIS 2-AL — Deterministic Math Engine

Type a math or calculation question you already have. MrSOLIS 2-AL parses
it, generates fresh variations by tweaking numbers/coefficients, and
**recomputes every answer symbolically with sympy** — solved, not guessed.
Zero LLM calls anywhere.

## Setup
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
No spaCy/PPTX/PDF libraries needed — the engine works purely from typed
input now.

## Run
```powershell
python -m qgen.server
```
Open `mrsolis-2-al.html` in your browser.

## What it understands
- **Word problems** with a formula — 26 formulas across electrical,
  mechanics, energy, geometry (circle/sphere/cylinder), waves, and more.
  Can swap which quantity is unknown across variations.
- **Differentiation / Integration** — polynomials, trig, exp, log, sqrt,
  pi — anything sympy handles from a parsed expression.
- **Limits** — direct substitution and 0/0 removable-singularity forms.
- **Equations** — "solve `<expr>` = `<expr>`" for x, linear or quadratic.
- **Proofs** — irrationality of root-p for prime p, via Euclid's lemma.
  Honest about scope: composite radicands get a clear explanation, not a
  fake proof.

## This session's fixes
- **Question-count accuracy**: the TF-IDF near-duplicate filter was
  scoring differently-numbered questions as "near-duplicate" (shared
  template words dominated the similarity score) and silently dropping
  them. Disabled for this pipeline — exact-hash dedup is what actually
  matters for templated output — plus a retry loop that escalates the
  variation search until it hits the requested count or is genuinely
  exhausted.
- **Symbol support**: root, pi, times, divide, squared, cubed now
  normalize into forms sympy parses correctly (this also backs the
  on-screen math keyboard).

## UI
One question at a time, not a scrolling list. Running score shown live.
Optional countdown timer for the whole quiz (set in minutes before
generating) — auto-submits when it hits zero. Solution steps are hidden
during the quiz and only revealed in the post-quiz review screen, per
question. Exit button available mid-quiz (confirms before discarding
progress). A floating Keyboard button opens an on-screen panel with every
symbol the parser actually supports, grouped by operators/powers/
functions/calculus shortcuts, inserting at the cursor position.

## Known limits
Product/quotient/chain rule phrased as prose, implicit differentiation,
and multi-line stacked fractions aren't covered. Irrationality proofs are
scoped to prime radicands (composite square-free numbers need a more
involved exponent-parity argument not yet implemented). Word-problem
formulas need explicit numbers+units and a clear "calculate/find X" ask.
`ingest.py`/`nlp.py` (PPTX/PDF/DOCX + spaCy) ship unused, in case slide-
scanning gets wired back in later — not required for the current flow.

## Hosting it as a web app

**Live now on GitHub Pages:**
https://aduamankwahkwasi292-wq.github.io/mrsolis-2-al/

The whole engine runs **in the visitor's browser** via Pyodide (CPython +
sympy compiled to WebAssembly) — the page boots the engine client-side and
computes everything locally. No server, no cold starts, no sleep, free
hosting forever. The first visit downloads ~20 MB of engine and takes
~10-20s to boot; after that it's cached and instant.

### Updating the live site (one command)

```powershell
# 1. make your changes, then:
git add -A; git commit -m "describe your change"
# 2. ship it:
.\deploy.ps1
```

`deploy.ps1` mirrors `main` onto the `gh-pages` branch (the Pages source),
skipping junk like `__pycache__` and the local SQLite file. The site
updates about a minute later.

If GitHub Actions is available on the account, pushing to `main` also
triggers `.github/workflows/deploy.yml`, which publishes the identical
bundle automatically — the manual script is the fallback/override either
way.

### Local development

```powershell
python -m qgen.server   # serves mrsolis-2-al.html at http://127.0.0.1:8420
```
The page auto-detects this backend via `/health` and uses it instead of
the in-browser engine (same JSON contract both ways). You can also point
any hosted copy at a local engine with the "Engine URL" box in settings.

### Alternative: server-based hosting (Render/Railway/Fly/Docker)

The FastAPI server still works exactly as before — `render.yaml`,
`Dockerfile` and `requirements.txt` are all intact:

- **Render**: New -> Web Service -> connect repo; `render.yaml` fills in
  build/start commands. Free tier sleeps after ~15 min idle.
- **Railway/Fly.io**: deploy from the included `Dockerfile`.
- **Any VPS**: `docker build -t mrsolis-2-al . && docker run -p 8420:8420 mrsolis-2-al`
