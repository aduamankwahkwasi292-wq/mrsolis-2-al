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

The server now serves the frontend itself (at `/`), so there's one app to
deploy — no separate static-site hosting needed.

### Deploy to Render (free, no credit card, recommended)

1. Push this project to a GitHub repo (`.gitignore` already excludes
   `__pycache__` and the local SQLite file).
2. At render.com, **New -> Web Service** -> connect that repo. Render
   reads `render.yaml` automatically and fills in the build/start commands
   (`pip install -r requirements.txt` / `python -m qgen.server`) — just
   click **Create Web Service**.
3. Render gives you a public URL like `https://mrsolis-2-al.onrender.com`.
   Open it directly — that *is* the app, frontend and backend both.

**How updates work**: once connected, every `git push` to your main branch
triggers an automatic redeploy. No manual re-upload, ever:
```powershell
git add .
git commit -m "describe your change"
git push
```
Render rebuilds and swaps in the new version within a minute or two.

**Free tier trade-offs** (fine for a personal/portfolio project, worth
knowing about): the free web service spins down after 15 minutes of
inactivity, so the first request after a quiet period takes ~30-50s to
wake up. Disk is not persistent across redeploys, so the SQLite no-repeat
history (`qgen_store.sqlite3`) resets each time you push an update — the
app still works fine, it just means the "never repeats a question"
guarantee resets on redeploy, not on every request. If either matters to
you, Render's Starter plan ($7/mo) removes both (no sleep, persistent
disk) with the exact same repo — no code changes needed.

### Alternative: Railway or Fly.io

Both work the same way via the included `Dockerfile`:
- **Railway**: New Project -> Deploy from GitHub repo -> it detects the
  Dockerfile automatically. Push-to-deploy works the same as Render.
- **Fly.io**: `fly launch` in the project folder (detects the Dockerfile),
  then `fly deploy` for updates. Requires a credit card even for its
  trial tier, as of this writing.

### Running the Docker image yourself (any VPS)
```bash
docker build -t mrsolis-2-al .
docker run -p 8420:8420 mrsolis-2-al
```
