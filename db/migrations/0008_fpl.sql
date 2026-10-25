-- FPL per-gameweek player data of 2025-26, from the vaastav/Fantasy-Premier-League
-- archive. Its own table, not player_match_stats: Understat already writes minutes,
-- goals, and assists there for Arsenal's matches, and the two sources must not mix.

CREATE TABLE fpl_player_match (
    player_id integer NOT NULL REFERENCES players (id),
    match_id integer NOT NULL REFERENCES matches (id),
    team_id integer NOT NULL REFERENCES teams (id),
    gameweek smallint NOT NULL CHECK (gameweek BETWEEN 1 AND 38),
    -- Only rows with minutes: a player who did not play has no FPL numbers.
    minutes smallint NOT NULL CHECK (minutes > 0),
    goals smallint NOT NULL CHECK (goals >= 0),
    assists smallint NOT NULL CHECK (assists >= 0),
    clean_sheet boolean NOT NULL,
    saves smallint NOT NULL CHECK (saves >= 0),
    bonus smallint NOT NULL CHECK (bonus BETWEEN 0 AND 3),
    -- BPS and points can be negative: a red card or an own goal takes points away.
    bps smallint NOT NULL,
    yellow_cards smallint NOT NULL CHECK (yellow_cards BETWEEN 0 AND 1),
    red_cards smallint NOT NULL CHECK (red_cards BETWEEN 0 AND 1),
    defensive_contribution smallint NOT NULL CHECK (defensive_contribution >= 0),
    points smallint NOT NULL,
    price numeric(4, 1) NOT NULL CHECK (price > 0),
    PRIMARY KEY (player_id, match_id)
);

CREATE INDEX fpl_player_match_match_id_idx ON fpl_player_match (match_id);

CREATE VIEW v_fpl_player_match AS
SELECT
    f.match_id,
    s.label AS season,
    m.match_date,
    f.gameweek,
    p.name AS player,
    t.name AS team,
    CASE WHEN f.team_id = m.home_team_id THEN at.name ELSE ht.name END AS opponent,
    f.minutes,
    f.goals,
    f.assists,
    f.clean_sheet,
    f.saves,
    f.bonus,
    f.bps,
    f.yellow_cards,
    f.red_cards,
    f.defensive_contribution,
    f.points,
    f.price
FROM fpl_player_match f
JOIN matches m ON m.id = f.match_id
JOIN seasons s ON s.id = m.season_id
JOIN players p ON p.id = f.player_id
JOIN teams t ON t.id = f.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id;

COMMENT ON VIEW v_fpl_player_match IS 'One row per player per league match played, for every Premier League player in 2025-26 only. Source: Fantasy Premier League (FPL), via the vaastav/Fantasy-Premier-League archive. No xG: use v_player_match for xG.';
COMMENT ON COLUMN v_fpl_player_match.match_id IS 'Match identifier. Join key to v_league_matches and v_player_match.';
COMMENT ON COLUMN v_fpl_player_match.season IS 'Season label. Always 2025-26.';
COMMENT ON COLUMN v_fpl_player_match.match_date IS 'Date the match was played.';
COMMENT ON COLUMN v_fpl_player_match.gameweek IS 'FPL gameweek of the match, 1 to 38. A double gameweek has two matches.';
COMMENT ON COLUMN v_fpl_player_match.player IS 'Canonical player name.';
COMMENT ON COLUMN v_fpl_player_match.team IS 'Team the player played for in this match.';
COMMENT ON COLUMN v_fpl_player_match.opponent IS 'The other team in the match.';
COMMENT ON COLUMN v_fpl_player_match.minutes IS 'Minutes played in the match, as FPL counts them.';
COMMENT ON COLUMN v_fpl_player_match.goals IS 'Goals scored, own goals excluded. In Arsenal matches they equal the goals of v_player_match, except one: FPL gives Noni Madueke a goal in Leeds v Arsenal on 2026-01-31 that v_player_match counts as an own goal.';
COMMENT ON COLUMN v_fpl_player_match.assists IS 'Assists by the FPL rule, which can differ from the assists of v_player_match.';
COMMENT ON COLUMN v_fpl_player_match.clean_sheet IS 'True when FPL gave the player a clean sheet: no goal conceded while on the pitch for 60 minutes or more.';
COMMENT ON COLUMN v_fpl_player_match.saves IS 'Saves made, for goalkeepers.';
COMMENT ON COLUMN v_fpl_player_match.bonus IS 'FPL bonus points, 0 to 3, given to the best BPS scores of the match.';
COMMENT ON COLUMN v_fpl_player_match.bps IS 'FPL Bonus Points System score. Can be negative.';
COMMENT ON COLUMN v_fpl_player_match.yellow_cards IS 'Yellow cards, 0 or 1.';
COMMENT ON COLUMN v_fpl_player_match.red_cards IS 'Red cards, 0 or 1.';
COMMENT ON COLUMN v_fpl_player_match.defensive_contribution IS 'FPL defensive contribution count: clearances, blocks, interceptions, and tackles, plus recoveries for midfielders and forwards. A count, not points.';
COMMENT ON COLUMN v_fpl_player_match.points IS 'FPL points scored in the match. Can be negative.';
COMMENT ON COLUMN v_fpl_player_match.price IS 'FPL price of the player at that gameweek, in millions of pounds.';

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON fpl_player_match TO ingest;
GRANT SELECT ON fpl_player_match, v_fpl_player_match TO analyst_ro;
