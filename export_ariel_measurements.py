# export_ariel_measurements_compatible.py
import csv
import math
import argparse
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore

# ---------- Defaults ----------
DEFAULT_COLLECTION = "Data"
DEFAULT_CENTER_LAT = 32.105
DEFAULT_CENTER_LON = 35.190
DEFAULT_RADIUS_KM  = 5.0

# ---------- Firestore connection ----------
def init_firestore(sa_path="Firebase_Key.json"):
    cred = credentials.Certificate(sa_path)
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)
    return firestore.client()

# ---------- Compatibility for where/filter between versions ----------
def add_filter(q, field, op, val):
    try:
        from google.cloud.firestore_v1 import FieldFilter
        return q.where(filter=FieldFilter(field, op, val))
    except Exception:
        return q.where(field, op, val)

# ---------- Geography ----------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    from math import radians, sin, cos, atan2, sqrt
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    phi1, phi2 = radians(lat1), radians(lat2)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlmb/2)**2
    return R * (2*atan2(sqrt(a), sqrt(1-a)))

def lat_span_deg(radius_km):  # ≈ 1°lat = 110.574 km
    return radius_km / 110.574

def lon_span_deg(lat, radius_km):  # ≈ 1°lon = 111.320·cos(lat)
    return radius_km / (111.320 * math.cos(math.radians(lat)))

# ---------- CSV ----------
def write_csv(rows, out_path):
    if not rows:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["info"]); w.writerow(["no rows matched your filters"])
        return
    keys = set()
    for r in rows: keys.update(r.keys())
    headers = sorted(keys)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            cleaned = {}
            for k, v in r.items():
                if isinstance(v, datetime):
                    cleaned[k] = v.astimezone(timezone.utc).isoformat()
                else:
                    cleaned[k] = v
            w.writerow(cleaned)

# ---------- Date helpers (optional) ----------
def try_parse_date(val):
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(val, fmt).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return None

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Export Firestore measurements in Ariel area to CSV.")
    ap.add_argument("--firebase-key", default="Firebase_Key.json")
    ap.add_argument("--collection",  default=DEFAULT_COLLECTION)
    ap.add_argument("--out",         default="ariel_measurements.csv")
    ap.add_argument("--center-lat", type=float, default=DEFAULT_CENTER_LAT)
    ap.add_argument("--center-lon", type=float, default=DEFAULT_CENTER_LON)
    ap.add_argument("--radius-km",  type=float, default=DEFAULT_RADIUS_KM)
    ap.add_argument("--date-field", type=str, default=None, help="e.g., DATE / timestamp (optional)")
    ap.add_argument("--date-start", type=str, default=None, help="YYYY-MM-DD (optional)")
    ap.add_argument("--date-end",   type=str, default=None, help="YYYY-MM-DD (optional)")
    ap.add_argument("--provider",   type=str, default=None, help="exact match on Provider (optional)")
    args = ap.parse_args()

    db = init_firestore(args.firebase_key)

    # Bounding box for lat/lon
    # No server-side filter for LAT because LAT is string in our data
    q = db.collection(args.collection)
    if args.provider:
        q = add_filter(q, "Provider", "==", args.provider)

    docs = q.stream()  # Client-side filtering for box+radius only

    # Client-side filtering by LON, radius, and date (if requested)
    start_dt = datetime.strptime(args.date_start, "%Y-%m-%d").replace(tzinfo=timezone.utc) if args.date_start else None
    end_dt   = datetime.strptime(args.date_end,   "%Y-%m-%d").replace(tzinfo=timezone.utc) if args.date_end   else None

    rows = []
    for d in docs:
        data = d.to_dict() or {}
        try:
            lat = float(data.get("LAT")) if data.get("LAT") is not None else None
            lon = float(data.get("LON")) if data.get("LON") is not None else None
            if lon is None and "LNG" in data:  # Common fallback
                lon = float(data["LNG"])
        except Exception:
            continue

        if lat is None or lon is None:
            continue

        if not (lon_min <= lon <= lon_max):
            continue
        if haversine_km(args.center_lat, args.center_lon, lat, lon) > args.radius_km:
            continue

        if (start_dt or end_dt) and args.date_field and args.date_field in data:
            dt = try_parse_date(data[args.date_field])
            if dt:
                if start_dt and dt < start_dt: continue
                if end_dt   and dt > end_dt:   continue

        data["_doc_id"] = d.id
        rows.append(data)

    write_csv(rows, args.out)
    print(f"Exported {len(rows)} rows → {args.out}")

if __name__ == "__main__":
    main()

