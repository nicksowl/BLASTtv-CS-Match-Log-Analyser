import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Union


# ----------------------------
# Regex patterns (compiled once)
# ----------------------------

FACEIT_ANY_RE = re.compile(r"FACEIT\^*", re.IGNORECASE)

# Timestamp prefix: 11/28/2021 - 20:26:21:
LOG_TS_RE = re.compile(
    r"^(?P<date>\d{2}/\d{2}/\d{4}) - (?P<time>\d{2}:\d{2}:\d{2}):\s*"
)

# FACEIT key event patterns
FACEIT_MAP = re.compile(r"\bBlocked map\s+(?P<map>de_[a-z0-9_]+)\b", re.IGNORECASE)
FACEIT_MATCH_START = re.compile(r"\bAdmin\b.*\bstarted the match\b", re.IGNORECASE)

# Winner line: "... Team <name> won."
FACEIT_WIN_LINE = re.compile(r"\bTeam\b.*\bwon\b", re.IGNORECASE)
FACEIT_WINNER = re.compile(
    r"\bTeam\s+(?P<team>\"[^\"]+\"|'[^']+'|.+?)\s+won\b",
    re.IGNORECASE,
)

# Score markers like [0 - 1], [16 - 6], etc.
FACEIT_SCORE_ANY = re.compile(r"\[\s*\d+\s*-\s*\d+\s*\]")
FACEIT_SCORE_VALUE = re.compile(r"\[\s*(?P<a>\d+)\s*-\s*(?P<b>\d+)\s*\]")

FACEIT_SCORE_MARKER = re.compile(r"\[\s*0\s*-\s*1\s*\]")

# Capture: <teamA> [0 - 1] <teamB>
FACEIT_TEAMS_FROM_SCORE = re.compile(
    r"(?P<left>.+?)\s*\[\s*0\s*-\s*1\s*\]\s*(?P<right>.+)",
    re.IGNORECASE,
)

# Extract rounds played from MatchStatus lines:
# Example fragment: "MatchStatus: Score: 6:16 ... RoundsPlayed: 22 ..."
# Not inside the FACEIT block, but useful to get the actual rounds played in same file.
ROUNDS_PLAYED_RE = re.compile(r"\bRoundsPlayed:\s*(?P<rounds>\d+)\b", re.IGNORECASE)


# Types for JSON-friendly output
JSONScalar = Union[str, int, float, bool, None]
JSONValue = Union[JSONScalar, List["JSONValue"], Dict[str, "JSONValue"]]


# ----------------------------
# Data containers
# ----------------------------

@dataclass
class ParsedLog:
    faceit_lines: List[str]
    faceit_key_events: Dict[str, JSONValue]


# ----------------------------
# Low-level helpers
# ----------------------------

def extract_faceit_lines(log_path: Union[str, Path]) -> List[str]:
    path = Path(log_path)
    faceit_lines: List[str] = []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if FACEIT_ANY_RE.search(line):
                faceit_lines.append(line.rstrip("\n"))

    return faceit_lines


def extract_dt_parts(line: str) -> Optional[Tuple[str, str]]:
    m = LOG_TS_RE.match(line)
    if not m:
        return None
    return m.group("date"), m.group("time")


def strip_prefix_timestamp(line: str) -> str:
    return LOG_TS_RE.sub("", line).strip()


def clean_team_name(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"[\x00-\x1F\x7F]", "", s)  # control chars
    s = re.sub(r"\[\s*FACEIT\^*\s*\]", "", s, flags=re.IGNORECASE)  # FACEIT tags

    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()

    s = re.sub(r"^\s*Team\s+", "", s, flags=re.IGNORECASE).strip()
    s = s.strip(" \t\r\n|:-.!,")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_two_teams_from_score_line(line: str) -> Optional[Tuple[str, str]]:
    payload = strip_prefix_timestamp(line)
    m = FACEIT_TEAMS_FROM_SCORE.search(payload)
    if not m:
        return None

    left = m.group("left").split(":")[-1].strip()
    right = m.group("right")

    team_1 = clean_team_name(left)
    team_2 = clean_team_name(right)

    if len(team_1) < 2 or len(team_2) < 2:
        return None

    return team_1, team_2


def extract_score_from_line(line: str) -> Optional[str]:
    m = FACEIT_SCORE_VALUE.search(line)
    if not m:
        return None
    return f"{m.group('a')}-{m.group('b')}"


def calculate_match_length_pretty(start_dt: Optional[str], end_dt: Optional[str]) -> Optional[str]:
    if not start_dt or not end_dt:
        return None

    try:
        start = datetime.strptime(start_dt, "%m/%d/%Y - %H:%M:%S")
        end = datetime.strptime(end_dt, "%m/%d/%Y - %H:%M:%S")
    except ValueError:
        return None

    seconds = int((end - start).total_seconds())
    if seconds < 0:
        return None

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def calculate_total_rounds(log_path: Union[str, Path]) -> Optional[int]:
    """
    Despite the name, this returns the round count for this match by extracting:
      RoundsPlayed: <n>
    """
    path = Path(log_path)
    rounds: Optional[int] = None

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = ROUNDS_PLAYED_RE.search(line)
            if m:
                rounds = int(m.group("rounds"))  # keep the last seen value (final status)
    return rounds


# ----------------------------
# High-level extraction
# ----------------------------

def extract_faceit_match_key_events(
    faceit_lines: List[str],
    total_rounds: Optional[int] = None,
) -> Dict[str, JSONValue]:
    match_date: Optional[str] = None
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None

    map_name: Optional[str] = None
    team_1: Optional[str] = None
    team_2: Optional[str] = None
    winning_team: Optional[str] = None
    final_score: Optional[str] = None

    for line in faceit_lines:
        if map_name is None:
            m_map = FACEIT_MAP.search(line)
            if m_map:
                map_name = m_map.group("map").lower()

        if start_dt is None and FACEIT_MATCH_START.search(line):
            parts = extract_dt_parts(line)
            if parts:
                d, t = parts
                start_dt = f"{d} - {t}"
                match_date = match_date or d

        if team_1 is None and team_2 is None and FACEIT_SCORE_MARKER.search(line):
            teams = extract_two_teams_from_score_line(line)
            if teams:
                team_1, team_2 = teams

        if FACEIT_WIN_LINE.search(line):
            parts = extract_dt_parts(line)
            if parts:
                d, t = parts
                end_dt = f"{d} - {t}"
                match_date = match_date or d

            m_win = FACEIT_WINNER.search(line)
            if m_win:
                winning_team = clean_team_name(m_win.group("team"))

        if FACEIT_SCORE_ANY.search(line):
            score = extract_score_from_line(line)
            if score:
                final_score = score

    match_length = calculate_match_length_pretty(start_dt, end_dt)

    return {
        "date": match_date,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "match_length": match_length,
        "map": map_name,
        "team_1": team_1,
        "team_2": team_2,
        "winning_team": winning_team,
        "final_score": final_score,
        "total_rounds": total_rounds,  # actually rounds played (e.g. 22)
    }


def parse_log(log_path: Union[str, Path]) -> ParsedLog:
    faceit_lines = extract_faceit_lines(log_path)

    total_rounds = calculate_total_rounds(log_path)

    faceit_key_events = extract_faceit_match_key_events(
        faceit_lines=faceit_lines,
        total_rounds=total_rounds,
    )
    return ParsedLog(faceit_lines=faceit_lines, faceit_key_events=faceit_key_events)


def dump_json(data: Dict[str, JSONValue], out_path: Union[str, Path]) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return path


# ----------------------------
# CLI entry point (for quick testing)
# ----------------------------

if __name__ == "__main__":
    log_file = Path("data/raw/blast-match-data-Nuke.txt")
    parsed = parse_log(log_file)

    print(f"FACEIT lines found: {len(parsed.faceit_lines)}\n")
    for i, line in enumerate(parsed.faceit_lines, start=1):
        print(f"{i:04d}: {line}")

    out_file = dump_json(parsed.faceit_key_events, "data/processed/match_faceit_key_events.json")
    print(f"\nWrote: {out_file}")
    print(f"\nOutput:")
    print(json.dumps(parsed.faceit_key_events, indent=2))