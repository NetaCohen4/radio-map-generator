#!/usr/bin/env python3
# export_ariel_plmn_timewindow.py
# Download Firestore docs from collection "Data" filtered by:
# - Location: Ariel area (configurable center+radius)
# - PLMN (default 42501)
# - Time window(s) parsed from doc ID pattern: USERID_YYYYMMDD_HHMMSS
# Service account JSON assumed at ../firebase-key/Firebase_Key.json (outside code folder)

import os
import csv
import math
import argparse
from typing import List, Tuple
import firebase_admin
from firebase_admin import credentials, firestore

DEFAULT_COLLECTION = "Data"

# Ariel center + radius (km) — tweak as needed
DEFAULT_CENTER_LAT = 32.105
DEFAULT_CENTER_LON = 35.195
DEFAULT_RADIUS_KM  = 5.0

DEFAULT_PLMN = "42501"

# ---------------- Firestore init ----------------
def init_firestore(sa_path):
    cred = credentials.Certificate(sa_path)
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)
    return firestore.client()

def add_filter(q, field, op, val):
    """Compat for different Firestore client versions."""
    try:
        from google.cloud.firestore_v1 import FieldFilter
        return q.where(filter=FieldFilter(field, op, val))
    except Exception:
        return q.where(field, op, val)

# ---------------- Geo helpers ----------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    from math import radians, sin, cos, atan2, sqrt
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    phi1, phi2 = radians(lat1), radians(lat2)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlmb/2)**2
    return R * (2*atan2(sqrt(a), sqrt(1-a)))

def lon_span_deg(lat, radius_km):
    # ≈ 1° lon = 111.320 * cos(lat)
    return radius_km / (111.320 * math.cos(math.radians(lat)))

def lat_span_deg(radius_km):
    # ≈ 1° lat = 110.574 km
    return radius_km / 110.574

# ---------------- Time window parsing ----------------
def parse_hours_spec(spec: str) -> List[Tuple[int, int]]:
    """
    Parse a spec like:
      "23:00-07:00" (wraps midnight)
      "07:00-23:00" (daytime)
      "00:00-24:00" (all)
      "06:00-09:00,13:30-15:00" (multiple ranges)
    Returns list of (start_hour, end_hour) with minutes ignored for the doc-id check.
    """
    ranges = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            a, b = [p.strip() for p in part.split("-", 1)]
            ah, am = [int(x) for x in a.split(":")]
            bh, bm = [int(x) for x in b.split(":")]
            # we only use hour granularity because doc id has HHMMSS; minutes won’t hurt but we round down
            ranges.append((ah, bh))
        except Exception:
            raise ValueError(f"Invalid --hours segment: '{part}'. Use HH:MM-HH:MM[,HH:MM-HH:MM...]")
    if not ranges:
        raise ValueError("Empty --hours spec.")
    return ranges

def hour_in_any_range(hh: int, ranges: List[Tuple[int, int]]) -> bool:
    """
    Returns True if hour 'hh' is within any of the ranges.
    Range semantics:
      - Non-wrapping: start < end  -> start <= hh < end
      - Wrapping:     start > end  -> hh >= start OR hh < end
      - Full-day:     start == end -> all 24h
    """
    for start, end in ranges:
        if start == end:
            return True  # 00-00 means full day
        if start < end:
            if start <= hh < end:
                return True
        else:
            if (hh >= start) or (hh < end):
                return True
    return False

def hour_from_doc_id(doc_id: str) -> int:
    """
    Extract HH (0..23) from doc id like '001_20250608_120042'.
    Returns -1 if not parseable.
    """
    try:
        parts = doc_id.split("_")
        hhmmss = parts[-1]
        return int(hhmmss[:2])
    except Exception:
        return -1

# ---------------- CSV writer ----------------
def write_csv(rows, out_path):
    if not rows:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["info"])
            w.writerow(["no rows matched your filters"])
        return

    keys = set()
    for r in rows:
        keys.update(r.keys())
    headers = sorted(keys)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

# ---------------- Main ----------------
def main():
    ap = argparse.ArgumentParser(
        description="Export Firestore 'Data' docs for Ariel, PLMN filter, and configurable time window(s) → CSV"
    )
    # Service account outside code folder:
    ap.add_argument("--key-dir",  default=os.path.join("..", "firebase-key"))
    ap.add_argument("--key-file", default="Firebase_Key.json")

    ap.add_argument("--collection", default=DEFAULT_COLLECTION)
    ap.add_argument("--out",        default="ariel_filtered.csv")

    # Geo (Ariel)
    ap.add_argument("--center-lat", type=float, default=DEFAULT_CENTER_LAT)
    ap.add_argument("--center-lon", type=float, default=DEFAULT_CENTER_LON)
    ap.add_argument("--radius-km",  type=float, default=DEFAULT_RADIUS_KM)

    # Network filter
    ap.add_argument("--plmn", default=DEFAULT_PLMN, help="Exact match on PLMN (e.g., 42501)")

    # Time-window(s) from doc-id HHMMSS
    ap.add_argument(
        "--hours",
        default="23:00-07:00",
        help="Time ranges, e.g. '23:00-07:00' (night), '07:00-23:00' (day), or multiple '06:00-09:00,13:00-15:00'"
    )

    args = ap.parse_args()

    # Resolve service account path
    sa_path = os.path.abspath(os.path.join(args.key_dir, args.key_file))
    if not os.path.exists(sa_path):
        raise FileNotFoundError(f"Service account not found at {sa_path}")

    time_ranges = parse_hours_spec(args.hours)

    db = init_firestore(sa_path)

    # Build bounding box for quick filter
    dlat = lat_span_deg(args.radius_km)
    dlon = lon_span_deg(args.center_lat, args.radius_km)
    lat_min, lat_max = args.center_lat - dlat, args.center_lat + dlat
    lon_min, lon_max = args.center_lon - dlon, args.center_lon + dlon

    # Start query; server-side filter by PLMN when possible
    q = db.collection(args.collection)
    try:
        q = add_filter(q, "PLMN", "==", args.plmn)
    except Exception:
        pass

    rows = []
    matched = 0
    for doc in q.stream():
        data = doc.to_dict() or {}

        # 1) Time filter via doc id hour
        hh = hour_from_doc_id(doc.id)
        if hh < 0 or not hour_in_any_range(hh, time_ranges):
            continue

        # 2) Ensure PLMN match if the field is present (string compare)
        plmn_val = str(data.get("PLMN", "")).strip()
        if plmn_val != args.plmn:
            continue

        # 3) Geo filter (LAT/LON or LAT/LNG)
        try:
            lat_raw = data.get("LAT")
            lon_raw = data.get("LON", data.get("LNG"))
            lat = float(lat_raw) if lat_raw is not None else None
            lon = float(lon_raw) if lon_raw is not None else None
        except Exception:
            continue
        if lat is None or lon is None:
            continue

        # bbox then precise circle
        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
            continue
        if haversine_km(args.center_lat, args.center_lon, lat, lon) > args.radius_km:
            continue

        # keep doc id for traceability
        data["_doc_id"] = doc.id
        rows.append(data)
        matched += 1

    write_csv(rows, args.out)
    print(f"Exported {matched} measurements → {args.out}")

if __name__ == "__main__":
    main()

