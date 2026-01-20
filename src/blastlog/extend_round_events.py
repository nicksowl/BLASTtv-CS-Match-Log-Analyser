from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional, TypedDict


# ----------------------------
# Paths / constants
# ----------------------------

PATH_IN: Path = Path("data/processed/match_round_events.json")
PATH_OUT: Path = Path("data/processed/match_round_events_extended.json")
JSON_INDENT: int = 2


# ----------------------------
# Regex patterns (log formats)
# ----------------------------

TS_RE = re.compile(r"^(\d{1,2}/\d{1,2}/\d{4})\s+-\s+(\d{2}:\d{2}:\d{2}):")
PLAYER_BLOB_RE = re.compile(r"^.+?<\d+><[^>]+><[^>]+>$")

KILL_RE = re.compile(
    r"""
    ^.*?:\s*'(?P<killer>[^']+)'\s+.*?
    killed\s+'(?P<victim>[^']+)'
    .*?\swith\s+'(?P<weapon>[^']+)'
    """,
    re.IGNORECASE | re.VERBOSE,
)

TEAM_SCORED_RE = re.compile(
    r"Team\s+'(?P<side>CT|TERRORIST)'\s+scored\s+'(?P<score>\d+)'",
    re.IGNORECASE,
)

MATCHSTATUS_TEAM_RE = re.compile(
    r"MatchStatus:\s*Team\s+playing\s+'(?P<side>CT|TERRORIST)'\s*:\s*(?P<team>.+?)\s*$",
    re.IGNORECASE,
)


# ----------------------------
# Typed structures
# ----------------------------

class KillEvent(TypedDict):
    time: Optional[str]     # "HH:MM:SS"
    killed_by: str
    killed: str
    weapon: str
    is_headshot: bool


class RoundSummary(TypedDict):
    round_start: Optional[str]
    round_end: Optional[str]
    round_length_seconds: Optional[int]
    round_length_minutes_seconds: Optional[str]
    winning_side: Optional[str]
    winning_team: Optional[str]
    total_kills: int
    mvp_kills_player: Optional[str]
    mvp_kills: int
    kill_events: list[KillEvent]


class MatchOverview(TypedDict, total=False):
    average_round_length: Optional[str]
    shortest_round: Optional[dict[str, Any]]
    longest_round: Optional[dict[str, Any]]
    mvp_kills: Optional[dict[str, Any]]
    lsp_deaths: Optional[dict[str, Any]]
    top_weapon: Optional[dict[str, Any]]
    most_headshots: Optional[dict[str, Any]]


# ----------------------------
# Time helpers
# ----------------------------

def parse_timestamp(line: str) -> Optional[datetime]:
    m = TS_RE.match(line)
    if not m:
        return None
    return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%m/%d/%Y %H:%M:%S")


def time_only(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")


def mmss_from_seconds(seconds: int) -> str:
    s = max(0, int(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


# ----------------------------
# Round timing
# ----------------------------

@dataclass(frozen=True)
class RoundTimes:
    start: datetime
    end: datetime

    @property
    def length_seconds(self) -> int:
        return int((self.end - self.start).total_seconds())

    @property
    def length_mmss(self) -> str:
        return mmss_from_seconds(self.length_seconds)


def infer_round_times(lines: Iterable[str]) -> Optional[RoundTimes]:
    dts = [dt for dt in (parse_timestamp(l) for l in lines) if dt is not None]
    if not dts:
        return None
    return RoundTimes(start=min(dts), end=max(dts))


# ----------------------------
# Kill extraction
# ----------------------------

def player_name(identity_blob: str) -> str:
    return identity_blob.split("<", 1)[0].strip()


def extract_kill_event(line: str) -> Optional[KillEvent]:
    lower = line.lower()
    if "killed other" in lower:
        return None

    m = KILL_RE.search(line)
    if not m:
        return None

    killer_blob = m.group("killer").strip()
    victim_blob = m.group("victim").strip()

    if not PLAYER_BLOB_RE.match(killer_blob):
        return None
    if not PLAYER_BLOB_RE.match(victim_blob):
        return None

    weapon = m.group("weapon").strip().lower()
    ts = parse_timestamp(line)
    t = time_only(ts) if ts else None

    return {
        "time": t,
        "killed_by": player_name(killer_blob),
        "killed": player_name(victim_blob),
        "weapon": weapon,
        "is_headshot": ("headshot" in lower),
    }


def compute_round_mvp(kill_events: list[KillEvent]) -> tuple[Optional[str], int]:
    counts: dict[str, int] = {}
    best_player: Optional[str] = None
    best_kills = 0

    for ev in kill_events:
        killer = ev["killed_by"]
        counts[killer] = counts.get(killer, 0) + 1
        if counts[killer] > best_kills:
            best_kills = counts[killer]
            best_player = killer

    return best_player, best_kills


# ----------------------------
# Winner extraction
# ----------------------------

def extract_scores(lines: Iterable[str]) -> dict[str, int]:
    scores: dict[str, int] = {}
    for line in lines:
        m = TEAM_SCORED_RE.search(line)
        if m:
            scores[m.group("side").upper()] = int(m.group("score"))
    return scores


def extract_team_map(lines: Iterable[str]) -> dict[str, str]:
    teams: dict[str, str] = {}
    for line in lines:
        m = MATCHSTATUS_TEAM_RE.search(line)
        if m:
            teams[m.group("side").upper()] = m.group("team").strip()
    return teams


def extract_winner(lines: Iterable[str]) -> tuple[Optional[str], Optional[str]]:
    scores = extract_scores(lines)
    teams = extract_team_map(lines)

    ct = scores.get("CT")
    t = scores.get("TERRORIST")
    if ct is None or t is None or ct == t:
        return None, None

    side = "CT" if ct > t else "TERRORIST"
    return side, teams.get(side)


# ----------------------------
# Round builder
# ----------------------------

def build_round_summary(lines: list[str]) -> RoundSummary:
    times = infer_round_times(lines)

    kill_events: list[KillEvent] = []
    for line in lines:
        ev = extract_kill_event(line)
        if ev:
            kill_events.append(ev)

    total_kills = len(kill_events)
    mvp_player, mvp_kills = compute_round_mvp(kill_events) if kill_events else (None, 0)
    winning_side, winning_team = extract_winner(lines)

    if times is None:
        return {
            "round_start": None,
            "round_end": None,
            "round_length_seconds": None,
            "round_length_minutes_seconds": None,
            "winning_side": winning_side,
            "winning_team": winning_team,
            "total_kills": total_kills,
            "mvp_kills_player": mvp_player,
            "mvp_kills": mvp_kills,
            "kill_events": kill_events,
        }

    return {
        "round_start": time_only(times.start),
        "round_end": time_only(times.end),
        "round_length_seconds": times.length_seconds,
        "round_length_minutes_seconds": times.length_mmss,
        "winning_side": winning_side,
        "winning_team": winning_team,
        "total_kills": total_kills,
        "mvp_kills_player": mvp_player,
        "mvp_kills": mvp_kills,
        "kill_events": kill_events,
    }


# ----------------------------
# Match overview builder
# ----------------------------

def build_match_overview(rounds: dict[str, RoundSummary]) -> MatchOverview:
    lengths: list[tuple[str, int]] = [
        (rk, rs["round_length_seconds"])
        for rk, rs in rounds.items()
        if isinstance(rs.get("round_length_seconds"), int)
    ]

    overview: MatchOverview = {
        "average_round_length": None,
        "shortest_round": None,
        "longest_round": None,
        "mvp_kills": None,
        "lsp_deaths": None,
        "top_weapon": None,
        "most_headshots": None,
    }

    if lengths:
        total = sum(sec for _, sec in lengths)
        avg = int(round(total / len(lengths)))
        overview["average_round_length"] = mmss_from_seconds(avg)

        r_short, s_short = min(lengths, key=lambda x: x[1])
        r_long, s_long = max(lengths, key=lambda x: x[1])

        overview["shortest_round"] = {"round": r_short, "length": mmss_from_seconds(s_short), "length_seconds": s_short}
        overview["longest_round"] = {"round": r_long, "length": mmss_from_seconds(s_long), "length_seconds": s_long}

    kills_by_player: dict[str, int] = {}
    deaths_by_player: dict[str, int] = {}
    kills_by_weapon: dict[str, int] = {}
    headshots_by_player: dict[str, int] = {}

    for rs in rounds.values():
        for ev in rs["kill_events"]:
            killer = ev["killed_by"]
            victim = ev["killed"]
            weapon = ev["weapon"]

            kills_by_player[killer] = kills_by_player.get(killer, 0) + 1
            deaths_by_player[victim] = deaths_by_player.get(victim, 0) + 1
            kills_by_weapon[weapon] = kills_by_weapon.get(weapon, 0) + 1

            if ev["is_headshot"]:
                headshots_by_player[killer] = headshots_by_player.get(killer, 0) + 1

    if kills_by_player:
        p, k = max(kills_by_player.items(), key=lambda kv: kv[1])
        overview["mvp_kills"] = {"player": p, "kills": k}

    if deaths_by_player:
        p, d = max(deaths_by_player.items(), key=lambda kv: kv[1])
        overview["lsp_deaths"] = {"player": p, "deaths": d}

    if kills_by_weapon:
        w, k = max(kills_by_weapon.items(), key=lambda kv: kv[1])
        overview["top_weapon"] = {"weapon": w, "kills": k}

    if headshots_by_player:
        p, h = max(headshots_by_player.items(), key=lambda kv: kv[1])
        overview["most_headshots"] = {"player": p, "headshots": h}

    return overview


# ----------------------------
# Transformation + I/O
# ----------------------------

def transform(input_data: dict[str, Any]) -> dict[str, Any]:
    """
    Output format:
    {
      "rounds": { "round_1": {...}, ... },
      "match_overview": {...}
    }

    Note: We intentionally drop round_count / total_event_lines (and anything else top-level).
    """
    rounds_in = input_data.get("rounds")
    if not isinstance(rounds_in, dict):
        raise ValueError("Input JSON must contain a 'rounds' object mapping round keys to lists of event lines.")

    rounds_out: dict[str, RoundSummary] = {}
    for round_key, lines in rounds_in.items():
        if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
            raise ValueError(f"Round '{round_key}' must be a list of strings.")
        rounds_out[round_key] = build_round_summary(lines)

    return {
        "rounds": rounds_out,
        "match_overview": build_match_overview(rounds_out),
    }


def write_json_safely(path: Path, payload: dict[str, Any]) -> None:
    """
    Write JSON to disk with a clear error if it fails.
    This is the "fallback" you asked for: it fails loudly and cleanly.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=JSON_INDENT),
        encoding="utf-8",
    )


def run() -> int:
    """
    Main execution wrapper.
    Returns an exit code (0 success, 1 failure) instead of exploding silently.
    """
    try:
        if not PATH_IN.exists():
            print(f"[ERROR] Input JSON not found: {PATH_IN}")
            return 1

        raw = PATH_IN.read_text(encoding="utf-8")
        data: dict[str, Any] = json.loads(raw)

        extended = transform(data)
        write_json_safely(PATH_OUT, extended)

        rounds_count = len(extended.get("rounds", {}))
        print(f"[OK] JSON created: {PATH_OUT}")
        print(f"[OK] Rounds processed: {rounds_count}")
        print(f"[OK] Overview keys: {list((extended.get('match_overview') or {}).keys())}")
        return 0

    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in input file: {PATH_IN}")
        print(f"[ERROR] {e}")
        return 1
    except Exception as e:
        print(f"[ERROR] Failed to create output JSON.")
        print(f"[ERROR] {type(e).__name__}: {e}")
        return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()