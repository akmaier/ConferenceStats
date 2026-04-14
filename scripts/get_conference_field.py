#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Read one field from config/conferences.csv for a given conference slug and year.")
    parser.add_argument("--conference-slug", required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--field", required=True)
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "config" / "conferences.csv"))
    args = parser.parse_args()

    config_path = Path(args.config)
    with config_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        if row.get("conference_slug") == args.conference_slug and row.get("year") == str(args.year):
            if args.field not in row:
                raise SystemExit(f"Field {args.field!r} not found in {config_path}")
            print(row[args.field])
            return

    raise SystemExit(
        f"No row found in {config_path} for conference_slug={args.conference_slug!r}, year={args.year!r}"
    )


if __name__ == "__main__":
    main()
