import json
from pathlib import Path


in_path = Path("data/raw/blast-match-data-Nuke.txt")
out_path = Path("data/processed/blast-match-data-Nuke.json")


lines = []
with open(in_path, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        # replace quotes inside the log line
        line = line.replace('"', "'")
        lines.append(line)

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(lines, f, ensure_ascii=False, indent=2)

print(f"Wrote {out_path} with {len(lines)} lines")
