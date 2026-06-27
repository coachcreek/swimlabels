#!/usr/bin/env python3
"""Ribbon usage reporting.

Ribbons are awarded for places 1st-6th to swimmers aged 12 and under; older
age groups receive business cards instead. Different coloured ribbons are
ordered per place, so the key planning number is how many of each place we hand
out. This report reads the saved per-meet results in ``data/<season>/*.json``
(no PDF re-parsing) and prints per-meet ribbon counts with a running season
total, so prior full seasons can be compared against the current year-to-date.
"""
import argparse
import datetime
import glob
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

PLACES = ["1st", "2nd", "3rd", "4th", "5th", "6th"]

# Age groups that receive ribbons (12 and under). Anything else (13-14,
# 15-18, 15&Over, ...) gets a business card instead of ribbons.
RIBBON_AGES = {"6&Under", "8&Under", "9-10", "11-12"}

# Age groups (13 and up) that receive a business card -- the same card for any
# 1st-6th place finish. These are the complement of RIBBON_AGES.
CARD_AGES = {"13-14", "15-18", "15&Over"}

# Meet codes that never use ribbons and so are excluded from the report
# (time trials are intra-team timing, not an award meet).
EXCLUDED_MEET_CODES = {"time_trials"}


def _meet_sort_key(meet_date: str):
    """Sort key for a stored MM/DD/YY meet date, oldest first."""
    try:
        return datetime.datetime.strptime(meet_date, "%m/%d/%y")
    except (ValueError, TypeError):
        # Undated meets sort last but stay stable.
        return datetime.datetime.max


def load_meets(season: int | None = None) -> list[dict]:
    """Load saved meet files, one dict per meet, sorted by meet date.

    Each meet file is treated as a single meet (one row in the report). The
    current data never combines multiple meets into one file; if that changes,
    results should be tagged with their source PDF upstream in ``save_results``
    so they can be split here reliably.
    """
    if season is not None:
        paths = glob.glob(str(DATA_DIR / str(season) / "*.json"))
    else:
        paths = glob.glob(str(DATA_DIR / "*" / "*.json"))

    meets = [json.loads(Path(p).read_text()) for p in paths]
    meets = [m for m in meets if m.get("meet_code") not in EXCLUDED_MEET_CODES]
    meets.sort(key=lambda m: _meet_sort_key(m.get("meet_date", "")))
    return meets


def count_ribbons(results: list[dict]) -> dict[str, int]:
    """Count ribbon-eligible (12 & under) results per place for a meet."""
    counts = {place: 0 for place in PLACES}
    for r in results:
        if r.get("age") in RIBBON_AGES and r.get("place") in counts:
            counts[r["place"]] += 1
    return counts


def count_cards(results: list[dict]) -> int:
    """Count business cards (any 1st-6th place, ages 13 & up) for a meet.

    The same card is given regardless of place, so this is a single total
    rather than a per-place breakdown.
    """
    return sum(
        1
        for r in results
        if r.get("age") in CARD_AGES and r.get("place") in set(PLACES)
    )


def _print_season(season: int, meets: list[dict], is_current: bool) -> None:
    title = f"{season} (year-to-date)" if is_current else str(season)
    bar = "=" * 62
    print(f"\n== {title} {bar}"[:64])
    header = (
        f"{'Meet':<18}{'Date':<9}"
        + "".join(f"{p:>5}" for p in PLACES)
        + f"{'Cards':>8}"
    )
    print(header)

    running = 0
    season_totals = {place: 0 for place in PLACES}
    season_cards = 0
    for meet in meets:
        counts = count_ribbons(meet.get("results", []))
        cards = count_cards(meet.get("results", []))
        meet_total = sum(counts.values())
        running += meet_total
        season_cards += cards
        for place in PLACES:
            season_totals[place] += counts[place]
        code = meet.get("meet_code", "?")
        # Strip the season prefix from MM/DD/YY for a compact MM/DD column.
        date = meet.get("meet_date", "")
        date_short = date[:5] if len(date) >= 5 else date
        row = (
            f"{code:<18}{date_short:<9}"
            + "".join(f"{counts[p]:>5}" for p in PLACES)
            + f"{cards:>8}"
        )
        print(row)

    label = "Ribbons YTD so far" if is_current else "Ribbons season total"
    totals_row = (
        f"{'TOTAL':<18}{'':<9}"
        + "".join(f"{season_totals[p]:>5}" for p in PLACES)
        + f"{season_cards:>8}"
    )
    num_meets = len(meets)
    average_row = (
        f"{'AVERAGE':<18}{'':<9}"
        + "".join(
            f"{(season_totals[p] / num_meets if num_meets else 0):>5.1f}"
            for p in PLACES
        )
        + f"{(season_cards / num_meets if num_meets else 0):>8.1f}"
    )
    print("-" * len(header))
    print(totals_row)
    print(average_row)
    card_label = "Cards YTD so far" if is_current else "Cards season total"
    print(f"{label}: {running}")
    print(f"{card_label}: {season_cards}")


def report_ribbons() -> None:
    meets = load_meets()
    by_season: dict[int, list[dict]] = {}
    for meet in meets:
        by_season.setdefault(meet.get("season"), []).append(meet)

    current_year = datetime.date.today().year

    print("Award usage -- per-meet counts with season total")
    print("Ribbon columns (1st-6th): ages 12 & under. "
          "Cards: total 1st-6th finishes for ages 13 & up.")

    for season in sorted(by_season):
        _print_season(season, by_season[season], is_current=(season == current_year))


def main() -> None:
    parser = argparse.ArgumentParser(description="Swim meet reporting.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ribbons", help="Per-meet ribbon usage with season totals.")
    args = parser.parse_args()

    if args.command == "ribbons":
        report_ribbons()


if __name__ == "__main__":
    main()
