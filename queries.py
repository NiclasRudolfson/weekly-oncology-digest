"""
PubMed RSS feed URLs for the weekly digest.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO CHANGE THE RSS URL (permanent change)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to https://pubmed.ncbi.nlm.nih.gov/
2. Run the search you want (add filters for article types, dates, etc.)
3. Click "Create RSS" directly below the result count
4. Set "Number of items to be sent in each RSS" to 100
5. Click "Create RSS"
6. Copy the feed URL shown (starts with https://pubmed.ncbi.nlm.nih.gov/rss/search/)
7. Replace the URL in RSS_URLS below with the new URL
8. Commit the change — the next scheduled run will use it automatically

You can add multiple feeds (one per major search topic).
Duplicate PMIDs across feeds are removed automatically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO USE A ONE-OFF URL (without editing this file)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Option A — GitHub Actions manual trigger (no code change needed):
  1. Go to your repository on GitHub
  2. Click "Actions" → "Weekly Oncology Digest" → "Run workflow"
  3. Fill in the "RSS feed URL override" field with your new URL
  4. Click "Run workflow"
  This overrides the URL below for that single run only.

Option B — local command line:
  python main.py --rss-url "https://pubmed.ncbi.nlm.nih.gov/rss/search/..."
"""

RSS_URLS = [
    # ── Active feed ───────────────────────────────────────────────────────────
    # Current search: [edit this comment to describe your PubMed search]
    # Generated: [edit this comment with the date you created the feed]
    "https://pubmed.ncbi.nlm.nih.gov/rss/search/1BKD3NT7c-BK2PVxO2hDbLLkJpO6NsOch9fmY_Gw_1wlyz_1TS/?limit=100",

    # ── Add additional feeds below (one per line) ─────────────────────────────
    # "https://pubmed.ncbi.nlm.nih.gov/rss/search/<your-second-feed-id>/?limit=100",
]
