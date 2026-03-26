"""Ollama Cloud API client for AI enrichment using official SDK."""

from __future__ import annotations

import json
import os

from ollama import Client

from src.shared.logging import setup_logging

logger = setup_logging(__name__)

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:397b")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")


def _get_client() -> Client:
    return Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
    )


def extract_keywords_and_topics(title: str, content_text: str) -> dict:
    """Extract keywords and topics from an article using Ollama Cloud API.

    Returns:
        {"keywords": ["keyword1", ...], "topics": ["topic1", ...], "summary": "..."}
    """
    if not OLLAMA_API_KEY:
        logger.warning("OLLAMA_API_KEY not set, skipping enrichment")
        return {"keywords": [], "topics": [], "summary": ""}

    prompt = f"""Analyze the following tech blog article and extract:
1. keywords: 5-10 technical keywords (in Korean if the article is Korean)
2. topics: 1-3 trending topics/categories (e.g. "AI/ML", "DevOps", "Frontend", "Backend", "Data Engineering", "Security", "Mobile", "Cloud")
3. summary: 2-3 sentence summary in Korean

Article title: {title}
Article content (first 3000 chars): {content_text[:3000]}

Respond in JSON format only, no other text:
{{"keywords": ["keyword1", "keyword2", ...], "topics": ["topic1", ...], "summary": "..."}}"""

    try:
        client = _get_client()
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )

        raw_response = response["message"]["content"]
        result = _parse_json_response(raw_response)
        logger.info(
            "Enriched: title=%s, keywords=%d, topics=%d",
            title[:50],
            len(result.get("keywords", [])),
            len(result.get("topics", [])),
        )
        return result

    except Exception:
        logger.exception("Failed to enrich: title=%s", title[:50])
        return {"keywords": [], "topics": [], "summary": ""}


def _parse_json_response(raw: str) -> dict:
    """Parse JSON from LLM response, handling common issues."""
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]

    raw = raw.strip()

    try:
        result = json.loads(raw)
        return {
            "keywords": result.get("keywords", []),
            "topics": result.get("topics", []),
            "summary": result.get("summary", ""),
        }
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON from LLM response: %s", raw[:200])
        return {"keywords": [], "topics": [], "summary": ""}
