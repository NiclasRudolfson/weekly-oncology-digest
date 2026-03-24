"""Load a DigestConfig from a TOML file in the digests/ directory."""

import tomllib
from pathlib import Path

from digests.base import DigestConfig


def load_digest(name: str) -> DigestConfig:
    """
    Load and return the DigestConfig for the given digest name.

    Reads digests/{name}.toml relative to this file's directory.

    Args:
        name: Digest identifier, e.g. "oncology". Must match a .toml filename.

    Raises:
        FileNotFoundError: If no matching .toml file exists.
        KeyError: If a required TOML key is missing.
    """
    path = Path(__file__).parent / f"{name}.toml"
    if not path.exists():
        available = [p.stem for p in Path(__file__).parent.glob("*.toml")]
        raise FileNotFoundError(
            f"No digest config found for '{name}' (looked for {path}).\n"
            f"Available digests: {', '.join(sorted(available)) or 'none'}"
        )

    with open(path, "rb") as f:
        data = tomllib.load(f)

    return DigestConfig(
        digest_id=data["digest"]["id"],
        title=data["digest"]["title"],
        recipient_env_var=data["digest"]["recipient_env_var"],
        rss_urls=data["feeds"]["rss_urls"],
        sections=data["sections"]["order"],
        classify_criteria=data["prompts"]["classify_criteria"].strip(),
        summary_max_words=data["prompts"].get("summary_max_words", 20),
        rss_journals_html=data["prompts"].get("rss_journals_html", "").strip(),
    )
