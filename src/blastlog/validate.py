from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


RAW_PATH = Path("data/raw/blast-match-data-Nuke.txt")
OUT_PATH = Path("data/processed/events.parquet")

KILL_SUBSTR = " killed "
WEAPON_RE = re.compile(r'with "(?P<weapon>[^"]+)"')
HEADSHOT_RE = re.compile(r"\(headshot\)")


def missing_report(df: pd.DataFrame, cols: list[str], title: str) -> None:
    print(f"\nMISSING-FIELD REPORT: {title}")
    present = [c for c in cols if c in df.columns]
    if not present:
        print("No requested columns exist in this dataframe.")
        return

    rep = (df[present].isna().mean() * 100).sort_values(ascending=False)
    print(rep.to_string(float_format=lambda x: f"{x:.2f}%"))

    # Optional: show counts too
    counts = df[present].isna().sum().sort_values(ascending=False)
    print("\nMissing counts:")
    print(counts.to_string())


def main() -> None:
    if not RAW_PATH.exists():
        raise SystemExit(f"Missing {RAW_PATH}")

    if not OUT_PATH.exists():
        raise SystemExit(
            f"Missing {OUT_PATH}. Run: python src/blastlog/parse.py"
        )

    # --- raw file checks ---
    raw_lines = RAW_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    total_lines = len(raw_lines)
    raw_kill_lines = [ln for ln in raw_lines if KILL_SUBSTR in ln]

    print("RAW FILE")
    print("Total lines:", total_lines)
    print("Lines containing ' killed ':", len(raw_kill_lines))
    if raw_kill_lines:
        print("\nExample raw kill line:")
        print(raw_kill_lines[0][:300])

    # --- parsed file checks ---
    df = pd.read_parquet(OUT_PATH)
    
    # Overall missingness (all events)
    missing_report(
        df,
        cols=[
            "dt", "event", "round",
            "player_name", "player_userid", "player_steam", "player_team",
            "attacker_name", "attacker_userid", "attacker_steam", "attacker_team",
            "victim_name", "victim_userid", "victim_steam", "victim_team",
            "weapon", "is_headshot",
        ],
        title="All events"
    )
    
    print("\nPARSED DATASET")
    print("Parsed rows:", len(df))
    if "event" in df.columns:
        # print("\nTop event labels:")
        # print(df["event"].value_counts().head(25))
        
        print("\nALL EVENT LABELS (sorted by count desc):")
        event_counts = df["event"].value_counts(dropna=False)

        # Print all, not just head()
        print(event_counts.to_string())

        print("\nTotal unique event labels:", event_counts.index.nunique())

        # Save to disk for easy sharing / debugging
        out_txt = Path("data/processed/event_counts.txt")
        out_txt.write_text(event_counts.to_string() + f"\n\nTotal unique: {event_counts.index.nunique()}\n",
                        encoding="utf-8")
        print("Wrote:", out_txt)

    # Kill rows based on msg (most reliable)
    if "msg" not in df.columns:
        raise SystemExit("Parsed file has no 'msg' column. Something is wrong.")

    msg = df["msg"].astype(str)
    kills = df[
        msg.str.contains(KILL_SUBSTR, na=False) &
        ~msg.str.contains(" killed other ", na=False)
    ].copy()
    
    if len(kills) > 0:
        missing_report(
            kills,
            cols=[
                "round",
                "attacker_name", "attacker_userid", "attacker_steam", "attacker_team",
                "victim_name", "victim_userid", "victim_steam", "victim_team",
                "weapon", "is_headshot",
            ],
            title="Kill events only"
        )
    
    print("Kill rows in parsed DF (PvP only):", len(kills))
    print("Kill rows in parsed DF (msg contains ' killed '):", len(kills))

    if len(raw_kill_lines) and len(kills) == 0:
        print("\n❌ Raw log contains kills, but parsed dataset has 0 kill rows.")
        print("That means parsing isn't matching dt/msg format or you're reading wrong file.")
        return

    # Missing field rates
    if len(kills) > 0:
        def miss(col: str) -> str:
            return f"{kills[col].isna().mean() * 100:.1f}% missing"

        cols = ["attacker_name", "victim_name", "weapon", "is_headshot", "round"]
        present_cols = [c for c in cols if c in kills.columns]

        print("\nMissing-field rates on kill rows:")
        for c in present_cols:
            print(f"- {c}: {miss(c)}")

        # Show samples with raw + extracted
        print("\nSamples (raw msg + extracted fields):")
        sample = kills.sort_values("dt").head(10)
        for _, r in sample.iterrows():
            msg = r["msg"]
            weapon_raw = WEAPON_RE.search(msg)
            weapon_raw = weapon_raw["weapon"] if weapon_raw else None
            hs_raw = bool(HEADSHOT_RE.search(msg))

            print("\n---")
            print("dt:", r.get("dt"), "| round:", r.get("round"))
            print("extracted attacker:", r.get("attacker_name"), "| victim:", r.get("victim_name"))
            print("extracted weapon:", r.get("weapon"), "| headshot:", r.get("is_headshot"))
            print("raw weapon:", weapon_raw, "| raw headshot:", hs_raw)
            print("msg:", msg[:260])

        # Quick sanity: top killers
        if "attacker_name" in kills.columns:
            print("\nTop killers:")
            print(kills.groupby("attacker_name").size().sort_values(ascending=False).head(15))

        # First kill per player
        if "attacker_name" in kills.columns:
            first_kill = (kills.sort_values("dt")
                          .groupby("attacker_name", as_index=False)
                          .first()[["attacker_name", "dt", "round", "victim_name", "weapon"]])
            print("\nFirst kill per player (first 15):")
            print(first_kill.head(15))

    print("\n✅ Validation complete.")


if __name__ == "__main__":
    main()