import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

# -----------------------
# Paths 
# -----------------------
LOG_PATH: Path = Path("data/raw/blast-match-data-Nuke.txt")
KEY_EVENT_PATH: Path = Path("data/processed/match_faceit_key_events.json")
OUT_PATH: Path = Path("data/processed/match_start_end_roster_accolade.json")

TS_FMT: str = "%m/%d/%Y - %H:%M:%S"

# -----------------------
# Domain types
# -----------------------
class Side(str, Enum):
    CT = "CT"
    T = "TERRORIST"


TeamMap = dict[Side, str]
RosterBySide = dict[Side, list[str]]
Snapshot = dict[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class MatchData:
    """Extracted match slice we operate on (only lines within frame)."""
    start_ts: str
    end_ts: str
    events: list[str]


# -----------------------
# Regex (compiled once)
# -----------------------
LINE_TS_RE = re.compile(
    r'^(?P<ts>\d{1,2}/\d{1,2}/\d{4}\s*-\s*\d{2}:\d{2}:\d{2}):\s*'
)

TEAM_NAME_RE = re.compile(
    r'MatchStatus:\s*Team playing\s*"(?P<side>CT|TERRORIST)"\s*:\s*(?P<name>.+?)\s*$'
)

# "player<id><steam><CT>" dropped "m4a1"
PLAYER_SIDE_RE = re.compile(
    r'^.*:\s*"(?P<player>[^"<]+?)<\d+><[^>]*><(?P<side>CT|TERRORIST)>"\s+'
    r'(?:dropped|picked up)\s+".+?"\s*$'
)

ACCOLADE_MARKER_RE = re.compile(r"\bACCOLADE\b", re.IGNORECASE)
TAB_RE = re.compile(r"\t+")
MULTISPACE_RE = re.compile(r" +")


# -----------------------
# Parsing helpers
# -----------------------
def parse_ts(ts: str) -> datetime:
    """Parse a log timestamp string into a datetime."""
    return datetime.strptime(ts, TS_FMT)


def extract_line_ts(line: str) -> Optional[str]:
    """Return timestamp string from a log line (or None if absent)."""
    m = LINE_TS_RE.match(line)
    return m.group("ts") if m else None


def load_frame(path: Path) -> tuple[str, str]:
    """Load start/end timestamps from JSON frame file."""
    frame: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return str(frame["start_dt"]), str(frame["end_dt"])


# -----------------------
# Core extraction
# -----------------------
def iter_lines_in_range(path: Path, start_ts: str, end_ts: str) -> Iterable[str]:
    """
    Yield all lines in [start_ts, end_ts] inclusive.
    We parse timestamps per-line and filter.
    """
    start_dt: datetime = parse_ts(start_ts)
    end_dt: datetime = parse_ts(end_ts)

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line: str = raw.rstrip("\n")
            ts: Optional[str] = extract_line_ts(line)
            if ts is None:
                continue

            dt: datetime = parse_ts(ts)
            if start_dt <= dt <= end_dt:
                yield line


def extract_events_in_range(path: Path, start_ts: str, end_ts: str) -> list[str]:
    """Materialise all lines in range into a list (our working dataset)."""
    return list(iter_lines_in_range(path, start_ts, end_ts))


# -----------------------
# Match understanding
# -----------------------
def team_names_at_ts(events: list[str], target_ts: str) -> TeamMap:
    """
    Most recent CT/TERRORIST -> team names at or before target_ts.
    Prevents team mixing when sides swap.
    """
    target_dt: datetime = parse_ts(target_ts)
    mapping: TeamMap = {}

    for line in reversed(events):
        ts = extract_line_ts(line)
        if ts is None:
            continue

        dt = parse_ts(ts)
        if dt > target_dt:
            continue

        m = TEAM_NAME_RE.search(line)
        if not m:
            continue

        side = Side(m.group("side"))
        if side not in mapping:
            mapping[side] = m.group("name").strip()

        if Side.CT in mapping and Side.T in mapping:
            break

    mapping.setdefault(Side.CT, Side.CT.value)
    mapping.setdefault(Side.T, Side.T.value)
    return mapping


def _is_gotv(player_name: str) -> bool:
    """Filter out GOTV pseudo-player entries."""
    return player_name.strip().upper().endswith("GOTV")


def roster_from_exact_ts(
    events: list[str],
    target_ts: str,
    *,
    target_per_side: int = 5,
) -> RosterBySide:
    """
    Roster using only action lines at EXACT timestamp (match_start use-case).
    """
    players: dict[Side, set[str]] = {Side.CT: set(), Side.T: set()}

    for line in events:
        if extract_line_ts(line) != target_ts:
            continue

        m = PLAYER_SIDE_RE.match(line)
        if not m:
            continue

        player: str = m.group("player").strip()
        if _is_gotv(player):
            continue

        side: Side = Side(m.group("side"))
        players[side].add(player)

    return {
        side: sorted(names, key=str.lower)[:target_per_side]
        for side, names in players.items()
    }


def roster_at_end_backward(
    events: list[str],
    end_ts: str,
    *,
    target_per_side: int = 5,
) -> RosterBySide:
    """
    For end_dt, the exact second often contains too few actions.
    Scan backward within extracted events until we have enough unique players per side.
    """
    end_dt: datetime = parse_ts(end_ts)
    players: dict[Side, set[str]] = {Side.CT: set(), Side.T: set()}

    for line in reversed(events):
        ts = extract_line_ts(line)
        if ts is None:
            continue

        dt = parse_ts(ts)
        if dt > end_dt:
            continue

        m = PLAYER_SIDE_RE.match(line)
        if not m:
            continue

        player: str = m.group("player").strip()
        if _is_gotv(player):
            continue

        side: Side = Side(m.group("side"))
        players[side].add(player)

        if len(players[Side.CT]) >= target_per_side and len(players[Side.T]) >= target_per_side:
            break

    return {
        side: sorted(names, key=str.lower)[:target_per_side]
        for side, names in players.items()
    }


def build_snapshot(team_map: Mapping[Side, str], roster_by_side: Mapping[Side, list[str]]) -> Snapshot:
    """
    Output format:
    {
      "TeamName": {"side": "CT", "roster": [...]},
      "OtherTeam": {"side": "TERRORIST", "roster": [...]}
    }
    """
    out: Snapshot = {}
    for side in (Side.CT, Side.T):
        team_name: str = team_map.get(side, side.value)
        out[team_name] = {"side": side.value, "roster": roster_by_side.get(side, [])}
    return out


# -----------------------
# Accolades
# -----------------------
def normalise_whitespace(s: str) -> str:
    """Replace tabs with spaces and collapse repeated spaces."""
    s = TAB_RE.sub(" ", s)
    s = MULTISPACE_RE.sub(" ", s)
    return s.strip()


def extract_accolades_raw(events: Iterable[str]) -> list[str]:
    """Return accolades as a list of raw, cleaned strings only."""
    out: list[str] = []
    for line in events:
        if ACCOLADE_MARKER_RE.search(line):
            out.append(normalise_whitespace(line))
    return out


# -----------------------
# Output / display
# -----------------------
def pretty_print(result: Mapping[str, Any]) -> None:
    """Console output without JSON escaping."""
    print("match_start:")
    for team, data in result["match_start"].items():
        print(f"  {team} ({data['side']}): {data['roster']}")

    print("\nmatch_end:")
    for team, data in result["match_end"].items():
        print(f"  {team} ({data['side']}): {data['roster']}")

    print(f"\naccolade_events: {len(result['accolade_events'])}")
    for line in result["accolade_events"]:
        print(f"  {line}")


# -----------------------
# Main
# -----------------------
def main() -> None:
    start_ts, end_ts = load_frame(KEY_EVENT_PATH)

    events: list[str] = extract_events_in_range(LOG_PATH, start_ts, end_ts)
    match = MatchData(start_ts=start_ts, end_ts=end_ts, events=events)

    start_team_map: TeamMap = team_names_at_ts(match.events, match.start_ts)
    end_team_map: TeamMap = team_names_at_ts(match.events, match.end_ts)

    start_roster: RosterBySide = roster_from_exact_ts(match.events, match.start_ts, target_per_side=5)
    end_roster: RosterBySide = roster_at_end_backward(match.events, match.end_ts, target_per_side=5)

    accolades: list[str] = extract_accolades_raw(match.events)

    result: dict[str, Any] = {
        "match_start": build_snapshot(start_team_map, start_roster),
        "match_end": build_snapshot(end_team_map, end_roster),
        "accolade_events": accolades,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    pretty_print(result)


if __name__ == "__main__":
    main()