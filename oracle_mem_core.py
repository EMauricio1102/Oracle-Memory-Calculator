#!/usr/bin/env python3
"""
Shared core logic for Oracle Memory Calculator

Rules:
  - Allocated = total * allocated_percent (default 0.75)
  - SGA_MAX = SGA_TARGET = ceil( Allocated * sga_percent ) in GiB (whole GiB)
  - PGA_AGGREGATE_LIMIT = Allocated * pga_limit_percent
  - PGA_AGGREGATE_TARGET = PGA_AGGREGATE_LIMIT / 2
Outputs:
  - Helper functions to format a human-readable report and SQL in MB (integers)
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal, Dict, Any
import math
import csv
import json

GiB = 1024  # MB per GiB

@dataclass
class Inputs:
    total_value: float
    total_unit: Literal["GiB", "MB"]
    allocated_percent: float  # fraction 0..1
    sga_percent: float        # fraction 0..1
    pga_limit_percent: float  # fraction 0..1

@dataclass
class Results:
    # Core values in GiB
    total_gib: float
    allocated_gib: float
    sga_gib_rounded: int
    pga_limit_gib: float
    pga_target_gib: float

    # SQL MB (integers)
    sga_mb: int
    pga_limit_mb: int
    pga_target_mb: int


def to_gib(total_value: float, unit: str) -> float:
    if unit == "GiB":
        return float(total_value)
    elif unit == "MB":
        return float(total_value) / GiB
    else:
        raise ValueError("unit must be 'GiB' or 'MB'")


def calculate(inputs: Inputs) -> Results:
    if inputs.total_value <= 0:
        raise ValueError("total_value must be positive")
    for name, v in ("allocated_percent", inputs.allocated_percent), ("sga_percent", inputs.sga_percent), ("pga_limit_percent", inputs.pga_limit_percent):
        if not (0 < v <= 1):
            raise ValueError(f"{name} must be in (0,1], e.g. 0.75 for 75%")

    total_gib = to_gib(inputs.total_value, inputs.total_unit)

    allocated_gib = total_gib * inputs.allocated_percent
    # SGA must be rounded UP to whole GiB
    sga_gib_rounded = math.ceil(allocated_gib * inputs.sga_percent)

    pga_limit_gib = allocated_gib * inputs.pga_limit_percent
    pga_target_gib = pga_limit_gib / 2.0

    # SQL in MB (integers)
    sga_mb = int(sga_gib_rounded * GiB)
    pga_limit_mb = int(round(pga_limit_gib * GiB, 0))
    pga_target_mb = int(round(pga_target_gib * GiB, 0))

    return Results(
        total_gib=total_gib,
        allocated_gib=allocated_gib,
        sga_gib_rounded=sga_gib_rounded,
        pga_limit_gib=pga_limit_gib,
        pga_target_gib=pga_target_gib,
        sga_mb=sga_mb,
        pga_limit_mb=pga_limit_mb,
        pga_target_mb=pga_target_mb,
    )


def format_report(inputs: Inputs, results: Results) -> str:
    lines = []
    lines.append("=== CALCULATED VALUES ===")
    lines.append(f"Total (input):               {results.total_gib:,.2f} GiB")
    lines.append(f"Allocated to Oracle:         {results.allocated_gib:,.2f} GiB")
    lines.append("")
    lines.append(f"SGA_MAX / SGA_TARGET:        {results.sga_gib_rounded:,d} GiB")
    lines.append(f"PGA_AGGREGATE_LIMIT:         {results.pga_limit_gib:,.2f} GiB")
    lines.append(f"PGA_AGGREGATE_TARGET:        {results.pga_target_gib:,.2f} GiB")
    lines.append("")
    lines.append("=== SQL COMMANDS ===")
    lines.append(format_sql(results))
    return "\n".join(lines)


def format_sql(results: Results) -> str:
    return "\n".join([
        f"ALTER SYSTEM SET sga_max_size         = {results.sga_mb}M SCOPE=SPFILE;",
        f"ALTER SYSTEM SET sga_target           = {results.sga_mb}M SCOPE=SPFILE;",
        f"ALTER SYSTEM SET pga_aggregate_limit  = {results.pga_limit_mb}M SCOPE=SPFILE;",
        f"ALTER SYSTEM SET pga_aggregate_target = {results.pga_target_mb}M SCOPE=SPFILE;",
    ])


def to_dict(inputs: Inputs, results: Results) -> Dict[str, Any]:
    return {"inputs": asdict(inputs), "results": asdict(results)}


def export_json(path: str, inputs: Inputs, results: Results) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(to_dict(inputs, results), f, indent=2)


def export_csv(path: str, inputs: Inputs, results: Results) -> None:
    # One-row CSV for easy import into planning docs
    fieldnames = [
        "total_gib", "allocated_gib", "sga_gib_rounded", "pga_limit_gib", "pga_target_gib",
        "sga_mb", "pga_limit_mb", "pga_target_mb",
        "allocated_percent", "sga_percent", "pga_limit_percent", "input_unit", "input_total"
    ]
    data = {
        "total_gib": results.total_gib,
        "allocated_gib": results.allocated_gib,
        "sga_gib_rounded": results.sga_gib_rounded,
        "pga_limit_gib": results.pga_limit_gib,
        "pga_target_gib": results.pga_target_gib,
        "sga_mb": results.sga_mb,
        "pga_limit_mb": results.pga_limit_mb,
        "pga_target_mb": results.pga_target_mb,
        "allocated_percent": inputs.allocated_percent,
        "sga_percent": inputs.sga_percent,
        "pga_limit_percent": inputs.pga_limit_percent,
        "input_unit": inputs.total_unit,
        "input_total": inputs.total_value,
    }
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(data)
