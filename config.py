"""
Central configuration.

All runtime values come from environment variables so that the same code works
locally (via a .env file) and in GitHub Actions (via repository secrets/variables).
See .env.example for the full list of required variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── PubMed ────────────────────────────────────────────────────────────────────

PUBMED_API_KEY  = os.getenv("PUBMED_API_KEY", "")
PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# How many days back to search PubMed.
# The digest runs Monday (4 days = Thu–Sun) and Thursday (3 days = Mon–Wed).
# The workflow auto-computes this from the weekday; override with
# DATE_RANGE_DAYS env var or the --days CLI argument.
DATE_RANGE_DAYS = int(os.getenv("DATE_RANGE_DAYS", "3"))


# ── Gemini models ─────────────────────────────────────────────────────────────
#
# CLASSIFY_MODEL  — used for Step 1: include/exclude screening (high volume,
#                   low complexity → Flash for cost efficiency)
# EXTRACT_MODEL   — used for Step 2: structured data extraction (complex clinical
#                   reasoning → Flash is capable enough; swap for gemini-2.5-pro if needed)
#
# Both models are free within Google AI Studio's free tier limits.
# Find current model IDs at: https://ai.google.dev/gemini-api/docs/models

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLASSIFY_MODEL = "gemini-3-flash-preview"
EXTRACT_MODEL  = "gemini-3-flash-preview"


# ── Email (Gmail SMTP) ────────────────────────────────────────────────────────

SMTP_HOST      = "smtp.gmail.com"
SMTP_PORT      = 587
SMTP_USER      = os.getenv("SMTP_USER")
SMTP_PASSWORD  = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL   = os.getenv("SENDER_EMAIL")
RECIPIENT_EMAILS = [
    e.strip() for e in os.getenv("RECIPIENT_EMAILS", "").split(",") if e.strip()
]

# Subject prefix / email header title
DIGEST_TITLE = os.getenv("DIGEST_TITLE", "Weekly Oncology Research Digest")
