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

The generated PDF is written to `output/`, named after the input file with the
`raw_` prefix replaced by `labels_`.

## Input files

Place the raw meet results PDF in `input/`, named `raw_<CODE>.pdf` — for
example `raw_ntc_dual.pdf`. The script globs `input/raw_<CODE>*.pdf`, so a
**combo meet** can be produced by dropping multiple matching files (e.g.
`raw_ccc_dual.pdf` and `raw_mb2_dual.pdf`); their labels are merged into a
single `labels_combo_*.pdf`.

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
drop the matching `raw_<CODE>.pdf` into `input/`.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install PyPDF2 reportlab pyyaml
```
