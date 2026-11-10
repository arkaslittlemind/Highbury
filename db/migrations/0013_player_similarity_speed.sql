-- A faster v_player_similarity (finding F-05 of item 34). The 0012 view joined one row
-- for each player and metric to make the pairs: about 690,000 rows for 2025-26, so a query
-- with no player filter took about 3.5 s of the 5 s statement timeout. This version joins
-- one row for each player and computes the distance from two arrays. The columns, the
-- rows, and the values stay the same, and CREATE OR REPLACE VIEW keeps the grant and the
-- comments of 0012.
CREATE OR REPLACE VIEW v_player_similarity AS
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
profiles AS (
    -- One row for each player: his z-scores in metric order. The pair join below then
    -- joins players, not metrics, which makes a query with no player filter about four
    -- times faster. float8 keeps the arithmetic of each pair cheap.
    SELECT
        season,
        name,
        player_id,
        team_id,
        minutes,
        array_agg(z::float8 ORDER BY metric) AS z_vector
    FROM z_scores
    GROUP BY season, name, player_id, team_id, minutes
),
pairs AS (
    -- The name is a group key of profiles, so a filter on the player still reaches this
    -- join and the database pairs only that player with the others.
    SELECT
        a.season,
        a.name AS player,
        a.player_id,
        a.team_id,
        a.minutes,
        b.name AS similar_player,
        b.team_id AS similar_team_id,
        b.minutes AS similar_minutes,
        (
            SELECT sqrt(sum((x - y) ^ 2))
            FROM unnest(a.z_vector, b.z_vector) AS u (x, y)
        ) AS distance,
        cardinality(a.z_vector) AS metrics
    FROM profiles a
    JOIN profiles b ON b.season = a.season AND b.player_id <> a.player_id
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
