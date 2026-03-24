"""
Digest — entry point.

Usage:
  python main.py                             # run the default (oncology) digest
  python main.py --digest oncology           # same, explicit
  python main.py --digest haematology        # run a different digest
  python main.py --rss-url <URL>             # one-off RSS feed URL override
  python main.py --dry-run                   # fetch + process, do NOT send email
  python main.py --save-html out.html        # also write the digest email to a file

Pipeline (5 steps):
  1. Fetch   — download PubMed RSS feed(s), skip already-seen PMIDs, retrieve full records
  2. Classify — Gemini screens each article (major interest / minor interest / excluded)
  3. Report  — save classification_report.html (uploaded as a GitHub Actions artifact)
  4. Extract — Gemini extracts rich structured clinical data from major-interest articles
  5. Render  — build HTML email and send (or skip if --dry-run)

Seen PMIDs are stored in seen_pmids_{digest_id}.txt and updated after each successful
send, so each article appears in exactly one digest regardless of publication date.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Ensure src/ and project root are on the path when run from project root
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import config
from fetch import fetch_articles
from summarize import run_pipeline
from format_email import render_html
from format_report import render_report
from send_email import send_digest


def _load_seen_pmids(path: Path) -> set[str]:
    if path.exists():
        return set(path.read_text().split())
    return set()


def _save_seen_pmids(path: Path, seen: set[str]) -> None:
    path.write_text("\n".join(sorted(seen)) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and send a weekly literature digest."
    )
    parser.add_argument(
        "--digest", metavar="NAME", default="general_oncology",
        help=(
            "Which digest to run. Must match a .toml file in the digests/ folder "
            "(e.g. 'oncology' → digests/oncology.toml). Default: oncology"
        ),
    )
    parser.add_argument(
        "--rss-url", metavar="URL", default=None,
        help=(
            "Override the RSS feed URL(s) in the digest config with a single URL. "
            "Useful for one-off runs without editing the config file."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and process but do NOT send the email",
    )
    parser.add_argument(
        "--save-html", metavar="FILE",
        help="Save the rendered digest email HTML to this file for local inspection",
    )
    args = parser.parse_args()

    # Load the digest configuration from the matching TOML file
    from digests._loader import load_digest
    cfg = load_digest(args.digest)

    seen_pmids_file = Path(f"seen_pmids_{cfg.digest_id}.txt")

    # Resolve RSS URLs: CLI override takes precedence, else use digest config
    if args.rss_url:
        rss_urls = [args.rss_url]
        print(f"  [RSS override] Using URL from --rss-url argument")
    else:
        rss_urls = cfg.rss_urls

    print("=" * 60)
    print(f"  {cfg.title}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Deduplication: PMID-based ({seen_pmids_file})")
    print("=" * 60)

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    print("\n[1/5] Fetching articles from PubMed...")
    seen_pmids = _load_seen_pmids(seen_pmids_file)
    print(f"  Loaded {len(seen_pmids)} previously seen PMIDs")
    articles, new_pmids = fetch_articles(rss_urls=rss_urls, seen_pmids=seen_pmids)

    if not articles:
        print("  No new articles found.")
        sys.exit(0)

    # ── 2. Classify + Extract ─────────────────────────────────────────────────
    print("\n[2/5] Classifying articles and extracting data...")
    classified, extracted, minor_interest = run_pipeline(articles, cfg)

    if not extracted and not minor_interest:
        print("  No articles passed classification — nothing to send.")
        sys.exit(0)

    # ── 3. Save classification report ─────────────────────────────────────────
    print("\n[3/5] Saving classification report...")
    report_html = render_report(classified, rss_urls=rss_urls)
    report_path = Path("classification_report.html")
    report_path.write_text(report_html, encoding="utf-8")
    n_major = sum(1 for a in classified if a.get("status") == "major_interest")
    n_minor = sum(1 for a in classified if a.get("status") == "minor_interest")
    print(f"  Saved: {report_path}  ({len(classified)} articles, "
          f"{n_major} major, {n_minor} minor)")

    # ── 4. Render email ───────────────────────────────────────────────────────
    print("\n[4/5] Rendering HTML email...")
    html = render_html(
        extracted, minor_interest, cfg.title,
        sections=cfg.sections,
        rss_journals_html=cfg.rss_journals_html,
    )

    if args.save_html:
        Path(args.save_html).write_text(html, encoding="utf-8")
        print(f"  Digest email saved to: {args.save_html}")

    # ── 5. Send ───────────────────────────────────────────────────────────────
    if args.dry_run:
        print("\n[5/5] Dry-run mode — email NOT sent, seen_pmids NOT updated.")
        print("  Inspect the outputs:")
        print(f"    Digest preview:         {args.save_html or '(use --save-html FILE)'}")
        print(f"    Classification report:  {report_path}")
    else:
        print("\n[5/5] Sending email...")
        week_str = datetime.now().strftime("%B %d, %Y")
        subject  = f"{cfg.title} — {week_str}"
        send_digest(html, subject, recipient_env_var=cfg.recipient_env_var)
        _save_seen_pmids(seen_pmids_file, seen_pmids | new_pmids)
        print(f"  Updated {seen_pmids_file} ({len(seen_pmids | new_pmids)} total PMIDs)")

    print("\nDone.")


if __name__ == "__main__":
    main()
