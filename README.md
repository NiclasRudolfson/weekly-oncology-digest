# Weekly Oncology Digest

An automated pipeline that fetches new oncology publications from PubMed twice a week, screens and summarises them with AI, and delivers a formatted HTML email digest to a list of recipients.

---

## How it works

```
PubMed RSS feed(s)
      │
      ▼
1. Fetch          — Download articles via PubMed RSS + efetch API
      │
      ▼
2. Classify       — Gemini Flash screens every article (major interest / minor interest / excluded)
      │
      ▼
3. Report         — Save classification_report.html (uploaded as a GitHub Actions artifact)
      │
      ▼
4. Extract        — Gemini Flash pulls structured clinical data from major-interest articles
      │
      ▼
5. Render & Send  — Build HTML email and deliver via Gmail SMTP
```

### Schedule

The digest runs automatically via GitHub Actions:

| Day       | Time (UTC) | Coverage window |
|-----------|-----------|-----------------|
| Monday    | 07:00     | Thursday – Sunday (4 days) |
| Thursday  | 07:00     | Monday – Wednesday (3 days) |

Articles published on the same day as the digest are always excluded to prevent duplicates.

### Classification rubric

| Decision | Criteria |
|---|---|
| **Major interest** (full summary) | All RCTs (any phase) · Meta-analyses of RCT data · Articles in NEJM / JAMA / Lancet / BMJ · ESMO / ASCO / ESTRO / ASTRO / NCCN / MASCC guidelines · Trial methodology & regulatory science |
| **Minor interest** (title/journal/PMID only) | Single-arm phase I/II trials · Non-RCT meta-analyses · RCT secondary analyses · High-quality observational studies in top journals · Other society guidelines · Reviews · Diagnostic studies · Toxicity studies · European/global epidemiology |
| **Excluded** | No abstract · Editorials/opinion · Case reports · US health policy · Non-oncology · Preclinical basic science · Patient education |

---

## Project structure

```
.
├── main.py                  # Entry point — orchestrates the five-step pipeline
├── config.py                # All runtime config — reads from environment variables / .env
├── queries.py               # PubMed RSS feed URLs (edit here to change the search)
├── requirements.txt         # Python dependencies
│
├── src/
│   ├── fetch.py             # PubMed RSS + efetch download
│   ├── summarize.py         # Gemini classify + extract passes
│   ├── format_email.py      # Renders the HTML digest email
│   ├── format_report.py     # Renders the classification report HTML
│   └── send_email.py        # Gmail SMTP delivery
│
└── .github/
    └── workflows/
        └── weekly_digest.yml  # GitHub Actions workflow
```

---

## Setup

### 1. Required secrets (GitHub → Settings → Secrets and variables → Actions)

| Secret name | What to put there |
|---|---|
| `GEMINI_API_KEY` | Your Google AI Studio API key ([get one here](https://aistudio.google.com/)) |
| `PUBMED_API_KEY` | Your NCBI API key ([register here](https://www.ncbi.nlm.nih.gov/account/)) |
| `SMTP_USER` | The Gmail address used to send (e.g. `digest@gmail.com`) |
| `SMTP_PASSWORD` | A Gmail **App Password** — not your regular password ([create one here](https://myaccount.google.com/apppasswords)) |
| `SENDER_EMAIL` | The "From" address shown in the email (usually same as `SMTP_USER`) |
| `RECIPIENT_EMAILS` | Comma-separated list of recipient addresses |
| `DIGEST_TITLE` | *(Optional)* Email subject prefix — defaults to `Weekly Oncology Research Digest` |

### 2. Local development

```bash
# Clone and install
git clone https://github.com/NiclasRudolfson/weekly-oncology-digest.git
cd weekly-oncology-digest
pip install -r requirements.txt

# Copy and fill in your credentials
cp .env.example .env   # then edit .env with your API keys and email settings

# Test without sending an email
python main.py --dry-run --save-html digest_preview.html
```

---

## Common tasks

### Change the PubMed search

The RSS feed URLs that drive the digest live in **`queries.py`**.

1. Go to [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/) and run your search
2. Click **Create RSS** (below the result count)
3. Set *Number of items* to **100**, then click **Create RSS**
4. Copy the feed URL (starts with `https://pubmed.ncbi.nlm.nih.gov/rss/search/`)
5. Replace the URL in `RSS_URLS` in `queries.py`
6. Commit and push — the next scheduled run picks it up automatically

You can add multiple feeds (one per line); duplicate PMIDs are removed automatically.

### Add or remove recipients

Edit the `RECIPIENT_EMAILS` secret in **GitHub → Settings → Secrets and variables → Actions**. Use a comma-separated list.

### Run manually (one-off)

Go to **GitHub → Actions → Oncology Digest → Run workflow** and fill in the optional fields:

| Field | Purpose |
|---|---|
| *Days back* | Override the automatic date window (useful after a missed run) |
| *RSS feed URL override* | Use a different PubMed search for this run only — no code change needed |
| *Dry run* | Fetch and process but do **not** send the email; preview is still uploaded as an artifact |

### Inspect what the AI included / excluded

After every run (scheduled or manual), GitHub Actions uploads two HTML artifacts:

- **classification_report** — every article the AI saw, with its decision and reason
- **digest_preview** — the rendered email exactly as recipients received it

Go to **Actions → [workflow run] → Artifacts** to download them.

### Adjust the AI models

Model names are set at the top of `config.py`:

```python
CLASSIFY_MODEL = "gemini-2.5-flash-preview"   # high-volume screening pass
EXTRACT_MODEL  = "gemini-2.5-flash-preview"   # structured data extraction pass
```

Both steps use Gemini Flash by default (free tier). Swap either for `gemini-2.5-pro` if you need higher extraction quality. Current model IDs: [ai.google.dev/gemini-api/docs/models](https://ai.google.dev/gemini-api/docs/models)

### Change the email schedule

Edit the two `cron:` lines in `.github/workflows/weekly_digest.yml`:

```yaml
schedule:
  - cron: "0 7 * * 1"   # Monday   07:00 UTC
  - cron: "0 7 * * 4"   # Thursday 07:00 UTC
```

Times are in UTC. Use [crontab.guru](https://crontab.guru/) to build a new expression.

### Modify the classification rubric

The full include/exclude criteria are defined as a prompt string `_CLASSIFY_PROMPT` at the top of **`src/summarize.py`**. Edit the bullet points directly — no structural code changes required.

### Modify what gets extracted

The extraction schema and instructions live in `_EXTRACT_PROMPT` in the same file (`src/summarize.py`). The rendering templates in `src/format_email.py` must match any new fields you add.

---

## Dependencies

| Package | Purpose |
|---|---|
| `google-genai` | Gemini API (classify + extract) |
| `python-dotenv` | Load `.env` for local development |
| `requests` | HTTP calls to PubMed APIs |

See `requirements.txt` for pinned versions.
