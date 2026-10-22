-- StatsBomb starts the clock of each half at its own minute: the second half starts
-- at 45:00, while first-half stoppage time runs to 47:xx. Only the period orders two
-- events across half time, so a pass can be compared with a substitution.
-- Null until the season is loaded again; the loader sets it on every event.
ALTER TABLE events ADD COLUMN period smallint CHECK (period BETWEEN 1 AND 5);

-- A replaced view can only gain columns at its end.
CREATE OR REPLACE VIEW v_passes AS
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
    e.possession,
    e.period
FROM events e
JOIN matches m ON m.id = e.match_id
JOIN seasons s ON s.id = m.season_id
JOIN teams t ON t.id = e.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id
LEFT JOIN players p ON p.id = e.player_id
LEFT JOIN players r ON r.id = e.recipient_id
WHERE e.type = 'pass';

CREATE OR REPLACE VIEW v_substitutions AS
SELECT
    e.match_id,
    s.label AS season,
    m.match_date,
    t.name AS team,
    CASE WHEN e.team_id = m.home_team_id THEN at.name ELSE ht.name END AS opponent,
    e.minute,
    e.second,
    p.name AS player_off,
    r.name AS player_on,
    e.outcome AS reason,
    e.period
FROM events e
JOIN matches m ON m.id = e.match_id
JOIN seasons s ON s.id = m.season_id
JOIN teams t ON t.id = e.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id
LEFT JOIN players p ON p.id = e.player_id
LEFT JOIN players r ON r.id = e.recipient_id
WHERE e.type = 'substitution';

COMMENT ON COLUMN v_passes.minute IS 'Match minute of the pass. Each half starts its own clock, so order passes by (period, minute, second).';
COMMENT ON COLUMN v_passes.period IS 'Half of the match: 1 or 2. Compare (period, minute, second) to order events across half time.';
COMMENT ON COLUMN v_substitutions.minute IS 'Match minute of the substitution. The second half starts at 45, so compare (period, minute, second) with v_passes.';
COMMENT ON COLUMN v_substitutions.period IS 'Half of the match: 1 or 2. A change at half time is at minute 45 of period 2.';
