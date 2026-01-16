from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd


LINE_RE = re.compile(
    r'^(?P<date>\d{2}/\d{2}/\d{4}) - (?P<time>\d{2}:\d{2}:\d{2}): (?P<msg>.*)$'
)

# Finds the first player token in the line, if present:
# "name<userid><STEAM_...><TEAM>"
PLAYER_RE = re.compile(
    r'"(?P<name>[^"<]+?)<(?P<userid>\d+)><(?P<steam>STEAM_[^>]+)><(?P<team>[^>]*)>"'
)

def first_n_players(msg: str, n: int = 2) -> list[dict]:
    players = []
    for m in PLAYER_RE.finditer(msg):
        players.append({
            "name": m["name"],
            "userid": int(m["userid"]),
            "steam": m["steam"],
            "team": m["team"] or None,
        })
        if len(players) >= n:
            break
    return players

def parse_player_token(token: str) -> dict:
    """
    token looks like: "name<userid><STEAM_...><TEAM>"
    """
    m = PLAYER_RE.search(token)
    if not m:
        return {
            "name": None, "userid": None, "steam": None, "team": None
        }
    return {
        "name": m["name"],
        "userid": int(m["userid"]),
        "steam": m["steam"],
        "team": m["team"] or None,
    }

TRIGGERED_RE = re.compile(r'triggered "(?P<trigger>[^"]+)"')
PLAYER_VERB_RE = re.compile(r'"\s*[^"]+?"\s+(?P<verb>[a-z][a-z ]+?)\s+"')  # e.g. '"A" killed "B"'
PLAYER_ACTION_RE = re.compile(r'"\s*[^"]+?"\s+(?P<verb>[a-z][a-z ]+?)\s+') # e.g. '"A" purchased ...'

KILL_RE = re.compile(
    r'^(?P<attacker>"[^"]+?<\d+><STEAM_[^>]+><[^>]*>")\s+killed\s+'
    r'(?P<victim>"[^"]+?<\d+><STEAM_[^>]+><[^>]*>")'
    r'.*?\s+with\s+"(?P<weapon>[^"]+)"'
    r'(?P<extra>.*)$'
)
WEAPON_RE = re.compile(r'with "(?P<weapon>[^"]+)"')
HEADSHOT_RE = re.compile(r"\(headshot\)")


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def classify_event(msg: str) -> str:
    """
    Return a stable event label for *every* line.

    Priority:
    1) Any triggered "<X>" event -> "trigger_<x>"
    2) Player vs player style verbs (killed/attacked/assisted...) -> verb slug (e.g. "killed", "attacked")
    3) Player action verbs (purchased/picked up/dropped/...) -> verb slug
    4) Connection-ish system messages -> specific labels
    5) Otherwise -> "other"
    """

    # 1) triggered events (World or player triggered "Something")
    t = TRIGGERED_RE.search(msg)
    if t:
        return "trigger_" + slugify(t["trigger"])

    # 2) Player vs player lines often look like:  "A<...>" killed "B<...>" with "ak47"
    pv = PLAYER_VERB_RE.search(msg)
    if pv:
        return slugify(pv["verb"])

    # 3) Player action lines like: "A<...>" purchased "ak47"
    pa = PLAYER_ACTION_RE.search(msg)
    if pa:
        return slugify(pa["verb"])

    # 4) Known system-ish patterns that don't match the above well
    if " connected, address " in msg:
        return "connect"
    if " entered the game" in msg:
        return "enter_game"
    if " disconnected" in msg:
        return "disconnect"
    if " switched from team " in msg:
        return "team_switch"
    if " say " in msg or " say_team " in msg:
        return "chat"

    return "other"


@dataclass(frozen=True)
class ParsedLine:
    dt: pd.Timestamp
    event: str
    msg: str
    round: int | None

    attacker_name: str | None
    attacker_userid: int | None
    attacker_steam: str | None
    attacker_team: str | None

    victim_name: str | None
    victim_userid: int | None
    victim_steam: str | None
    victim_team: str | None

    weapon: str | None
    is_headshot: bool | None


def iter_parsed_lines(path: Path) -> Iterator[ParsedLine]:
    """
    Parse the raw log file and yield structured rows.

    Rules:
    - We only yield events that happen during "real gameplay": between
      trigger_round_start and trigger_round_end (inclusive).
    - We ALSO keep restart markers: trigger_restart_round_1_second.
    - We maintain a derived round counter by counting trigger_round_start.
    - On restart_round_1_second we reset state so the next round_start becomes round 1.
    """

    current_round: int | None = None
    in_round = False

    ROUND_START_EVENTS = {"trigger_round_start"}
    ROUND_END_EVENTS = {
        "trigger_round_end",
        "trigger_round_officially_end",
        "trigger_round_ended",
    }
    RESTART_EVENTS = {"trigger_restart_round_1_second"}

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            m = LINE_RE.match(line)
            if not m:
                continue

            dt = pd.to_datetime(
                f"{m['date']} {m['time']}",
                format="%m/%d/%Y %H:%M:%S",
                errors="coerce",
            )
            if pd.isna(dt):
                continue

            msg = m["msg"]
            event = classify_event(msg)

            # --- restart handling (keep + reset state) ---
            if event in RESTART_EVENTS:
                in_round = False
                current_round = 0  # so next Round_Start becomes round 1

            # --- round start ---
            if event in ROUND_START_EVENTS:
                in_round = True
                if current_round is None or current_round == 0:
                    current_round = 1
                else:
                    current_round += 1

            # Decide whether to keep this row:
            keep_boundary = event in (ROUND_START_EVENTS | ROUND_END_EVENTS | RESTART_EVENTS)
            if not in_round and not keep_boundary:
                continue

            # --- field extraction (kills etc.) ---
            attacker = {"name": None, "userid": None, "steam": None, "team": None}
            victim = {"name": None, "userid": None, "steam": None, "team": None}
            weapon = None
            is_headshot = None

            # Robust kill extraction (don’t rely on a strict full-line regex)
            if " killed " in msg:
                players = first_n_players(msg, n=2)
                if len(players) >= 2:
                    attacker = players[0]
                    victim = players[1]

                w = WEAPON_RE.search(msg)
                weapon = w["weapon"] if w else None
                is_headshot = bool(HEADSHOT_RE.search(msg))

            yield ParsedLine(
                dt=dt,
                event=event,
                msg=msg,
                round=current_round,

                attacker_name=attacker["name"],
                attacker_userid=attacker["userid"],
                attacker_steam=attacker["steam"],
                attacker_team=attacker["team"],

                victim_name=victim["name"],
                victim_userid=victim["userid"],
                victim_steam=victim["steam"],
                victim_team=victim["team"],

                weapon=weapon,
                is_headshot=is_headshot,
            )

            # Flip in_round off AFTER recording the round end marker itself
            if event in ROUND_END_EVENTS:
                in_round = False


def parse_to_dataframe(path: Path) -> pd.DataFrame:
    rows = [pl.__dict__ for pl in iter_parsed_lines(path)]
    df = pd.DataFrame(rows)
    # Normalise round numbers so the first detected round becomes 1
    if "round" in df.columns and df["round"].notna().any():
        first_round = int(df["round"].dropna().min())
        if first_round > 1:
            df["round"] = df["round"] - (first_round - 1)

    # Make sure dt is datetime64[ns] in pandas
    if not df.empty:
        df["dt"] = pd.to_datetime(df["dt"], errors="coerce")
        df = df.dropna(subset=["dt"])

    return df


def main() -> None:
    raw_path = Path("data/raw/blast-match-data-Nuke.txt")
    out_path = Path("data/processed/events.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not raw_path.exists():
        raise SystemExit(
            f"Missing input file at {raw_path}. Put your .txt there first."
        )

    df = parse_to_dataframe(raw_path)
    print("Parsed rows:", len(df))
    print(df["event"].value_counts().head(10))

    df.to_parquet(out_path, index=False)
    print("Wrote:", out_path)


if __name__ == "__main__":
    main()