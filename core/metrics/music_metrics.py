from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("yuna.metrics")

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
        REGISTRY,
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

# ---------------------------------------------------------
# Metric Definitions
# ---------------------------------------------------------
if HAS_PROMETHEUS:
    # 1. Latency Histograms
    RESOLUTION_LATENCY = Histogram(
        "yuna_music_resolution_latency_seconds",
        "Time taken to resolve a query/track to canonical metadata (seconds)",
        ["source"],
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
    )
    EXTRACTION_LATENCY = Histogram(
        "yuna_music_extraction_latency_seconds",
        "Time taken to extract playable audio stream URL (seconds)",
        buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0],
    )

    # 2. Gauges
    ACTIVE_VOICE_CONNECTIONS = Gauge(
        "yuna_music_active_voice_connections",
        "Number of currently connected and active Discord voice channels",
    )
    ACTIVE_CATALOG_SESSIONS = Gauge(
        "yuna_music_catalog_sessions_active",
        "Number of active Virtual Artist/Album/Soundtrack Catalog sessions",
    )

    # 3. Counters
    PREFETCH_ATTEMPTS = Counter(
        "yuna_music_prefetch_attempts_total",
        "Total number of background stream prefetch attempts initiated",
    )
    PREFETCH_SUCCESS = Counter(
        "yuna_music_prefetch_success_total",
        "Total number of background stream prefetches completed successfully",
    )
    PREFETCH_FAILURES = Counter(
        "yuna_music_prefetch_failures_total",
        "Total number of background stream prefetches that failed",
    )
    STREAM_EXTRACTION_ERRORS = Counter(
        "yuna_music_stream_extraction_errors_total",
        "Total number of stream extraction errors encountered during playback",
    )
    CATALOG_TRACKS_SELECTED = Counter(
        "yuna_music_catalog_tracks_selected_total",
        "Total number of tracks selected from active virtual catalogs",
    )
    RECOMMENDATIONS_SELECTED = Counter(
        "yuna_music_recommendations_selected_total",
        "Total number of algorithmic/similar-vibe recommendations selected",
    )
    RECOMMENDATIONS_SKIPPED = Counter(
        "yuna_music_recommendations_skipped_total",
        "Total number of algorithmic recommendations that were skipped by users",
    )
else:
    RESOLUTION_LATENCY = None
    EXTRACTION_LATENCY = None
    ACTIVE_VOICE_CONNECTIONS = None
    ACTIVE_CATALOG_SESSIONS = None
    PREFETCH_ATTEMPTS = None
    PREFETCH_SUCCESS = None
    PREFETCH_FAILURES = None
    STREAM_EXTRACTION_ERRORS = None
    CATALOG_TRACKS_SELECTED = None
    RECOMMENDATIONS_SELECTED = None
    RECOMMENDATIONS_SKIPPED = None


# ---------------------------------------------------------
# Safe Recording Helper Functions (Never raise, never block)
# ---------------------------------------------------------

def record_resolution_latency(source: str, duration_sec: float) -> None:
    if not HAS_PROMETHEUS or RESOLUTION_LATENCY is None:
        return
    try:
        clean_source = str(source or "unknown").lower()
        RESOLUTION_LATENCY.labels(source=clean_source).observe(max(0.0, float(duration_sec)))
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record resolution latency: {e}")


def record_extraction_latency(duration_sec: float) -> None:
    if not HAS_PROMETHEUS or EXTRACTION_LATENCY is None:
        return
    try:
        EXTRACTION_LATENCY.observe(max(0.0, float(duration_sec)))
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record extraction latency: {e}")


def record_active_voice_connections(count: int) -> None:
    if not HAS_PROMETHEUS or ACTIVE_VOICE_CONNECTIONS is None:
        return
    try:
        ACTIVE_VOICE_CONNECTIONS.set(max(0, int(count)))
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record active voice connections: {e}")


def record_active_catalog_sessions(count: int) -> None:
    if not HAS_PROMETHEUS or ACTIVE_CATALOG_SESSIONS is None:
        return
    try:
        ACTIVE_CATALOG_SESSIONS.set(max(0, int(count)))
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record active catalog sessions: {e}")


def record_prefetch_attempt() -> None:
    if not HAS_PROMETHEUS or PREFETCH_ATTEMPTS is None:
        return
    try:
        PREFETCH_ATTEMPTS.inc()
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record prefetch attempt: {e}")


def record_prefetch_success() -> None:
    if not HAS_PROMETHEUS or PREFETCH_SUCCESS is None:
        return
    try:
        PREFETCH_SUCCESS.inc()
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record prefetch success: {e}")


def record_prefetch_failure() -> None:
    if not HAS_PROMETHEUS or PREFETCH_FAILURES is None:
        return
    try:
        PREFETCH_FAILURES.inc()
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record prefetch failure: {e}")


def record_stream_extraction_error() -> None:
    if not HAS_PROMETHEUS or STREAM_EXTRACTION_ERRORS is None:
        return
    try:
        STREAM_EXTRACTION_ERRORS.inc()
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record stream extraction error: {e}")


def record_catalog_track_selected() -> None:
    if not HAS_PROMETHEUS or CATALOG_TRACKS_SELECTED is None:
        return
    try:
        CATALOG_TRACKS_SELECTED.inc()
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record catalog track selected: {e}")


def record_recommendation_selected() -> None:
    if not HAS_PROMETHEUS or RECOMMENDATIONS_SELECTED is None:
        return
    try:
        RECOMMENDATIONS_SELECTED.inc()
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record recommendation selected: {e}")


def record_recommendation_skipped() -> None:
    if not HAS_PROMETHEUS or RECOMMENDATIONS_SKIPPED is None:
        return
    try:
        RECOMMENDATIONS_SKIPPED.inc()
    except Exception as e:
        logger.debug(f"[METRICS] Failed to record recommendation skipped: {e}")


def generate_latest_metrics() -> bytes:
    """Renders Prometheus metrics exposition text."""
    if not HAS_PROMETHEUS:
        return b"# prometheus_client not installed\n"
    try:
        return generate_latest(REGISTRY)
    except Exception as e:
        logger.error(f"[METRICS] Failed to generate metrics exposition: {e}")
        return f"# Error generating metrics: {e}\n".encode("utf-8")
