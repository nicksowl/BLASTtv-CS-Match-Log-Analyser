// frontend/src/App.tsx
import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  Stack,
  Typography,
} from "@mui/material";
import SportsEsportsIcon from "@mui/icons-material/SportsEsports";

import { loadParsedMatchData, type ParsedMatchData } from "./data/parseMatch";

/**
 * Pretty-print unknown JSON objects safely.
 * Useful while you’re still exploring the shape of `match_round_events_extended.json`.
 */
function safeJsonPreview(value: unknown, maxChars = 9000): string {
  try {
    const s = JSON.stringify(value, null, 2);
    return s.length > maxChars ? s.slice(0, maxChars) + "\n…(truncated)" : s;
  } catch {
    return String(value);
  }
}

/**
 * Determine the roster chip border colour based on team side.
 * - CT => lightblue
 * - T  => salmon
 * - other/unknown => divider
 *
 * We normalise because data sources love inventing new side strings.
 */
function sideBorderColour(sideRaw: unknown): string {
  const side = String(sideRaw ?? "").toLowerCase();
  const isCT = side.includes("ct");
  const isT = side === "t" || side.includes("terror");
  return isCT ? "lightblue" : isT ? "salmon" : "divider";
}

export default function App() {
  // --- Data loading state ---
  const [data, setData] = useState<ParsedMatchData | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // --- UI state ---
  const [isMatchExpanded, setIsMatchExpanded] = useState(false);
  const [isRoundsOverviewOpen, setIsRoundsOverviewOpen] = useState(false);

  /**
   * Allow opening multiple rounds at once.
   * We store open round keys in a Set for O(1) membership checks.
   */
  const [openRoundKeys, setOpenRoundKeys] = useState<Set<string>>(new Set());

  /**
   * Load parsed match data once on mount.
   * The `cancelled` flag prevents setting state after unmount.
   */
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const all = await loadParsedMatchData();
        if (!cancelled) setData(all);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  /**
   * Extract `match_overview` from matchRoundEventsExtended (if present).
   * Using `any` temporarily keeps us flexible while the schema evolves.
   */
  const matchOverview = useMemo(() => {
    const ext: any = data?.matchRoundEventsExtended;
    const mo = ext?.match_overview;
    return mo && typeof mo === "object" ? mo : null;
  }, [data]);

  /**
   * Extract the rounds dictionary from extended data:
   * expected shape: { rounds: { round_1: {...}, round_2: {...}, ... } }
   */
  const roundsMap = useMemo(() => {
    const ext: any = data?.matchRoundEventsExtended;
    const rounds = ext?.rounds;
    if (rounds && typeof rounds === "object" && !Array.isArray(rounds)) {
      return rounds as Record<string, any>;
    }
    return null;
  }, [data]);

  /**
   * Sort round keys naturally by round number (round_1, round_2, ...).
   */
  const roundKeys = useMemo(() => {
    if (!roundsMap) return [];
    const keys = Object.keys(roundsMap);

    const toNum = (k: string) => {
      const m = k.match(/\d+/);
      return m ? Number(m[0]) : Number.POSITIVE_INFINITY;
    };

    return keys.sort((a, b) => toNum(a) - toNum(b));
  }, [roundsMap]);

  /**
   * Toggle a round open/closed without closing others.
   */
  const toggleRound = (rk: string) => {
    setOpenRoundKeys((prev) => {
      const next = new Set(prev);
      if (next.has(rk)) next.delete(rk);
      else next.add(rk);
      return next;
    });
  };

  /**
   * Toggle match expansion.
   * When collapsing, also collapse rounds UI for a clean state reset.
   */
  const toggleMatchExpanded = () => {
    setIsMatchExpanded((prev) => {
      const next = !prev;
      if (!next) {
        setIsRoundsOverviewOpen(false);
        setOpenRoundKeys(new Set());
      }
      return next;
    });
  };

  /**
   * Toggle rounds overview.
   * When opening, clear which rounds are open for a clean start.
   */
  const toggleRoundsOverview = () => {
    setIsRoundsOverviewOpen((prev) => {
      const next = !prev;
      if (next) setOpenRoundKeys(new Set());
      return next;
    });
  };

  /**
   * Render a single "roster card" for start/end.
   * This removes duplicated JSX and keeps roster styles consistent.
   */
  const renderRosterCard = (
    title: string,
    rosterBlock: Record<string, { side: string; roster: string[] }>
  ) => (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent>
        <Typography fontWeight={900} sx={{ textAlign: "center", mb: 1 }}>
          {title}
        </Typography>

        <Grid container spacing={2}>
          {Object.entries(rosterBlock).map(([teamName, team]) => {
            const border = sideBorderColour(team.side);

            return (
              <Grid item xs={12} sm={6} key={`${title}-${teamName}`}>
                <Typography fontWeight={900}>{teamName}</Typography>

                <Typography variant="body2" sx={{ opacity: 0.75, mb: 1 }}>
                  Side: {team.side}
                </Typography>

                <Stack spacing={0.5}>
                  {team.roster.map((p) => (
                    <Chip
                      key={p}
                      label={p}
                      size="small"
                      variant="outlined"
                      sx={{
                        color: "text.primary", // keep text black
                        borderColor: border, // colour via border only
                        "& .MuiChip-label": { fontWeight: 500 }, // lighter font weight
                      }}
                    />
                  ))}
                </Stack>
              </Grid>
            );
          })}
        </Grid>
      </CardContent>
    </Card>
  );

  return (
    <Box
      sx={{
        minHeight: "100vh",
        width: "100%",
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-start",
      }}
    >
      {/* Main page container */}
      <Box
        sx={{
          width: "100%",
          maxWidth: 1100,
          mx: "auto",
          px: 3,
          py: 4,
        }}
      >
        {/* Page header */}
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
          <SportsEsportsIcon />
          <Typography variant="h5" fontWeight={700}>
            BLASTlog - CS Match Logs Analyser
          </Typography>
        </Stack>

        {/* Errors */}
        {err && <Alert severity="error">{err}</Alert>}

        {/* Loading state */}
        {!err && !data && (
          <Stack direction="row" spacing={2} alignItems="center">
            <CircularProgress />
            <Typography>Loading match data…</Typography>
          </Stack>
        )}

        {/* Main content */}
        {data && (
          <Box>
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Stack spacing={1}>
                  {/* Match headline row */}
                  <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
                    <Typography variant="h6" fontWeight={900}>
                      Date: {data.faceitKeyEvents.date} • {data.faceitKeyEvents.team_1} vs{" "}
                      {data.faceitKeyEvents.team_2} • Final score: {data.faceitKeyEvents.final_score} • Map:{" "}
                      {data.faceitKeyEvents.map}
                    </Typography>

                    <Chip
                      label={isMatchExpanded ? "Hide" : "Expand"}
                      size="small"
                      variant="outlined"
                      clickable
                      sx={{ mt: 0.25, flexShrink: 0, cursor: "pointer", userSelect: "none" }}
                      onClick={toggleMatchExpanded}
                    />
                  </Stack>

                  {/* Expanded area */}
                  {isMatchExpanded && (
                    <Box sx={{ mt: 1 }}>
                      <Divider sx={{ mb: 2 }} />

                      <Typography variant="subtitle1" fontWeight={900} sx={{ textAlign: "center", mb: 1 }}>
                        Overview
                      </Typography>

                      <Stack spacing={1.25} alignItems="center" sx={{ width: "100%" }}>
                        {/* Start/End */}
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap justifyContent="center">
                          <Chip label={`Start: ${data.faceitKeyEvents.start_dt}`} />
                          <Chip label={`End: ${data.faceitKeyEvents.end_dt}`} />
                        </Stack>

                        {/* Winner */}
                        <Chip
                          label={`Winning team: ${data.faceitKeyEvents.winning_team}`}
                          color="success"
                          variant="filled"
                          sx={{ fontWeight: 800, opacity: 0.9 }}
                        />

                        {/* Totals */}
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap justifyContent="center">
                          <Chip label={`Total match length (hh:mm:ss): ${data.faceitKeyEvents.match_length}`} />
                          <Chip label={`Total rounds: ${data.faceitKeyEvents.total_rounds}`} />
                        </Stack>

                        {/* Everything below depends on extended overview existing */}
                        {matchOverview && (
                          <>
                            <Divider sx={{ width: "100%", my: 1 }} />

                            <Typography variant="subtitle1" fontWeight={900} sx={{ textAlign: "center", mb: 1 }}>
                              Teams
                            </Typography>

                            <Grid container spacing={2} sx={{ mb: 1 }} justifyContent="center">
                              <Grid item xs={12} md={6}>
                                {renderRosterCard("Match start", data.matchStartEndRosterAccolade.match_start)}
                              </Grid>
                              <Grid item xs={12} md={6}>
                                {renderRosterCard("Match end", data.matchStartEndRosterAccolade.match_end)}
                              </Grid>
                            </Grid>

                            <Divider sx={{ width: "100%", my: 1 }} />

                            <Typography variant="subtitle1" fontWeight={900} sx={{ textAlign: "center", mb: 1 }}>
                              Highlights
                            </Typography>

                            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap justifyContent="center">
                              <Chip label={`AVG round length (mm:ss): ${matchOverview.average_round_length}`} />
                              <Chip
                                label={`Shortest round (mm:ss): ${matchOverview.shortest_round?.round} (${matchOverview.shortest_round?.length})`}
                              />
                              <Chip
                                label={`Longest round (mm:ss): ${matchOverview.longest_round?.round} (${matchOverview.longest_round?.length})`}
                              />
                              <Chip
                                label={`MVP kills (player - kills): ${matchOverview.mvp_kills?.player} (${matchOverview.mvp_kills?.kills})`}
                              />
                              <Chip
                                label={`LVP (player - deaths): ${matchOverview.lsp_deaths?.player} (${matchOverview.lsp_deaths?.deaths})`}
                              />
                              <Chip
                                label={`Top weapon (kills): ${matchOverview.top_weapon?.weapon} (${matchOverview.top_weapon?.kills})`}
                              />
                              <Chip
                                label={`Most headshots (player): ${matchOverview.most_headshots?.player} (${matchOverview.most_headshots?.headshots})`}
                              />
                            </Stack>

                            <Divider sx={{ width: "100%", my: 2 }} />

                            <Typography variant="subtitle1" fontWeight={900} sx={{ textAlign: "center", mb: 1 }}>
                              Rounds overview
                            </Typography>

                            <Stack alignItems="center" sx={{ mb: 2 }}>
                              <Button
                                variant="contained"
                                size="large"
                                sx={{
                                  borderRadius: 3,
                                  textTransform: "none",
                                  fontWeight: 900,
                                  px: 3,
                                  py: 1.1,
                                  userSelect: "none",
                                  opacity: 0.9,
                                }}
                                onClick={toggleRoundsOverview}
                              >
                                {isRoundsOverviewOpen ? "Hide" : "View"}
                              </Button>
                            </Stack>

                            {/* Rounds grid */}
                            {isRoundsOverviewOpen && (
                              <Box sx={{ display: "flex", justifyContent: "center" }}>
                                <Box sx={{ width: "100%", maxWidth: 980 }}>
                                  {!roundsMap ? (
                                    <Alert severity="warning">
                                      Couldn’t find <code>matchRoundEventsExtended.rounds</code> in the JSON.
                                    </Alert>
                                  ) : (
                                    <Grid container spacing={2} justifyContent="center">
                                      {roundKeys.map((rk) => {
                                        const isOpen = openRoundKeys.has(rk);
                                        const roundData = (roundsMap as any)[rk];

                                        return (
                                          <Grid item xs={12} sm={6} md={4} key={rk}>
                                            <Card
                                              variant="outlined"
                                              sx={{ width: "100%", height: "100%", cursor: "pointer" }}
                                              onClick={() => toggleRound(rk)}
                                            >
                                              <CardContent sx={{ py: 1.75, "&:last-child": { pb: 1.75 } }}>
                                                <Stack
                                                  direction="row"
                                                  justifyContent="space-between"
                                                  alignItems="center"
                                                >
                                                  <Typography fontWeight={900}>{rk}</Typography>
                                                  <Chip
                                                    label={isOpen ? "Hide" : "Open"}
                                                    size="small"
                                                    variant="outlined"
                                                    sx={{ flexShrink: 0, userSelect: "none" }}
                                                  />
                                                </Stack>

                                                {isOpen && (
                                                  <Box sx={{ mt: 1 }}>
                                                    <Divider sx={{ mb: 1 }} />
                                                    <Box
                                                      component="pre"
                                                      sx={{
                                                        m: 0,
                                                        p: 1.5,
                                                        borderRadius: 2,
                                                        bgcolor: "rgba(0,0,0,0.04)",
                                                        overflow: "auto",
                                                        maxHeight: 300,
                                                        fontSize: 12,
                                                      }}
                                                    >
                                                      {safeJsonPreview(roundData, 12000)}
                                                    </Box>
                                                  </Box>
                                                )}
                                              </CardContent>
                                            </Card>
                                          </Grid>
                                        );
                                      })}
                                    </Grid>
                                  )}
                                </Box>
                              </Box>
                            )}
                          </>
                        )}
                      </Stack>
                    </Box>
                  )}
                </Stack>
              </CardContent>
            </Card>
          </Box>
        )}
      </Box>
    </Box>
  );
}