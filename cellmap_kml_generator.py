#!/usr/bin/env python3
import argparse
import math
from pathlib import Path
from typing import List, Tuple, Optional

import pandas as pd
import re


KML_NS = "http://www.opengis.net/kml/2.2"
GMON_ICON = "https://sites.google.com/site/pynetmony/home/iconrxl.png"

def clamp(x, a, b):
    return max(a, min(b, x))

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def idw_predict(lat, lon, pts: List[Tuple[float,float,float]], neighbors=12, power=2.0) -> Optional[float]:
    if not pts:
        return None
    dists = [(haversine(lat, lon, la, lo), v) for la, lo, v in pts]
    dists.sort(key=lambda x: x[0])
    used = dists[:neighbors]
    if used and used[0][0] < 5.0:
        return used[0][1]
    if used and used[0][0] > 2000:
        return None
    num = 0.0
    den = 0.0
    for d, v in used:
        w = 1.0 / ((d + 1e-6) ** power)
        num += w * v
        den += w
    return num / den if den > 0 else None

# ---- GMoN-like icon styles table (id, aabbggrr color) ----
STYLE_TABLE = [
    ('rxl113', 'ff000000'),  # very poor
    ('rxl105', 'ffff0000'),  # poor (red)
    ('rxl80',  'ff00ffff'),  # fair
    ('rxl76',  'ff00a5ff'),  # good
    ('rxl69',  'ff0000ff'),  # very good
    ('rxl92',  'ff00ff00'),  # excellent (green)
]

def kml_header(name: str) -> str:
    parts = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(f'<kml xmlns="{KML_NS}">')
    parts.append('  <Document>')
    parts.append(f'    <name>{name}</name>')
    for sid, color in STYLE_TABLE:
        parts.append(f'''    <Style id="{sid}">
      <IconStyle>
        <color>{color}</color>
        <scale>0.5</scale>
        <Icon><href>{GMON_ICON}</href></Icon>
      </IconStyle>
    </Style>''')
    parts.append('''    <Style id="antenna">
      <IconStyle>
        <color>ff00ffff</color>
        <scale>1.0</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>
      </IconStyle>
    </Style>''')
    return '\n'.join(parts) + '\n'

def kml_footer() -> str:
    return '  </Document>\n</kml>\n'

def kml_point(name: str, lat: float, lon: float, desc: str, style_id: str) -> str:
    return (
f'    <Placemark>\n'
f'      <name>{name}</name>\n'
f'      <description><![CDATA[{desc}]]></description>\n'
f'      <styleUrl>#{style_id}</styleUrl>\n'
f'      <Point><coordinates>{lon:.6f},{lat:.6f},0</coordinates></Point>\n'
f'    </Placemark>\n'
    )

def kml_tile_polygon(lat_min, lon_min, lat_max, lon_max, fill_color: str) -> str:
    return f'''    <Placemark>
      <Style>
        <PolyStyle>
          <color>{fill_color}</color>
          <outline>0</outline>
        </PolyStyle>
      </Style>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              {lon_min:.6f},{lat_min:.6f},0
              {lon_max:.6f},{lat_min:.6f},0
              {lon_max:.6f},{lat_max:.6f},0
              {lon_min:.6f},{lat_max:.6f},0
              {lon_min:.6f},{lat_min:.6f},0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
'''

def continuous_tile_color(value: float, metric: str, alpha: int) -> str:
    # Typical ranges: RSRP [-120, -80], RSSI [-110, -60]
    if metric.upper() == "RSRP":
        lo, hi = -120.0, -80.0
    else:
        lo, hi = -110.0, -60.0
    t = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    # 0→red, 0.5→yellow, 1→green

    if t < 0.5:

        frac = t / 0.5
        r, g, b = 255, int(255 * frac), 0
    else:

        frac = (t - 0.5) / 0.5
        r, g, b = int(255 * (1 - frac)), 255, 0

    return f"{alpha:02x}{b:02x}{g:02x}{r:02x}"



def style_for_value(metric: str, val: float) -> str:
    m = metric.upper()
    if m == 'RSRP':
        if val <= -115: return 'rxl113'
        if val <= -105: return 'rxl105'
        if val <= -95:  return 'rxl80'
        if val <= -90:  return 'rxl76'
        if val <= -85:  return 'rxl69'
        return 'rxl92'
    else:
        if val <= -110: return 'rxl113'
        if val <= -100: return 'rxl105'
        if val <= -90:  return 'rxl80'
        if val <= -80:  return 'rxl76'
        if val <= -70:  return 'rxl69'
        return 'rxl92'

def choose_metric(row, prefer: str):
    try:
        if prefer == 'RSRP':
            v = row.get('RSRP/RSCP')
            return ('RSRP', float(v)) if pd.notna(v) else None
        elif prefer == 'RSSI':
            v = row.get('RSSI')
            return ('RSSI', float(v)) if pd.notna(v) else None
        else:
            sys = int(row.get('SYSTEM')) if pd.notna(row.get('SYSTEM')) else None
            if sys in (4, 7):
                v = row.get('RSRP/RSCP')
                if pd.notna(v):
                    return ('RSRP', float(v))
            v = row.get('RSSI')
            return ('RSSI', float(v)) if pd.notna(v) else None
    except Exception:
        return None

def _read_measurements_auto(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=None, engine="python")  # auto-detect delimiter
    norm = {}
    for c in df.columns:
        k = re.sub(r"[\s_-]+","",str(c).strip().lower())
        if k in {"lat","latitude","gpslat","y","latdd"}:
            norm[c] = "LAT"
        elif k in {"lon","long","longitude","lng","gpslon","x","londd"}:
            norm[c] = "LON"
        elif k in {"rsrp","rsrprscp","lte_rsrp"}:
            norm[c] = "RSRP/RSCP"
        elif k in {"rsrq","ecio","rsrqecio","lte_rsrq"}:
            norm[c] = "RSRQ/ECIO"
        elif k in {"rssi","signal","gsmrssi","lte_rssi"}:
            norm[c] = "RSSI"
    if norm:
        df = df.rename(columns=norm)
    if "LAT" in df.columns: df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
    if "LON" in df.columns: df["LON"] = pd.to_numeric(df["LON"], errors="coerce")
    return df
    
def main():
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument('--measurements', required=True)
    ap.add_argument('--antennas', required=False)
    ap.add_argument('--out', required=True)
    ap.add_argument('--metric', default='auto', choices=['auto','RSRP','RSSI'])
    ap.add_argument('--grid_step_deg', type=float, default=0.001)
    ap.add_argument('--idw_neighbors', type=int, default=12)
    ap.add_argument('--idw_power', type=float, default=2.0)
    ap.add_argument('--tile_alpha', type=int, default=120)
    args = ap.parse_args()

    df = _read_measurements_auto(args.measurements)

    if 'LAT' not in df.columns or 'LON' not in df.columns:
        print('Error: CSV missing LAT/LON columns.', file=sys.stderr)
        sys.exit(2)

    placemarks = []
    meas_pts: List[Tuple[float,float,float]] = []
    for i, row in df.iterrows():
        lat = row['LAT']; lon = row['LON']
        if pd.isna(lat) or pd.isna(lon):
            continue
        mv = choose_metric(row, args.metric)
        if mv is None:
            continue
        metric_name, value = mv
        sid = style_for_value(metric_name, value)
        fields = ['SYSTEM','PLMN','xNBID','LOCAL_CID','PCI/PSC/BSIC','ARFCN','BAND','RSSI','RSRP/RSCP','RSRQ/ECIO','SNR','DATE','TIME']
        desc = '<br/>'.join([f'<b>{k}</b>: {row.get(k)}' for k in fields if k in df.columns])
        name_parts = []
        if 'xNBID' in df.columns and pd.notna(row.get('xNBID')):
            name_parts.append(str(int(row.get('xNBID'))))
        if 'LOCAL_CID' in df.columns and pd.notna(row.get('LOCAL_CID')):
            name_parts.append(str(int(row.get('LOCAL_CID'))))
        name = '-'.join(name_parts) if name_parts else f'Meas {i}'
        placemarks.append(kml_point(name, float(lat), float(lon), desc, sid))
        meas_pts.append((float(lat), float(lon), float(value)))

    antenna_placemarks = []
    if args.antennas and Path(args.antennas).exists():
        adf = pd.read_csv(args.antennas)
        colmap = {c.lower(): c for c in adf.columns}
        latc = colmap.get('lat'); lonc = colmap.get('lon')
        namec = colmap.get('name', None)
        if latc and lonc:
            for _, r in adf.iterrows():
                try:
                    alat = float(r[latc]); alon = float(r[lonc])
                except Exception:
                    continue
                nm = str(r[namec]) if namec and pd.notna(r[namec]) else 'Antenna'
                desc = ''
                if 'id' in colmap and pd.notna(r[colmap['id']]):
                    desc = 'ID: {}'.format(r[colmap['id']])
                antenna_placemarks.append(kml_point(nm, alat, alon, desc, 'antenna'))

    if meas_pts:
        lats = [p[0] for p in meas_pts]; lons = [p[1] for p in meas_pts]
        lat_min, lat_max = min(lats)-0.002, max(lats)+0.002
        lon_min, lon_max = min(lons)-0.002, max(lons)+0.002
    else:
        lat_min = lon_min = 0; lat_max = lon_max = 0

    tiles = []
    if meas_pts:
        step = args.grid_step_deg
        lat = lat_min
        while lat <= lat_max:
            lon = lon_min
            while lon <= lon_max:
                pred = idw_predict(lat, lon, meas_pts, neighbors=args.idw_neighbors, power=args.idw_power)
                if pred is not None:
                    # pick base color from style table using RSRP mapping, then override alpha
                    sid = style_for_value('RSRP', pred)
                    table = dict(STYLE_TABLE)
                    base = table.get(sid, 'ff00ff00')  # default green
                    a = max(0, min(255, int(args.tile_alpha)))
                    fill_color = f"{a:02x}{base[2:]}"  # aabbggrr
                    tiles.append(kml_tile_polygon(lat, lon, lat+step, lon+step, fill_color))
                lon += step
            lat += step

    name = 'Coverage map (GMoN-like points + bolder IDW tiles)'
    kml_parts = [kml_header(name)]
    kml_parts.append('    <Folder><name>Prediction (IDW tiles)</name>\n')
    kml_parts.extend(tiles)
    kml_parts.append('    </Folder>\n')
    kml_parts.append('    <Folder><name>Measurements</name>\n')
    kml_parts.extend(placemarks)
    kml_parts.append('    </Folder>\n')
    kml_parts.append('    <Folder><name>Antennas</name>\n')
    kml_parts.extend(antenna_placemarks)
    kml_parts.append('    </Folder>\n')
    kml_parts.append(kml_footer())

    Path(args.out).write_text(''.join(kml_parts), encoding='utf-8')
    print(f'Wrote KML → {args.out}')

if __name__ == '__main__':
    main()
