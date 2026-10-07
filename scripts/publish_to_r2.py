#!/usr/bin/env python3
"""
scripts/publish_to_r2.py

Automated Cloudflare R2 Publisher for the Fresno County NG911 Pipeline.
Syncs cloud-native GeoParquet marts, PMTiles vector archives, and GeoLibre project
definitions to Cloudflare R2 object storage with zero egress fees and full
HTTP byte-range support (HTTP 206) for DuckDB-WASM and MapLibre streaming.
"""

import os
import sys
import mimetypes
import boto3
from botocore.config import Config

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "data", "output")

DEFAULT_PUBLIC_URL = "https://pub-152dce9299c94555bb415d992fe120e7.r2.dev"


def get_content_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".parquet":
        return "application/vnd.apache.parquet"
    elif ext == ".pmtiles":
        return "application/vnd.pmtiles"
    elif ext == ".geojson":
        return "application/geo+json"
    elif ext in [".json", ".geolibre"]:
        return "application/json"
    elif ext == ".csv":
        return "text/csv"
    content_type, _ = mimetypes.guess_type(file_path)
    return content_type or "application/octet-stream"


def main():
    print("=" * 70)
    print("     CLOUDFLARE R2 PIPELINE PUBLISHER (GEOPARQUET & PMTILES)")
    print("=" * 70)

    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    bucket_name = os.environ.get("R2_BUCKET_NAME")
    public_base_url = os.environ.get("R2_PUBLIC_URL", DEFAULT_PUBLIC_URL).rstrip("/")

    if not all([account_id, access_key, secret_key, bucket_name]):
        print("[NOTICE] Cloudflare R2 credentials not fully set in environment.")
        print("  Required: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME")
        print("  Skipping R2 publish step.")
        sys.exit(0)

    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
    print(f"Connecting to Cloudflare R2 Bucket: '{bucket_name}' via {endpoint_url}...")

    s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(retries={"max_attempts": 5, "mode": "standard"})
    )

    # Collect files to upload
    files_to_upload = []
    for root, _, files in os.walk(OUTPUT_DIR):
        for f in files:
            # Skip scratch, logs, temporary files
            if f.startswith(".") or f.endswith(".wal"):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in [".parquet", ".pmtiles", ".geojson", ".json", ".geolibre", ".csv"]:
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(abs_path, OUTPUT_DIR)
                files_to_upload.append((abs_path, rel_path))

    print(f"Found {len(files_to_upload)} deliverables to sync to R2...")

    uploaded_count = 0
    total_bytes = 0

    for abs_path, rel_path in sorted(files_to_upload, key=lambda x: x[1]):
        file_size = os.path.getsize(abs_path)
        content_type = get_content_type(abs_path)
        size_mb = file_size / (1024 * 1024)

        print(f"  -> Uploading '{rel_path}' ({size_mb:.2f} MB, {content_type})...")
        with open(abs_path, "rb") as f:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=rel_path,
                Body=f,
                ContentType=content_type,
                CacheControl="public, max-age=3600"
            )
        uploaded_count += 1
        total_bytes += file_size

    total_mb = total_bytes / (1024 * 1024)
    print("\n" + "=" * 70)
    print(f"  SUCCESSFULLY PUBLISHED {uploaded_count} FILES ({total_mb:.2f} MB) TO CLOUDFLARE R2")
    print("=" * 70)
    print(f"\nPublic R2 Root: {public_base_url}")
    print(f"1-Click GeoLibre Live Streaming Link:")
    print(f"  https://web.geolibre.app/?url={public_base_url}/ng911_address_comparison_r2.geolibre.json")


if __name__ == "__main__":
    main()
