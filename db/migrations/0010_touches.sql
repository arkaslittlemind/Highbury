-- One row per touch, for the heatmap. A touch is an event where the player plays or
-- wins the ball. Pressures have no ball, a carry moves a ball already touched, and
-- StatsBomb marks a ball receipt before the pass or carry that the player makes, so
-- the common touch counts leave these out.
CREATE VIEW v_touches AS
WITH touches AS (
    SELECT match_id, player_id, team_id, minute, second, type, x, y
    FROM events
    WHERE type IN (
        'pass', 'dribble', 'duel', 'clearance', 'interception', 'ball_recovery', 'block',
        'miscontrol'
    )
    UNION ALL
    SELECT match_id, player_id, team_id, minute, NULL, 'shot', x, y
    FROM shots
)
SELECT
    tc.match_id,
    s.label AS season,
    m.match_date,
    p.name AS player,
    t.name AS team,
    CASE WHEN tc.team_id = m.home_team_id THEN at.name ELSE ht.name END AS opponent,
    tc.minute,
    tc.second,
    tc.type,
    tc.x,
    tc.y
FROM touches tc
JOIN matches m ON m.id = tc.match_id
JOIN seasons s ON s.id = m.season_id
JOIN players p ON p.id = tc.player_id
JOIN teams t ON t.id = tc.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id
-- 2025-26 has shots but no events: its shots alone would be a wrong touch count.
WHERE s.data_level = 'EVENT' AND tc.x IS NOT NULL AND tc.y IS NOT NULL;

COMMENT ON VIEW v_touches IS 'One row per touch of the ball, 2003-04 only: passes, shots, dribbles, duels, clearances, interceptions, ball recoveries, blocks, and miscontrols. Pressures, carries, and ball receipts are not touches. No row exists for 2025-26.';
COMMENT ON COLUMN v_touches.match_id IS 'Match identifier. Join key to v_matches.';
COMMENT ON COLUMN v_touches.season IS 'Season label. Always 2003-04.';
COMMENT ON COLUMN v_touches.match_date IS 'Date the match was played.';
COMMENT ON COLUMN v_touches.player IS 'Canonical name of the player who touched the ball.';
COMMENT ON COLUMN v_touches.team IS 'Team of the player.';
COMMENT ON COLUMN v_touches.opponent IS 'The other team in the match.';
COMMENT ON COLUMN v_touches.minute IS 'Match minute of the touch.';
COMMENT ON COLUMN v_touches.second IS 'Second within the minute. Null for a shot.';
COMMENT ON COLUMN v_touches.type IS 'The kind of touch: pass, shot, dribble, duel, clearance, interception, ball_recovery, block, or miscontrol.';
COMMENT ON COLUMN v_touches.x IS 'Position along the pitch length, 0 to 120. The team of the player attacks towards 120.';
COMMENT ON COLUMN v_touches.y IS 'Position along the pitch width, 0 to 80.';

GRANT SELECT ON v_touches TO analyst_ro;
