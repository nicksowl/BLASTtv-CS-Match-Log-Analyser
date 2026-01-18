import json
import re
from datetime import datetime
from pathlib import Path

IN_PATH = Path("data/processed/blast-match-data-Nuke.json")
OUT_PATH = Path("data/processed/blast-match-data-summary_with_rounds.json")

TS_RE = re.compile(r"^(?P<ts>\d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}): (?P<body>.*)$")

MATCH_START_RE = re.compile(r"^World triggered 'Match_Start' on '(?P<map>[^']+)'$")
TEAM_PLAYING_RE = re.compile(r"^MatchStatus: Team playing '(?P<side>CT|TERRORIST)': (?P<team>.+)$")
ROUND_START_RE = re.compile(r"^World triggered 'Round_Start'$")
ROUND_END_RE = re.compile(r"^World triggered 'Round_End'$")

# Notice examples:
# Team 'CT' triggered 'SFUI_Notice_CTs_Win' (CT '1') (T '0')
# Team 'CT' triggered 'SFUI_Notice_Bomb_Defused' (CT '2') (T '0')
# Team 'TERRORIST' triggered 'SFUI_Notice_Terrorists_Win' (CT '2') (T '1')
NOTICE_RE = re.compile(
    r"^Team '(?P<side>CT|TERRORIST)' triggered 'SFUI_Notice_(?P<notice>[^']+)' \(CT '(?P<ct>\d+)'\) \(T '(?P<t>\d+)'\)$"
)

# MatchStatus: Score: 1:0 on map 'de_nuke' RoundsPlayed: 1
SCORE_RE = re.compile(
    r"^MatchStatus: Score: (?P<ct>\d+):(?P<t>\d+) on map '(?P<map>[^']+)' RoundsPlayed: (?P<rp>\d+)$"
)

def parse_ts_body(line: str):
    m = TS_RE.match(line)
    if not m:
        return None, line.strip()
    ts = datetime.strptime(m.group("ts"), "%m/%d/%Y - %H:%M:%S").isoformat()
    return ts, m.group("body").strip()

def winner_side_from_notice(notice_side: str) -> str:
    return "CT" if notice_side == "CT" else "T"

def main():
    lines = json.load(open(IN_PATH, "r", encoding="utf-8"))

    match = {"map": None, "teams": {}, "final_score": None, "winner_team": None}
    rounds = []
    open_round = None

    last_score = None  # (ct, t, roundsplayed, map)

    for raw in lines:
        ts, body = parse_ts_body(raw)

        mm = MATCH_START_RE.match(body)
        if mm:
            match["map"] = mm.group("map")

        tm = TEAM_PLAYING_RE.match(body)
        if tm:
            side = tm.group("side")
            # normalise TERRORIST -> T
            match["teams"]["CT" if side == "CT" else "T"] = tm.group("team").strip()

        sm = SCORE_RE.match(body)
        if sm:
            last_score = (int(sm.group("ct")), int(sm.group("t")), int(sm.group("rp")), sm.group("map"))

        if ROUND_START_RE.match(body):
            # If a previous round never got a Round_End, keep it but mark it incomplete.
            if open_round is not None:
                open_round["complete"] = False
                rounds.append(open_round)

            open_round = {
                "round_no": len(rounds) + 1,
                "start_ts": ts,
                "end_ts": None,
                "complete": False,
                "winner_side": None,   # CT or T
                "winner_team": None,   # resolved later
                "score_after": None,   # {CT: x, T: y} from notice lines if present
                "notice": None,        # raw notice type
            }
            continue

        nm = NOTICE_RE.match(body)
        if nm and open_round is not None:
            side = winner_side_from_notice(nm.group("side"))
            ct = int(nm.group("ct"))
            t = int(nm.group("t"))
            open_round["winner_side"] = side
            open_round["notice"] = nm.group("notice")
            open_round["score_after"] = {"CT": ct, "T": t}

        if ROUND_END_RE.match(body) and open_round is not None:
            open_round["end_ts"] = ts
            open_round["complete"] = True
            rounds.append(open_round)
            open_round = None

    # If file ends with an open round
    if open_round is not None:
        open_round["complete"] = False
        rounds.append(open_round)

    # Resolve winner_team for rounds
    for r in rounds:
        side = r["winner_side"]
        if side in ("CT", "T"):
            r["winner_team"] = match["teams"].get(side)

    # Compute: number of completed rounds
    completed_rounds = [r for r in rounds if r["complete"]]
    match["rounds_started"] = sum(1 for r in rounds if r["start_ts"] is not None)
    match["rounds_completed"] = len(completed_rounds)

    # Final score and winner team: prefer MatchStatus score (most reliable)
    if last_score:
        ct, t, rp, _map = last_score
        match["final_score"] = {"CT": ct, "T": t, "rounds_played_reported": rp}

        if ct > t:
            match["winner_team"] = match["teams"].get("CT")
        elif t > ct:
            match["winner_team"] = match["teams"].get("T")

    out = {
        "match": match,
        "rounds": rounds,
        "notes": {
            "rule": "A round counts as completed only if it has both Round_Start and Round_End.",
            "incomplete_rounds": [r["round_no"] for r in rounds if not r["complete"]],
        },
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH}")
    print(f"Rounds started: {match['rounds_started']}")
    print(f"Rounds completed (Start->End): {match['rounds_completed']}")
    print(f"Final score: {match['final_score']}")
    print(f"Winner team: {match['winner_team']}")

if __name__ == "__main__":
    main()
