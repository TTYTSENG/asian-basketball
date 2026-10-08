PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS leagues (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, official_url TEXT NOT NULL
);
-- Team keys are local keys derived from official names, not invented official IDs.
CREATE TABLE IF NOT EXISTS teams (
 league_id TEXT NOT NULL, team_key TEXT NOT NULL, name TEXT NOT NULL,
 PRIMARY KEY (league_id,team_key), FOREIGN KEY (league_id) REFERENCES leagues(id)
);
CREATE TABLE IF NOT EXISTS players (
 league_id TEXT NOT NULL, player_id TEXT NOT NULL, name TEXT NOT NULL,
 PRIMARY KEY (league_id,player_id), FOREIGN KEY (league_id) REFERENCES leagues(id)
);
CREATE TABLE IF NOT EXISTS games (
 league_id TEXT NOT NULL, game_id TEXT NOT NULL, game_date TEXT NOT NULL,
 game_time TEXT NOT NULL DEFAULT '', home_team_key TEXT NOT NULL, away_team_key TEXT NOT NULL,
 home_score INTEGER CHECK(home_score>=0), away_score INTEGER CHECK(away_score>=0),
 completed INTEGER NOT NULL CHECK(completed IN (0,1)), has_detail INTEGER NOT NULL DEFAULT 0,
 official_url TEXT NOT NULL, payload_json TEXT NOT NULL, imported_at TEXT NOT NULL,
 PRIMARY KEY (league_id,game_id),
 FOREIGN KEY (league_id,home_team_key) REFERENCES teams(league_id,team_key),
 FOREIGN KEY (league_id,away_team_key) REFERENCES teams(league_id,team_key)
);
CREATE INDEX IF NOT EXISTS games_by_date ON games(league_id,game_date DESC);
CREATE TABLE IF NOT EXISTS player_game_stats (
 league_id TEXT NOT NULL, game_id TEXT NOT NULL, player_id TEXT NOT NULL,
 side TEXT NOT NULL CHECK(side IN ('home','away')), points INTEGER NOT NULL CHECK(points>=0),
 fgm INTEGER NOT NULL CHECK(fgm>=0), fga INTEGER NOT NULL CHECK(fga>=fgm),
 turnovers INTEGER NOT NULL CHECK(turnovers>=0), seconds REAL NOT NULL CHECK(seconds>=0),
 PRIMARY KEY (league_id,game_id,player_id),
 FOREIGN KEY (league_id,game_id) REFERENCES games(league_id,game_id),
 FOREIGN KEY (league_id,player_id) REFERENCES players(league_id,player_id)
);
CREATE INDEX IF NOT EXISTS stats_by_player ON player_game_stats(league_id,player_id);
CREATE TABLE IF NOT EXISTS game_sources (
 league_id TEXT NOT NULL, game_id TEXT NOT NULL, role TEXT NOT NULL,
 url TEXT NOT NULL, PRIMARY KEY(league_id,game_id,role),
 FOREIGN KEY (league_id,game_id) REFERENCES games(league_id,game_id)
);
CREATE TABLE IF NOT EXISTS lineup_stats (
 lineup_id INTEGER PRIMARY KEY, league_id TEXT NOT NULL, game_id TEXT NOT NULL,
 side TEXT NOT NULL CHECK(side IN ('home','away')), label TEXT NOT NULL,
 seconds REAL NOT NULL CHECK(seconds>=0), net_points INTEGER NOT NULL,
 UNIQUE(league_id,game_id,side,label),
 FOREIGN KEY (league_id,game_id) REFERENCES games(league_id,game_id)
);
CREATE TABLE IF NOT EXISTS lineup_members (
 lineup_id INTEGER NOT NULL, league_id TEXT NOT NULL, player_id TEXT NOT NULL,
 PRIMARY KEY(lineup_id,player_id),
 FOREIGN KEY(lineup_id) REFERENCES lineup_stats(lineup_id) ON DELETE CASCADE,
 FOREIGN KEY(league_id,player_id) REFERENCES players(league_id,player_id)
);
CREATE TABLE IF NOT EXISTS game_analyses (
 league_id TEXT NOT NULL, game_id TEXT NOT NULL, point_number INTEGER NOT NULL CHECK(point_number BETWEEN 1 AND 3),
 title TEXT NOT NULL, content TEXT NOT NULL, quality_note TEXT NOT NULL,
 generated_at TEXT NOT NULL, PRIMARY KEY(league_id,game_id,point_number),
 FOREIGN KEY(league_id,game_id) REFERENCES games(league_id,game_id)
);
CREATE TABLE IF NOT EXISTS news_articles (
 league_id TEXT NOT NULL, url TEXT NOT NULL, title TEXT NOT NULL,
 published_date TEXT, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
 PRIMARY KEY(league_id,url), FOREIGN KEY(league_id) REFERENCES leagues(id)
);
CREATE TABLE IF NOT EXISTS snapshots (
 snapshot_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, generated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS update_runs (
 run_id INTEGER PRIMARY KEY, generated_at TEXT NOT NULL, imported_at TEXT NOT NULL,
 source_errors_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS insights (
 insight_id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
 author TEXT NOT NULL DEFAULT '凸肚男', status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published')),
 created_at TEXT NOT NULL, published_at TEXT
);
CREATE TABLE IF NOT EXISTS player_advanced_stats (
 league_id TEXT NOT NULL, game_id TEXT NOT NULL, player_id TEXT NOT NULL,
 ftm INTEGER CHECK(ftm>=0), fta INTEGER CHECK(fta>=ftm), assists INTEGER CHECK(assists>=0),
 rebounds INTEGER CHECK(rebounds>=0), steals INTEGER CHECK(steals>=0), blocks INTEGER CHECK(blocks>=0),
 usg REAL CHECK(usg>=0), eff REAL, ast_to REAL CHECK(ast_to>=0),
 potential_assists INTEGER, passes_made INTEGER, passes_received INTEGER, secondary_assists INTEGER, vorp REAL,
 PRIMARY KEY(league_id,game_id,player_id),
 FOREIGN KEY(league_id,game_id) REFERENCES games(league_id,game_id),
 FOREIGN KEY(league_id,player_id) REFERENCES players(league_id,player_id)
);
CREATE TABLE IF NOT EXISTS ato_sequences (
 league_id TEXT NOT NULL, game_id TEXT NOT NULL, sequence_number INTEGER NOT NULL,
 period INTEGER NOT NULL, timeout_seconds REAL NOT NULL, offense TEXT, defense TEXT,
 points INTEGER NOT NULL, turnovers INTEGER NOT NULL, eligible INTEGER NOT NULL CHECK(eligible IN (0,1)),
 exclusion_reason TEXT, inbounder_id TEXT, receiver_id TEXT, finisher_id TEXT,
 PRIMARY KEY(league_id,game_id,sequence_number),
 FOREIGN KEY(league_id,game_id) REFERENCES games(league_id,game_id)
);
PRAGMA user_version = 2;
