-- The on-ball details of 2003-04 that the advanced metrics need. StatsBomb is the one
-- source with them, so each column is null or false on every row of 2025-26.
ALTER TABLE events
    ADD COLUMN pass_length real CHECK (pass_length >= 0),
    ADD COLUMN pass_type text,
    ADD COLUMN shot_assist boolean NOT NULL DEFAULT false,
    ADD COLUMN goal_assist boolean NOT NULL DEFAULT false,
    ADD COLUMN aerial_won boolean NOT NULL DEFAULT false,
    ADD COLUMN duel_type text;

-- StatsBomb puts an aerial win on the event that won it, and that can be a shot.
ALTER TABLE shots ADD COLUMN aerial_won boolean NOT NULL DEFAULT false;

CREATE VIEW v_player_match_advanced AS
WITH event_counts AS (
    SELECT
        match_id,
        player_id,
        count(*) FILTER (WHERE type = 'pass' AND (shot_assist OR goal_assist)) AS chances_created,
        count(*) FILTER (
            WHERE type = 'duel' AND duel_type = 'tackle'
            AND outcome IN ('won', 'success in play', 'success out')
        ) AS tackles_won,
        count(*) FILTER (
            WHERE type = 'duel' AND duel_type = 'tackle' AND outcome IN ('lost in play', 'lost out')
        ) AS tackles_lost,
        count(*) FILTER (WHERE aerial_won) AS aerials_won,
        count(*) FILTER (WHERE type = 'duel' AND duel_type = 'aerial lost') AS aerials_lost,
        -- Throw-ins are not passes for pass accuracy, as most providers count it.
        count(*) FILTER (WHERE type = 'pass' AND pass_type IS DISTINCT FROM 'throw-in') AS passes,
        count(*) FILTER (
            WHERE type = 'pass' AND pass_type IS DISTINCT FROM 'throw-in' AND outcome IS NULL
        ) AS passes_completed,
        count(*) FILTER (
            WHERE type = 'pass' AND pass_type IS DISTINCT FROM 'throw-in' AND pass_length >= 35
        ) AS long_balls,
        count(*) FILTER (
            WHERE type = 'pass' AND pass_type IS DISTINCT FROM 'throw-in' AND pass_length >= 35
            AND outcome IS NULL
        ) AS long_balls_completed
    FROM events
    WHERE player_id IS NOT NULL
    GROUP BY match_id, player_id
),
shot_counts AS (
    SELECT match_id, player_id, count(*) FILTER (WHERE aerial_won) AS aerials_won
    FROM shots
    GROUP BY match_id, player_id
),
counts AS (
    SELECT
        pms.match_id,
        pms.player_id,
        pms.team_id,
        coalesce(e.chances_created, 0) AS chances_created,
        coalesce(e.tackles_won, 0) AS tackles_won,
        coalesce(e.tackles_lost, 0) AS tackles_lost,
        coalesce(e.aerials_won, 0) + coalesce(sc.aerials_won, 0) AS aerials_won,
        coalesce(e.aerials_lost, 0) AS aerials_lost,
        coalesce(e.passes, 0) AS passes,
        coalesce(e.passes_completed, 0) AS passes_completed,
        coalesce(e.long_balls, 0) AS long_balls,
        coalesce(e.long_balls_completed, 0) AS long_balls_completed
    FROM player_match_stats pms
    JOIN matches m ON m.id = pms.match_id
    JOIN seasons s ON s.id = m.season_id
    LEFT JOIN event_counts e ON e.match_id = pms.match_id AND e.player_id = pms.player_id
    LEFT JOIN shot_counts sc ON sc.match_id = pms.match_id AND sc.player_id = pms.player_id
    -- Only a season with event data has these metrics: zeros would be wrong for 2025-26.
    WHERE s.data_level = 'EVENT'
)
SELECT
    c.match_id,
    s.label AS season,
    m.match_date,
    p.name AS player,
    t.name AS team,
    CASE WHEN c.team_id = m.home_team_id THEN at.name ELSE ht.name END AS opponent,
    c.chances_created,
    c.tackles_won + c.tackles_lost + c.aerials_won + c.aerials_lost AS duels,
    c.tackles_won + c.aerials_won AS duels_won,
    c.aerials_won + c.aerials_lost AS aerial_duels,
    c.aerials_won AS aerial_duels_won,
    round(100.0 * c.aerials_won / NULLIF(c.aerials_won + c.aerials_lost, 0), 1)
        AS aerial_duels_won_pct,
    c.passes,
    c.passes_completed,
    round(100.0 * c.passes_completed / NULLIF(c.passes, 0), 1) AS pass_completion_pct,
    c.long_balls,
    c.long_balls_completed,
    round(100.0 * c.long_balls_completed / NULLIF(c.long_balls, 0), 1) AS long_ball_completion_pct
FROM counts c
JOIN matches m ON m.id = c.match_id
JOIN seasons s ON s.id = m.season_id
JOIN players p ON p.id = c.player_id
JOIN teams t ON t.id = c.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id;

COMMENT ON VIEW v_player_match_advanced IS 'One row per player per match played, 2003-04 only: chances created, duels, aerial duels, pass accuracy, and long balls from StatsBomb events. No row exists for 2025-26. For a season %, use round(100.0 * sum(won) / NULLIF(sum(total), 0), 1), never the mean of the match % values.';
COMMENT ON COLUMN v_player_match_advanced.match_id IS 'Match identifier. Join key to v_matches and v_player_match.';
COMMENT ON COLUMN v_player_match_advanced.season IS 'Season label. Always 2003-04.';
COMMENT ON COLUMN v_player_match_advanced.match_date IS 'Date the match was played.';
COMMENT ON COLUMN v_player_match_advanced.player IS 'Canonical player name.';
COMMENT ON COLUMN v_player_match_advanced.team IS 'Team the player played for in this match.';
COMMENT ON COLUMN v_player_match_advanced.opponent IS 'The other team in the match.';
COMMENT ON COLUMN v_player_match_advanced.chances_created IS 'Passes that led to a shot or a goal (StatsBomb shot assists and goal assists).';
COMMENT ON COLUMN v_player_match_advanced.duels IS 'Tackle duels plus aerial duels.';
COMMENT ON COLUMN v_player_match_advanced.duels_won IS 'Tackle duels won (outcome won, success in play, or success out) plus aerial duels won.';
COMMENT ON COLUMN v_player_match_advanced.aerial_duels IS 'Aerial duels: the ones won plus the ones lost.';
COMMENT ON COLUMN v_player_match_advanced.aerial_duels_won IS 'Aerial duels won: StatsBomb marks the pass, clearance, miscontrol, or shot that won it.';
COMMENT ON COLUMN v_player_match_advanced.aerial_duels_won_pct IS 'Aerial duels won as a % of aerial duels, 1 decimal. Null with no aerial duel.';
COMMENT ON COLUMN v_player_match_advanced.passes IS 'Passes attempted, throw-ins excluded.';
COMMENT ON COLUMN v_player_match_advanced.passes_completed IS 'Passes completed, throw-ins excluded.';
COMMENT ON COLUMN v_player_match_advanced.pass_completion_pct IS 'Passes completed as a % of passes, 1 decimal. Null with no pass.';
COMMENT ON COLUMN v_player_match_advanced.long_balls IS 'Passes of 35 yards or more (about 32 m), throw-ins excluded.';
COMMENT ON COLUMN v_player_match_advanced.long_balls_completed IS 'Long balls completed.';
COMMENT ON COLUMN v_player_match_advanced.long_ball_completion_pct IS 'Long balls completed as a % of long balls, 1 decimal. Null with no long ball.';

GRANT SELECT ON v_player_match_advanced TO analyst_ro;
