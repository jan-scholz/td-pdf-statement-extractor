# TD Credit Card Statement PDF Extractor

![python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) ![coverage: 90%](https://img.shields.io/badge/coverage-90%25-brightgreen)

Extracts transactions from TD credit card statement PDFs into CSV.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)


## Usage

Run directly from GitHub (no clone needed):

```sh
uv run https://raw.githubusercontent.com/jan-scholz/td-pdf-statement-extractor/refs/heads/main/extract_pdf.py *.pdf
```

Or from a local copy:

```sh
uv run extract_pdf.py *.pdf
```

Save to a file:

```sh
uv run extract_pdf.py *.pdf --save transactions.csv
```

Print table blocks to stderr for debugging:

```sh
uv run extract_pdf.py *.pdf --debug
```

## Tests

Fast unit tests (no docling required):

```sh
uv run --with pytest,pandas python -m pytest tests/test_extract_pdf.py -v
```

All tests (including slow ones that depend on actual docling library):

```sh
uv run --with pytest,pandas,docling python -m pytest tests/ -v
```

Coverage report (HTML):

```sh
uv run --with pytest,pandas,pytest-cov,docling python -m pytest tests/ --cov=extract_pdf --cov-report=html
open htmlcov/index.html
```

Rebuild the test PDF fixture (requires [pandoc](https://pandoc.org/)):

```sh
pandoc -o tests/doc.pdf tests/doc.md
```

# Dependencies

Dependencies `docling` and `pandas` are declared inline in the script and managed automatically by `uv run`. [Docling](https://github.com/DS4SD/docling) for PDF-to-markdown conversion was the only PDF extractor that was able to extract transaction tables consistently.
