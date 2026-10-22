-- The whole league of both seasons from football-data.co.uk: every match, the
-- half-time score, the referee, and the match stats of each team. Arsenal's
-- matches keep their StatsBomb or Understat row; the football-data loader fills
-- the new columns on it instead of adding a second row.

-- Null until the football-data loader runs, so a season loader alone still works.
ALTER TABLE matches
    ADD COLUMN home_ht_goals smallint CHECK (home_ht_goals >= 0),
    ADD COLUMN away_ht_goals smallint CHECK (away_ht_goals >= 0),
    ADD COLUMN referee text;

CREATE TABLE team_match_stats (
    match_id integer NOT NULL REFERENCES matches (id),
    team_id integer NOT NULL REFERENCES teams (id),
    shots smallint NOT NULL CHECK (shots >= 0),
    shots_on_target smallint NOT NULL CHECK (shots_on_target >= 0),
    corners smallint NOT NULL CHECK (corners >= 0),
    fouls smallint NOT NULL CHECK (fouls >= 0),
    yellow_cards smallint NOT NULL CHECK (yellow_cards >= 0),
    red_cards smallint NOT NULL CHECK (red_cards >= 0),
    source text NOT NULL,
    PRIMARY KEY (match_id, team_id),
    CHECK (shots_on_target <= shots)
);

-- matches now holds every league match. The view keeps its old meaning, so the
-- queries that the agent already writes on it do not change.
CREATE OR REPLACE VIEW v_matches AS
SELECT
    m.id AS match_id,
    s.label AS season,
    m.match_date,
    ht.name AS home_team,
    at.name AS away_team,
    m.home_goals,
    m.away_goals,
    m.venue
FROM matches m
JOIN seasons s ON s.id = m.season_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id
WHERE 'Arsenal' IN (ht.name, at.name);

COMMENT ON VIEW v_matches IS 'One row per Arsenal league match. For other matches, use v_league_matches.';

CREATE VIEW v_league_matches AS
SELECT
    m.id AS match_id,
    s.label AS season,
    m.match_date,
    ht.name AS home_team,
    at.name AS away_team,
    m.home_goals,
    m.away_goals,
    m.home_ht_goals,
    m.away_ht_goals,
    m.referee,
    hs.shots AS home_shots,
    aw.shots AS away_shots,
    hs.shots_on_target AS home_shots_on_target,
    aw.shots_on_target AS away_shots_on_target,
    hs.corners AS home_corners,
    aw.corners AS away_corners,
    hs.fouls AS home_fouls,
    aw.fouls AS away_fouls,
    hs.yellow_cards AS home_yellow_cards,
    aw.yellow_cards AS away_yellow_cards,
    hs.red_cards AS home_red_cards,
    aw.red_cards AS away_red_cards
FROM matches m
JOIN seasons s ON s.id = m.season_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id
-- A match with no stats row still shows, with nulls in the stat columns.
LEFT JOIN team_match_stats hs ON hs.match_id = m.id AND hs.team_id = m.home_team_id
LEFT JOIN team_match_stats aw ON aw.match_id = m.id AND aw.team_id = m.away_team_id;

COMMENT ON VIEW v_league_matches IS 'One row per league match of every team, both seasons. Source: football-data.co.uk. Use v_matches for questions about Arsenal matches only.';
COMMENT ON COLUMN v_league_matches.match_id IS 'Match identifier. Join key to v_matches and the other views.';
COMMENT ON COLUMN v_league_matches.season IS 'Season label, for example 2003-04 or 2025-26.';
COMMENT ON COLUMN v_league_matches.match_date IS 'Date the match was played.';
COMMENT ON COLUMN v_league_matches.home_team IS 'Name of the home team.';
COMMENT ON COLUMN v_league_matches.away_team IS 'Name of the away team.';
COMMENT ON COLUMN v_league_matches.home_goals IS 'Full-time goals of the home team.';
COMMENT ON COLUMN v_league_matches.away_goals IS 'Full-time goals of the away team.';
COMMENT ON COLUMN v_league_matches.home_ht_goals IS 'Half-time goals of the home team.';
COMMENT ON COLUMN v_league_matches.away_ht_goals IS 'Half-time goals of the away team.';
COMMENT ON COLUMN v_league_matches.referee IS 'Name of the referee, as initial and surname, for example M Dean.';
COMMENT ON COLUMN v_league_matches.home_shots IS 'Shots of the home team, on and off target. Not the same count as the shots in v_shots, which come from another source.';
COMMENT ON COLUMN v_league_matches.away_shots IS 'Shots of the away team, on and off target. Not the same count as the shots in v_shots, which come from another source.';
COMMENT ON COLUMN v_league_matches.home_shots_on_target IS 'Shots on target of the home team.';
COMMENT ON COLUMN v_league_matches.away_shots_on_target IS 'Shots on target of the away team.';
COMMENT ON COLUMN v_league_matches.home_corners IS 'Corners won by the home team.';
COMMENT ON COLUMN v_league_matches.away_corners IS 'Corners won by the away team.';
COMMENT ON COLUMN v_league_matches.home_fouls IS 'Fouls committed by the home team.';
COMMENT ON COLUMN v_league_matches.away_fouls IS 'Fouls committed by the away team.';
COMMENT ON COLUMN v_league_matches.home_yellow_cards IS 'Yellow cards of the home team. A second yellow that becomes a red is not counted here.';
COMMENT ON COLUMN v_league_matches.away_yellow_cards IS 'Yellow cards of the away team. A second yellow that becomes a red is not counted here.';
COMMENT ON COLUMN v_league_matches.home_red_cards IS 'Red cards of the home team.';
COMMENT ON COLUMN v_league_matches.away_red_cards IS 'Red cards of the away team.';

CREATE VIEW v_league_table AS
WITH results AS (
    SELECT season_id, home_team_id AS team_id, home_goals AS scored, away_goals AS conceded
    FROM matches
    UNION ALL
    SELECT season_id, away_team_id, away_goals, home_goals
    FROM matches
),
totals AS (
    SELECT
        season_id,
        team_id,
        count(*) AS played,
        count(*) FILTER (WHERE scored > conceded) AS won,
        count(*) FILTER (WHERE scored = conceded) AS drawn,
        count(*) FILTER (WHERE scored < conceded) AS lost,
        sum(scored) AS goals_for,
        sum(conceded) AS goals_against
    FROM results
    GROUP BY season_id, team_id
)
SELECT
    s.label AS season,
    t.name AS team,
    -- The first three tie-breaks of the Premier League. Teams equal on all three
    -- share a position; the league's later tie-breaks are not modelled.
    rank() OVER (
        PARTITION BY tt.season_id
        ORDER BY 3 * tt.won + tt.drawn DESC, tt.goals_for - tt.goals_against DESC,
            tt.goals_for DESC
    ) AS position,
    tt.played,
    tt.won,
    tt.drawn,
    tt.lost,
    tt.goals_for,
    tt.goals_against,
    tt.goals_for - tt.goals_against AS goal_difference,
    3 * tt.won + tt.drawn AS points
FROM totals tt
JOIN seasons s ON s.id = tt.season_id
JOIN teams t ON t.id = tt.team_id;

COMMENT ON VIEW v_league_table IS 'One row per team per season: the final league table, from the scores of v_league_matches. Order by position.';
COMMENT ON COLUMN v_league_table.season IS 'Season label, for example 2003-04 or 2025-26.';
COMMENT ON COLUMN v_league_table.team IS 'Name of the team.';
COMMENT ON COLUMN v_league_table.position IS 'League position: 1 is the champion. Ranked by points, then goal difference, then goals for. Teams equal on all three share a position.';
COMMENT ON COLUMN v_league_table.played IS 'Matches played.';
COMMENT ON COLUMN v_league_table.won IS 'Matches won.';
COMMENT ON COLUMN v_league_table.drawn IS 'Matches drawn.';
COMMENT ON COLUMN v_league_table.lost IS 'Matches lost.';
COMMENT ON COLUMN v_league_table.goals_for IS 'Goals scored, own goals of the opponent included.';
COMMENT ON COLUMN v_league_table.goals_against IS 'Goals conceded.';
COMMENT ON COLUMN v_league_table.goal_difference IS 'Goals for minus goals against.';
COMMENT ON COLUMN v_league_table.points IS 'League points: 3 for a win, 1 for a draw.';

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON team_match_stats TO ingest;
GRANT SELECT ON team_match_stats, v_league_matches, v_league_table TO analyst_ro;
