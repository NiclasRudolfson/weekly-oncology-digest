"""
Fetch articles from PubMed using RSS feeds + E-utilities efetch.

Flow:
  1. RSS feed  → list of PMIDs (all items in feed, no date filtering)
  2. Deduplicate against seen_pmids → only new PMIDs proceed
  3. efetch    → full XML records (including complete abstracts) for those PMIDs
  4. parse     → list of article dicts

Rate limits (efetch only):
  - Without API key: 3 requests/sec
  - With API key:   10 requests/sec
  Set PUBMED_API_KEY in your environment to use the higher limit.
"""

import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _requests_session() -> requests.Session:
    """Return a session with automatic retries on transient server errors."""
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

import config
from queries import RSS_URLS


# ── RSS parsing ───────────────────────────────────────────────────────────────

def _fetch_rss(url: str) -> list[str]:
    """Fetch a PubMed RSS feed and return all PMIDs present in the feed."""
    resp = _requests_session().get(url, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    pmids = []
    for item in root.findall(".//item"):
        link = item.findtext("link", "") or item.findtext("guid", "")
        # PubMed links end in /<pmid>/ (may include ?utm_* query params)
        pmid = link.split("?")[0].rstrip("/").split("/")[-1]
        if pmid.isdigit():
            pmids.append(pmid)
    return pmids


def _efetch(pmids: list[str]) -> str:
    """Run efetch for a batch of PMIDs and return raw XML."""
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    if config.PUBMED_API_KEY:
        params["api_key"] = config.PUBMED_API_KEY
    url = f"{config.PUBMED_BASE_URL}/efetch.fcgi"
    resp = _requests_session().get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.text


# ── XML parsing ───────────────────────────────────────────────────────────────

def _text(node, path: str, default: str = "") -> str:
    found = node.find(path)
    return "".join(found.itertext()).strip() if found is not None else default


def _parse_article(node) -> Optional[dict]:
    citation = node.find("MedlineCitation")
    if citation is None:
        return None

    article = citation.find("Article")
    if article is None:
        return None

    pmid = _text(citation, "PMID")
    title = _text(article, "ArticleTitle")
    if not title:
        return None

    # Abstract: collect labeled and unlabeled sections
    abstract_parts = []
    abstract_node = article.find("Abstract")
    if abstract_node is not None:
        for t in abstract_node.findall("AbstractText"):
            label = t.get("Label", "")
            body = "".join(t.itertext()).strip()
            abstract_parts.append(f"{label}: {body}" if label else body)
    abstract = " ".join(abstract_parts)
    if not abstract:
        return None

    # Authors (up to first 5)
    authors = []
    for a in article.findall(".//Author"):
        last = _text(a, "LastName")
        fore = _text(a, "ForeName")
        if last:
            authors.append(f"{last} {fore}".strip())
        if len(authors) >= 5:
            break

    # Journal
    journal_node = article.find("Journal")
    journal = ""
    if journal_node is not None:
        journal = _text(journal_node, "Title") or _text(journal_node, "ISOAbbreviation")

    # Publication date
    date_node = article.find(".//PubDate")
    pub_date = ""
    if date_node is not None:
        year = _text(date_node, "Year")
        month = _text(date_node, "Month")
        pub_date = f"{year} {month}".strip()

    # DOI
    doi = ""
    for id_node in node.findall(".//ArticleId"):
        if id_node.get("IdType") == "doi":
            doi = id_node.text or ""
            break

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "journal": journal,
        "pub_date": pub_date,
        "doi": doi,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def _parse_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    articles = []
    for node in root.findall(".//PubmedArticle"):
        try:
            a = _parse_article(node)
            if a:
                articles.append(a)
        except Exception as e:
            print(f"  Warning: failed to parse one article — {e}")
    return articles


# ── Public interface ──────────────────────────────────────────────────────────

def fetch_articles(
    rss_urls: list[str] = None,
    seen_pmids: set[str] = None,
) -> tuple[list[dict], set[str]]:
    """
    Fetch articles from PubMed RSS feeds, skipping any PMID in seen_pmids.

    Deduplicates by PMID across feeds, then retrieves full records via efetch.

    Returns:
        (articles, new_pmids) where new_pmids is the full set of PMIDs fetched
        from the feed that were not in seen_pmids (regardless of parse success),
        so the caller can mark them all as seen.
    """
    rss_urls = rss_urls or RSS_URLS
    seen_pmids = seen_pmids or set()

    all_pmids: set[str] = set()
    for url in rss_urls:
        print(f"  RSS: {url[:80]}")
        pmids = _fetch_rss(url)
        print(f"    → {len(pmids)} articles in feed")
        all_pmids.update(pmids)

    new_pmids = all_pmids - seen_pmids
    print(f"  Total unique PMIDs in feed: {len(all_pmids)}")
    print(f"  New (not yet seen):         {len(new_pmids)}")

    if not new_pmids:
        return [], set()

    # Fetch full records (including abstracts) in batches of 100
    pmid_list = list(new_pmids)
    articles = []
    for i in range(0, len(pmid_list), 100):
        batch = pmid_list[i : i + 100]
        xml_text = _efetch(batch)
        articles.extend(_parse_xml(xml_text))
        if i + 100 < len(pmid_list):
            time.sleep(0.4)

    print(f"  Successfully parsed {len(articles)} articles")
    return articles, new_pmids
