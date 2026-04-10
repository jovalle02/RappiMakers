"""
Transform 200+ raw availability CSVs into a single clean dataset.
"""

import os
import glob
import re
import pandas as pd
from datetime import datetime

RAW_DIR = os.path.join(os.path.dirname(__file__), "Archivo")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "availability.csv")


def parse_timestamp(ts_str: str) -> datetime | None:
    """Parse timestamps like 'Sun Feb 01 2026 06:11:20 GMT-0500 (hora estandar de Colombia)'"""
    match = re.match(
        r"\w+ (\w+ \d+ \d+ \d+:\d+:\d+) GMT([+-]\d{4})", ts_str.strip()
    )
    if not match:
        return None
    dt_part, tz_offset = match.groups()
    dt = datetime.strptime(dt_part, "%b %d %Y %H:%M:%S")
    return dt


def process_single_csv(filepath: str) -> list[tuple[datetime, int]]:
    """Extract (timestamp, value) pairs from a single wide-format CSV."""
    with open(filepath, "r", encoding="utf-8") as f:
        header_line = f.readline().strip()
        data_line = f.readline().strip()

    headers = header_line.split(",")
    values = data_line.split(",")

    # First 4 columns are metadata: Plot name, metric, Value Prefix, Value Suffix
    timestamp_headers = headers[4:]
    data_values = values[4:]

    rows = []
    for ts_str, val_str in zip(timestamp_headers, data_values):
        ts = parse_timestamp(ts_str)
        if ts is None:
            continue
        try:
            value = int(val_str)
        except (ValueError, TypeError):
            continue
        rows.append((ts, value))

    return rows


def transform():
    """Main transform pipeline."""
    csv_files = glob.glob(os.path.join(RAW_DIR, "AVAILABILITY-data*.csv"))

    # Step 1: Extract all data points from all files
    all_rows = []
    for i, filepath in enumerate(csv_files):
        rows = process_single_csv(filepath)
        all_rows.extend(rows)

    # Step 2: Build DataFrame
    df = pd.DataFrame(all_rows, columns=["timestamp", "store_count"])

    # Step 3: Deduplicate by timestamp (overlapping files have identical values)
    df = df.drop_duplicates(subset="timestamp", keep="first")

    # Step 4: Sort chronologically
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Step 5: Add derived columns
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    df["minute"] = df["timestamp"].dt.minute
    df["day_of_week"] = df["timestamp"].dt.day_name()
    df["day_num"] = df["timestamp"].dt.dayofweek  # 0=Monday, 6=Sunday

    # Percentage change from previous point
    df["pct_change"] = df["store_count"].pct_change() * 100

    # Rolling average (30-min window = 180 points at 10-sec intervals)
    df["rolling_avg_30m"] = (
        df["store_count"].rolling(window=180, center=True, min_periods=1).mean().round(0).astype(int)
    )

    # Daily percentage: value as % of that day's peak
    daily_peaks = df.groupby("date")["store_count"].transform("max")
    df["daily_pct"] = ((df["store_count"] / daily_peaks) * 100).round(2)

    # Anomaly detection: flag points where value deviates > 2 std from the average for that (day_of_week, hour) combination
    hourly_stats = df.groupby(["hour"])["store_count"].agg(["mean", "std"])
    df = df.merge(hourly_stats, left_on="hour", right_index=True, suffixes=("", "_hourly"))
    df["z_score"] = ((df["store_count"] - df["mean"]) / df["std"]).round(3)
    df["is_anomaly"] = df["z_score"].abs() > 2
    df = df.drop(columns=["mean", "std"])

    # Step 6: Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)


if __name__ == "__main__":
    transform()
