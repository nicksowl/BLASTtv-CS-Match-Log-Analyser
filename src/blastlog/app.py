from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


DATA_PATH = Path("data/processed/events.parquet")


@st.cache_data
def load_events(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    # Ensure dt is datetime
    if "dt" in df.columns:
        df["dt"] = pd.to_datetime(df["dt"], errors="coerce")
    return df


def kill_events(df: pd.DataFrame) -> pd.DataFrame:
    # Most reliable: use the raw message substring
    return df[df["msg"].astype(str).str.contains(" killed ", na=False)].copy()


def main() -> None:
    st.set_page_config(page_title="BLAST CS Match Log Analyser", layout="wide")
    st.title("BLAST CS Match Log Analyser")
    st.caption("Because reading raw server logs is a punishment, not a hobby.")

    if not DATA_PATH.exists():
        st.error(
            f"Missing {DATA_PATH}. Run the parser first:\n\n"
            "python src/blastlog/parse.py"
        )
        st.stop()

    df = load_events(str(DATA_PATH))
    if df.empty:
        st.warning("Parsed dataset is empty.")
        st.stop()

    kills = kill_events(df)

    # Sidebar filters
    st.sidebar.header("Filters")

    # Team filter (attacker team is most useful for kill stats)
    teams_series = kills["attacker_team"] if "attacker_team" in kills.columns else pd.Series([], dtype="object")
    teams = sorted([t for t in teams_series.dropna().unique()])
    team = st.sidebar.selectbox("Attacker team", ["All"] + teams)

    # Round filter (use ALL events so slider starts at the first detected round, not first kill)
    # Round filter (use ALL events; never show 0)
    if "round" in df.columns and df["round"].notna().any():
        rmin = int(df["round"].dropna().min())
        rmax = int(df["round"].dropna().max())

        # If parsing uses 0 as a reset marker, don't expose it in UI
        rmin = max(1, rmin)

        round_range = st.sidebar.slider(
            "Round range",
            min_value=rmin,
            max_value=rmax,
            value=(rmin, rmax),
        )
    else:
        round_range = None

    # Apply filters
    kf = kills.copy()
    if team != "All" and "attacker_team" in kf.columns:
        kf = kf[kf["attacker_team"] == team]
    if round_range and "round" in kf.columns:
        kf = kf[kf["round"].between(round_range[0], round_range[1])]

    # KPI row
    c1, c2, c3 = st.columns(3)
    c1.metric("Events", f"{len(df):,}")
    c2.metric("Kills", f"{len(kf):,}")
    if "round" in df.columns and df["round"].notna().any():
        c3.metric("Rounds (detected)", f"{int(df['round'].dropna().max())}")
    else:
        c3.metric("Rounds (detected)", "N/A")

    st.markdown("---")

    left, right = st.columns(2)

    with left:
        st.subheader("Most kills")
        if "attacker_name" in kf.columns and kf["attacker_name"].notna().any():
            leaderboard = (kf.groupby("attacker_name")
                           .size()
                           .sort_values(ascending=False)
                           .reset_index(name="kills"))
            st.dataframe(leaderboard, use_container_width=True, height=420)
        else:
            st.info("No attacker_name extracted for kills yet.")

    with right:
        st.subheader("First kill per player")
        if "attacker_name" in kf.columns and kf["attacker_name"].notna().any():
            first_kill = (kf.sort_values("dt")
                          .groupby("attacker_name", as_index=False)
                          .first()[["attacker_name", "dt", "round", "victim_name", "weapon"]])
            st.dataframe(first_kill, use_container_width=True, height=420)
        else:
            st.info("No attacker_name extracted for kills yet.")

    st.markdown("---")

    st.subheader("Kills")
    sample_cols = [c for c in ["dt", "round", "attacker_name", "victim_name", "weapon", "is_headshot", "msg"] if c in kf.columns]
    st.dataframe(kf[sample_cols].head(200), use_container_width=True, height=320)


if __name__ == "__main__":
    main()