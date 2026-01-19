#!/usr/bin/env python3
"""
RAG diagnostic script for inspecting Pinecone index and testing retrieval.

This script helps debug RAG retrieval issues by:
1. Showing Pinecone index statistics
2. Inspecting metadata of indexed vectors
3. Testing retrieval with specific queries
4. Comparing expected vs actual results

Usage:
    # Show index stats and sample vectors
    python scripts/rag_diagnostic.py --stats

    # Inspect vectors for a specific document
    python scripts/rag_diagnostic.py --inspect "2026_NVIDIA_Strategic_Analysis"

    # Test retrieval with a query
    python scripts/rag_diagnostic.py --query "NVIDIA VRAM unbundling strategy"

    # Run all diagnostic tests
    python scripts/rag_diagnostic.py --all

Requirements:
    - PINECONE_API_KEY and PINECONE_INDEX_NAME in environment
    - AWS credentials for Bedrock embeddings
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Add backend to path for imports
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_env() -> None:
    """Load environment variables from .env file."""
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def get_pinecone_client():
    """Initialize and return Pinecone client."""
    from src.utils.pinecone_client import PineconeClient
    return PineconeClient()


def get_embeddings_client():
    """Initialize and return embeddings client."""
    from src.utils.embeddings import BedrockEmbeddings
    return BedrockEmbeddings()


def print_stats(client) -> None:
    """Print Pinecone index statistics."""
    print(f"\n{BOLD}{CYAN}=== Pinecone Index Statistics ==={RESET}\n")

    try:
        stats = client.get_stats()
        print(f"  Total vectors: {GREEN}{stats['total_vector_count']}{RESET}")
        print(f"  Dimension: {stats['dimension']}")
        print(f"  Index fullness: {stats.get('index_fullness', 0):.2%}")

        if stats.get("namespaces"):
            print(f"\n  Namespaces:")
            for ns, ns_stats in stats["namespaces"].items():
                ns_name = ns if ns else "(default)"
                print(f"    - {ns_name}: {ns_stats.get('vector_count', 0)} vectors")
    except Exception as e:
        print(f"{RED}Error getting stats: {e}{RESET}")


def inspect_document(client, doc_id_prefix: str, limit: int = 5) -> None:
    """Inspect vectors for a specific document."""
    print(f"\n{BOLD}{CYAN}=== Inspecting Vectors for '{doc_id_prefix}' ==={RESET}\n")

    # We need to query to find vectors - Pinecone doesn't support listing by metadata
    # So we'll do a dummy query and filter
    try:
        embeddings = get_embeddings_client()

        # Create a dummy query that should match broadly
        dummy_query = "document content"

        async def get_embedding():
            return await embeddings.embed_text(dummy_query)

        query_vector = asyncio.run(get_embedding())

        # Query with document_id filter
        results = client.query(
            vector=query_vector,
            top_k=limit * 3,  # Get more to filter
            filter={"document_id": {"$eq": doc_id_prefix}} if doc_id_prefix else None,
            include_metadata=True,
        )

        if not results:
            # Try partial match by querying all and filtering
            results = client.query(
                vector=query_vector,
                top_k=50,
                include_metadata=True,
            )
            results = [r for r in results if doc_id_prefix.lower() in r.get("id", "").lower()]

        if not results:
            print(f"{YELLOW}No vectors found matching '{doc_id_prefix}'{RESET}")
            return

        print(f"Found {len(results)} vectors (showing up to {limit}):\n")

        for i, result in enumerate(results[:limit], 1):
            metadata = result.get("metadata", {})
            print(f"{BOLD}[{i}] Vector ID:{RESET} {result['id']}")
            print(f"    Score: {result.get('score', 'N/A'):.4f}")
            print(f"    {BLUE}Metadata:{RESET}")

            # Key metadata fields to show
            key_fields = [
                "document_id", "document_type", "parent_id",
                "source_name", "source_type", "headline", "publication_date",
                "ticker", "fiscal_year", "section", "page_number"
            ]

            for field in key_fields:
                value = metadata.get(field)
                if value is not None:
                    # Truncate long values
                    str_value = str(value)
                    if len(str_value) > 60:
                        str_value = str_value[:57] + "..."
                    print(f"      {field}: {GREEN}{str_value}{RESET}")
                else:
                    print(f"      {field}: {YELLOW}(not set){RESET}")

            # Show text preview
            parent_text = metadata.get("parent_text", "")
            if parent_text:
                preview = parent_text[:150].replace("\n", " ")
                print(f"    {BLUE}Text preview:{RESET} {preview}...")

            print()

    except Exception as e:
        print(f"{RED}Error inspecting document: {e}{RESET}")
        import traceback
        traceback.print_exc()


async def test_query(client, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Test a RAG query and show results."""
    print(f"\n{BOLD}{CYAN}=== Testing Query ==={RESET}")
    print(f"Query: \"{query}\"\n")

    try:
        embeddings = get_embeddings_client()

        # Embed query
        print(f"  Generating embedding...")
        query_vector = await embeddings.embed_text(query)

        # Query Pinecone
        print(f"  Querying Pinecone (top_k={top_k})...")
        results = client.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
        )

        if not results:
            print(f"\n{YELLOW}No results found for this query.{RESET}")
            return []

        print(f"\n{GREEN}Found {len(results)} results:{RESET}\n")

        for i, result in enumerate(results, 1):
            metadata = result.get("metadata", {})
            score = result.get("score", 0)

            # Determine source info
            doc_type = metadata.get("document_type", "unknown")
            if doc_type == "10k":
                source = f"{metadata.get('ticker', '?')} 10-K {metadata.get('fiscal_year', '?')}"
            else:
                source = metadata.get("source_name") or metadata.get("document_id", "Unknown")
                headline = metadata.get("headline")
                if headline:
                    source = f"{source}: {headline[:50]}..."

            # Score color based on relevance
            if score >= 0.8:
                score_color = GREEN
            elif score >= 0.6:
                score_color = YELLOW
            else:
                score_color = RED

            print(f"{BOLD}[{i}]{RESET} {score_color}Score: {score:.4f}{RESET}")
            print(f"    Source: {source}")
            print(f"    Section: {metadata.get('section', 'N/A')}, Page: {metadata.get('page_number', '?')}")

            # Show matched text preview
            child_text = metadata.get("child_text_raw", metadata.get("child_text", ""))
            if child_text:
                preview = child_text[:200].replace("\n", " ")
                print(f"    Preview: {preview}...")

            print()

        return results

    except Exception as e:
        print(f"{RED}Error testing query: {e}{RESET}")
        import traceback
        traceback.print_exc()
        return []


def run_diagnostic_tests(client) -> None:
    """Run a suite of diagnostic tests."""
    print(f"\n{BOLD}{CYAN}=== Running Diagnostic Tests ==={RESET}\n")

    # Test queries that should return our news articles
    test_queries = [
        ("NVIDIA VRAM unbundling strategy 2026", "NVIDIA Strategic Analysis"),
        ("global memory shortage crisis impact on smartphones", "IDC Memory Shortage"),
        ("GDDR7 memory supply constraints GPU", "NVIDIA Strategic Analysis"),
        ("AI data center memory demand DRAM", "IDC Memory Shortage"),
        ("RTX 50 series GPU allocation", "NVIDIA Strategic Analysis"),
    ]

    results_summary = []

    for query, expected_source in test_queries:
        print(f"\n{BOLD}Test:{RESET} \"{query}\"")
        print(f"Expected to find: {expected_source}")

        results = asyncio.run(test_query(client, query, top_k=3))

        if results:
            top_result = results[0]
            top_metadata = top_result.get("metadata", {})
            top_doc_id = top_metadata.get("document_id", "")
            top_score = top_result.get("score", 0)

            # Check if expected source is in results
            found_expected = any(
                expected_source.lower() in r.get("metadata", {}).get("document_id", "").lower()
                for r in results
            )

            if found_expected and top_score >= 0.6:
                status = f"{GREEN}PASS{RESET}"
            elif found_expected:
                status = f"{YELLOW}WEAK{RESET}"
            else:
                status = f"{RED}FAIL{RESET}"

            results_summary.append((query, status, top_score, top_doc_id))
        else:
            results_summary.append((query, f"{RED}NO RESULTS{RESET}", 0, "N/A"))

    # Print summary
    print(f"\n{BOLD}{CYAN}=== Test Summary ==={RESET}\n")
    for query, status, score, doc_id in results_summary:
        print(f"  [{status}] Score: {score:.3f} | {query[:50]}...")
        print(f"         Top result: {doc_id[:60]}")


def main():
    parser = argparse.ArgumentParser(
        description="RAG diagnostic tool for Pinecone inspection and query testing"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show Pinecone index statistics"
    )
    parser.add_argument(
        "--inspect", type=str, metavar="DOC_ID",
        help="Inspect vectors for a document (partial match supported)"
    )
    parser.add_argument(
        "--query", type=str, metavar="QUERY",
        help="Test RAG retrieval with a query"
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="Number of results to return for queries (default: 5)"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all diagnostic tests"
    )

    args = parser.parse_args()

    # Load environment
    load_env()

    # Check for required env vars
    if not os.environ.get("PINECONE_API_KEY"):
        print(f"{RED}Error: PINECONE_API_KEY not set{RESET}")
        print("Set it in backend/.env or as an environment variable")
        sys.exit(1)

    # Initialize client
    print(f"{CYAN}Initializing Pinecone client...{RESET}")
    try:
        client = get_pinecone_client()
        print(f"{GREEN}✓ Connected to Pinecone{RESET}")
    except Exception as e:
        print(f"{RED}Failed to connect: {e}{RESET}")
        sys.exit(1)

    # Run requested operations
    if args.stats or args.all:
        print_stats(client)

    if args.inspect:
        inspect_document(client, args.inspect, limit=args.top_k)

    if args.query:
        asyncio.run(test_query(client, args.query, top_k=args.top_k))

    if args.all:
        run_diagnostic_tests(client)

    # If no specific action, show stats
    if not any([args.stats, args.inspect, args.query, args.all]):
        print_stats(client)
        print(f"\n{YELLOW}Tip: Use --help to see available options{RESET}")


if __name__ == "__main__":
    main()
