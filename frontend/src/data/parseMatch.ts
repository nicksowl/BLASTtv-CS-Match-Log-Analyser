import { loadJson } from "./loadJson";

/**
 * 1) match_faceit_key_events.json
 */
export type FaceitKeyEvents = {
  date: string;
  start_dt: string;
  end_dt: string;
  match_length: string;
  map: string;
  team_1: string;
  team_2: string;
  winning_team: string;
  final_score: string;
  total_rounds: number;
};

export const loadFaceitKeyEvents = () =>
  loadJson<FaceitKeyEvents>("/data/match_faceit_key_events.json");

/**
 * 2) match_round_events_extended.json
 */
export type MatchRoundEventsExtended = unknown;

export const loadMatchRoundEventsExtended = () =>
  loadJson<MatchRoundEventsExtended>("/data/match_round_events_extended.json");

/**
 * 3) match_start_end_roster_accolade.json
 */
export type TeamRoster = {
  side: string;
  roster: string[];
};

export type MatchStartEndRosterAccolade = {
  match_start: Record<string, TeamRoster>;
  match_end: Record<string, TeamRoster>;
  accolade_events: string[];
};

export const loadMatchStartEndRosterAccolade = () =>
  loadJson<MatchStartEndRosterAccolade>("/data/match_start_end_roster_accolade.json");

/**
 * 4) Export of all data from all files (in parallel)
 */
export type ParsedMatchData = {
  faceitKeyEvents: FaceitKeyEvents;
  matchRoundEventsExtended: MatchRoundEventsExtended;
  matchStartEndRosterAccolade: MatchStartEndRosterAccolade;
};

export const loadParsedMatchData = async (): Promise<ParsedMatchData> => {
  const [faceitKeyEvents, matchRoundEventsExtended, matchStartEndRosterAccolade] =
    await Promise.all([
      loadFaceitKeyEvents(),
      loadMatchRoundEventsExtended(),
      loadMatchStartEndRosterAccolade(),
    ]);

  return {
    faceitKeyEvents,
    matchRoundEventsExtended,
    matchStartEndRosterAccolade,
  };
};