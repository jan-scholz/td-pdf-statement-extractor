# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "docling",
#     "pandas",
# ]
# ///

"""Extract transactions from TD credit card statement PDFs to CSV."""

import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from docling.document_converter import DocumentConverter


def extract_markdown(pdf_path: str) -> str:
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    return result.document.export_to_markdown()


def extract_table_blocks(markdown: str) -> list[str]:
    """Split on empty lines, keep blocks where first char is '|'."""
    blocks = re.split(r"\n\s*\n", markdown)
    return [b.strip() for b in blocks if b.strip().startswith("|")]


def parse_statement_date(blocks: list[str]) -> datetime:
    """Find and parse 'STATEMENT DATE: Month DD, YYYY' from table blocks."""
    for block in blocks:
        m = re.search(r"STATEMENT DATE:\s*(\w+ \d{1,2},\s*\d{4})", block)
        if m:
            return datetime.strptime(m.group(1), "%B %d, %Y")
    raise ValueError("Could not find STATEMENT DATE in any table block")


def parse_transaction_date(raw: str, statement_date: datetime) -> pd.Timestamp | None:
    """Parse 'MON DD' like 'DEC 23' into a full date using statement year."""
    raw = raw.strip()
    if not raw:
        return None
    # Insert space between month and day if missing (e.g. "MAY1" -> "MAY 1")
    raw = re.sub(r"^([A-Za-z]{3})(\d)", r"\1 \2", raw)
    try:
        parsed = datetime.strptime(f"{raw} 2000", "%b %d %Y")
    except ValueError:
        return None
    year = statement_date.year
    # If statement is in Jan/Feb/Mar and transaction is in Oct/Nov/Dec, use prior year
    if statement_date.month <= 3 and parsed.month >= 10:
        year -= 1
    return pd.Timestamp(year=year, month=parsed.month, day=parsed.day)


def parse_amount(raw: str) -> float | None:
    """Parse '$1,524.37' or '-$10.00' into a float."""
    raw = raw.strip()
    if not raw:
        return None
    cleaned = raw.replace("$", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_transaction_table(block: str, statement_date: datetime) -> pd.DataFrame:
    """Parse a markdown transaction table into a DataFrame."""
    lines = block.strip().splitlines()
    rows = []
    for line in lines:
        # Skip separator rows
        if re.match(r"\|[-\s|]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return pd.DataFrame()

    # First row is header
    header = [h.upper().strip() for h in rows[0]]
    if "TRANSACTION DATE" not in header:
        return pd.DataFrame()

    data_rows = []
    for row in rows[1:]:
        if len(row) < len(header):
            row.extend([""] * (len(header) - len(row)))
        record = dict(zip(header, row))

        amount = parse_amount(record.get("AMOUNT($)", ""))
        if amount is None:
            continue

        data_rows.append(
            {
                "transaction_date": parse_transaction_date(
                    record.get("TRANSACTION DATE", ""), statement_date
                ),
                "posting_date": parse_transaction_date(
                    record.get("POSTING DATE", ""), statement_date
                ),
                "description": record.get("ACTIVITY DESCRIPTION", "").strip(),
                "amount": amount,
            }
        )

    return pd.DataFrame(data_rows)


def process_pdf(pdf_path: str, debug: bool = False) -> pd.DataFrame:
    """Extract and parse all transactions from a single PDF."""
    print(f"Processing {pdf_path} ...", file=sys.stderr)
    markdown = extract_markdown(pdf_path)
    blocks = extract_table_blocks(markdown)
    statement_date = parse_statement_date(blocks)
    print(f"  Statement date: {statement_date.date()}", file=sys.stderr)

    frames = []
    for i, block in enumerate(blocks):
        if debug:
            print(f"\n--- Table block {i} ---\n{block}\n", file=sys.stderr)
        df = parse_transaction_table(block, statement_date)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_files", nargs="+", help="PDF files to process")
    parser.add_argument("--save", metavar="FILE", help="save CSV to FILE")
    parser.add_argument(
        "--debug", action="store_true", help="print table blocks to stderr"
    )
    args = parser.parse_args()

    all_frames = []
    for pdf_path in args.pdf_files:
        if not Path(pdf_path).exists():
            print(f"Error: {pdf_path} not found", file=sys.stderr)
            continue
        df = process_pdf(pdf_path, debug=args.debug)
        if not df.empty:
            df["source_file"] = Path(pdf_path).name
            all_frames.append(df)

    if not all_frames:
        print("No transactions found.", file=sys.stderr)
        sys.exit(1)

    combined = pd.concat(all_frames, ignore_index=True)
    for col in ("transaction_date", "posting_date"):
        combined[col] = pd.to_datetime(combined[col]).dt.date

    if args.save:
        out = Path(args.save)
        combined.to_csv(out)
        print(f"\nSaved {len(combined)} transactions to {out}", file=sys.stderr)
    else:
        print(combined.to_csv())


if __name__ == "__main__":
    main()
