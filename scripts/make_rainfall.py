"""Generate data/demo/rainfall_supaul.csv -- bundled ancillary data for the
weather-corroboration panel.

Daily rainfall for Supaul district around the synthetic flood date. Values follow
the shape of a real Kosi-basin monsoon burst (a multi-day high-intensity spell
preceding inundation) but are SYNTHETIC, matched to the synthetic scenes. The
panel must label them as such -- corroboration is only honest if its provenance is.

Normals are approximate IMD district-average monsoon values for the region.
"""

import csv
import datetime as dt
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "demo" / "rainfall_supaul.csv"

# (date, observed_mm) -- burst peaks 22-26 Aug, scene acquired 27 Aug.
OBS = {
    "2024-08-15": 4.2, "2024-08-16": 0.0, "2024-08-17": 11.8, "2024-08-18": 6.5,
    "2024-08-19": 2.1, "2024-08-20": 0.0, "2024-08-21": 18.4, "2024-08-22": 96.7,
    "2024-08-23": 141.3, "2024-08-24": 88.9, "2024-08-25": 72.5, "2024-08-26": 115.8,
    "2024-08-27": 31.2, "2024-08-28": 9.6, "2024-08-29": 3.4, "2024-08-30": 0.0,
}
NORMAL_MM_PER_DAY = 12.4      # late-August district normal


def main():
    rows = []
    for d, mm in sorted(OBS.items()):
        date = dt.date.fromisoformat(d)
        rows.append({
            "date": d,
            "district": "Supaul",
            "state": "Bihar",
            "rainfall_mm": mm,
            "normal_mm": NORMAL_MM_PER_DAY,
            "departure_pct": round((mm - NORMAL_MM_PER_DAY) / NORMAL_MM_PER_DAY * 100, 1),
            "source": "SYNTHETIC",
        })

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # Summary the panel headlines with -- 5 days to the acquisition.
    window = [r for r in rows if "2024-08-23" <= r["date"] <= "2024-08-27"]
    total = sum(r["rainfall_mm"] for r in window)
    normal = NORMAL_MM_PER_DAY * len(window)
    print(f"wrote {len(rows)} rows -> {OUT.name}")
    print(f"  5-day total to acquisition: {total:.1f} mm "
          f"(normal {normal:.1f} mm, departure +{(total-normal)/normal*100:.0f}%)")
    print(f"  peak 24h: {max(r['rainfall_mm'] for r in rows):.1f} mm")


if __name__ == "__main__":
    main()
