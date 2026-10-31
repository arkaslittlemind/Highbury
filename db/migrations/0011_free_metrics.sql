-- The free 2025-26 metrics: chances created from Understat's key passes, and the
-- tackles, recoveries, and CBI counts of the FPL file. StatsBomb rows of 2003-04 keep
-- chances_created null: their value is in v_player_match_advanced.
ALTER TABLE player_match_stats
    ADD COLUMN chances_created smallint CHECK (chances_created >= 0);

-- Nullable so that rows loaded before this migration read as not loaded, not as zero.
-- The FPL loader always writes them.
ALTER TABLE fpl_player_match
    ADD COLUMN tackles smallint CHECK (tackles >= 0),
    ADD COLUMN recoveries smallint CHECK (recoveries >= 0),
    ADD COLUMN clearances_blocks_interceptions smallint
        CHECK (clearances_blocks_interceptions >= 0);

-- CREATE OR REPLACE VIEW can only add columns at the end, and it keeps the grants.
CREATE OR REPLACE VIEW v_player_match AS
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
    pms.xa,
    pms.chances_created
FROM player_match_stats pms
JOIN matches m ON m.id = pms.match_id
JOIN seasons s ON s.id = m.season_id
JOIN players p ON p.id = pms.player_id
JOIN teams t ON t.id = pms.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id;

CREATE OR REPLACE VIEW v_player_season AS
SELECT
    p.name AS player,
    s.label AS season,
    count(*) AS matches,
    sum(pms.minutes) AS minutes,
    sum(pms.goals) AS goals,
    sum(pms.assists) AS assists,
    sum(pms.xg) AS xg,
    sum(pms.xa) AS xa,
    coalesce(max(sc.shots), 0) AS shots,
    sum(pms.chances_created) AS chances_created
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

CREATE OR REPLACE VIEW v_fpl_player_match AS
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
    f.price,
    f.tackles,
    f.recoveries,
    f.clearances_blocks_interceptions
FROM fpl_player_match f
JOIN matches m ON m.id = f.match_id
JOIN seasons s ON s.id = m.season_id
JOIN players p ON p.id = f.player_id
JOIN teams t ON t.id = f.team_id
JOIN teams ht ON ht.id = m.home_team_id
JOIN teams at ON at.id = m.away_team_id;

COMMENT ON COLUMN v_player_match.chances_created IS 'Chances created in the match: Understat key passes, passes that led to a shot. 2025-26 only; null for 2003-04, where v_player_match_advanced.chances_created has the StatsBomb value. A comparison of the two seasons names the two providers.';
COMMENT ON COLUMN v_player_season.chances_created IS 'Total chances created: Understat key passes, passes that led to a shot. 2025-26 only; null for 2003-04, where the sum of v_player_match_advanced.chances_created has the StatsBomb value. A comparison of the two seasons names the two providers.';
COMMENT ON COLUMN v_fpl_player_match.tackles IS 'Tackles made in the match, as FPL counts them.';
COMMENT ON COLUMN v_fpl_player_match.recoveries IS 'Ball recoveries in the match, as FPL counts them.';
COMMENT ON COLUMN v_fpl_player_match.clearances_blocks_interceptions IS 'Clearances, blocks, and interceptions in the match, as one FPL count (CBI). defensive_contribution already includes it and the tackles (and the recoveries for midfielders and forwards), so never add these columns to defensive_contribution.';
