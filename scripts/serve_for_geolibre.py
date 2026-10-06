#!/usr/bin/env python3
"""
scripts/serve_for_geolibre.py

Launches a local CORS-enabled HTTP server serving data/output/
so any user can inspect NG911 pilot layers directly in https://web.geolibre.app/
without needing ESRI ArcGIS or desktop GIS software installed.
Supports HTTP byte-range requests for direct GeoParquet querying in the browser.
"""

import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8088
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "output")

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=OUTPUT_DIR, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range, Content-Type, Accept')
        self.send_header('Access-Control-Expose-Headers', 'Content-Range, Content-Length, Accept-Ranges')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def main():
    if not os.path.exists(OUTPUT_DIR):
        print(f"Error: Output directory {OUTPUT_DIR} does not exist. Run scripts/run_pilot.py first.")
        sys.exit(1)

    print("=" * 78)
    print("      GEOLIBRE WEB VIEWER (https://web.geolibre.app/) LOCAL DATA PROVIDER")
    print("=" * 78)
    print(f"Serving files from: {OUTPUT_DIR}")
    print(f"Local Server Base:  http://localhost:{PORT}/")
    print("-" * 78)
    print("Available NG911 Layers for GeoLibre (GeoJSON & GeoParquet):")
    print(f"  1. SSAP Address Points (GeoJSON):  http://localhost:{PORT}/mart_ng911_fresno_ssap_sample.geojson")
    print(f"  2. RCL Road Centerlines (GeoJSON): http://localhost:{PORT}/mart_ng911_fresno_rcl_sample.geojson")
    print(f"  3. QA Fishbone Vectors (GeoJSON):  http://localhost:{PORT}/mart_ng911_fresno_fishbones_sample.geojson")
    print(f"  4. Full SSAP Points (Parquet):     http://localhost:{PORT}/mart_ng911_fresno_ssap.parquet")
    print(f"  5. Full RCL Centerlines (Parquet): http://localhost:{PORT}/mart_ng911_fresno_rcl.parquet")
    print(f"  6. QA Discrepancies (Parquet):     http://localhost:{PORT}/mart_ng911_fresno_qa_discrepancies.parquet")
    print("-" * 78)
    print("HOW TO VIEW IN WEB.GEOLIBRE.APP (Zero-Install / Non-ESRI):")
    print("  Method A (Drag & Drop - Recommended):")
    print("    1. Open https://web.geolibre.app/ in Chrome/Firefox/Safari.")
    print("    2. Drag and drop any .geojson or .parquet file from:")
    print(f"       {OUTPUT_DIR}")
    print("       directly onto the map.")
    print("  Method B (URL Streaming):")
    print("    1. In https://web.geolibre.app/, click 'Add Layer' / '+' icon.")
    print("    2. Paste one of the local URLs listed above.")
    print("=" * 78)
    print("Server running. Press Ctrl+C to stop.\n")

    httpd = HTTPServer(('127.0.0.1', PORT), CORSRequestHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
