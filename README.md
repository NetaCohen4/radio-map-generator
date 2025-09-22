# Radio Coverage Map Generator

Transform raw CSV measurement data into colorful KML coverage maps (Voice/Data) for visualization in Google Earth or Google My Maps.
The project processes cellular network measurements, interpolates coverage in unmeasured areas, and generates intuitive maps with color-coded signal strength.


Example coverage map generated with this tool.




## 🚀 Features

Convert CSV logs of cellular signal measurements into KML maps.

Support for multiple providers, measurement types (voice/data).

Grid-based interpolation to predict coverage in unmeasured areas.

Color-coded map tiles for quick visual insights.

Configurable thresholds for green/yellow/orange/red zones.

Works seamlessly with Google Earth, Google My Maps, and other KML viewers.

## 📂 Input Data

The tool expects a CSV file with at least:

LAT – Latitude

LON – Longitude

SIGNAL – Signal strength (dBm)

Additional columns (e.g., timestamp, provider, cell ID) may be included for filtering.

⚡ Installation & Quick Start
## Clone the repository
git clone https://github.com/yourusername/radio-map-generator.git
cd radio-map-generator

## (Optional) create a virtual environment
python3 -m venv venv
source venv/bin/activate   # Linux / macOS
venv\Scripts\activate      # Windows

## Install dependencies
pip install -r requirements.txt

🖥 Command Line Usage

Basic usage:

python cellmap_kml_generator.py \
  --measurements input.csv \
  --antennas antennas.csv \
  --out coverage_map.kml \
  --metric auto \
  --grid_step_deg 0.0005 \
  --tile_alpha 160


Main arguments:

--measurements : CSV file with signal measurements

--antennas : CSV with antenna metadata (optional but recommended)

--out : Output KML file

--metric : Signal metric (RSRP, RSRQ, RSSI, or auto)

--grid_step_deg : Grid resolution in degrees (default: 0.0005)

--tile_alpha : Tile transparency (0–255)

## 🌍 Examples
Road coverage map
python cellmap_kml_generator.py --measurements road.csv --out road.kml

Urban coverage with antenna data
python cellmap_kml_generator.py \
  --measurements ariel_measurements.csv \
  --antennas antennas.csv \
  --out ariel_coverage.kml

🎨 Color Scale & Legend

Green – Strong coverage

Yellow – Good coverage

Orange – Weak coverage

Red – Poor or no coverage

Thresholds can be customized inside the script.

❓ FAQ / Troubleshooting

Q: I get Error: CSV missing LAT/LON columns.
→ Make sure your CSV header includes exactly LAT and LON.

Q: Why does my map look “all red”?
→ Adjust signal thresholds or verify the measurement metric used.

🛠 Roadmap

 Add interactive web viewer (Leaflet/Mapbox).

 Support for heatmaps.

 Automatic legend generation.

 Jupyter notebook examples.

🤝 Contributing & License

Pull requests are welcome! For major changes, please open an issue first.
Distributed under the MIT License. See LICENSE for details.
