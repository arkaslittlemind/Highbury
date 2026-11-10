-- Player similarity within one season: per-90 profiles, z-scores within the qualified
-- players of the season, and the Euclidean distance between two profiles. The scores are
-- SQL so that the verifier can check each one against a row, and the model never
-- computes one.
CREATE VIEW v_player_similarity AS
WITH match_counts AS (
    -- 2003-04: Arsenal players only, the event metrics of v_player_match_advanced plus
    -- goals, shots, and xG. One row for each player, match, and metric.
    SELECT
        s.label AS season,
        pms.player_id,
        pms.team_id,
        m.match_date,
        pms.minutes,
        v.metric,
        v.value
    FROM player_match_stats pms
    JOIN matches m ON m.id = pms.match_id
    JOIN seasons s ON s.id = m.season_id
    JOIN teams t ON t.id = pms.team_id
    JOIN players p ON p.id = pms.player_id
    -- The view has the player name and not the id. A name is unique within one match.
    JOIN v_player_match_advanced a ON a.match_id = pms.match_id AND a.player = p.name
    LEFT JOIN (
        SELECT match_id, player_id, count(*) AS shots
        FROM shots
        GROUP BY match_id, player_id
    ) sh ON sh.match_id = pms.match_id AND sh.player_id = pms.player_id
    CROSS JOIN LATERAL (
        VALUES
            ('chances_created', a.chances_created::numeric),
            ('duels_won', a.duels_won::numeric),
            ('aerial_duels_won', a.aerial_duels_won::numeric),
            ('passes_completed', a.passes_completed::numeric),
            ('long_balls_completed', a.long_balls_completed::numeric),
            ('goals', pms.goals::numeric),
            ('shots', coalesce(sh.shots, 0)::numeric),
            ('xg', coalesce(pms.xg, 0)::numeric)
    ) v (metric, value)
    WHERE t.name = 'Arsenal'
    UNION ALL
    -- 2025-26: every league player, from FPL. Understat covers only Arsenal's matches, so
    -- it has no league-wide profile. Points, bonus, BPS, and price are scores made from
    -- the counts, clean sheets are a team result, and defensive_contribution already holds
    -- the tackles and the CBI.
    SELECT
        s.label,
        f.player_id,
        f.team_id,
        m.match_date,
        f.minutes,
        v.metric,
        v.value
    FROM fpl_player_match f
    JOIN matches m ON m.id = f.match_id
    JOIN seasons s ON s.id = m.season_id
    CROSS JOIN LATERAL (
        VALUES
            ('goals', f.goals::numeric),
            ('assists', f.assists::numeric),
            ('tackles', f.tackles::numeric),
            ('recoveries', f.recoveries::numeric),
            ('clearances_blocks_interceptions', f.clearances_blocks_interceptions::numeric),
            ('saves', f.saves::numeric)
    ) v (metric, value)
),
totals AS (
    -- Each match row appears once for each metric, so sum(minutes) within one metric is
    -- the season minutes of the player.
    SELECT
        season,
        player_id,
        metric,
        coalesce(sum(value), 0) AS value,
        sum(minutes) AS minutes,
        -- After a transfer, the club of the most recent match.
        (array_agg(team_id ORDER BY match_date DESC))[1] AS team_id
    FROM match_counts
    GROUP BY season, player_id, metric
),
z_scores AS (
    SELECT
        season,
        player_id,
        name,
        team_id,
        minutes,
        metric,
        -- A metric with no spread says nothing about likeness, so its z-score is 0.
        coalesce(
            (per_90 - avg(per_90) OVER w) / nullif(stddev_pop(per_90) OVER w, 0), 0
        ) AS z
    FROM (
        SELECT tt.*, p.name, tt.value * 90.0 / tt.minutes AS per_90
        FROM totals tt
        JOIN players p ON p.id = tt.player_id
        WHERE tt.minutes >= 900
    ) qualified
    WINDOW w AS (PARTITION BY season, metric)
),
pairs AS (
    -- The name is a group key, so a filter on the player reaches the join below and the
    -- database pairs only that player with the others.
    SELECT
        a.season,
        a.name AS player,
        a.player_id,
        a.team_id,
        a.minutes,
        b.name AS similar_player,
        b.team_id AS similar_team_id,
        b.minutes AS similar_minutes,
        sqrt(sum((a.z - b.z) ^ 2)) AS distance,
        count(*)::int AS metrics
    FROM z_scores a
    JOIN z_scores b
        ON b.season = a.season AND b.metric = a.metric AND b.player_id <> a.player_id
    GROUP BY
        a.season, a.name, a.player_id, a.team_id, a.minutes,
        b.player_id, b.name, b.team_id, b.minutes
),
named AS (
    SELECT
        pr.season,
        pr.player,
        pr.player_id,
        t.name AS team,
        pr.minutes,
        pr.similar_player,
        st.name AS similar_team,
        pr.similar_minutes,
        pr.distance,
        pr.metrics
    FROM pairs pr
    JOIN teams t ON t.id = pr.team_id
    JOIN teams st ON st.id = pr.similar_team_id
)
SELECT
    season,
    player,
    team,
    minutes,
    similar_player,
    similar_team,
    similar_minutes,
    -- The partition names the player, so a filter on season and player reaches below the
    -- window and the database ranks only the pairs of that player.
    row_number() OVER (
        PARTITION BY season, player, player_id ORDER BY distance, similar_player
    ) AS rank,
    round(distance::numeric, 2) AS distance,
    metrics
FROM named;

COMMENT ON VIEW v_player_similarity IS 'Player similarity within one season: one row for each pair of two different players who played 900 league minutes or more in that season. Lower distance means more alike; rank 1 is the most alike. 2003-04 compares Arsenal players only (StatsBomb, 8 metrics); 2025-26 compares every league player (FPL, 6 metrics). Never compare players of the two seasons: the metrics differ. Cite distance as it is; never compute, scale, or convert it. Example: SELECT similar_player, similar_team, distance FROM v_player_similarity WHERE season = ''2003-04'' AND player = ''Patrick Vieira'' ORDER BY rank LIMIT 5.';
COMMENT ON COLUMN v_player_similarity.season IS 'Season label, 2003-04 or 2025-26. Both players of a row are from this season.';
COMMENT ON COLUMN v_player_similarity.player IS 'The player whose likeness the row measures.';
COMMENT ON COLUMN v_player_similarity.team IS 'Team of the player. In 2025-26, after a transfer, the team of his most recent league match.';
COMMENT ON COLUMN v_player_similarity.minutes IS 'League minutes of the player in the season, 900 or more.';
COMMENT ON COLUMN v_player_similarity.similar_player IS 'The other player of the pair.';
COMMENT ON COLUMN v_player_similarity.similar_team IS 'Team of the other player, by the same rule as team.';
COMMENT ON COLUMN v_player_similarity.similar_minutes IS 'League minutes of the other player in the season, 900 or more.';
COMMENT ON COLUMN v_player_similarity.rank IS 'Rank of the other player by distance for this player and season: 1 is the most alike. Ties go in name order.';
COMMENT ON COLUMN v_player_similarity.distance IS 'Euclidean distance between the per-90 profiles of the two players, each metric as a z-score within the qualified players of the season. 0 means the same profile; lower is more alike. Not a percentage.';
COMMENT ON COLUMN v_player_similarity.metrics IS 'Number of per-90 metrics in the distance. 2003-04: 8 (chances created, duels won, aerial duels won, passes completed, accurate long balls, goals, shots, xG). 2025-26: 6 (goals, assists, tackles, recoveries, clearances-blocks-interceptions, saves).';

GRANT SELECT ON v_player_similarity TO analyst_ro;
