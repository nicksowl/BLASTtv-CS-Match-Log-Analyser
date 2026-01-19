import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

FACEIT_PATH = Path("data/processed/match_faceit_key_events.json")
LOG_PATH = Path("data/raw/blast-match-data-Nuke.txt")
OUT_PATH = Path("data/processed/match_round_events.json")

DT_FORMAT = "%m/%d/%Y - %H:%M:%S"
TS_PREFIX_LEN = len("MM/DD/YYYY - HH:MM:SS")  # 19


def parse_line_dt(line: str) -> Optional[datetime]:
    try:
        return datetime.strptime(line[:TS_PREFIX_LEN], DT_FORMAT)
    except Exception:
        return None


def normalise_line_for_json(line: str) -> str:
    # Avoid \" in JSON by replacing quotes inside log lines
    return line.replace('"', "'")


def load_match_window(faceit_path: Path) -> tuple[datetime, datetime]:
    data = json.loads(faceit_path.read_text(encoding="utf-8"))
    return (
        datetime.strptime(data["start_dt"], DT_FORMAT),
        datetime.strptime(data["end_dt"], DT_FORMAT),
    )


def read_lines_in_window(log_path: Path, start_dt: datetime, end_dt: datetime) -> List[str]:
    lines: List[str] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        dt = parse_line_dt(line)
        if dt is not None and start_dt <= dt <= end_dt:
            lines.append(line)
    return lines


def group_non_empty_rounds(lines: List[str]) -> Dict[str, List[str]]:
    rounds: Dict[str, List[str]] = {}

    in_round = False
    round_num = 0
    current_key: Optional[str] = None
    current_events: List[str] = []

    for line in lines:
        if 'World triggered "Round_Start"' in line:
            in_round = True
            round_num += 1
            current_key = None
            current_events = []
            continue

        if in_round and 'World triggered "Round_End"' in line:
            if current_events:
                if current_key is None:
                    current_key = f"round_{round_num}"
                rounds[current_key] = current_events
            in_round = False
            current_key = None
            current_events = []
            continue

        if in_round:
            if current_key is None:
                current_key = f"round_{round_num}"
            current_events.append(normalise_line_for_json(line))

    return rounds


def main() -> None:
    start_dt, end_dt = load_match_window(FACEIT_PATH)
    windowed_lines = read_lines_in_window(LOG_PATH, start_dt, end_dt)

    rounds = group_non_empty_rounds(windowed_lines)
    total_event_lines = sum(len(events) for events in rounds.values())

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "round_count": len(rounds),
        "total_event_lines": total_event_lines,
        "rounds": rounds,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {len(rounds)} rounds / {total_event_lines} event lines to {OUT_PATH}")


if __name__ == "__main__":
    main()