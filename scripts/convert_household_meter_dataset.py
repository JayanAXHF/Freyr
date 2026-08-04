"""Convert the "15-minute household power consumption" JSON dataset into a
CSV that ``SiteConfig.meter_feed_path`` can load directly.

Source dataset: one JSON file per household (``meters_<id>_measurement.json``),
each a list of daily records with a 96-element ``consumption`` array (kWh
consumed in each 15-minute interval). This script picks one or more meter
IDs, sums them into a single site load, converts kWh-per-interval to average
kW (multiply by 4), and writes a two-column ``timestamp,load_kw`` CSV.

    .venv/bin/python scripts/convert_household_meter_dataset.py \\
        --data-dir "/path/to/repository" \\
        --meter-ids 4 106 305 \\
        --output data/meter_feed.csv

Then point a config at it: ``SiteConfig(meter_feed_path="data/meter_feed.csv")``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

INTERVAL_MINUTES = 15


def _load_meter_series(path: Path) -> pd.Series:
    records = json.loads(path.read_text())
    timestamps = []
    values = []
    for record in records:
        day_start = pd.Timestamp(
            year=record["year"], month=record["month"], day=record["day"]
        )
        consumption_kwh = record["consumption"]
        for i, kwh in enumerate(consumption_kwh):
            timestamps.append(day_start + pd.Timedelta(minutes=INTERVAL_MINUTES * i))
            values.append(kwh)
    series = pd.Series(values, index=pd.DatetimeIndex(timestamps), name="load_kw")
    series = series[~series.index.duplicated(keep="first")].sort_index()
    return series * (60 / INTERVAL_MINUTES)  # kWh/interval -> average kW


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", required=True, type=Path, help="Path to the dataset's repository/ folder"
    )
    parser.add_argument(
        "--meter-ids",
        required=True,
        nargs="+",
        type=int,
        help="One or more meterIDs to sum into a single site load",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    total = None
    for meter_id in args.meter_ids:
        path = args.data_dir / f"meters_{meter_id}_measurement.json"
        series = _load_meter_series(path)
        total = series if total is None else total.add(series, fill_value=0.0)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame({"timestamp": total.index, "load_kw": total.to_numpy()})
    frame.to_csv(args.output, index=False)
    print(
        f"wrote {len(frame)} rows ({total.index[0]} .. {total.index[-1]}) "
        f"from {len(args.meter_ids)} meter(s) -> {args.output}"
    )


if __name__ == "__main__":
    main()
