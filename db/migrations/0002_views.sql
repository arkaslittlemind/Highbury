-- Flat views for the analyst agent. Column comments are read by the LLM through
-- get_schema, so each one says what the column means and how to use it.

CREATE VIEW v_matches AS
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
JOIN teams at ON at.id = m.away_team_id;

COMMENT ON VIEW v_matches IS 'One row per league match.';
COMMENT ON COLUMN v_matches.match_id IS 'Match identifier. Join key to the other views.';
COMMENT ON COLUMN v_matches.season IS 'Season label, for example 2003-04 or 2025-26.';
COMMENT ON COLUMN v_matches.match_date IS 'Date the match was played.';
COMMENT ON COLUMN v_matches.home_team IS 'Name of the home team.';
COMMENT ON COLUMN v_matches.away_team IS 'Name of the away team.';
COMMENT ON COLUMN v_matches.home_goals IS 'Goals scored by the home team.';
COMMENT ON COLUMN v_matches.away_goals IS 'Goals scored by the away team.';
COMMENT ON COLUMN v_matches.venue IS 'Stadium name. Can be null.';

CREATE VIEW v_shots AS
SELECT
    sh.match_id,
    s.label AS season,
    m.match_date,
    p.name AS player,
    t.name AS team,
    CASE WHEN sh.team_id = m.home_team_id THEN at.name ELSE ht.name END AS opponent,
    sh.minute,
    sh.x,
    sh.y,
    sh.xg,
    sh.outcome,
    sh.outcome = 'goal' AS is_goal,
    sh.body_part,
    sh.situation,
    sh.source
FROM shots sh
JOIN matches m ON m.id = sh.match_id
JOIN seasons s ON s.id = m.season_id
JOIN players p ON p.id = sh.player_id
JOIN teams t ON t.id = sh.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id;

COMMENT ON VIEW v_shots IS 'One row per shot, both seasons.';
COMMENT ON COLUMN v_shots.match_id IS 'Match identifier. Join key to v_matches.';
COMMENT ON COLUMN v_shots.season IS 'Season label, for example 2003-04 or 2025-26.';
COMMENT ON COLUMN v_shots.match_date IS 'Date the match was played.';
COMMENT ON COLUMN v_shots.player IS 'Canonical name of the player who took the shot.';
COMMENT ON COLUMN v_shots.team IS 'Team the shooter played for in this match.';
COMMENT ON COLUMN v_shots.opponent IS 'The other team in the match.';
COMMENT ON COLUMN v_shots.minute IS 'Match minute of the shot.';
COMMENT ON COLUMN v_shots.x IS 'Pitch length position, 0 to 120. The shooting team attacks towards 120.';
COMMENT ON COLUMN v_shots.y IS 'Pitch width position, 0 to 80. The goal centre is at 40.';
COMMENT ON COLUMN v_shots.xg IS 'Expected goals for the shot, 0 to 1. The model differs by source: StatsBomb for 2003-04, Understat for 2025-26. State this caveat when comparing seasons.';
COMMENT ON COLUMN v_shots.outcome IS 'Shot result in lowercase. The value goal means a goal.';
COMMENT ON COLUMN v_shots.is_goal IS 'True when the shot was a goal. Count goals with this column.';
COMMENT ON COLUMN v_shots.body_part IS 'Body part used. Can be null.';
COMMENT ON COLUMN v_shots.situation IS 'Play situation, for example open play or penalty. Can be null.';
COMMENT ON COLUMN v_shots.source IS 'Data source of the shot: statsbomb or understat.';

CREATE VIEW v_player_match AS
SELECT
    pms.match_id,
    s.label AS season,
    m.match_date,
    p.name AS player,
    t.name AS team,
    CASE WHEN pms.team_id = m.home_team_id THEN at.name ELSE ht.name END AS opponent,
    pms.minutes,
    pms.goals,
    pms.assists,
    pms.xg,
    pms.xa
FROM player_match_stats pms
JOIN matches m ON m.id = pms.match_id
JOIN seasons s ON s.id = m.season_id
JOIN players p ON p.id = pms.player_id
JOIN teams t ON t.id = pms.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id;

COMMENT ON VIEW v_player_match IS 'One row per player per match played.';
COMMENT ON COLUMN v_player_match.match_id IS 'Match identifier. Join key to v_matches.';
COMMENT ON COLUMN v_player_match.season IS 'Season label, for example 2003-04 or 2025-26.';
COMMENT ON COLUMN v_player_match.match_date IS 'Date the match was played.';
COMMENT ON COLUMN v_player_match.player IS 'Canonical player name.';
COMMENT ON COLUMN v_player_match.team IS 'Team the player played for in this match.';
COMMENT ON COLUMN v_player_match.opponent IS 'The other team in the match.';
COMMENT ON COLUMN v_player_match.minutes IS 'Minutes played in the match.';
COMMENT ON COLUMN v_player_match.goals IS 'Goals scored in the match.';
COMMENT ON COLUMN v_player_match.assists IS 'Assists in the match.';
COMMENT ON COLUMN v_player_match.xg IS 'Expected goals in the match. Null when the source has none. The model differs by season.';
COMMENT ON COLUMN v_player_match.xa IS 'Expected assists in the match. Null when the source has none.';

CREATE VIEW v_player_season AS
SELECT
    p.name AS player,
    s.label AS season,
    count(*) AS matches,
    sum(pms.minutes) AS minutes,
    sum(pms.goals) AS goals,
    sum(pms.assists) AS assists,
    sum(pms.xg) AS xg,
    sum(pms.xa) AS xa,
    coalesce(max(sc.shots), 0) AS shots
FROM player_match_stats pms
JOIN matches m ON m.id = pms.match_id
JOIN seasons s ON s.id = m.season_id
JOIN players p ON p.id = pms.player_id
LEFT JOIN (
    SELECT sh.player_id, sm.season_id, count(*) AS shots
    FROM shots sh
    JOIN matches sm ON sm.id = sh.match_id
    GROUP BY sh.player_id, sm.season_id
) sc ON sc.player_id = pms.player_id AND sc.season_id = m.season_id
GROUP BY p.id, p.name, s.label;

COMMENT ON VIEW v_player_season IS 'One row per player per season. Totals only.';
COMMENT ON COLUMN v_player_season.player IS 'Canonical player name.';
COMMENT ON COLUMN v_player_season.season IS 'Season label, for example 2003-04 or 2025-26.';
COMMENT ON COLUMN v_player_season.matches IS 'Number of league matches played.';
COMMENT ON COLUMN v_player_season.minutes IS 'Total minutes played. Use it to compute per-90 values in SQL: value * 90.0 / minutes.';
COMMENT ON COLUMN v_player_season.goals IS 'Total league goals.';
COMMENT ON COLUMN v_player_season.assists IS 'Total league assists.';
COMMENT ON COLUMN v_player_season.xg IS 'Total expected goals. The model differs by season: StatsBomb for 2003-04, Understat for 2025-26.';
COMMENT ON COLUMN v_player_season.xa IS 'Total expected assists. Null when the source has none.';
COMMENT ON COLUMN v_player_season.shots IS 'Total shots taken.';

CREATE VIEW v_passes AS
SELECT
    e.match_id,
    s.label AS season,
    m.match_date,
    p.name AS player,
    r.name AS recipient,
    t.name AS team,
    CASE WHEN e.team_id = m.home_team_id THEN at.name ELSE ht.name END AS opponent,
    e.minute,
    e.second,
    e.x,
    e.y,
    e.end_x,
    e.end_y,
    e.outcome,
    e.under_pressure,
    e.possession
FROM events e
JOIN matches m ON m.id = e.match_id
JOIN seasons s ON s.id = m.season_id
JOIN teams t ON t.id = e.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id
LEFT JOIN players p ON p.id = e.player_id
LEFT JOIN players r ON r.id = e.recipient_id
WHERE e.type = 'pass';

COMMENT ON VIEW v_passes IS 'One row per pass. 2003-04 only: no pass data exists for 2025-26.';
COMMENT ON COLUMN v_passes.match_id IS 'Match identifier. Join key to v_matches.';
COMMENT ON COLUMN v_passes.season IS 'Season label. Only 2003-04 has passes.';
COMMENT ON COLUMN v_passes.match_date IS 'Date the match was played.';
COMMENT ON COLUMN v_passes.player IS 'Canonical name of the passer.';
COMMENT ON COLUMN v_passes.recipient IS 'Canonical name of the receiver. Null when the pass was not received.';
COMMENT ON COLUMN v_passes.team IS 'Team of the passer.';
COMMENT ON COLUMN v_passes.opponent IS 'The other team in the match.';
COMMENT ON COLUMN v_passes.minute IS 'Match minute of the pass.';
COMMENT ON COLUMN v_passes.second IS 'Second within the minute.';
COMMENT ON COLUMN v_passes.x IS 'Start position along the pitch length, 0 to 120. The passing team attacks towards 120.';
COMMENT ON COLUMN v_passes.y IS 'Start position along the pitch width, 0 to 80.';
COMMENT ON COLUMN v_passes.end_x IS 'End position along the pitch length, 0 to 120.';
COMMENT ON COLUMN v_passes.end_y IS 'End position along the pitch width, 0 to 80.';
COMMENT ON COLUMN v_passes.outcome IS 'Null for a completed pass. Otherwise the reason it failed, in lowercase.';
COMMENT ON COLUMN v_passes.under_pressure IS 'True when the passer was under pressure.';
COMMENT ON COLUMN v_passes.possession IS 'Possession sequence number within the match.';
