# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "pytest",
# ]
# ///

"""Tests for extract_pdf parsing logic."""

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Stub out docling so extract_pdf can be imported without it
if "docling" not in sys.modules:
    docling_stub = types.ModuleType("docling")
    docling_dc = types.ModuleType("docling.document_converter")
    docling_dc.DocumentConverter = MagicMock()
    sys.modules["docling"] = docling_stub
    sys.modules["docling.document_converter"] = docling_dc

# Add parent directory to path so we can import extract_pdf
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import patch

import pandas as pd
import pytest

extract_pdf = importlib.import_module("extract_pdf")
extract_table_blocks = extract_pdf.extract_table_blocks
parse_amount = extract_pdf.parse_amount
parse_statement_date = extract_pdf.parse_statement_date
parse_transaction_table = extract_pdf.parse_transaction_table
process_pdf = extract_pdf.process_pdf



# -- Parse Statement Date --------------------
@pytest.mark.parametrize(
    "block, expected",
    [
        ("| MR JOHN DOE STATEMENT DATE: March 22, 2025 | 1 OF 4 |", (2025, 3, 22)),
        ("| MR JOHN DOE STATEMENT DATE: January 1, 1990 | 1 OF 4 |", (1990, 1, 1)),
        ("| MR JOHN DOE STATEMENT DATE: December 31, 2026 | 1 OF 4 |", (2026, 12, 31)),
    ],
)
def test_parse_statement_date(block, expected):
    blocks = [block]
    statement_date = parse_statement_date(blocks)
    assert (statement_date.year, statement_date.month, statement_date.day) == expected


def test_parse_statement_date_missing():
    blocks = [
        "| TRANSACTION DATE | POSTING DATE | ACTIVITY DESCRIPTION | AMOUNT($) |",
        "| some | other | table | data |",
    ]
    with pytest.raises(ValueError, match="Could not find STATEMENT DATE"):
        parse_statement_date(blocks)


# -- Parse Amount ----------------------------
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("$19.99", 19.99),
        ("$1,524.37", 1524.37),
        ("-$10.00", -10.00),
        ("$0.00", 0.0),
        ("$666.66", 666.66),
        ("", None),
        ("  ", None),
        ("N/A", None),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


# -- Year Transition -------------------------
YEAR_TRANSITION_MD = """\
<!-- tag -->

## Title

| MR JOHN DOE 1234 11XX XXXX 1234 STATEMENT DATE: January 15, 2026   | 1 OF 4   |
|---------------------------------------------------------------------|----------|
| PREVIOUS STATEMENT: December 15, 2025                               |          |
| STATEMENT PERIOD: December 15, 2025 to January 15, 2026             |          |

| TRANSACTION DATE   | POSTING DATE   | ACTIVITY DESCRIPTION                | AMOUNT($)   |
|--------------------|----------------|-------------------------------------|-------------|
|                    |                | PREVIOUS STATEMENT BALANCE          | $666.66     |
| DEC 20             | DEC 22         | IKEA                                | $19.99      |
| DEC 31             | JAN 2          | COFFEE ROASTERS                     | $12.34      |

Text

| TRANSACTION DATE   | POSTING DATE   | ACTIVITY DESCRIPTION                | AMOUNT($)   |
|--------------------|----------------|-------------------------------------|-------------|
| JAN 5              | JAN 5          | GROCERY STORE                       | $45.00      |
"""


def test_year_transition():
    blocks = extract_table_blocks(YEAR_TRANSITION_MD)
    statement_date = parse_statement_date(blocks)

    assert statement_date.year == 2026
    assert statement_date.month == 1

    frames = [parse_transaction_table(block, statement_date) for block in blocks]
    frames = [df for df in frames if not df.empty]
    combined = pd.concat(frames, ignore_index=True)

    # DEC 20 transaction should be in 2025 (prior year)
    dec20 = combined[combined["description"] == "IKEA"].iloc[0]
    assert dec20["transaction_date"] == pd.Timestamp(2025, 12, 20)

    # DEC 31 transaction date in 2025, but JAN 2 posting date in 2026
    dec31 = combined[combined["description"] == "COFFEE ROASTERS"].iloc[0]
    assert dec31["transaction_date"] == pd.Timestamp(2025, 12, 31)
    assert dec31["posting_date"] == pd.Timestamp(2026, 1, 2)

    # JAN 5 transaction stays in 2026
    jan5 = combined[combined["description"] == "GROCERY STORE"].iloc[0]
    assert jan5["transaction_date"] == pd.Timestamp(2026, 1, 5)


# -- Process PDF -----------------------------
SAMPLE_MD = """\
| MR JOHN DOE STATEMENT DATE: August 01, 2025 | 1 OF 4 |
|----------------------------------------------|--------|

| TRANSACTION DATE | POSTING DATE | ACTIVITY DESCRIPTION | AMOUNT($) |
|------------------|--------------|----------------------|-----------|
| JUL 20           | JUL 22       | IKEA                 | $19.99    |
| AUG 1            | AUG 2        | COFFEE ROASTERS      | $12.34    |
"""


@patch.object(extract_pdf, "extract_markdown", return_value=SAMPLE_MD)
def test_process_pdf(mock_extract):
    df = process_pdf("fake.pdf")
    mock_extract.assert_called_once_with("fake.pdf")
    assert len(df) == 2
    assert list(df["description"]) == ["IKEA", "COFFEE ROASTERS"]
    assert list(df["amount"]) == [19.99, 12.34]
    assert df.iloc[0]["transaction_date"] == pd.Timestamp(2025, 7, 20)
    assert df.iloc[1]["posting_date"] == pd.Timestamp(2025, 8, 2)


@patch.object(extract_pdf, "extract_markdown", return_value="No tables here.")
def test_process_pdf_no_tables(mock_extract):
    with pytest.raises(ValueError, match="Could not find STATEMENT DATE"):
        process_pdf("empty.pdf")
