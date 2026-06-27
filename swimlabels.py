#!/usr/bin/env python3
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import yaml
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from parsing import clean_non_ascii, extract_meet_info, extract_text, parse_text

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"
DATA_DIR = Path(__file__).parent / "data"
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def sort_data(data: list[dict]) -> list[dict]:
    return sorted(data, key=lambda x: (x["age_type"], x["gender"], x["last_name"], x["first_name"]))


def save_results(
    data: list[dict],
    season: int,
    meet_code: str,
    meet_clean: str,
    source_pdfs: list[str],
) -> Path:
    """Persist parsed results as JSON at ``data/<season>/<meet_code>.json``.

    The file holds a small header (meet identity and provenance) plus the full
    list of parsed result records, so it can later be loaded back for
    cross-meet querying without re-running the PDF parser.
    """
    meet_date = data[0]["meet_date"] if data else None
    record = {
        "season": season,
        "meet_code": meet_code,
        "meet_name": meet_clean,
        "meet_date": meet_date,
        "source_pdfs": source_pdfs,
        "parsed_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "results": data,
    }

    season_data_dir = DATA_DIR / str(season)
    season_data_dir.mkdir(parents=True, exist_ok=True)
    out_path = season_data_dir / f"{meet_code}.json"
    with open(out_path, "w") as f:
        json.dump(record, f, indent=2)
    return out_path


def load_all_results(season: int | None = None) -> list[dict]:
    """Load saved results, flattened to one record per swimmer result.

    Each returned record is the stored per-result dict augmented with the
    meet-level ``season`` and ``meet_code`` so the combined list can be
    filtered across meets and seasons (e.g. one swimmer's history, best times).
    Pass ``season`` to restrict the load to a single season.
    """
    if season is not None:
        files = sorted((DATA_DIR / str(season)).glob("*.json"))
    else:
        files = sorted(DATA_DIR.glob("*/*.json"))

    results = []
    for path in files:
        with open(path) as f:
            meet = json.load(f)
        for result in meet.get("results", []):
            results.append({
                **result,
                "season": meet.get("season"),
                "meet_code": meet.get("meet_code"),
            })
    return results


def create_pdf(sorted_data: list[dict], output_path: Path) -> None:
    label_width = 2.625 * inch
    label_height = 1.0375 * inch
    margin_left = 0.25 * inch
    margin_top = 0.5 * inch
    horizontal_gap = 0.25 * inch
    vertical_gap = 0.0 * inch
    text_height = 0.15 * inch

    c = canvas.Canvas(str(output_path), pagesize=letter)
    c.setFont("Times-Roman", 8)

    x = margin_left
    y = letter[1] - margin_top

    for i, entry in enumerate(sorted_data):
        lines = [
            f"Heat: {entry['heat']}  Place: {entry['place']}  Time: {entry['time']}",
            f"{entry['event_num']}  {entry['gender']}  {entry['age']}  {entry['event_name']}",
            f"{entry['last_name']}, {entry['first_name']}",
            f"Saybrook Sharks - {entry['meet_date']}",
            entry["meet_name_clean"],
        ]
        y_line = y
        for line in lines:
            c.drawString(x, y_line, line)
            y_line -= text_height

        if (i + 1) % 3 == 0:
            x = margin_left
            y -= (label_height + vertical_gap)
            if (i + 1) % 30 == 0:
                c.showPage()
                c.setFont("Times-Roman", 8)
                y = letter[1] - margin_top
        else:
            x += (label_width + horizontal_gap)

    c.save()


def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def format_meet_name(meet_config) -> str:
    """Build the clean meet name printed on the label's last line.

    A meet may be configured either as a plain string (printed verbatim) or as
    a mapping with an ``opponent`` name and a ``home`` boolean. For the mapping
    form the line reads ``{opponent} @ Saybrook`` when home and
    ``Saybrook @ {opponent}`` when away.
    """
    if isinstance(meet_config, str):
        return meet_config

    opponent = meet_config["opponent"]
    if meet_config.get("home"):
        return f"{opponent} @ Saybrook"
    return f"Saybrook @ {opponent}"


def generate_output_filename(input_filenames: list[str]) -> str:
    """Generate output filename from input filename(s) by replacing 'raw_' with 'labels_'."""
    if len(input_filenames) == 1:
        return input_filenames[0].replace("raw_", "labels_")

    # For combo meets, extract meet codes and join them
    meet_codes = []
    for filename in sorted(input_filenames):
        match = re.search(r'raw_(.+?)(?:_dual|_trial|\.pdf)', filename)
        if match:
            meet_codes.append(match.group(1))

    suffix = ""
    match = re.search(r'((?:_dual|_trial)?\.pdf)$', input_filenames[0])
    if match:
        suffix = match.group(1).replace(".pdf", "")

    return f"labels_combo_{'_'.join(meet_codes)}{suffix}.pdf"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Avery 5160 swim meet award labels for Saybrook Sharks."
    )
    parser.add_argument(
        "meet", metavar="CODE",
        help="Meet code to use from config file (e.g. ntc_dual)"
    )
    parser.add_argument(
        "--season", metavar="YEAR", type=int, default=datetime.date.today().year,
        help="Season/year to use from config file (defaults to the current year)"
    )

    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    corrections = config.get("corrections", {})
    if args.season not in config.get("seasons", {}):
        parser.error(f"Season {args.season} not found in config")

    meet_config = config["seasons"][args.season].get("meets", {}).get(args.meet)
    if not meet_config:
        parser.error(f"Meet '{args.meet}' not found in season {args.season}")
    meet_clean = format_meet_name(meet_config)

    # Input and output are organized into per-season subdirectories.
    season_input_dir = INPUT_DIR / str(args.season)
    season_output_dir = OUTPUT_DIR / str(args.season)

    # Look for input files matching the meet code
    input_files = list(season_input_dir.glob(f"raw_{args.meet}*.pdf"))
    if not input_files:
        parser.error(f"No input files found for meet code '{args.meet}' in {season_input_dir}")

    input_filenames = sorted([f.name for f in input_files])
    output_filename = generate_output_filename(input_filenames)

    all_data = []
    for filename in input_filenames:
        input_path = season_input_dir / filename
        if not input_path.exists():
            print(f"Error: input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        raw_text = extract_text(input_path)
        # Date and raw meet name are derived per-file from the PDF itself.
        date, meet_raw = extract_meet_info(clean_non_ascii(raw_text))
        all_data += parse_text(raw_text, meet_raw, date, meet_clean)

    if not all_data:
        print("Error: no label data parsed from input file(s).", file=sys.stderr)
        sys.exit(1)

    sorted_data = sort_data(all_data)

    data_path = save_results(
        all_data, args.season, args.meet, meet_clean, input_filenames
    )
    print(f"Saved results to {data_path}.")

    season_output_dir.mkdir(parents=True, exist_ok=True)
    output_path = season_output_dir / output_filename
    create_pdf(sorted_data, output_path)
    print(f"Created {output_path} with {len(sorted_data)} labels.")


if __name__ == "__main__":
    main()
