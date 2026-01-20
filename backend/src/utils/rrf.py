"""
Reciprocal Rank Fusion (RRF) for merging multiple ranked result lists.

This module implements the RRF algorithm for combining results from multiple
retrieval sources (e.g., dense embeddings + BM25 sparse search). RRF is
particularly effective because it:

- Doesn't require score normalization across different ranking methods
- Handles missing documents gracefully (only scores lists containing them)
- Provides robust fusion even when individual rankers have different score scales

Algorithm:
    For each document d:
        score(d) = Σ 1/(k + rank(d, list_i)) for all lists containing d

    Where k is a constant (default 60) that controls the importance of
    lower-ranked documents. Higher k values give more weight to top results.

Usage:
    from src.utils.rrf import rrf_fusion

    # Dense search results (ranked by cosine similarity)
    dense_results = [
        {"id": "chunk1", "score": 0.95, "metadata": {...}},
        {"id": "chunk2", "score": 0.87, "metadata": {...}},
    ]

    # BM25 results (ranked by term frequency)
    bm25_results = [
        {"id": "chunk2", "score": 12.5, "metadata": {...}},
        {"id": "chunk3", "score": 8.2, "metadata": {...}},
    ]

    # Fuse results
    fused = rrf_fusion([dense_results, bm25_results])
    # Returns: [{"id": "chunk2", "rrf_score": 0.032, "sources": ["dense", "bm25"], ...}, ...]

Note:
    KG (Knowledge Graph) results are NOT included in RRF because they operate
    at document-level, not chunk-level. KG boost is applied separately via
    HybridRetriever._apply_kg_boost() after RRF fusion.

Reference:
    - Paper: "Reciprocal Rank Fusion outperforms Condorcet and individual
      Rank Learning Methods" (Cormack et al., 2009)
    - PHASE_2B_HOW_TO_GUIDE.md Section 9.1
    - backend.mdc for Python patterns
"""

from __future__ import annotations

from typing import Any, TypedDict

import structlog

# Configure structured logger
logger = structlog.get_logger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class RRFResult(TypedDict):
    """Result from RRF fusion."""

    id: str
    rrf_score: float
    sources: list[str]
    metadata: dict[str, Any]


# =============================================================================
# Constants
# =============================================================================

# Default k constant for RRF (standard in literature)
# Higher k gives more weight to top-ranked documents
DEFAULT_K = 60

# Source labels for tracking result provenance
SOURCE_LABELS = ["dense", "bm25", "source_3", "source_4", "source_5"]


# =============================================================================
# RRF Implementation
# =============================================================================


def rrf_fusion(
    result_lists: list[list[dict[str, Any]]],
    k: int = DEFAULT_K,
    source_labels: list[str] | None = None,
) -> list[RRFResult]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF computes a combined score for each document based on its rank in each
    input list. Documents appearing in multiple lists get higher scores.
    The algorithm is robust to different score scales across ranking methods.

    Args:
        result_lists: List of result lists to fuse. Each result list should
            contain dicts with at least an "id" field. Optional "score" and
            "metadata" fields are preserved in output.
        k: RRF constant (default 60). Higher values give more weight to
            top-ranked documents. Standard value from literature.
        source_labels: Optional labels for each result list (e.g., ["dense", "bm25"]).
            Used to track which sources contributed to each result.
            Defaults to ["dense", "bm25", "source_3", ...].

    Returns:
        List of fused results sorted by RRF score (descending). Each result
        contains:
        - id: Document/chunk identifier
        - rrf_score: Combined RRF score
        - sources: List of source labels that contained this document
        - metadata: Merged metadata from all sources (first occurrence wins)

    Example:
        >>> dense = [{"id": "c1", "score": 0.9}, {"id": "c2", "score": 0.8}]
        >>> bm25 = [{"id": "c2", "score": 12.0}, {"id": "c3", "score": 8.0}]
        >>> results = rrf_fusion([dense, bm25])
        >>> results[0]["id"]  # c2 appears in both lists
        'c2'
        >>> results[0]["sources"]
        ['dense', 'bm25']

    Note:
        - Empty result lists are skipped (don't contribute to scores)
        - Documents only in one list still get a score from that list
        - Original scores are ignored; only ranks matter
    """
    if not result_lists:
        logger.debug("rrf_fusion_empty_input")
        return []

    # Filter out empty lists
    non_empty_lists = [lst for lst in result_lists if lst]
    if not non_empty_lists:
        logger.debug("rrf_fusion_all_empty")
        return []

    # Use provided labels or defaults
    labels = source_labels or SOURCE_LABELS[: len(non_empty_lists)]
    if len(labels) < len(non_empty_lists):
        # Extend with generic labels if not enough provided
        labels = list(labels) + [
            f"source_{i}" for i in range(len(labels), len(non_empty_lists))
        ]

    # Track scores, sources, and metadata for each document
    doc_scores: dict[str, float] = {}
    doc_sources: dict[str, list[str]] = {}
    doc_metadata: dict[str, dict[str, Any]] = {}

    # Process each result list
    for list_idx, result_list in enumerate(non_empty_lists):
        source_label = labels[list_idx]

        for rank, result in enumerate(result_list, start=1):
            doc_id = result.get("id")
            if doc_id is None:
                logger.warning(
                    "rrf_missing_id",
                    list_index=list_idx,
                    rank=rank,
                )
                continue

            # Calculate RRF contribution: 1 / (k + rank)
            rrf_contribution = 1.0 / (k + rank)

            # Accumulate score
            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0.0
                doc_sources[doc_id] = []
                # Store metadata from first occurrence (default to empty dict if None)
                doc_metadata[doc_id] = result.get("metadata") or {}

            doc_scores[doc_id] += rrf_contribution
            doc_sources[doc_id].append(source_label)

    # Build output list
    fused_results: list[RRFResult] = []
    for doc_id, score in doc_scores.items():
        fused_results.append(
            RRFResult(
                id=doc_id,
                rrf_score=score,
                sources=doc_sources[doc_id],
                metadata=doc_metadata[doc_id],
            )
        )

    # Sort by RRF score descending
    fused_results.sort(key=lambda x: x["rrf_score"], reverse=True)

    logger.debug(
        "rrf_fusion_complete",
        input_lists=len(non_empty_lists),
        unique_docs=len(fused_results),
        multi_source_docs=sum(1 for r in fused_results if len(r["sources"]) > 1),
        top_score=fused_results[0]["rrf_score"] if fused_results else 0.0,
    )

    return fused_results


def rrf_score_explanation(score: float, k: int = DEFAULT_K) -> str:
    """
    Generate a human-readable explanation of an RRF score.

    Useful for debugging and understanding why certain documents rank higher.

    Args:
        score: The RRF score to explain.
        k: The k constant used in RRF calculation.

    Returns:
        Human-readable explanation string.

    Example:
        >>> rrf_score_explanation(0.032)
        'RRF score 0.032 ≈ rank 1 in 2 lists (k=60)'
    """
    # Estimate number of lists and average rank from score
    # score = n * 1/(k + avg_rank) → avg_rank ≈ n/score - k
    # For score=0.032 with k=60: if n=2, avg_rank ≈ 2.5

    if score <= 0:
        return "RRF score 0.000 = not in any list"

    # Common cases
    single_rank1 = 1.0 / (k + 1)  # ~0.0164 for k=60
    double_rank1 = 2.0 / (k + 1)  # ~0.0328 for k=60

    if abs(score - double_rank1) < 0.001:
        return f"RRF score {score:.4f} ≈ rank 1 in 2 lists (k={k})"
    elif abs(score - single_rank1) < 0.001:
        return f"RRF score {score:.4f} ≈ rank 1 in 1 list (k={k})"
    else:
        # Estimate sources based on score magnitude
        estimated_sources = max(1, round(score / single_rank1))
        return (
            f"RRF score {score:.4f} ≈ appears in ~{estimated_sources} list(s) (k={k})"
        )
