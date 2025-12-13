import pandas as pd
from datetime import datetime
import json

def normalize_messy_csv(csv_path):
    df = pd.read_csv(csv_path)

    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    cols = df.columns.tolist()
    col_map = {
        "id": cols[0],
        "name": cols[1],
        "joined": cols[2],
        "value": cols[3],
    }

    def to_iso(x):
        if pd.isna(x):
            return None
        try:
            return pd.to_datetime(x).date().isoformat()
        except Exception:
            return None

    def to_int(x):
        try:
            return int(float(x))
        except Exception:
            return None

    records = []
    for _, row in df.iterrows():
        records.append({
            "id": to_int(row[col_map["id"]]),
            "name": str(row[col_map["name"]]),
            "joined": to_iso(row[col_map["joined"]]),
            "value": to_int(row[col_map["value"]]),
        })

    records.sort(key=lambda x: x["id"])
    return json.dumps(records)
