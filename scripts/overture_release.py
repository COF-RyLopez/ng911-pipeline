"""
scripts/overture_release.py

The Overture release every build reads: $OVERTURE_RELEASE if set (to pin one, e.g. to reproduce an old
build), else the newest release, from Overture's STAC catalog or, if that is unreachable, from a listing
of the S3 release/ prefix. Overture keeps only about two releases on S3, so a hard-coded release goes
stale within about two months.

The resolved id is written back to os.environ, so every later call in the run, and every subprocess it
starts (dbt, other scripts), reads the same release even if Overture publishes mid-run.
"""
import os
import re
import urllib.request

BUCKET = "s3://overturemaps-us-west-2"
STAC_CATALOG = "https://stac.overturemaps.org/catalog.json"
S3_LISTING = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/?list-type=2&prefix=release/&delimiter=/"
RELEASE_ID = re.compile(r"\d{4}-\d{2}-\d{2}\.\d+")


def _newest(text):
    """The newest release id mentioned in a catalog or listing ('2026-11-18.0' sorts by date, then suffix)."""
    ids = set(RELEASE_ID.findall(text))
    return max(ids, key=lambda r: (r.split(".")[0], int(r.split(".")[1]))) if ids else None


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ng911-pipeline"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def release_id():
    rid = os.environ.get("OVERTURE_RELEASE", "").strip()
    if not rid:
        for url in (STAC_CATALOG, S3_LISTING):
            try:
                rid = _newest(_get(url))
            except OSError as e:
                print(f"[overture_release] {url} unreachable ({e}); trying the next source")
                rid = None
            if rid:
                break
        if not rid:
            raise SystemExit("Could not find the latest Overture release (STAC and the S3 listing both failed). "
                             "Set OVERTURE_RELEASE, e.g. OVERTURE_RELEASE=2026-11-18.0.")
        print(f"[overture_release] using the latest Overture release, {rid}")
        os.environ["OVERTURE_RELEASE"] = rid
    if not RELEASE_ID.fullmatch(rid):
        raise SystemExit(f"OVERTURE_RELEASE={rid!r} isn't a release id like 2026-11-18.0")
    return rid


def release_path():
    """s3://overturemaps-us-west-2/release/<release id>"""
    return f"{BUCKET}/release/{release_id()}"


def _test():
    assert _newest('"href": "./2026-10-21.0/catalog.json", "./2026-11-18.0/catalog.json"') == "2026-11-18.0"
    assert _newest("<Prefix>release/2026-11-18.0/</Prefix><Prefix>release/2026-11-18.1/</Prefix>") == "2026-11-18.1"
    assert _newest("<Prefix>release/2026-09-23.10/</Prefix><Prefix>release/2026-09-23.9/</Prefix>") == "2026-09-23.10"
    assert _newest("nothing here") is None


if __name__ == "__main__":
    _test()
    print(release_id())
