# swimlabels

Generate printable [Avery 5160](https://www.avery.com/products/labels/5160) award
labels for the Saybrook Sharks swim team from a meet's results PDF.

The script reads a results PDF, extracts each swimmer's placing, and lays the
results out as labels (3 across × 10 down per letter page) ready to print and
stick onto ribbons and award cards.

## Usage

```bash
python3 swimlabels.py CODE [--season YEAR]
```

- `CODE` — the meet code, e.g. `ntc_dual`. Must match a meet in `config.yaml`
  and a matching input file in `input/` (see below).
- `--season YEAR` — the season to look up in `config.yaml`. Defaults to the
  current calendar year.

Examples:

```bash
# Use the current season
python3 swimlabels.py ntc_dual

# Generate labels for a past season
python3 swimlabels.py ntc_dual --season 2025
```

The generated PDF is written to `output/<SEASON>/`, named after the input file
with the `raw_` prefix replaced by `labels_`.

## Input files

Input and output are organized into per-season subdirectories (e.g.
`input/2025/`, `input/2026/`). Place the raw meet results PDF in
`input/<SEASON>/`, named `raw_<CODE>.pdf` — for example
`input/2026/raw_ntc_dual.pdf`. The script globs
`input/<SEASON>/raw_<CODE>*.pdf`, so a **combo meet** can be produced by
dropping multiple matching files (e.g. `raw_ccc_dual.pdf` and
`raw_mb2_dual.pdf`); their labels are merged into a single `labels_combo_*.pdf`.

The meet date and the meet name as it appears in the results are read directly
from the PDF, so they do not need to be configured.

## Configuration

`config.yaml` maps each meet code to the clean meet name printed on the label,
grouped by season:

```yaml
seasons:
  2025:
    meets:
      ntc_dual: "SAY @ NTC"
      we_dual: "White Eagle"
  2026:
    meets: {}
```

To add a meet for a new season, add an entry under that season's `meets:` and
drop the matching `raw_<CODE>.pdf` into `input/<SEASON>/`.

### Name corrections

The raw PDFs sometimes contain messy or ambiguous swimmer names. The
`corrections:` section of `config.yaml` fixes these without code changes:

- `names:` — exact-match replacements applied to any parsed first or last
  name. Keys must reproduce the parsed value **including trailing spaces**.
- `records:` — one-off overrides for a single result, matched on fields such
  as `meet_name_raw`, `event_name`, `last_name` and `first_name`; the `set:`
  block replaces the matched fields.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install PyPDF2 reportlab pyyaml
```

## Tests

Characterization tests pin the parser output against snapshots of the real
meet PDFs, so refactors that change parsing get caught:

```bash
python3 -m unittest tests.test_parsing

# Regenerate snapshots after an intentional parser change:
python3 tests/test_parsing.py --update
```

The source PDFs are gitignored, so the tests require the local `input/` files.
