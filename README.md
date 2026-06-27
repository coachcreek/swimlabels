# swimlabels

Generate printable [Avery 5160](https://www.avery.com/products/labels/5160) award
labels for the Saybrook Sharks swim team from a meet's results PDF.

The script reads a results PDF, extracts each swimmer's placing, and lays the
results out as labels (3 across × 10 down per letter page) ready to print and
stick onto ribbons and award cards. Each run also saves the parsed results to
`data/` so they can be reported on later (see [Reporting](#reporting)).

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

Each run does two things:

- Writes the generated labels PDF to `output/<SEASON>/`, named after the input
  file with the `raw_` prefix replaced by `labels_` (combo meets are named
  `labels_combo_<codes>.pdf`).
- Saves the parsed results to `data/<SEASON>/<CODE>.json` for later reporting.

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
grouped by season. A meet may be configured two ways:

- **Plain string** — printed verbatim as the meet name.
- **Home/away mapping** — an `opponent` name plus a `home` boolean. The label
  reads `<opponent> @ Saybrook` when `home: true` and `Saybrook @ <opponent>`
  when `home: false`.

```yaml
seasons:
  2025:
    meets:
      ntc_dual: "Naperville Tennis Club"
      we_dual: "White Eagle"
  2026:
    meets:
      steeplerun_dual:
        opponent: "Steeple Run"
        home: true
      ccc_dual:
        opponent: "Cress Creek Commons"
        home: false
```

To add a meet for a new season, add an entry under that season's `meets:` and
drop the matching `raw_<CODE>.pdf` into `input/<SEASON>/`.

### Name corrections

The raw PDFs sometimes contain messy or ambiguous swimmer names. The
`corrections:` section of `config.yaml` fixes these without code changes:

- `names:` — exact-match replacements applied to any parsed first or last
  name. Names are stripped of surrounding whitespace before matching, so keys
  are the **trimmed** parsed value.
- `records:` — one-off overrides for a single result, matched on fields such
  as `meet_name_raw`, `event_name`, `last_name` and `first_name`; the `set:`
  block replaces the matched fields.

## Reporting

Past runs are saved to `data/<SEASON>/<CODE>.json`, and `report.py` reads those
files (no PDF re-parsing) to summarize award usage:

```bash
python3 report.py ribbons
```

The `ribbons` report prints, per meet, how many ribbons were handed out for
each place (1st–6th, for swimmers aged 12 & under) alongside a count of business
cards (any 1st–6th finish for ages 13 & up), with per-season totals and
averages. This makes it easy to compare prior full seasons against the current
year-to-date when ordering ribbons. Time trials are excluded from the report.

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

The `input/`, `output/`, `data/` and `tests/snapshots/` directories are all
gitignored, so the tests require the local `input/` PDFs to be present and will
generate their snapshots on first `--update`.
