-- Coordinates everywhere use the 120 x 80 pitch, attacking left to right.

CREATE TABLE seasons (
    id smallint PRIMARY KEY,
    label text NOT NULL UNIQUE,
    data_level text NOT NULL CHECK (data_level IN ('EVENT', 'SHOT', 'AGGREGATE'))
);

CREATE TABLE teams (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE
);

CREATE TABLE players (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    position text,
    known_as text
);

CREATE TABLE player_aliases (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id integer NOT NULL REFERENCES players (id),
    source text NOT NULL,
    source_player_id text,
    source_name text NOT NULL,
    UNIQUE (source, source_name)
);

CREATE TABLE matches (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    season_id smallint NOT NULL REFERENCES seasons (id),
    match_date date NOT NULL,
    home_team_id integer NOT NULL REFERENCES teams (id),
    away_team_id integer NOT NULL REFERENCES teams (id),
    home_goals smallint NOT NULL,
    away_goals smallint NOT NULL,
    venue text,
    source text NOT NULL,
    source_match_id text NOT NULL,
    UNIQUE (source, source_match_id)
);

CREATE TABLE shots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    match_id integer NOT NULL REFERENCES matches (id),
    player_id integer NOT NULL REFERENCES players (id),
    team_id integer NOT NULL REFERENCES teams (id),
    minute smallint NOT NULL,
    x real NOT NULL CHECK (x BETWEEN 0 AND 120),
    y real NOT NULL CHECK (y BETWEEN 0 AND 80),
    xg real NOT NULL CHECK (xg BETWEEN 0 AND 1),
    outcome text NOT NULL,
    body_part text,
    situation text,
    source text NOT NULL,
    source_shot_id text NOT NULL,
    UNIQUE (source, source_shot_id)
);

-- 2003-04 only: StatsBomb is the one source with event data.
CREATE TABLE events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    match_id integer NOT NULL REFERENCES matches (id),
    player_id integer REFERENCES players (id),
    team_id integer NOT NULL REFERENCES teams (id),
    type text NOT NULL,
    minute smallint NOT NULL,
    second smallint NOT NULL,
    x real CHECK (x BETWEEN 0 AND 120),
    y real CHECK (y BETWEEN 0 AND 80),
    end_x real CHECK (end_x BETWEEN 0 AND 120),
    end_y real CHECK (end_y BETWEEN 0 AND 80),
    outcome text,
    under_pressure boolean NOT NULL DEFAULT false,
    possession integer,
    recipient_id integer REFERENCES players (id),
    source_event_id text NOT NULL UNIQUE
);

CREATE TABLE player_match_stats (
    player_id integer NOT NULL REFERENCES players (id),
    match_id integer NOT NULL REFERENCES matches (id),
    team_id integer NOT NULL REFERENCES teams (id),
    minutes smallint NOT NULL,
    goals smallint NOT NULL DEFAULT 0,
    assists smallint NOT NULL DEFAULT 0,
    xg real,
    xa real,
    PRIMARY KEY (player_id, match_id)
);

CREATE TABLE data_catalog (
    season_id smallint NOT NULL REFERENCES seasons (id),
    metric text NOT NULL,
    available boolean NOT NULL,
    source text,
    notes text,
    PRIMARY KEY (season_id, metric)
);

CREATE INDEX shots_player_id_idx ON shots (player_id);
CREATE INDEX shots_match_id_idx ON shots (match_id);
CREATE INDEX events_match_id_idx ON events (match_id);
CREATE INDEX events_player_id_idx ON events (player_id);
CREATE INDEX matches_season_id_idx ON matches (season_id);
