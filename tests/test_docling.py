# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "docling",
#     "pandas",
#     "pytest",
# ]
# ///

"""Slow integration tests that require docling."""

import sys
from pathlib import Path

# Add parent directory to path so we can import extract_pdf
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extract_pdf import (
    extract_markdown,
    extract_table_blocks,
    parse_statement_date,
    process_pdf,
)

TESTS_DIR = Path(__file__).resolve().parent


def test_extract_markdown():
    pdf_path = str(TESTS_DIR / "doc.pdf")
    md = extract_markdown(pdf_path)
    blocks = extract_table_blocks(md)
    statement_date = parse_statement_date(blocks)

    assert statement_date.year == 2026
    assert statement_date.month == 1
    assert statement_date.day == 15

    assert "IKEA" in md
    assert "COFFEE ROASTERS" in md
    assert "GROCERY STORE" in md


def test_process_pdf_integration():
    pdf_path = str(TESTS_DIR / "doc.pdf")
    df = process_pdf(pdf_path)

    assert len(df) == 4
    assert "IKEA" in df["description"].values
    assert "COFFEE ROASTERS" in df["description"].values
    assert "GROCERY STORE" in df["description"].values
