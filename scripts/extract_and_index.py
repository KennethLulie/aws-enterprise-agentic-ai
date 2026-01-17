#!/usr/bin/env python3
"""
Document extraction batch script for VLM-based PDF processing.

This standalone script extracts structured data from PDF documents using
Claude Vision (via AWS Bedrock). It's designed to run locally and process
documents in batch with progress tracking, cost estimation, and graceful
interruption handling.

Usage:
    # Show help
    python scripts/extract_and_index.py --help

    # Check extraction status (no API calls)
    python scripts/extract_and_index.py --status

    # Dry run - list what would be processed
    python scripts/extract_and_index.py --dry-run

    # Extract all documents
    python scripts/extract_and_index.py

    # Extract only 10-K documents
    python scripts/extract_and_index.py --doc-types 10k

    # Force re-extraction of a single document
    python scripts/extract_and_index.py --doc AAPL_10K_2024 --force

Reference:
    - PHASE_2A_HOW_TO_GUIDE.md Section 5.3 for requirements
    - backend.mdc for Python patterns
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add backend/src to path for imports when running locally
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = PROJECT_ROOT / "backend"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    print("Warning: python-dotenv not installed. Using existing environment variables.")


# =============================================================================
# Dependency Checking (before importing heavy modules)
# =============================================================================


def check_dependencies() -> list[str]:
    """
    Check for required dependencies and return list of missing ones.

    Returns:
        List of error messages for missing dependencies.
    """
    errors: list[str] = []

    # Check Python packages
    required_packages = [
        ("structlog", "pip install structlog"),
        ("boto3", "pip install boto3"),
        ("pdf2image", "pip install pdf2image"),
        ("PIL", "pip install Pillow"),
        ("tenacity", "pip install tenacity"),
    ]

    for package, install_cmd in required_packages:
        try:
            __import__(package)
        except ImportError:
            errors.append(f"Missing Python package: {package} (install with: {install_cmd})")

    # Check poppler-utils (required by pdf2image)
    import shutil
    if not shutil.which("pdfinfo"):
        errors.append(
            "Missing system dependency: poppler-utils\n"
            "  Install with:\n"
            "    Ubuntu/Debian: sudo apt-get install poppler-utils\n"
            "    macOS: brew install poppler\n"
            "    Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases"
        )

    return errors


def check_aws_credentials() -> tuple[bool, str]:
    """
    Verify AWS credentials are configured and working.

    Returns:
        Tuple of (success, message).
    """
    try:
        import boto3
        sts = boto3.client("sts", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        identity = sts.get_caller_identity()
        return True, f"AWS credentials valid (Account: {identity['Account']})"
    except Exception as e:
        return False, f"AWS credentials error: {e}"


# Check dependencies before importing our modules
_dep_errors = check_dependencies()
if _dep_errors:
    print("\033[31mMissing dependencies:\033[0m")
    for err in _dep_errors:
        print(f"  - {err}")
    print("\nPlease install missing dependencies and try again.")
    sys.exit(1)

# Now import our modules (after dependency check passes)
from src.ingestion.document_processor import (
    DocumentProcessor,
    DocumentProcessingError,
    ESTIMATED_COST_PER_PAGE_10K,
    ESTIMATED_COST_PER_PAGE_REFERENCE,
)

# =============================================================================
# Constants
# =============================================================================

# Terminal colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Default paths relative to project root
DEFAULT_RAW_DIR = PROJECT_ROOT / "documents" / "raw"
DEFAULT_EXTRACTED_DIR = PROJECT_ROOT / "documents" / "extracted"

# Estimated pages per document for cost calculation
ESTIMATED_PAGES_10K = 100
ESTIMATED_PAGES_REFERENCE = 10


# =============================================================================
# Signal Handling
# =============================================================================

_interrupted = False


def _signal_handler(signum: int, frame: Any) -> None:
    """Handle interrupt signal gracefully."""
    global _interrupted
    if _interrupted:
        # Second interrupt - exit immediately
        print(f"\n{RED}Forced exit.{RESET}")
        sys.exit(1)
    _interrupted = True
    print(f"\n{YELLOW}Interrupt received. Finishing current document, then stopping...{RESET}")
    print(f"{YELLOW}Press Ctrl+C again to force exit.{RESET}")


# =============================================================================
# Output Formatting
# =============================================================================


def print_header(text: str) -> None:
    """Print a styled header."""
    print(f"\n{BOLD}{text}{RESET}")
    print("=" * len(text))


def print_status_header() -> None:
    """Print the status command header."""
    print(f"\n{BOLD}Document Extraction Status{RESET}")
    print("=" * 26)


def format_date(iso_date: str | None) -> str:
    """Format ISO date string for display."""
    if not iso_date:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return iso_date[:10] if iso_date else "N/A"


def format_cost(cost: float) -> str:
    """Format cost for display."""
    return f"${cost:.2f}"


# =============================================================================
# Status Command
# =============================================================================


def show_status(processor: DocumentProcessor) -> None:
    """Show extraction status from manifest."""
    print_status_header()

    manifest = processor.manifest
    documents = manifest.get("documents", {})
    totals = manifest.get("totals", {})

    # Extracted documents
    extracted = [
        (doc_id, doc)
        for doc_id, doc in documents.items()
        if doc.get("extracted_at")
    ]

    if extracted:
        print(f"\n{GREEN}Extracted: {len(extracted)} documents{RESET}")
        for doc_id, doc in sorted(extracted, key=lambda x: x[0]):
            pages = doc.get("pages_processed", 0)
            cost = doc.get("extraction_cost_usd", 0)
            date = format_date(doc.get("extracted_at"))
            print(f"  - {doc_id} ({pages} pages, {format_cost(cost)}, {date})")
    else:
        print(f"\n{YELLOW}Extracted: 0 documents{RESET}")

    # Pending documents (files in raw dir not in manifest)
    raw_dir = processor.raw_dir
    pending_files: list[tuple[str, str]] = []

    if raw_dir.exists():
        for pdf in sorted(raw_dir.glob("*.pdf")):
            if not pdf.is_file():
                continue
            doc_id = processor._get_document_id(pdf)
            if doc_id not in documents or not documents[doc_id].get("extracted_at"):
                pending_files.append((pdf.name, "new"))

    if pending_files:
        print(f"\n{YELLOW}Pending: {len(pending_files)} documents{RESET}")
        for filename, status in pending_files:
            print(f"  - {filename} ({status})")
    else:
        print(f"\n{GREEN}Pending: 0 documents{RESET}")

    # Cost summary
    total_cost = totals.get("total_extraction_cost_usd", 0)
    print(f"\n{CYAN}Total extraction cost so far: {format_cost(total_cost)}{RESET}")

    # Estimate pending cost
    if pending_files:
        estimated_pending_cost = 0.0
        for filename, _ in pending_files:
            doc_type = processor._detect_doc_type(filename)
            if doc_type == "10k":
                estimated_pending_cost += ESTIMATED_PAGES_10K * ESTIMATED_COST_PER_PAGE_10K
            else:
                estimated_pending_cost += ESTIMATED_PAGES_REFERENCE * ESTIMATED_COST_PER_PAGE_REFERENCE
        print(f"{CYAN}Estimated cost for pending: ~{format_cost(estimated_pending_cost)}{RESET}")

    print()


# =============================================================================
# Dry Run Command
# =============================================================================


def show_dry_run(
    processor: DocumentProcessor,
    doc_types: list[str] | None = None,
    force: bool = False,
    if_changed: bool = False,
) -> None:
    """Show what would be processed without actually processing."""
    print_header("Dry Run - Documents to Process")

    raw_dir = processor.raw_dir
    if not raw_dir.exists():
        print(f"{RED}Raw directory does not exist: {raw_dir}{RESET}")
        return

    # Find all PDF files
    pdf_files = [p for p in raw_dir.glob("*.pdf") if p.is_file()]

    if not pdf_files:
        print(f"{YELLOW}No PDF files found in {raw_dir}{RESET}")
        return

    # Filter by document type if specified
    if doc_types:
        doc_types_lower = [dt.lower() for dt in doc_types]
        pdf_files = [
            pdf for pdf in pdf_files
            if processor._detect_doc_type(pdf.name) in doc_types_lower
        ]

    # Check which would be processed
    would_process: list[tuple[Path, str]] = []
    would_skip: list[tuple[Path, str]] = []

    for pdf in sorted(pdf_files):
        try:
            should = processor.should_process(pdf, force=force, if_changed=if_changed)
            if should:
                doc_type = processor._detect_doc_type(pdf.name)
                would_process.append((pdf, doc_type))
            else:
                would_skip.append((pdf, "already extracted"))
        except DocumentProcessingError as e:
            would_skip.append((pdf, f"error: {e}"))

    # Display results
    if would_process:
        estimated_cost = 0.0
        print(f"\n{GREEN}Would process: {len(would_process)} documents{RESET}")
        for pdf, doc_type in would_process:
            if doc_type == "10k":
                est_cost = ESTIMATED_PAGES_10K * ESTIMATED_COST_PER_PAGE_10K
            else:
                est_cost = ESTIMATED_PAGES_REFERENCE * ESTIMATED_COST_PER_PAGE_REFERENCE
            estimated_cost += est_cost
            print(f"  - {pdf.name} ({doc_type}, ~{format_cost(est_cost)})")
        print(f"\n{CYAN}Estimated total cost: ~{format_cost(estimated_cost)}{RESET}")
    else:
        print(f"\n{YELLOW}No documents to process{RESET}")

    if would_skip:
        print(f"\n{BLUE}Would skip: {len(would_skip)} documents{RESET}")
        for pdf, reason in would_skip:
            print(f"  - {pdf.name} ({reason})")

    print()


# =============================================================================
# Process Single Document
# =============================================================================


async def process_single_document(
    processor: DocumentProcessor,
    doc_id: str,
    force: bool = False,
    if_changed: bool = False,
) -> dict[str, Any] | None:
    """Process a single document by ID."""
    # Find the PDF file
    raw_dir = processor.raw_dir
    matching_files = list(raw_dir.glob(f"{doc_id}*.pdf"))

    if not matching_files:
        # Try exact match with .pdf extension
        exact_path = raw_dir / f"{doc_id}.pdf"
        if exact_path.exists():
            matching_files = [exact_path]

    if not matching_files:
        print(f"{RED}No document found matching ID: {doc_id}{RESET}")
        print(f"Looked in: {raw_dir}")
        return None

    if len(matching_files) > 1:
        print(f"{YELLOW}Multiple documents match '{doc_id}':{RESET}")
        for f in matching_files:
            print(f"  - {f.name}")
        print(f"Using: {matching_files[0].name}")

    pdf_path = matching_files[0]
    actual_doc_id = processor._get_document_id(pdf_path)
    print(f"\n{BOLD}Processing {pdf_path.name}...{RESET}")

    try:
        result = await processor.process_document(
            pdf_path=pdf_path,
            force=force,
            if_changed=if_changed,
        )

        if result.get("skipped"):
            print(f"{YELLOW}  Skipped: {result.get('reason', 'already processed')}{RESET}")
        else:
            pages = result.get("pages_processed", 0)
            cost = result.get("estimated_cost_usd", 0)
            print(f"{GREEN}  Extracted {pages} pages{RESET}")
            print(f"  Saved to: {processor.extracted_dir / f'{actual_doc_id}.json'}")
            print(f"  Cost: {format_cost(cost)}")

        return result

    except DocumentProcessingError as e:
        print(f"{RED}  Failed: {e}{RESET}")
        return None


# =============================================================================
# Process All Documents
# =============================================================================


async def process_all_documents(
    processor: DocumentProcessor,
    doc_types: list[str] | None = None,
    force: bool = False,
    if_changed: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Process all documents with progress tracking."""
    global _interrupted

    raw_dir = processor.raw_dir
    if not raw_dir.exists():
        print(f"{RED}Raw directory does not exist: {raw_dir}{RESET}")
        return [], []

    # Find all PDF files
    pdf_files = [p for p in sorted(raw_dir.glob("*.pdf")) if p.is_file()]

    if not pdf_files:
        print(f"{YELLOW}No PDF files found in {raw_dir}{RESET}")
        return [], []

    # Filter by document type if specified
    if doc_types:
        doc_types_lower = [dt.lower() for dt in doc_types]
        pdf_files = [
            pdf for pdf in pdf_files
            if processor._detect_doc_type(pdf.name) in doc_types_lower
        ]

    # Count by type
    type_counts: dict[str, int] = {"10k": 0, "reference": 0}
    for pdf in pdf_files:
        doc_type = processor._detect_doc_type(pdf.name)
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

    type_str = ", ".join(f"{count} {dtype}" for dtype, count in type_counts.items() if count > 0)
    print(f"\n{BOLD}Processing {len(pdf_files)} documents ({type_str})...{RESET}\n")

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for i, pdf_path in enumerate(pdf_files, 1):
        if _interrupted:
            print(f"\n{YELLOW}Stopping after {i - 1} documents (interrupted){RESET}")
            break

        doc_id = processor._get_document_id(pdf_path)

        print(f"Processing {pdf_path.name}...")

        try:
            # Check if should process
            should = processor.should_process(pdf_path, force=force, if_changed=if_changed)
            if not should:
                print(f"  {BLUE}Skipped (already extracted){RESET}")
                # Load cached result
                cached_path = processor.extracted_dir / f"{doc_id}.json"
                if cached_path.exists():
                    with open(cached_path, encoding="utf-8") as f:
                        results.append(json.load(f))
                continue

            # Process the document
            result = await processor.process_document(
                pdf_path=pdf_path,
                force=force,
                if_changed=if_changed,
            )

            pages = result.get("pages_processed", 0)
            total_pages = result.get("total_pages", pages)
            cost = result.get("estimated_cost_usd", 0)

            # Show progress for each page (simulated - actual progress in VLMExtractor)
            print(f"  {GREEN}Extracted {pages}/{total_pages} pages{RESET}")
            print(f"  Saved to documents/extracted/{doc_id}.json")
            print(f"  Updated manifest (cost: {format_cost(cost)})")

            results.append(result)

        except DocumentProcessingError as e:
            print(f"  {RED}Failed: {e}{RESET}")
            errors.append({"file": pdf_path.name, "error": str(e)})

    return results, errors


# =============================================================================
# Summary
# =============================================================================


def print_summary(
    results: list[dict[str, Any]],
    errors: list[dict[str, str]],
    processor: DocumentProcessor,
) -> None:
    """Print final processing summary."""
    print_header("Summary")

    total_pages = sum(r.get("pages_processed", 0) for r in results)
    total_cost = sum(r.get("estimated_cost_usd", 0) for r in results)

    processed = len([r for r in results if not r.get("skipped")])
    skipped = len([r for r in results if r.get("skipped")])

    print(f"  Documents processed: {processed}")
    if skipped:
        print(f"  Documents skipped: {skipped}")
    print(f"  Total pages: {total_pages}")
    print(f"  Estimated cost: {format_cost(total_cost)}")

    if errors:
        print(f"\n{RED}  Failed documents: {len(errors)}{RESET}")
        for err in errors:
            print(f"    - {err['file']}: {err['error'][:50]}...")

    print(f"\n  Output directory: {processor.extracted_dir}")
    print(f"  Manifest: {processor.extracted_dir / 'manifest.json'}")
    print()


# =============================================================================
# Main
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract structured data from PDF documents using VLM (Claude Vision).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --status              Show extraction status (no API calls)
  %(prog)s --dry-run             List what would be processed
  %(prog)s                       Extract all pending documents
  %(prog)s --doc-types 10k       Extract only 10-K documents
  %(prog)s --doc AAPL_10K_2024   Extract a single document
  %(prog)s --force               Re-extract all documents
  %(prog)s --if-changed          Re-extract only if file content changed
        """,
    )

    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help=f"Path to raw PDF documents (default: {DEFAULT_RAW_DIR})",
    )
    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=DEFAULT_EXTRACTED_DIR,
        help=f"Path for extracted JSON output (default: {DEFAULT_EXTRACTED_DIR})",
    )
    parser.add_argument(
        "--doc-types",
        nargs="+",
        choices=["10k", "reference"],
        help="Filter by document type (10k, reference, or both)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if already in manifest",
    )
    parser.add_argument(
        "--if-changed",
        action="store_true",
        help="Re-extract only if file hash changed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List documents without processing (shows what would be extracted)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show manifest status and exit (no API calls)",
    )
    parser.add_argument(
        "--doc",
        type=str,
        metavar="DOC_ID",
        help="Process single document by ID (e.g., AAPL_10K_2024)",
    )

    return parser.parse_args()


async def async_main(args: argparse.Namespace) -> int:
    """Async main function."""
    # Initialize processor
    print(f"{CYAN}Initializing DocumentProcessor...{RESET}")
    print(f"  Raw directory: {args.raw_dir}")
    print(f"  Extracted directory: {args.extracted_dir}")

    try:
        processor = DocumentProcessor(
            raw_dir=args.raw_dir,
            extracted_dir=args.extracted_dir,
        )
    except Exception as e:
        print(f"{RED}Failed to initialize DocumentProcessor: {e}{RESET}")
        return 1

    # Handle --status command
    if args.status:
        show_status(processor)
        return 0

    # Handle --dry-run command
    if args.dry_run:
        show_dry_run(
            processor,
            doc_types=args.doc_types,
            force=args.force,
            if_changed=args.if_changed,
        )
        return 0

    # Handle --doc command (single document)
    if args.doc:
        result = await process_single_document(
            processor,
            doc_id=args.doc,
            force=args.force,
            if_changed=args.if_changed,
        )
        return 0 if result else 1

    # Process all documents
    results, errors = await process_all_documents(
        processor,
        doc_types=args.doc_types,
        force=args.force,
        if_changed=args.if_changed,
    )

    # Print summary
    print_summary(results, errors, processor)

    return 1 if errors else 0


def main() -> int:
    """Main entry point."""
    # Set up signal handler for graceful interruption
    signal.signal(signal.SIGINT, _signal_handler)

    # Parse arguments
    args = parse_args()

    # Check if raw directory exists
    if not args.raw_dir.exists():
        print(f"{RED}Error: Raw documents directory not found: {args.raw_dir}{RESET}")
        print(f"\nTo fix this:")
        print(f"  1. Create the directory: mkdir -p {args.raw_dir}")
        print(f"  2. Add PDF files to extract")
        print(f"  3. Run this script again")
        return 1

    # Check if raw directory has any PDFs
    pdf_files = list(args.raw_dir.glob("*.pdf"))
    if not pdf_files and not args.status:
        print(f"{YELLOW}Warning: No PDF files found in {args.raw_dir}{RESET}")
        print(f"\nTo extract documents:")
        print(f"  1. Add PDF files to {args.raw_dir}")
        print(f"  2. Name 10-K filings like: TICKER_10K_YEAR.pdf (e.g., AAPL_10K_2024.pdf)")
        print(f"  3. Run this script again")
        if not args.status:
            return 0  # Not an error, just nothing to do

    # Verify AWS credentials (skip for --status which doesn't need API calls)
    if not args.status and not args.dry_run:
        # Check environment variables first
        if not os.getenv("AWS_ACCESS_KEY_ID") and not os.getenv("AWS_PROFILE"):
            print(f"{YELLOW}Warning: AWS credentials not found in environment.{RESET}")
            print("Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or AWS_PROFILE.")

        # Verify credentials actually work
        print(f"{CYAN}Verifying AWS credentials...{RESET}")
        creds_ok, creds_msg = check_aws_credentials()
        if creds_ok:
            print(f"  {GREEN}✓ {creds_msg}{RESET}")
        else:
            print(f"  {RED}✗ {creds_msg}{RESET}")
            print(f"\nTo fix this:")
            print(f"  1. Check your AWS credentials in .env or environment")
            print(f"  2. Ensure you have access to AWS Bedrock in us-east-1")
            print(f"  3. Run: aws sts get-caller-identity (to verify credentials)")
            return 1

    # Run async main
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted.{RESET}")
        return 130  # Standard exit code for SIGINT


if __name__ == "__main__":
    sys.exit(main())
