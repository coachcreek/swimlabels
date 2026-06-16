#!/usr/bin/env python3
import argparse
import datetime
import re
import sys
from pathlib import Path

import yaml
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def extract_text(input_path: Path) -> str:
    with open(input_path, "rb") as f:
        reader = PdfReader(f)
        return "".join(page.extract_text() for page in reader.pages)


def clean_non_ascii(text: str) -> str:
    return text.replace("ϐ", "f")


def extract_meet_info(raw_text: str) -> tuple[str, str]:
    """Derive the meet date and raw meet name from the PDF text.

    Every record ends with a line like "Saybrook Sharks - 6/24/2025" followed
    immediately by the raw meet name (which may have the next record glued on).
    The date is normalized to MM/DD/YY to match the previous label output.
    """
    # Relay records insert a team designator (A/B/C/D) before the date, e.g.
    # "Saybrook Sharks - B   6/21/2025"; allow for it optionally.
    match = re.search(r'Saybrook Sharks - (?:[A-D]\s+)?(\d+)/(\d+)/(\d+)\s*\n([^\n]+)', raw_text)
    if not match:
        raise ValueError("Could not find a 'Saybrook Sharks - <date>' marker in the PDF text.")

    month, day, year = match.group(1), match.group(2), match.group(3)
    date = f"{int(month):02d}/{int(day):02d}/{int(year) % 100:02d}"

    # Strip any run-on record that the PDF glued onto the meet-name line.
    meet_raw = re.split(r'Heat:', match.group(4))[0].strip()

    return date, meet_raw


def clean_names(name: str) -> str:
    replacements = [
        ("Evie or Everly E  ", "Everly E"),
        ("John Henry H  ", "John Henry"),
        ("John Henry H   ", "John Henry"),
        ("Omalley", "O'Malley"),
        ("Wells -  ", "Wells"),
        ("Wells -    ", "Wells"),
        ("Wren or Wrenna R  ", "Wren"),
        ("G J  ", "Gianna"),
    ]
    for raw, clean in replacements:
        if raw == name:
            return clean
    return name


def parse_text(raw_text: str, meet_name_raw: str, meet_date: str, meet_name_clean: str) -> list[dict]:
    raw_text = clean_non_ascii(raw_text)
    # Segment on the per-record team marker, which terminates every record,
    # rather than the meet name. The delimiter is inserted after the meet name
    # that immediately follows the marker so each segment holds a full record.
    raw_data = re.sub(
        r'(Saybrook Sharks - (?:[A-D]\s+)?\d+/\d+/\d+\s*\n' + re.escape(meet_name_raw) + r')',
        r'\1||',
        raw_text,
    )
    segments = raw_data.split("||")

    clean_data = []
    for segment in segments:
        if not segment or re.search(r'^[_\W]+$', segment, re.MULTILINE):
            continue

        try:
            heat = re.search(r'Heat\W+(\d+)\W+Place', segment, re.MULTILINE).group(1)
            place = re.search(r'Place\W+(\d+[a-z]{2})\W+Time', segment, re.MULTILINE).group(1)
            time = re.search(r'Time\W+([\d\W]+( +CITY)?)$', segment, re.MULTILINE).group(1)
            event_num = re.search(r'^(#\d+)\W+(Boys|Girls)\W+\d', segment, re.MULTILINE).group(1)
            gender = re.search(r'^#\d+\W+(Boys|Girls)\W+\d', segment, re.MULTILINE).group(1)
            age = re.search(r'^#\d+\W+(Boys|Girls)\W+(\d+-\d+|\d+ & Under|\d+ & Over)', segment, re.MULTILINE).group(2)
            age = age.replace(" & ", "&")
            event_name = re.search(r'^#\d+\W+(Boys|Girls)\W+(\d+-\d+|\d+ & Under|\d+ & Over) *(.+)$', segment, re.MULTILINE).group(3)
            last_name = clean_names(re.search(r'^([\s\WA-Za-z]+)\, .+ *\d+ *$', segment, re.MULTILINE).group(1))
            first_name = clean_names(re.search(r'^[\s\WA-Za-z]+\, ([\s\WA-Za-z]+).* *\d+ *$', segment, re.MULTILINE).group(1))
        except AttributeError:
            continue

        # one-off relay name fix
        if meet_name_raw == "SAY @ NTC 2025" and event_name == "200 Yard Medley Relay" and last_name == "Jurjovec" and first_name == "George W  ":
            last_name = "Creek"
            first_name = "Killian M"

        age_type = "card" if re.search(r'(14|15|18)', age) else "ribbon"

        clean_data.append({
            "heat": heat,
            "place": place,
            "time": time,
            "event_num": event_num,
            "gender": gender,
            "age": age,
            "age_type": age_type,
            "event_name": event_name,
            "last_name": last_name,
            "first_name": first_name,
            "meet_name_clean": meet_name_clean,
            "meet_date": meet_date,
        })

    return clean_data


def sort_data(data: list[dict]) -> list[dict]:
    return sorted(data, key=lambda x: (x["age_type"], x["gender"], x["last_name"], x["first_name"]))


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
    if args.season not in config.get("seasons", {}):
        parser.error(f"Season {args.season} not found in config")

    meet_clean = config["seasons"][args.season].get("meets", {}).get(args.meet)
    if not meet_clean:
        parser.error(f"Meet '{args.meet}' not found in season {args.season}")

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

    season_output_dir.mkdir(parents=True, exist_ok=True)
    output_path = season_output_dir / output_filename
    create_pdf(sorted_data, output_path)
    print(f"Created {output_path} with {len(sorted_data)} labels.")


if __name__ == "__main__":
    main()
