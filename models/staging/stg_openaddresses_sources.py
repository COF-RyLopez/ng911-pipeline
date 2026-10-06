import os
import json
import glob
import pandas as pd

def model(dbt, session):
    # Points to a local clone of openaddresses/openaddresses/sources/us/ca/*.json
    source_dir = os.environ.get("OA_SOURCE_DIR", "sources/us/ca/")
    records = []

    for filepath in glob.glob(os.path.join(source_dir, "*.json")):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                # Filter layers that contain valid addresses
                for layer in data.get("layers", {}).get("addresses", []):
                    records.append({
                        "source_file": os.path.basename(filepath),
                        "municipal_endpoint": data.get("data"),
                        "layer_type": data.get("type"),
                        "hn_field": layer.get("number"),
                        "street_field": layer.get("street"),
                        "postcode_field": layer.get("postcode")
                    })
        except Exception:
            continue

    if not records:
        return pd.DataFrame(columns=[
            "source_file",
            "municipal_endpoint",
            "layer_type",
            "hn_field",
            "street_field",
            "postcode_field"
        ])

    return pd.DataFrame(records)
