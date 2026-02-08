import os
import json
import pandas as pd

candles_dir = "data/candles"

required_columns = {
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "count",
    "taker_buy_volume", "taker_buy_quote_volume"
}

results = []

for fname in os.listdir(candles_dir):
    if not fname.endswith(".json"):
        continue
    
    path = os.path.join(candles_dir, fname)
    with open(path, "r") as f:
        data = json.load(f)
    
    if isinstance(data, dict) and "candles" in data:
        sample = data["candles"][0] if data["candles"] else {}
    elif isinstance(data, list):
        sample = data[0] if data else {}
    else:
        sample = {}
    
    keys = set(sample.keys())
    missing = required_columns - keys
    status = "OK" if not missing else f"Missing: {sorted(list(missing))}"
    
    results.append({
        "file": fname,
        "status": status
    })

df = pd.DataFrame(results)
print(df)

