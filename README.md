# Weekly Digest

An automated pipeline that fetches new publications from PubMed, screens and summarises them with AI, and delivers a formatted HTML email digest to a list of recipients.

The system supports multiple independent digests (e.g. oncology, haematology) running from the same codebase. Each digest has its own configuration file that controls which articles to include, how they are organised, and who receives the email. Shared code — email design, AI logic, sending infrastructure — is the same for all digests, so a design change automatically applies to every digest.

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

The digest runs automatically via GitHub Actions every Monday at 05:30 UTC (07:30 Stockholm summer time). You can also trigger it manually from the Actions tab at any time.

---

## Managing digests

All configuration for a digest lives in a single TOML file in the `digests/` folder. TOML files are plain text — no coding knowledge is required to read or edit them, and you can edit them directly in the GitHub web interface (click any `.toml` file, then the pencil icon).

### Modifying an existing digest

1. Open the digest's config file, e.g. **`digests/oncology.toml`**, in the GitHub editor
2. Edit the section you want to change (see field descriptions below)
3. Commit the change — the next scheduled run picks it up automatically

### Adding a new digest

Four steps, all doable in the GitHub web interface:

**Step 1 — Create the config file**

Go to `digests/` in the repository, click **Add file → Create new file**, name it `{id}.toml` (e.g. `haematology.toml`), and paste the contents of `oncology.toml` as a starting point. Edit the fields to match your new digest.

**Step 2 — Add the recipient secret**

Go to **Settings → Secrets and variables → Actions → New repository secret**.

Create a secret named whatever you put in `recipient_env_var` in your new TOML (e.g. `HAEMATOLOGY_RECIPIENTS`). The value should be a comma-separated list of email addresses.

**Step 3 — Register the digest in the workflow**

Open **`.github/workflows/weekly_digest.yml`** and find the `matrix.include` section. Add one entry:

```yaml
- digest_id: haematology
  recipient_secret: HAEMATOLOGY_RECIPIENTS
```

**Step 4 — Create the deduplication file**

Create an empty file named **`seen_pmids_haematology.txt`** in the repository root (same folder as `seen_pmids_oncology.txt`). Commit it. The pipeline uses this file to track which articles have already been sent.

That's it. The new digest will run in parallel with the others every Monday.

---

### Config file fields

Every digest config file (`digests/*.toml`) has four sections:

#### `[digest]`

| Field | Description |
|---|---|
| `id` | Short identifier — must match the filename (e.g. `"oncology"` in `oncology.toml`) |
| `title` | Email subject and header title shown in the digest |
| `recipient_env_var` | Name of the GitHub secret holding recipient email addresses |

#### `[feeds]`

| Field | Description |
|---|---|
| `rss_urls` | List of PubMed RSS feed URLs. You can have more than one — duplicate articles are removed automatically. |

**How to get a PubMed RSS URL:**
1. Go to [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/) and run your search
2. Click **Create RSS** (below the result count)
3. Set *Number of items* to **100**, click **Create RSS**, copy the URL

#### `[sections]`

| Field | Description |
|---|---|
| `order` | Ordered list of section names. Controls both the AI classification and the email layout. The **first entry** is the fallback for articles that span multiple topics or can't be assigned to a specific section. |

#### `[prompts]`

| Field | Description |
|---|---|
| `summary_max_words` | Maximum words for the plain-language summary in major-interest articles. Increase for more detail. |
| `rss_journals_html` | HTML listing the journals covered, shown in the email footer. Supports `<em>` tags. |
| `classify_criteria` | The full text of the MAJOR INTEREST / MINOR INTEREST / EXCLUDED rubric. This is injected directly into the AI prompt. Edit the bullet points to change which articles are included and how they are categorised. |

---

## Setup (first time)

### Required secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret name | What to put there |
|---|---|
| `GEMINI_API_KEY` | Your Google AI Studio API key ([get one here](https://aistudio.google.com/)) |
| `PUBMED_API_KEY` | Your NCBI API key ([register here](https://www.ncbi.nlm.nih.gov/account/)) |
| `SMTP_USER` | The Gmail address used to send (e.g. `digest@gmail.com`) |
| `SMTP_PASSWORD` | A Gmail **App Password** — not your regular password ([create one here](https://myaccount.google.com/apppasswords)) |
| `SENDER_EMAIL` | The "From" address shown in the email (usually same as `SMTP_USER`) |
| `RECIPIENT_EMAILS` | Comma-separated list of recipient addresses for the oncology digest |

### Local development

```bash
# Clone and install
git clone https://github.com/NiclasRudolfson/weekly-oncology-digest.git
cd weekly-oncology-digest
pip install -r requirements.txt

# Copy and fill in your credentials
cp .env.example .env   # then edit .env with your API keys and email settings

# Test without sending an email (oncology digest by default)
python main.py --dry-run --save-html digest_preview.html

# Test a specific digest
python main.py --digest oncology --dry-run --save-html preview.html
```

---

## Project structure

```
.
├── main.py                  # Entry point — orchestrates the five-step pipeline
├── config.py                # Shared runtime config — API keys, SMTP settings
├── queries.py               # Legacy: RSS URLs for oncology (still used by oncology.toml)
├── requirements.txt         # Python dependencies
│
├── digests/                 # One config file per digest
│   ├── oncology.toml        # Oncology digest configuration (edit this to change the digest)
│   └── _loader.py           # Reads a .toml file and returns a DigestConfig object
│
├── seen_pmids_oncology.txt  # Tracks sent PMIDs for the oncology digest (auto-updated)
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
        └── weekly_digest.yml  # GitHub Actions workflow (matrix: one job per digest)
```

---

## Common tasks

### Run manually (one-off)

Go to **GitHub → Actions → Weekly Digests → Run workflow** and fill in the optional fields:

| Field | Purpose |
|---|---|
| *Digest* | Which digest to run (leave blank to run all) |
| *RSS feed URL override* | Use a different PubMed search for this run only |
| *Dry run* | Fetch and process but do **not** send the email; preview still uploaded |

### Inspect what the AI included / excluded

After every run (scheduled or manual), GitHub Actions uploads two HTML artifacts per digest:

- **classification-report-{id}** — every article the AI saw, with its decision and reason
- **digest-preview-{id}** — the rendered email exactly as recipients received it

Go to **Actions → [workflow run] → Artifacts** to download them.

### Add or remove recipients

Edit the corresponding GitHub secret (e.g. `RECIPIENT_EMAILS`) in **Settings → Secrets and variables → Actions**. Use a comma-separated list of addresses.

### Change the email schedule

Edit the `cron:` line in `.github/workflows/weekly_digest.yml`:

```yaml
schedule:
  - cron: "30 5 * * 1"   # Monday 05:30 UTC
```

Use [crontab.guru](https://crontab.guru/) to build a new expression. Times are in UTC.

### Adjust the AI models

Model names are set at the top of `config.py`:

```python
CLASSIFY_MODEL = "gemini-2.5-flash-preview"
EXTRACT_MODEL  = "gemini-2.5-flash-preview"
```

Both steps use Gemini Flash by default (free tier). Swap either for `gemini-2.5-pro` if you need higher quality. Current model IDs: [ai.google.dev/gemini-api/docs/models](https://ai.google.dev/gemini-api/docs/models)

---

## Dependencies

| Package | Purpose |
|---|---|
| `google-genai` | Gemini API (classify + extract) |
| `python-dotenv` | Load `.env` for local development |
| `requests` | HTTP calls to PubMed APIs |

`tomllib` (used to read digest config files) is part of the Python standard library since Python 3.11 — no installation needed.

See `requirements.txt` for pinned versions.
