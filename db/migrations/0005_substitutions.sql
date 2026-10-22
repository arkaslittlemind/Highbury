-- Substitutions let a pass network stop at the first change to the starting XI.
CREATE VIEW v_substitutions AS
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
    e.outcome AS reason
FROM events e
JOIN matches m ON m.id = e.match_id
JOIN seasons s ON s.id = m.season_id
JOIN teams t ON t.id = e.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id
LEFT JOIN players p ON p.id = e.player_id
LEFT JOIN players r ON r.id = e.recipient_id
WHERE e.type = 'substitution';

COMMENT ON VIEW v_substitutions IS 'One row per substitution. 2003-04 only: no substitution data is loaded for 2025-26.';
COMMENT ON COLUMN v_substitutions.match_id IS 'Match identifier. Join key to v_matches and v_passes.';
COMMENT ON COLUMN v_substitutions.season IS 'Season label. Only 2003-04 has substitutions.';
COMMENT ON COLUMN v_substitutions.match_date IS 'Date the match was played.';
COMMENT ON COLUMN v_substitutions.team IS 'Team that made the substitution.';
COMMENT ON COLUMN v_substitutions.opponent IS 'The other team in the match.';
COMMENT ON COLUMN v_substitutions.minute IS 'Match minute of the substitution, on the same clock as v_passes.minute.';
COMMENT ON COLUMN v_substitutions.second IS 'Second within the minute.';
COMMENT ON COLUMN v_substitutions.player_off IS 'Canonical name of the player who went off.';
COMMENT ON COLUMN v_substitutions.player_on IS 'Canonical name of the player who came on.';
COMMENT ON COLUMN v_substitutions.reason IS 'Why the change was made, in lowercase, for example tactical or injury.';

GRANT SELECT ON v_substitutions TO analyst_ro;
