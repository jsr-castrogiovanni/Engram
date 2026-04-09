"""Entity extraction — hybrid regex pipeline.

Extracts structured entities from fact content for Tier 0/2 detection.
Regex pass only for v0.1 (NER model is a future addition).
"""

from __future__ import annotations

import re
from typing import Any

# ── Regex patterns for entity extraction ─────────────────────────────

# Numeric values with units
_NUMERIC_PATTERNS = [
    # "1000 req/s", "500ms", "30 seconds", "5GB"
    re.compile(
        r"(?P<value>\d[\d,]*\.?\d*)\s*(?P<unit>req/s|rps|ms|seconds?|secs?|minutes?|mins?"
        r"|hours?|hrs?|days?|[KMGT]B|bytes?|%|connections?|threads?|workers?|retries|attempts)",
        re.IGNORECASE,
    ),
    # "port 5432", "version 3.2.1"
    re.compile(r"(?:port|version|v)\s*(?P<value>[\d.]+)", re.IGNORECASE),
]

# ALL_CAPS identifiers (config keys, env vars)
_CONFIG_KEY_PATTERN = re.compile(r"\b(?P<name>[A-Z][A-Z0-9_]{2,})\b")

# Service/component names — heuristic: lowercase words before "service", "server", etc.
_SERVICE_PATTERN = re.compile(
    r"\b(?P<name>[a-z][a-z0-9_-]+)\s+(?:service|server|worker|queue|cache|database|db|proxy|gateway)\b",
    re.IGNORECASE,
)

# Version strings
_VERSION_PATTERN = re.compile(r"\bv?(?P<value>\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9.]+)?)\b")

# Technology names (common ones)
_TECH_NAMES = {
    "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis",
    "elasticsearch", "kafka", "rabbitmq", "nginx", "docker", "kubernetes",
    "k8s", "graphql", "grpc", "rest", "jwt", "oauth", "s3", "sqs", "sns",
    "dynamodb", "cloudfront", "lambda", "ecs", "eks", "rds",
}


def extract_entities(content: str) -> list[dict[str, Any]]:
    """Extract structured entities from fact content via regex.

    Returns a list of entity dicts: {name, type, value?, unit?}
    """
    entities: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Numeric values with units
    for pattern in _NUMERIC_PATTERNS:
        for m in pattern.finditer(content):
            value = m.group("value").replace(",", "")
            unit = m.group("unit") if "unit" in m.groupdict() else None
            # Try to find what this number describes from surrounding context
            start = max(0, m.start() - 60)
            context = content[start : m.start()].lower()
            name = _infer_numeric_name(context, unit)
            key = f"numeric:{name}:{value}"
            if key not in seen:
                seen.add(key)
                entity: dict[str, Any] = {
                    "name": name,
                    "type": "numeric",
                    "value": _parse_number(value),
                }
                if unit:
                    entity["unit"] = unit.lower()
                entities.append(entity)

    # Config keys (ALL_CAPS)
    for m in _CONFIG_KEY_PATTERN.finditer(content):
        name = m.group("name")
        # Skip very short or common English words that happen to be caps
        if len(name) < 3 or name in {"THE", "AND", "FOR", "NOT", "BUT", "ALL", "HAS", "WAS"}:
            continue
        key = f"config_key:{name}"
        if key not in seen:
            seen.add(key)
            entities.append({"name": name, "type": "config_key"})

    # Service names
    for m in _SERVICE_PATTERN.finditer(content):
        name = m.group("name").lower()
        key = f"service:{name}"
        if key not in seen:
            seen.add(key)
            entities.append({"name": name, "type": "service"})

    # Technology names
    content_lower = content.lower()
    for tech in _TECH_NAMES:
        if tech in content_lower:
            key = f"technology:{tech}"
            if key not in seen:
                seen.add(key)
                entities.append({"name": tech, "type": "technology"})

    # Version strings (only if not already captured as numeric)
    for m in _VERSION_PATTERN.finditer(content):
        value = m.group("value")
        start = max(0, m.start() - 40)
        context = content[start : m.start()].lower()
        name = _infer_version_name(context)
        key = f"version:{name}:{value}"
        if key not in seen:
            seen.add(key)
            entities.append({"name": name, "type": "version", "value": value})

    return entities


def extract_keywords(content: str) -> list[str]:
    """Extract simple keywords from content for FTS enrichment."""
    # Remove common stop words and extract meaningful terms
    words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_-]{2,}\b", content)
    stop = {
        "the", "and", "for", "not", "but", "all", "has", "was", "are", "this",
        "that", "with", "from", "will", "been", "have", "does", "when", "which",
        "their", "about", "into", "than", "them", "then", "each", "other",
        "using", "used", "uses",
    }
    seen: set[str] = set()
    keywords: list[str] = []
    for w in words:
        wl = w.lower()
        if wl not in stop and wl not in seen:
            seen.add(wl)
            keywords.append(wl)
    return keywords[:30]  # Cap at 30 keywords


def _infer_numeric_name(context: str, unit: str | None) -> str:
    """Try to infer what a numeric value describes from surrounding text."""
    # Look for common patterns
    patterns = [
        (r"rate[- ]?limit", "rate_limit"),
        (r"timeout", "timeout"),
        (r"max[- ]?connections?", "max_connections"),
        (r"max[- ]?retries", "max_retries"),
        (r"ttl", "ttl"),
        (r"pool[- ]?size", "pool_size"),
        (r"batch[- ]?size", "batch_size"),
        (r"buffer[- ]?size", "buffer_size"),
        (r"cache[- ]?size", "cache_size"),
        (r"queue[- ]?size", "queue_size"),
        (r"threshold", "threshold"),
        (r"interval", "interval"),
        (r"port", "port"),
        (r"replicas?", "replicas"),
        (r"workers?", "workers"),
        (r"threads?", "threads"),
        (r"memory", "memory"),
        (r"cpu", "cpu"),
        (r"latency", "latency"),
        (r"throughput", "throughput"),
    ]
    for pattern, name in patterns:
        if re.search(pattern, context):
            return name
    if unit:
        return f"value_{unit.lower()}"
    return "numeric_value"


def _infer_version_name(context: str) -> str:
    """Try to infer what software a version string refers to."""
    # Check for technology names in context
    for tech in _TECH_NAMES:
        if tech in context:
            return f"{tech}_version"
    # Check for common patterns
    words = context.split()
    if words:
        return f"{words[-1].strip('.,:;')}_version"
    return "version"


def _parse_number(s: str) -> int | float:
    """Parse a numeric string to int or float."""
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return 0
