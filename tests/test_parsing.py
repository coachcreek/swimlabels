"""Characterization tests for the PDF parsing pipeline.

These tests pin the *current* parser output against snapshots generated from
the real meet PDFs in ``input/``. They exist to make the parsing.py extraction
(and the move of name corrections into config) safe: if the refactor changes
what the parser emits for any meet, a test fails.

Snapshots live in ``tests/snapshots/<season>_<code>.json`` and hold the parsed
``results`` list only (the volatile ``parsed_at`` timestamp is excluded).

To regenerate snapshots after an *intentional* parser change:

    python3 tests/test_parsing.py --update

The source PDFs are gitignored, so these tests require the local ``input/``
files to be present.
"""
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsing import (  # noqa: E402
    clean_non_ascii,
    extract_meet_info,
    extract_text,
    parse_text,
)
from swimlabels import format_meet_name, load_config  # noqa: E402

INPUT_DIR = PROJECT_ROOT / "input"
SNAPSHOT_DIR = Path(__file__).parent / "snapshots"
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def parse_meet(season: int, meet_code: str) -> list[dict]:
    """Run the full parse pipeline for one meet, mirroring main()."""
    config = load_config(CONFIG_PATH)
    corrections = config.get("corrections", {})
    meet_config = config["seasons"][season]["meets"][meet_code]
    meet_clean = format_meet_name(meet_config)

    season_input_dir = INPUT_DIR / str(season)
    input_files = sorted(season_input_dir.glob(f"raw_{meet_code}*.pdf"))

    all_data = []
    for input_path in input_files:
        raw_text = extract_text(input_path)
        date, meet_raw = extract_meet_info(clean_non_ascii(raw_text))
        all_data += parse_text(raw_text, meet_raw, date, meet_clean, corrections)
    return all_data


def discover_meets() -> list[tuple[int, str]]:
    """All (season, meet_code) pairs that have both config and input PDFs."""
    config = load_config(CONFIG_PATH)
    meets = []
    for season, season_cfg in config.get("seasons", {}).items():
        for meet_code in season_cfg.get("meets", {}):
            if list((INPUT_DIR / str(season)).glob(f"raw_{meet_code}*.pdf")):
                meets.append((season, meet_code))
    return sorted(meets)


def snapshot_path(season: int, meet_code: str) -> Path:
    return SNAPSHOT_DIR / f"{season}_{meet_code}.json"


class ParsingCharacterizationTest(unittest.TestCase):
    pass


def _make_test(season: int, meet_code: str):
    def test(self):
        snap = snapshot_path(season, meet_code)
        self.assertTrue(
            snap.exists(),
            f"No snapshot for {season} {meet_code}; run with --update first.",
        )
        expected = json.loads(snap.read_text())
        actual = parse_meet(season, meet_code)
        self.assertEqual(
            actual, expected,
            f"Parser output for {season} {meet_code} differs from snapshot.",
        )
    return test


for _season, _code in discover_meets():
    setattr(
        ParsingCharacterizationTest,
        f"test_{_season}_{_code}",
        _make_test(_season, _code),
    )


def update_snapshots() -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for season, meet_code in discover_meets():
        data = parse_meet(season, meet_code)
        snapshot_path(season, meet_code).write_text(json.dumps(data, indent=2))
        print(f"Wrote snapshot for {season} {meet_code} ({len(data)} records).")


if __name__ == "__main__":
    if "--update" in sys.argv:
        update_snapshots()
    else:
        unittest.main()
