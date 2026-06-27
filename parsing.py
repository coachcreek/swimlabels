"""PDF text extraction and parsing for swim meet results.

This module turns a raw results PDF into a list of per-swimmer result dicts.
The parsing is regex-heavy and tolerant of the messy text PyPDF2 produces; the
manual data fixes it applies (name cleanups and one-off per-record overrides)
are supplied by the caller via a ``corrections`` mapping (see config.yaml) so
this module stays free of hardcoded, meet-specific knowledge.
"""
import re
from pathlib import Path

from PyPDF2 import PdfReader


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


def clean_names(name: str, name_corrections: dict) -> str:
    """Apply an exact-match name correction, or return the name unchanged.

    ``name_corrections`` maps a parsed name string (including any trailing
    whitespace from the PDF) to its cleaned replacement.
    """
    return name_corrections.get(name, name)


def _apply_record_corrections(entry: dict, meet_name_raw: str, record_corrections: list) -> None:
    """Mutate ``entry`` in place for any matching one-off per-record override.

    Each correction has a ``match`` mapping (field -> required value) and a
    ``set`` mapping (field -> replacement). The implicit ``meet_name_raw`` is
    matched against the current file's raw meet name.
    """
    for correction in record_corrections:
        criteria = dict(correction.get("match", {}))
        expected_meet = criteria.pop("meet_name_raw", None)
        if expected_meet is not None and expected_meet != meet_name_raw:
            continue
        if all(entry.get(field) == value for field, value in criteria.items()):
            entry.update(correction.get("set", {}))


def parse_text(
    raw_text: str,
    meet_name_raw: str,
    meet_date: str,
    meet_name_clean: str,
    corrections: dict | None = None,
) -> list[dict]:
    corrections = corrections or {}
    name_corrections = corrections.get("names", {})
    record_corrections = corrections.get("records", [])

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
            # Names from the PDF carry stray surrounding whitespace; strip it
            # before correcting so corrections match clean values.
            last_name = clean_names(re.search(r'^([\s\WA-Za-z]+)\, .+ *\d+ *$', segment, re.MULTILINE).group(1).strip(), name_corrections)
            first_name = clean_names(re.search(r'^[\s\WA-Za-z]+\, ([\s\WA-Za-z]+).* *\d+ *$', segment, re.MULTILINE).group(1).strip(), name_corrections)
        except AttributeError:
            continue

        age_type = "card" if re.search(r'(14|15|18)', age) else "ribbon"

        entry = {
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
        }

        # one-off per-record fixes (e.g. relay swimmer recorded under wrong name)
        _apply_record_corrections(entry, meet_name_raw, record_corrections)

        clean_data.append(entry)

    return clean_data
