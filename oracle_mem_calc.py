#!/usr/bin/env python3
"""
Oracle Memory Calculator (CLI)

- Generic calculator (no RAM detection).
- Input total memory (GiB by default or MB) and get Oracle memory splits.
- Produces human-readable report and SQL in MB (integers).
- Optional JSON/CSV export and SQL file write-out.
"""
import argparse
from oracle_mem_core import Inputs, calculate, format_report, export_json, export_csv, format_sql


def main():
    parser = argparse.ArgumentParser(
        description="Generic Oracle memory calculator. Enter total memory and get SGA/PGA values and SQL.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "total",
        type=float,
        help="Total memory value to base calculations on (unit controlled by --unit).",
    )
    parser.add_argument(
        "--unit",
        choices=["GiB", "MB"],
        default="GiB",
        help="Unit of the total memory input.",
    )
    parser.add_argument(
        "--allocated",
        type=float,
        default=0.75,
        help="Fraction of total allocated to the database (e.g., 0.75 = 75%).",
    )
    parser.add_argument(
        "--sga",
        type=float,
        default=0.83,
        help="Fraction of allocated memory for SGA (SGA_MAX and SGA_TARGET; rounded up to whole GiB).",
    )
    parser.add_argument(
        "--pga-limit",
        type=float,
        default=0.16,
        help="Fraction of allocated memory for PGA_AGGREGATE_LIMIT.",
    )
    parser.add_argument(
        "--json-out",
        metavar="FILE.json",
        help="Write results as JSON to the given file.",
    )
    parser.add_argument(
        "--csv-out",
        metavar="FILE.csv",
        help="Write results as a one-row CSV to the given file.",
    )
    parser.add_argument(
        "--sql-out",
        metavar="FILE.sql",
        help="Write ALTER SYSTEM SQL to the given file.",
    )

    args = parser.parse_args()

    inputs = Inputs(
        total_value=args.total,
        total_unit=args.unit,
        allocated_percent=args.allocated,
        sga_percent=args.sga,
        pga_limit_percent=args.pga_limit,
    )

    results = calculate(inputs)

    report = format_report(inputs, results)
    print(report)

    if args.json_out:
        export_json(args.json_out, inputs, results)
        print(f"\n[+] JSON written: {args.json_out}")
    if args.csv_out:
        export_csv(args.csv_out, inputs, results)
        print(f"[+] CSV written: {args.csv_out}")
    if args.sql_out:
        with open(args.sql_out, 'w', encoding='utf-8') as f:
            f.write(format_sql(results) + "\n")
        print(f"[+] SQL written: {args.sql_out}")


if __name__ == "__main__":
    main()
