"""
Render the extracted digest records into a clean HTML email.

All CSS is inline — required for reliable rendering across email clients
(Gmail, Outlook, Apple Mail, etc.).

Layout:
  - Pure white page background; each section is its own warm-cream card.
  - 12 fixed oncology sections (amber serif heading), ordered:
      General Oncology → subspecialties A–Z → Methodological Issues
  - All major-interest articles rendered with:
      serif title (15 px) → meta line → summary paragraph
  - A final "Also published in the past week" card lists minor-interest articles
    as plain one-liners: Journal — Title — PMID (no extraction required).
"""

from datetime import datetime, timedelta


# ── Colour palette (warm / editorial) ─────────────────────────────────────────
BG      = "#FFFFFF"   # pure white – page background between cards
CARD    = "#FAF8F4"   # very light warm cream – section card backgrounds
TEXT    = "#1C1917"   # warm charcoal – all primary text
MUTED   = "#78716C"   # warm medium gray – meta lines, sub-labels
BORDER  = "#E2D9CE"   # warm light border – dividers between articles
AMBER   = "#92400E"   # amber-brown – section headings, PMID links, heading rule

# Font stacks
SERIF = "Georgia, 'Times New Roman', serif"
SANS  = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', "
         "Helvetica, Arial, sans-serif")


# ── Section ordering ──────────────────────────────────────────────────────────
SECTION_ORDER = [
    "General Oncology",
    "Breast Oncology",
    "CNS Oncology",
    "Gastrointestinal Oncology",
    "Gynaecological Oncology",
    "Haematological Oncology",
    "Head & Neck Oncology",
    "Melanoma & Skin Oncology",
    "Radiation Oncology",
    "Thoracic Oncology",
    "Urological Oncology",
    "Methodological Issues",
]

FULL_BLOCK_TYPES = {"Phase III", "Phase II", "Phase I", "Phase I/II",
                    "Guideline", "Systematic review",
                    "Literature review", "Statistical methodology"}


# ── Helpers ───────────────────────────────────────────────────────────────────

# Words that stay lowercase in title case (unless first or last in string)
_LOWERCASE_WORDS = frozenset({
    "a", "an", "the",
    "and", "or", "but", "nor", "so", "yet",
    "as", "if",
    "at", "by", "for", "in", "of", "on", "to", "up", "via", "per",
})


def _title_case(s: str) -> str:
    """
    Title-case a string following standard rules:
    - Always capitalise the first and last word.
    - Keep short articles, prepositions, and conjunctions lowercase.
    - Preserve all-caps abbreviations ≤ 6 characters (JAMA, JCO, NEJM …).
    """
    words = s.split()
    if not words:
        return s
    result = []
    for i, word in enumerate(words):
        if word.isupper() and len(word) <= 6:          # preserve abbreviations
            result.append(word)
        elif i == 0 or i == len(words) - 1:            # first / last always caps
            result.append(word.capitalize())
        elif word.lower() in _LOWERCASE_WORDS:         # function words stay lower
            result.append(word.lower())
        else:
            result.append(word.capitalize())
    return " ".join(result)


# ── Article renderers ─────────────────────────────────────────────────────────

def _full_article_block(rec: dict, is_last: bool = False) -> str:
    """
    Phase III / Guideline / Review / Methodology:
      serif title → meta line → summary paragraph.
    """
    title   = rec.get("title", "")
    pmid    = rec.get("pmid", "")
    link    = rec.get("link", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
    journal = _title_case(rec.get("journal", ""))
    stype   = rec.get("study_type", "")
    nou     = rec.get("new_or_update", "")
    summary = rec.get("summary", "")

    meta_parts = []
    if pmid:
        meta_parts.append(
            f'PMID:&nbsp;<a href="{link}" target="_blank"'
            f' style="color:{AMBER};text-decoration:none;">{pmid}</a>'
        )
    if journal:
        meta_parts.append(f"<em>{journal}</em>")
    if stype:
        meta_parts.append(stype)
    if nou:
        meta_parts.append(nou)
    meta_line = " &nbsp;&middot;&nbsp; ".join(meta_parts)

    divider = "" if is_last else f"border-bottom:1px solid {BORDER};"

    return f"""
    <div style="margin:0 0 26px 0;padding:0 0 26px 0;{divider}">
      <h4 style="margin:0 0 7px 0;font-size:15px;font-weight:700;
                 color:{TEXT};line-height:1.4;font-family:{SERIF};">{title}</h4>
      <p style="margin:0 0 9px 0;font-size:12px;color:{MUTED};line-height:1.5;
                font-family:{SANS};">{meta_line}</p>
      <p style="margin:0;font-size:14px;color:{TEXT};line-height:1.72;
                font-family:{SANS};">{summary}</p>
    </div>"""


def _minor_article_row(a: dict) -> str:
    """Single one-liner for a minor-interest article: Journal — Title — PMID."""
    title   = a.get("title", "")
    pmid    = a.get("pmid", "")
    url     = a.get("pubmed_url", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
    journal = _title_case(a.get("journal", "").split(":")[0].strip())

    pmid_link = (
        f' &nbsp;&mdash;&nbsp; <a href="{url}" target="_blank"'
        f' style="color:{AMBER};text-decoration:none;">PMID&nbsp;{pmid}</a>'
    ) if pmid else ""

    return f"""
    <div style="margin:0 0 10px 0;">
      <p style="margin:0;font-size:13px;color:{TEXT};line-height:1.7;
                font-family:{SANS};">
        <span style="color:{MUTED};"><em>{journal}</em></span>
        &nbsp;&mdash;&nbsp;{title}{pmid_link}
      </p>
    </div>"""


def _section_block(section_name: str,
                   records: list[dict],
                   minor_records: list[dict] | None = None) -> str:
    """
    One section as a cream card table-row, followed by a white spacer row.

    major-interest articles are rendered as full blocks with summaries.
    minor-interest articles for the same section follow under an italic
    'Also published in the past week' sub-heading.
    """
    minor_records = minor_records or []

    full_blocks = []
    for i, r in enumerate(records):
        is_last = (i == len(records) - 1) and not minor_records
        full_blocks.append(_full_article_block(r, is_last=is_last))

    minor_html = ""
    if minor_records:
        minor_rows = "".join(
            _minor_article_row(a) for a in minor_records
        )
        top_margin = "24px" if records else "0"
        minor_html = f"""
    <p style="margin:{top_margin} 0 14px 0;font-size:14px;font-weight:600;
              font-style:italic;color:{AMBER};font-family:{SERIF};">
      Non-randomized, observational, literature reviews
    </p>
    {minor_rows}"""

    return f"""
    <tr>
      <td style="background:{CARD};border-radius:8px;padding:28px 36px 4px 36px;
                 box-shadow:0 2px 10px rgba(0,0,0,0.06);">
        <h2 style="margin:0 0 6px 0;padding:0 0 12px 0;
                   font-size:20px;font-weight:700;color:{AMBER};
                   font-family:{SERIF};line-height:1.2;
                   border-bottom:2px solid {AMBER};">
          {section_name}
        </h2>
        <div style="height:20px;"></div>
        {"".join(full_blocks)}{minor_html}
      </td>
    </tr>
    <tr><td style="height:12px;"></td></tr>"""


# ── Static journal list (derived from the PubMed RSS search string) ───────────
# Alphabetical order; kept as abbreviations matching PubMed shorthand.
_RSS_JOURNALS = (
    "<em>Ann Intern Med</em>, <em>Ann Oncol</em>, <em>BMJ</em>, "
    "<em>CA Cancer J Clin</em>, <em>J Clin Oncol</em>, "
    "<em>J Natl Compr Canc Netw</em>, <em>JAMA</em>, "
    "<em>JAMA Intern Med</em>, <em>JAMA Netw Open</em>, <em>JAMA Oncol</em>, "
    "<em>Lancet</em>, <em>Lancet Oncol</em>, <em>N Engl J Med</em>, "
    "<em>Nat Med</em>, <em>Nat Rev Clin Oncol</em>, <em>PLoS Med</em>"
)


# ── Public interface ──────────────────────────────────────────────────────────

def render_html(extracted: list[dict], minor_interest: list[dict],
                title: str, days: int = 7) -> str:
    """
    Render the full HTML email from extracted records and minor-interest articles.

    Args:
        extracted:       Structured dicts from summarize.extract_structured_data()
                         (major-interest articles, shown with full summaries).
        minor_interest:  Raw article dicts for minor-interest articles, shown as
                         plain title / journal / PMID one-liners.
        title:           Email / digest title string (from config.DIGEST_TITLE).
        days:            Date window used for the PubMed search (default 7).
                         Used to compute and display the covered date range.

    Returns:
        Complete HTML string ready to send as an email.
    """
    today_dt  = datetime.now()
    from_dt   = today_dt - timedelta(days=days)
    today_str = today_dt.strftime("%B %d, %Y")

    # Eyebrow date range: "March 6–13, 2026" or "Feb 27 – Mar 6, 2026"
    if from_dt.month == today_dt.month:
        date_range = (
            f"{from_dt.strftime('%B %-d')}"
            f"–{today_dt.strftime('%-d, %Y')}"
        )
    else:
        date_range = (
            f"{from_dt.strftime('%B %-d')}"
            f" – {today_dt.strftime('%B %-d, %Y')}"
        )

    # Group major-interest extracted records by section
    by_section: dict[str, list] = {s: [] for s in SECTION_ORDER}
    for rec in extracted:
        sec = rec.get("section", "General Oncology")
        if sec not in by_section:
            sec = "General Oncology"
        by_section[sec].append(rec)

    # Group minor-interest raw article dicts by section (assigned by classifier)
    minor_by_section: dict[str, list] = {s: [] for s in SECTION_ORDER}
    for a in minor_interest:
        sec = a.get("section", "General Oncology")
        if sec not in minor_by_section:
            sec = "General Oncology"
        minor_by_section[sec].append(a)

    sections_html = ""
    article_count = len(extracted) + len(minor_interest)
    for section_name in SECTION_ORDER:
        major_recs = by_section[section_name]
        minor_recs = minor_by_section[section_name]
        if major_recs or minor_recs:
            sections_html += _section_block(section_name, major_recs, minor_recs)

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:{BG};font-family:{SANS};color:{TEXT};">

  <!-- Outer wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{BG};">
  <tr><td align="center" style="padding:32px 16px 24px 16px;">

  <!-- Content column (max 700 px) -->
  <table width="700" cellpadding="0" cellspacing="0"
         style="max-width:700px;width:100%;border-collapse:separate;border-spacing:0;">

    <!-- Header card -->
    <tr>
      <td style="background:{CARD};border-radius:8px;padding:36px 40px 28px 40px;
                 box-shadow:0 2px 10px rgba(0,0,0,0.06);">
        <p style="margin:0 0 10px 0;font-size:11px;font-weight:700;color:{MUTED};
                  text-transform:uppercase;letter-spacing:2px;font-family:{SANS};">
          Published on PubMed &middot; {date_range}
        </p>
        <h1 style="margin:0 0 12px 0;font-size:30px;font-weight:700;
                   color:{TEXT};line-height:1.15;font-family:{SERIF};">{title}</h1>
        <p style="margin:0;font-size:13px;color:{MUTED};font-family:{SANS};">
          {today_str} &nbsp;&middot;&nbsp; {article_count} articles
        </p>
      </td>
    </tr>
    <tr><td style="height:12px;"></td></tr>

    <!-- Section cards -->
    {sections_html}

    <!-- Footer -->
    <tr>
      <td style="padding:8px 4px 32px 4px;text-align:center;">
        <p style="margin:0 0 4px 0;font-size:11px;color:{MUTED};
                  line-height:1.7;font-family:{SANS};">
          Created by Niclas Falklind with assist by Claude and Gemini.
        </p>
        <p style="margin:0 0 4px 0;font-size:11px;color:{MUTED};
                  line-height:1.7;font-family:{SANS};">
          Articles sourced from {_RSS_JOURNALS}.
        </p>
        <p style="margin:0 0 4px 0;font-size:11px;color:{MUTED};
                  font-style:italic;font-family:{SANS};">
          Always verify findings against primary sources.
        </p>
        <p style="margin:0;font-size:11px;color:{MUTED};
                  font-style:italic;font-family:{SANS};">
          For personal, non-commercial use only.
        </p>
      </td>
    </tr>

  </table>

  </td></tr>
  </table>

</body>
</html>"""
