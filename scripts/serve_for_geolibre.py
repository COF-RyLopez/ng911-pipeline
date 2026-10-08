#!/usr/bin/env python3
"""
scripts/serve_for_geolibre.py

Launches a local CORS-enabled HTTP server with full HTTP 206 Byte-Range serving
support for data/output/ so any user can inspect 100% of NG911 pilot PMTiles,
GeoParquet, and GeoJSON layers directly in https://web.geolibre.app/

Supports HTTP range requests required by MapLibre / PMTiles in GeoLibre.
"""

import os
import re
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PORT = 8088
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "output")


class BetterThreadingHTTPServer(ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Suppress socket broken pipe / reset traces when client aborts tile ranges
        pass


class RangeCORSRequestHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=OUTPUT_DIR, **kwargs)

    def log_message(self, format, *args):
        # Filter out 206 tile access spam, but log index and other resources
        if "206" not in str(args):
            super().log_message(format, *args)

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

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(f.fileno())
        file_size = fs.st_size

        range_header = self.headers.get('Range')
        if range_header:
            match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else file_size - 1
                if start >= file_size:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    f.close()
                    return None
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", self.guess_type(path))
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                self.end_headers()
                f.seek(start)
                self.range_length = length
                return f

        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(file_size))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        self.range_length = None
        return f

    def copyfile(self, source, outputfile):
        try:
            if hasattr(self, 'range_length') and self.range_length is not None:
                bufsize = 64 * 1024
                remaining = self.range_length
                while remaining > 0:
                    chunk = source.read(min(bufsize, remaining))
                    if not chunk:
                        break
                    outputfile.write(chunk)
                    remaining -= len(chunk)
            else:
                super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True


def main():
    if not os.path.exists(OUTPUT_DIR):
        print(f"Error: Output directory {OUTPUT_DIR} does not exist. Run scripts/run_pilot.py first.")
        sys.exit(1)

    print("=" * 78)
    print("      GEOLIBRE LOCAL HTTP BYTE-RANGE DATA SERVER")
    print("=" * 78)
    print(f"Serving files from: {OUTPUT_DIR}")
    print(f"Local Server Base:  http://localhost:{PORT}/")
    print("-" * 78)
    print("PMTiles Archives (Full 100% County Coverage with Byte Serving):")
    print(f"  - Remediation Points (PMTiles): http://localhost:{PORT}/tiles/fresno_remediation.pmtiles")
    print(f"  - Road Centerlines (PMTiles):  http://localhost:{PORT}/tiles/fresno_rcl.pmtiles")
    print(f"  - QA Fishbones (PMTiles):      http://localhost:{PORT}/tiles/fresno_fishbones.pmtiles")
    print(f"  - SSAP Address Points:          http://localhost:{PORT}/tiles/fresno_ssap.pmtiles")
    print("-" * 78)
    print("HOW TO LOAD IN WEB.GEOLIBRE.APP:")
    print("  Local 1-Click Project URL:")
    print(f"    http://localhost:{PORT}/ng911_address_comparison_local.geolibre.json")
    print("=" * 78)
    print("Server running on http://127.0.0.1:8088/ ... Press Ctrl+C to stop.\n")

    httpd = BetterThreadingHTTPServer(('127.0.0.1', PORT), RangeCORSRequestHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
