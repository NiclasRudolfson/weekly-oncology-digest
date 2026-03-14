"""
Render a classification report as a standalone HTML file.

This is uploaded as a GitHub Actions artifact after every run so you can
inspect exactly which articles were included or excluded, and why.

To view it:
  GitHub → your repository → Actions → (select the run) → Artifacts
  → download "classification-report" → open classification_report.html

The report shows:
  - Run metadata (date, date window, article counts)
  - All INCLUDED articles (green) with their classification reason
  - All EXCLUDED articles (grey) with their classification reason
"""

from datetime import datetime


# ── Colour palette ────────────────────────────────────────────────────────────
NAVY   = "#1b4f72"
BLUE   = "#2980b9"
BG     = "#f0f4f8"
WHITE  = "#ffffff"
TEXT   = "#1a2b3c"
MUTED  = "#5d7a8a"
BORDER = "#dce9f0"

MAJ_BG     = "#d4edda"
MAJ_TEXT   = "#1a6630"
MAJ_BORDER = "#27ae60"
MIN_BG     = "#dbeafe"
MIN_TEXT   = "#1e40af"
MIN_BORDER = "#3b82f6"
EXC_BG     = "#f5f5f5"
EXC_TEXT   = "#555555"
EXC_BORDER = "#bdc3c7"


def render_report(classified: list[dict], days: int, rss_urls: list[str]) -> str:
    """
    Render an HTML classification report.

    Args:
        classified:  All article dicts from summarize.classify_articles(),
                     each carrying 'status', 'reason', 'title', 'pmid',
                     'pubmed_url', 'journal', and 'pub_date' fields.
        days:        The date window used for this run.
        rss_urls:    The RSS feed URL(s) used for this run.

    Returns:
        Complete HTML string ready to write to classification_report.html.
    """
    now = datetime.now()
    run_date = now.strftime("%B %d, %Y at %H:%M UTC")

    major    = [a for a in classified if a.get("status") == "major_interest"]
    minor    = [a for a in classified if a.get("status") == "minor_interest"]
    excluded = [a for a in classified if a.get("status") == "excluded"]

    # ── Summary badges ────────────────────────────────────────────────────────
    badges = (
        f'<span style="display:inline-block;padding:4px 12px;border-radius:99px;'
        f'font-size:13px;font-weight:600;background:{NAVY};color:#fff;margin-right:8px;">'
        f'{len(classified)} total</span>'
        f'<span style="display:inline-block;padding:4px 12px;border-radius:99px;'
        f'font-size:13px;font-weight:600;background:{MAJ_BG};color:{MAJ_TEXT};margin-right:8px;">'
        f'★ {len(major)} major</span>'
        f'<span style="display:inline-block;padding:4px 12px;border-radius:99px;'
        f'font-size:13px;font-weight:600;background:{MIN_BG};color:{MIN_TEXT};margin-right:8px;">'
        f'◆ {len(minor)} minor</span>'
        f'<span style="display:inline-block;padding:4px 12px;border-radius:99px;'
        f'font-size:13px;font-weight:600;background:{EXC_BG};color:{EXC_TEXT};">'
        f'✗ {len(excluded)} excluded</span>'
    )

    # ── RSS URLs ──────────────────────────────────────────────────────────────
    rss_html = "".join(
        f'<div style="font-size:12px;font-family:monospace;'
        f'color:{MUTED};word-break:break-all;margin-bottom:2px;">{url}</div>'
        for url in rss_urls
    )

    # ── Article rows ──────────────────────────────────────────────────────────
    def _row(a: dict) -> str:
        status = a.get("status", "excluded")
        if status == "major_interest":
            border, bg, label, l_color, l_bg = MAJ_BORDER, MAJ_BG, "MAJOR",  MAJ_TEXT, MAJ_BG
        elif status == "minor_interest":
            border, bg, label, l_color, l_bg = MIN_BORDER, MIN_BG, "MINOR",  MIN_TEXT, MIN_BG
        else:
            border, bg, label, l_color, l_bg = EXC_BORDER, EXC_BG, "EXCLUDED", EXC_TEXT, "#e8e8e8"

        pmid    = a.get("pmid", "")
        url     = a.get("pubmed_url", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
        title   = a.get("title", "")
        journal = a.get("journal", "")
        date    = a.get("pub_date", "")
        reason  = a.get("reason", "")

        meta_parts = []
        if journal: meta_parts.append(f"<em>{journal}</em>")
        if date:    meta_parts.append(date)
        if pmid:    meta_parts.append(
            f'<a href="{url}" target="_blank"'
            f' style="color:{BLUE};text-decoration:none;">PMID {pmid}</a>'
        )
        meta = " &nbsp;·&nbsp; ".join(meta_parts)

        return f"""
    <tr style="border-left:4px solid {border};background:{bg};">
      <td style="padding:12px 16px;vertical-align:top;">
        <span style="display:inline-block;padding:2px 8px;border-radius:4px;
                     font-size:11px;font-weight:700;color:{l_color};
                     background:{l_bg};letter-spacing:0.4px;margin-bottom:6px;">
          {label}
        </span>
        <div style="font-size:14px;font-weight:600;color:{TEXT};
                    line-height:1.4;margin-bottom:4px;">{title}</div>
        <div style="font-size:12px;color:{MUTED};">{meta}</div>
      </td>
      <td style="padding:12px 16px;vertical-align:top;width:200px;">
        <span style="font-size:12px;color:{MUTED};font-style:italic;">{reason}</span>
      </td>
    </tr>"""

    maj_rows = "".join(_row(a) for a in major)
    min_rows = "".join(_row(a) for a in minor)
    exc_rows = "".join(_row(a) for a in excluded)

    def _section_table(heading: str, rows_html: str, count: int) -> str:
        if not count:
            return (
                f'<h2 style="font-size:14px;color:{NAVY};margin:32px 0 8px;">'
                f'{heading} (0)</h2>'
                f'<p style="color:{MUTED};font-size:13px;">None.</p>'
            )
        return f"""
  <h2 style="font-size:14px;font-weight:700;color:{NAVY};
             border-bottom:2px solid {BORDER};padding-bottom:6px;
             margin:32px 0 16px;text-transform:uppercase;letter-spacing:0.5px;">
    {heading} ({count})
  </h2>
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
      <tr style="background:{NAVY};color:#fff;">
        <th style="padding:10px 16px;text-align:left;font-size:11px;
                   text-transform:uppercase;letter-spacing:0.4px;">Article</th>
        <th style="padding:10px 16px;text-align:left;font-size:11px;
                   text-transform:uppercase;letter-spacing:0.4px;width:200px;">Reason</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>"""

    maj_section = _section_table("Major Interest", maj_rows, len(major))
    min_section = _section_table("Minor Interest", min_rows, len(minor))
    exc_section = _section_table("Excluded Articles", exc_rows, len(excluded))

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Classification Report</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: {BG}; color: {TEXT}; padding: 32px 16px; }}
    .card {{ background: {WHITE}; border-radius: 8px;
             box-shadow: 0 2px 8px rgba(0,0,0,0.08);
             padding: 32px; max-width: 960px; margin: 0 auto 24px; }}
    tbody tr {{ border-bottom: 1px solid {BORDER}; }}
    tbody tr:hover {{ filter: brightness(0.97); }}
  </style>
</head>
<body>

  <!-- Header card -->
  <div class="card">
    <div style="background:{NAVY};margin:-32px -32px 24px -32px;
                padding:24px 32px;border-radius:8px 8px 0 0;">
      <h1 style="color:#fff;font-size:20px;margin-bottom:4px;">
        PubMed Classification Report
      </h1>
      <p style="color:rgba(255,255,255,0.65);font-size:13px;">{run_date}</p>
    </div>

    <div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:20px;">
      {badges}
    </div>

    <div style="font-size:13px;color:{MUTED};margin-bottom:6px;">
      <strong style="color:{TEXT};">Date window:</strong> past {days} days
    </div>
    <div style="font-size:13px;color:{MUTED};margin-bottom:4px;">
      <strong style="color:{TEXT};">RSS feeds:</strong>
    </div>
    {rss_html}
  </div>

  <!-- Articles card -->
  <div class="card">
    {maj_section}
    {min_section}
    {exc_section}
  </div>

</body>
</html>"""
