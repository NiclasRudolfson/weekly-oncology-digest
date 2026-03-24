from dataclasses import dataclass, field


@dataclass(frozen=True)
class DigestConfig:
    """All per-digest configuration, loaded from a TOML file in this directory."""

    # Identity
    digest_id: str          # Short identifier used for seen_pmids filename, artifacts, etc.
    title: str              # Email subject / header title
    recipient_env_var: str  # Name of the GitHub secret / env var holding recipient emails

    # Feeds
    rss_urls: list[str] = field(default_factory=list)

    # Sections (ordered list — first entry is the fallback for unclassifiable articles)
    sections: list[str] = field(default_factory=list)

    # Classify prompt — the full MAJOR/MINOR/EXCLUDED rubric text, injected into the template
    classify_criteria: str = ""

    # Extract prompt overrides
    summary_max_words: int = 20

    # Footer journal list HTML (optional)
    rss_journals_html: str = ""
