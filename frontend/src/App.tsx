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
 * Safely preview unknown JSON.
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
 * Normalise team-side naming conventions.
 */
function normaliseSide(sideRaw: unknown): { isCT: boolean; isT: boolean } {
  const side = String(sideRaw ?? "").toLowerCase();
  const isCT = side.includes("ct");
  const isT = side === "t" || side.includes("terror");
  return { isCT, isT };
}

/**
 * Border colour for roster chips (text stays black).
 */
function sideBorderColour(sideRaw: unknown): string {
  const { isCT, isT } = normaliseSide(sideRaw);
  return isCT ? "lightblue" : isT ? "salmon" : "divider";
}

/**
 * Sort "round_1, round_2, ..." by the numeric suffix.
 */
function sortRoundKeys(keys: string[]): string[] {
  const toNum = (k: string) => {
    const m = k.match(/\d+/);
    return m ? Number(m[0]) : Number.POSITIVE_INFINITY;
  };
  return [...keys].sort((a, b) => toNum(a) - toNum(b));
}

export default function App() {
  // -----------------------------
  // Data + error state
  // -----------------------------
  const [data, setData] = useState<ParsedMatchData | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // -----------------------------
  // UI state
  // -----------------------------
  const [isMatchExpanded, setIsMatchExpanded] = useState(false);
  const [isRoundsOverviewOpen, setIsRoundsOverviewOpen] = useState(false);
  const [isAccoladesOpen, setIsAccoladesOpen] = useState(false);

  /**
   * Allow multiple rounds to be open simultaneously.
   * `Set` gives O(1) membership checks.
   */
  const [openRoundKeys, setOpenRoundKeys] = useState<Set<string>>(new Set());

  // -----------------------------
  // Load data once on mount
  // -----------------------------
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

  // -----------------------------
  // Derived: match overview (from extended json)
  // -----------------------------
  const matchOverview = useMemo(() => {
    const ext: any = data?.matchRoundEventsExtended;
    const mo = ext?.match_overview;
    return mo && typeof mo === "object" ? mo : null;
  }, [data]);

  // -----------------------------
  // Derived: rounds dictionary (from extended json)
  // -----------------------------
  const roundsMap = useMemo(() => {
    const ext: any = data?.matchRoundEventsExtended;
    const rounds = ext?.rounds;
    if (rounds && typeof rounds === "object" && !Array.isArray(rounds)) {
      return rounds as Record<string, any>;
    }
    return null;
  }, [data]);

  const roundKeys = useMemo(() => {
    if (!roundsMap) return [];
    return sortRoundKeys(Object.keys(roundsMap));
  }, [roundsMap]);

  // -----------------------------
  // Actions / toggles
  // -----------------------------
  const toggleRound = (rk: string) => {
    setOpenRoundKeys((prev) => {
      const next = new Set(prev);
      if (next.has(rk)) next.delete(rk);
      else next.add(rk);
      return next;
    });
  };

  /**
   * Expand/collapse match details.
   * When collapsing, also reset sub-panels to keep the UI sane.
   */
  const toggleMatchExpanded = () => {
    setIsMatchExpanded((prev) => {
      const next = !prev;
      if (!next) {
        setIsRoundsOverviewOpen(false);
        setIsAccoladesOpen(false);
        setOpenRoundKeys(new Set());
      }
      return next;
    });
  };

  /**
   * Toggle rounds overview.
   * When closing it, also close the accolades panel.
   */
  const toggleRoundsOverview = () => {
    setIsRoundsOverviewOpen((prev) => {
      const next = !prev;
      if (next) setOpenRoundKeys(new Set());
      if (!next) setIsAccoladesOpen(false);
      return next;
    });
  };

  /**
   * Toggle accolade panel (only available under open rounds overview section).
   */
  const toggleAccolades = () => setIsAccoladesOpen((v) => !v);

  // -----------------------------
  // Styles: reuse button look
  // -----------------------------
  const primaryButtonSx = {
    borderRadius: 3,
    textTransform: "none" as const,
    fontWeight: 900,
    px: 3,
    py: 1.1,
    userSelect: "none" as const,
    opacity: 0.9,
  };

  const secondaryButtonSx = {
    ...primaryButtonSx,
    px: 2.25,
    py: 0.9,
    opacity: 0.88,
  };

  // -----------------------------
  // Render helpers
  // -----------------------------
  const renderRosterBlock = (block: Record<string, { side: string; roster: string[] }>) => (
    <Grid container spacing={2}>
      {Object.entries(block).map(([teamName, team]) => {
        const border = sideBorderColour(team.side);

        return (
          <Grid item xs={12} sm={6} key={teamName}>
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
                    borderColor: border, // CT/T colour is border only
                    "& .MuiChip-label": { fontWeight: 500 }, // slightly lighter
                  }}
                />
              ))}
            </Stack>
          </Grid>
        );
      })}
    </Grid>
  );

  // Convenience refs
  const faceit = data?.faceitKeyEvents;
  const accolades = data?.matchStartEndRosterAccolade?.accolade_events ?? [];

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
      {/* Main layout container */}
      <Box
        sx={{
          width: "100%",
          maxWidth: 1100,
          mx: "auto",
          px: 3,
          py: 4,
        }}
      >
        {/* Header */}
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
          <SportsEsportsIcon />
          <Typography variant="h5" fontWeight={700}>
            Blastlog - CS Match Logs Analyser
          </Typography>
        </Stack>

        {/* Error state */}
        {err && <Alert severity="error">{err}</Alert>}

        {/* Loading state */}
        {!err && !data && (
          <Stack direction="row" spacing={2} alignItems="center">
            <CircularProgress />
            <Typography>Loading match data…</Typography>
          </Stack>
        )}

        {/* Main content */}
        {data && faceit && (
          <Box>
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Stack spacing={1}>
                  {/* Match headline + expand */}
                  <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
                    <Typography variant="h6" fontWeight={900}>
                      Date: {faceit.date} • {faceit.team_1} vs {faceit.team_2} • Final score: {faceit.final_score} •
                      Map: {faceit.map}
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

                  {/* Expanded section */}
                  {isMatchExpanded && (
                    <Box sx={{ mt: 1 }}>
                      <Divider sx={{ mb: 2 }} />

                      {/* Overview */}
                      <Typography variant="subtitle1" fontWeight={900} sx={{ textAlign: "center", mb: 1 }}>
                        Overview
                      </Typography>

                      <Stack spacing={1.25} alignItems="center" sx={{ width: "100%" }}>
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap justifyContent="center">
                          <Chip label={`Start: ${faceit.start_dt}`} />
                          <Chip label={`End: ${faceit.end_dt}`} />
                        </Stack>

                        <Chip
                          label={`Winning team: ${faceit.winning_team}`}
                          color="success"
                          variant="filled"
                          sx={{ fontWeight: 800, opacity: 0.9 }}
                        />

                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap justifyContent="center">
                          <Chip label={`Total match length (hh:mm:ss): ${faceit.match_length}`} />
                          <Chip label={`Total rounds: ${faceit.total_rounds}`} />
                        </Stack>

                        {/* Everything below relies on extended overview being present */}
                        {matchOverview && (
                          <>
                            <Divider sx={{ width: "100%", my: 1 }} />

                            {/* Teams */}
                            <Typography variant="subtitle1" fontWeight={900} sx={{ textAlign: "center", mb: 1 }}>
                              Teams
                            </Typography>

                            <Grid container spacing={2} sx={{ mb: 1 }} justifyContent="center">
                              <Grid item xs={12} md={6}>
                                <Card variant="outlined" sx={{ height: "100%" }}>
                                  <CardContent>
                                    <Typography fontWeight={900} sx={{ textAlign: "center", mb: 1 }}>
                                      Match start
                                    </Typography>
                                    {renderRosterBlock(data.matchStartEndRosterAccolade.match_start)}
                                  </CardContent>
                                </Card>
                              </Grid>

                              <Grid item xs={12} md={6}>
                                <Card variant="outlined" sx={{ height: "100%" }}>
                                  <CardContent>
                                    <Typography fontWeight={900} sx={{ textAlign: "center", mb: 1 }}>
                                      Match end
                                    </Typography>
                                    {renderRosterBlock(data.matchStartEndRosterAccolade.match_end)}
                                  </CardContent>
                                </Card>
                              </Grid>
                            </Grid>

                            <Divider sx={{ width: "100%", my: 1 }} />

                            {/* Highlights */}
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

                            {/* Rounds overview */}
                            <Typography variant="subtitle1" fontWeight={900} sx={{ textAlign: "center", mb: 1 }}>
                              Rounds overview
                            </Typography>

                            <Stack alignItems="center" sx={{ mb: 2 }}>
                              <Button variant="contained" size="large" sx={primaryButtonSx} onClick={toggleRoundsOverview}>
                                {isRoundsOverviewOpen ? "Hide" : "View"}
                              </Button>
                            </Stack>

                            {isRoundsOverviewOpen && (
                              <Box sx={{ display: "flex", justifyContent: "center" }}>
                                <Box sx={{ width: "100%", maxWidth: 980 }}>
                                  {/* Rounds grid */}
                                  {!roundsMap ? (
                                    <Alert severity="warning">
                                      Couldn’t find <code>matchRoundEventsExtended.rounds</code> in the JSON.
                                    </Alert>
                                  ) : (
                                    <Grid container spacing={2} justifyContent="center" sx={{ mb: 2 }}>
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
                                                <Stack direction="row" justifyContent="space-between" alignItems="center">
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

                                  <Divider sx={{ width: "100%", my: 2 }} />

                                  {/* bonus button */}
                                  <Stack alignItems="center" sx={{ mb: 2 }}>
                                    <Button
                                      variant="contained"
                                      size="small"
                                      sx={secondaryButtonSx}
                                      onClick={toggleAccolades}
                                    >
                                      {isAccoladesOpen ? "Hide" : "See Bonus: Accolade events!"}
                                    </Button>
                                  </Stack>

                                  {/* Accolade events panel */}
                                  {isAccoladesOpen && (
                                    <Card variant="outlined">
                                      <CardContent>
                                        <Typography fontWeight={900} sx={{ mb: 1 }}>
                                          Accolade events
                                        </Typography>

                                        {accolades.length ? (
                                          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                            {accolades.map((a, idx) => (
                                              <Chip key={idx} label={a} />
                                            ))}
                                          </Stack>
                                        ) : (
                                          <Typography sx={{ opacity: 0.7 }}>
                                            No accolade events found in this match.
                                          </Typography>
                                        )}
                                      </CardContent>
                                    </Card>
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