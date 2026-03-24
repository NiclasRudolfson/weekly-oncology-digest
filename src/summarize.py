"""
Use Gemini to classify and extract structured data from PubMed articles.

Two-pass approach:
  1. Classify pass (Flash)  — include/exclude every article against an explicit rubric
  2. Extract pass (Flash)   — extract rich structured clinical data from included articles

The classify pass annotates each article dict with 'status' and 'reason' fields so
that a classification report can be generated and uploaded as a GitHub Actions artifact.

The extract pass returns a list of structured records (one per included article) that
drive the final email rendering.  Phase III records carry full trial details
(intervention, comparator, endpoints, results); Phase I/II records carry only the
minimum fields needed for compact listing.

Both passes are controlled by the DigestConfig passed in — the classification criteria,
section list, and summary length all come from the per-digest TOML configuration.
"""

import json
import re
from typing import Any, TYPE_CHECKING

from google import genai

import config

if TYPE_CHECKING:
    from digests.base import DigestConfig


client = genai.Client(api_key=config.GEMINI_API_KEY)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> Any:
    """Strip markdown fences and parse the first JSON array or object found."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    start = next((i for i, c in enumerate(text) if c in "{["), None)
    if start is None:
        raise ValueError(f"No JSON found in response:\n{text[:500]}")
    return json.loads(text[start:])


# ── Pass 1: Classify ──────────────────────────────────────────────────────────

_CLASSIFY_PROMPT_TEMPLATE = """\
Screen PubMed articles for a clinical digest.
Assign each article one of three decisions: major_interest, minor_interest, or excluded.

{classify_criteria}

For every non-excluded article also assign a "section" from this exact list:
{sections_list}
Use "{fallback_section}" for multi-topic or unclassifiable articles.
Excluded articles should have section "".

Return ONLY a JSON array, no markdown:
[{{"i":0,"decision":"major_interest","reason":"Phase III RCT","section":"{fallback_section}"}}, ...]

The "reason" field must be brief (3–6 words) and specific to the article.

Articles:
{articles}"""


def classify_articles(articles: list[dict], cfg: "DigestConfig") -> list[dict]:
    """
    Use Gemini Flash to include/exclude articles using the digest rubric from cfg.

    Mutates each article dict in-place by adding:
      - "status": "major_interest" | "minor_interest" | "excluded"
      - "reason": short explanation string
      - "section": section name (for minor_interest articles)

    Returns the full list (all articles, not just included ones).
    """
    if not articles:
        return []

    items = "\n\n".join(
        f"[{i}] Title: {a['title']}\nAbstract: {a['abstract'] or 'NO ABSTRACT'}"
        for i, a in enumerate(articles)
    )

    sections_list = ", ".join(f'"{s}"' for s in cfg.sections)
    fallback_section = cfg.sections[0] if cfg.sections else "General"

    prompt = _CLASSIFY_PROMPT_TEMPLATE.format(
        classify_criteria=cfg.classify_criteria,
        sections_list=sections_list,
        fallback_section=fallback_section,
        articles=items,
    )

    response = client.models.generate_content(
        model=config.CLASSIFY_MODEL,
        contents=prompt,
    )

    results = _extract_json(response.text)
    for r in results:
        a = articles[r["i"]]
        decision = r.get("decision", "excluded")
        if decision in ("major_interest", "minor_interest"):
            a["status"] = decision
        else:
            a["status"] = "excluded"
        a["reason"] = r.get("reason", "")
        # Store classifier-assigned section on minor articles (major articles get
        # their section from the extractor; excluded articles don't need one)
        if a["status"] == "minor_interest":
            a["section"] = r.get("section", fallback_section) or fallback_section

    # Defensive: mark any articles the model missed
    for a in articles:
        if "status" not in a:
            a["status"] = "excluded"
            a["reason"] = "Not returned by classifier"

    n_major = sum(1 for a in articles if a["status"] == "major_interest")
    n_minor = sum(1 for a in articles if a["status"] == "minor_interest")
    n_exc   = sum(1 for a in articles if a["status"] == "excluded")
    print(f"  Classified {len(articles)} articles: "
          f"{n_major} major, {n_minor} minor, {n_exc} excluded")
    return articles


# ── Pass 2: Extract structured data ──────────────────────────────────────────

_EXTRACT_PROMPT_TEMPLATE = """\
Extract structured data from publications for a clinical digest.

Use BOTH title AND abstract together. Trial names and phase labels in the title are authoritative.

Return a JSON array.  Each element must include:
- "i"          : index integer (matching the input index)
- "section"    : one of: {sections_list}
                 The last section in the list covers articles about trial design, surrogate
                 endpoints, statistical techniques, and regulatory science (FDA/EMA).
- "study_type" : one of: "Phase III", "Phase II", "Phase I", "Phase I/II",
                 "Guideline", "Systematic review", "Meta-analysis",
                 "Secondary analysis of RCT", "Observational study",
                 "Literature review", "Statistical methodology"
                 "Secondary analysis of RCT" covers post-hoc analyses of RCT data,
                 including subgroup analyses, pooled analyses of a small number of
                 trials, or analyses of new biomarkers using existing RCT datasets.
- "journal"    : use the provided journal name; strip anything after a colon.
                 Use "NR" only if truly absent.
- "new_or_update":
    Phase III → determine carefully:
      "First report"      if abstract uses "primary analysis", "primary endpoint results",
                          "we report", or has no mention of prior publications of this trial.
      "Updated analysis"  if abstract mentions "updated", "final analysis",
                          "extended follow-up", "previously reported", "additional follow-up",
                          "mature results", "long-term results".
    Guideline → "New guideline" or "Updated guideline"
    Reviews / methodology → "" (empty string)

For Phase III — additionally include:
- "population"          : patient context NOT already clear from the title (1 sentence max)
- "intervention"        : experimental arm description + n=  [structural guide — see summary]
- "comparator"          : control arm description + n=       [structural guide — see summary]
- "primary_endpoint"    : exact name from the abstract — do NOT assume PFS or OS
- "primary_result"      : numerical result with HR/RR/OR and 95% CI.
                          Omit p-value if CI is provided.
- "secondary_results"   : up to 2 key secondaries with HR/CI. Use "" if none reported.
                          If OS data are available, always include OS here regardless of
                          whether it was a primary or secondary endpoint.
- "summary"             : strictly ≤{summary_max_words} words of plain language PLUS the key
                          numerical result with CI.  Do NOT repeat anything already in the title.
                          Do NOT include p-values if CI is given.
                          If OS data are available, include both the primary endpoint
                          result and OS result, even if OS was a secondary endpoint.
                          Note: "population", "intervention", "comparator",
                          "primary_endpoint", "primary_result", and "secondary_results"
                          are provided as structured scaffolding to guide your thinking —
                          the summary should synthesise them into concise prose rather
                          than simply restating each field.

For Guideline / Systematic review / Literature review / Statistical methodology — additionally:
- "population"  : clinical scope or topic covered
- "summary"     : 1–2 sentences max; key recommendation or main finding.

For Phase I / Phase II / Phase I/II — additionally include:
- "population"  : patient context NOT already clear from the title (1 sentence max)
- "summary"     : 1–2 sentences max; key finding or result (dose, response rate, etc.).

Return ONLY the JSON array.  No markdown, no code fences.

Articles:
{articles}"""


def extract_structured_data(included: list[dict], cfg: "DigestConfig") -> list[dict]:
    """
    Use Gemini Flash to extract structured clinical data from included articles.

    Args:
        included: Article dicts that passed classification (status == "major_interest").
        cfg: Digest configuration (provides sections list and summary_max_words).

    Returns:
        List of extraction records, one per article, enriched with title/pmid/link
        from the source article for use during rendering.
    """
    if not included:
        return []

    items = "\n\n---\n\n".join(
        (
            f"[{i}] PMID: {a['pmid'] or 'N/A'}"
            f" | Link: {a['pubmed_url']}"
            f" | Journal: {a['journal'] or 'unknown'}\n"
            f"Title: {a['title']}\n"
            f"Abstract: {a['abstract'] or 'NO ABSTRACT'}"
        )
        for i, a in enumerate(included)
    )

    sections_list = ", ".join(f'"{s}"' for s in cfg.sections)

    prompt = _EXTRACT_PROMPT_TEMPLATE.format(
        sections_list=sections_list,
        summary_max_words=cfg.summary_max_words,
        articles=items,
    )

    response = client.models.generate_content(
        model=config.EXTRACT_MODEL,
        contents=prompt,
    )

    text = response.text.replace("```json", "").replace("```", "").strip()
    # Find the first '[' to handle any leading prose the model may add
    bracket = text.find("[")
    if bracket == -1:
        raise ValueError(f"Extraction returned no JSON array:\n{text[:500]}")
    records = json.loads(text[bracket:])

    # Enrich each record with source-article metadata needed for rendering
    for r in records:
        src = included[r["i"]]
        r["title"] = src["title"]
        r["pmid"]  = src["pmid"]
        r["link"]  = src["pubmed_url"]

    print(f"  Extracted structured data for {len(records)} articles")
    return records


# ── Public interface ──────────────────────────────────────────────────────────

def run_pipeline(
    articles: list[dict],
    cfg: "DigestConfig",
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Full two-pass pipeline: classify → extract.

    Args:
        articles: Raw article dicts from fetch_articles().
        cfg:      Digest configuration (sections, criteria, summary length, etc.)

    Returns:
        classified      — every article dict, annotated with 'status' and 'reason'
                          (used to build the classification report artifact)
        extracted       — structured records for major_interest articles only
                          (used to render the main digest sections with full summaries)
        minor_interest  — raw article dicts for minor_interest articles
                          (rendered as title / journal / PMID one-liners at the bottom)
    """
    print(f"  Classifying {len(articles)} articles with {config.CLASSIFY_MODEL}...")
    classified = classify_articles(articles, cfg)

    major    = [a for a in classified if a["status"] == "major_interest"]
    minor    = [a for a in classified if a["status"] == "minor_interest"]
    print(f"  Extracting structured data from {len(major)} major-interest articles"
          f" with {config.EXTRACT_MODEL}...")
    extracted = extract_structured_data(major, cfg)

    return classified, extracted, minor
