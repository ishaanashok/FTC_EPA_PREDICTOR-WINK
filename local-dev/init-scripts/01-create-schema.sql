-- FTC Predictor Local Development Database Schema
-- PostgreSQL schema that mirrors DynamoDB structure

-- Enable UUID extension for generating IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Teams table (mirrors FTC_Teams_stage)
CREATE TABLE teams (
    team_number INTEGER NOT NULL,
    season INTEGER NOT NULL,
    team_name VARCHAR(255) DEFAULT '',
    school_name TEXT DEFAULT '',
    city VARCHAR(255) DEFAULT '',
    state VARCHAR(255) DEFAULT '',
    country VARCHAR(255) DEFAULT '',
    rookie_year INTEGER,
    website TEXT,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- HTTP Caching Support & Change Detection
    last_modified VARCHAR(255),
    etag VARCHAR(255),
    api_last_modified TIMESTAMP WITH TIME ZONE,
    data_version VARCHAR(255),
    data_hash VARCHAR(255),
    
    PRIMARY KEY (team_number, season)
);

-- Create indexes to mirror DynamoDB GSIs
CREATE INDEX idx_teams_season ON teams (season);
CREATE INDEX idx_teams_team_number ON teams (team_number);
CREATE INDEX idx_teams_data_hash ON teams (data_hash) WHERE data_hash IS NOT NULL;

-- Events table (mirrors FTC_Events_stage)
CREATE TABLE events (
    event_code VARCHAR(50) NOT NULL,
    season INTEGER NOT NULL,
    event_name VARCHAR(255) DEFAULT '',
    event_type VARCHAR(50) DEFAULT '',
    date_start TIMESTAMP WITH TIME ZONE,
    date_end TIMESTAMP WITH TIME ZONE,
    venue TEXT,
    address TEXT,
    city VARCHAR(255),
    state VARCHAR(255),
    country VARCHAR(255),
    timezone VARCHAR(100),
    website TEXT,
    live_stream_url TEXT,
    team_count INTEGER DEFAULT 0,
    match_count INTEGER DEFAULT 0,
    team_numbers TEXT, -- Comma-separated list
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- HTTP Caching Support & Change Detection
    last_modified VARCHAR(255),
    etag VARCHAR(255),
    api_last_modified TIMESTAMP WITH TIME ZONE,
    data_version VARCHAR(255),
    data_hash VARCHAR(255),
    matches_last_modified VARCHAR(255),
    rankings_last_modified VARCHAR(255),
    
    PRIMARY KEY (event_code, season)
);

-- Create indexes to mirror DynamoDB GSIs
CREATE INDEX idx_events_season ON events (season);
CREATE INDEX idx_events_event_code ON events (event_code);
CREATE INDEX idx_events_date_start ON events (date_start);
CREATE INDEX idx_events_data_hash ON events (data_hash) WHERE data_hash IS NOT NULL;

-- Matches table (mirrors FTC_Matches_stage)
CREATE TABLE matches (
    match_id VARCHAR(255) NOT NULL PRIMARY KEY,
    season INTEGER NOT NULL,
    event_code VARCHAR(50) NOT NULL,
    match_number INTEGER NOT NULL,
    description TEXT DEFAULT '',
    tournament_level VARCHAR(50) DEFAULT '',
    series INTEGER,
    match_name VARCHAR(255),
    play_number INTEGER,
    field_number INTEGER,
    start_time TIMESTAMP WITH TIME ZONE,
    actual_start_time TIMESTAMP WITH TIME ZONE,
    post_result_time TIMESTAMP WITH TIME ZONE,
    
    -- Team information (stored as JSONB for flexibility)
    teams JSONB,
    red_teams INTEGER[],
    blue_teams INTEGER[],
    all_teams INTEGER[],
    
    -- Scores (stored as JSONB to match DynamoDB structure)
    red_score JSONB,
    blue_score JSONB,
    
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- HTTP Caching Support & Change Detection
    last_modified VARCHAR(255),
    etag VARCHAR(255),
    api_last_modified TIMESTAMP WITH TIME ZONE,
    data_version VARCHAR(255),
    data_hash VARCHAR(255)
);

-- Create indexes to mirror DynamoDB GSIs
CREATE INDEX idx_matches_team_season ON matches USING GIN (all_teams) WHERE all_teams IS NOT NULL;
CREATE INDEX idx_matches_event_season ON matches (event_code, season);
CREATE INDEX idx_matches_season ON matches (season);
CREATE INDEX idx_matches_tournament_level ON matches (tournament_level);
CREATE INDEX idx_matches_data_hash ON matches (data_hash) WHERE data_hash IS NOT NULL;

-- Helper function to extract team numbers from matches
CREATE OR REPLACE FUNCTION extract_team_numbers_from_match(match_teams JSONB)
RETURNS INTEGER[] AS $$
DECLARE
    team_numbers INTEGER[] := '{}';
    team_obj JSONB;
BEGIN
    FOR team_obj IN SELECT jsonb_array_elements(match_teams)
    LOOP
        team_numbers := array_append(team_numbers, (team_obj->>'teamNumber')::INTEGER);
    END LOOP;
    RETURN team_numbers;
END;
$$ LANGUAGE plpgsql;

-- EPA Calculations table (mirrors FTC_EPA_stage)
CREATE TABLE epa_calculations (
    team_number INTEGER NOT NULL,
    calculation_date DATE NOT NULL,
    historical_epa DECIMAL(10,4) DEFAULT 0.0,
    current_season_epa DECIMAL(10,4) DEFAULT 0.0,
    
    -- Season-specific EPAs (stored as JSONB)
    season_epas JSONB DEFAULT '{}',
    
    -- Match statistics
    total_matches INTEGER DEFAULT 0,
    recent_matches INTEGER DEFAULT 0,
    
    -- Performance metrics
    avg_auto_points DECIMAL(10,4) DEFAULT 0.0,
    avg_teleop_points DECIMAL(10,4) DEFAULT 0.0,
    avg_endgame_points DECIMAL(10,4) DEFAULT 0.0,
    
    -- Calculation metadata
    calculation_version VARCHAR(50) DEFAULT '1.0',
    data_quality VARCHAR(50) DEFAULT 'good',
    last_match_date DATE,
    
    -- Timestamps
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_latest BOOLEAN DEFAULT TRUE,
    
    PRIMARY KEY (team_number, calculation_date)
);

-- Create indexes for EPA queries
CREATE INDEX idx_epa_team_number ON epa_calculations (team_number);
CREATE INDEX idx_epa_calculation_date ON epa_calculations (calculation_date);
CREATE INDEX idx_epa_is_latest ON epa_calculations (is_latest) WHERE is_latest = TRUE;
CREATE INDEX idx_epa_current_season ON epa_calculations (current_season_epa DESC);

-- Sync Status table (mirrors FTC_SyncStatus_stage)
CREATE TABLE sync_status (
    sync_key VARCHAR(255) NOT NULL,
    last_sync_time TIMESTAMP WITH TIME ZONE NOT NULL,
    next_sync_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    records_processed INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    
    -- HTTP Caching Support for bandwidth optimization
    last_modified_header VARCHAR(255),
    if_modified_since_used VARCHAR(255),
    fms_only_modified_since_used VARCHAR(255),
    etag VARCHAR(255),
    data_changed BOOLEAN DEFAULT TRUE,
    bandwidth_saved INTEGER DEFAULT 0,
    
    PRIMARY KEY (sync_key, last_sync_time)
);

-- Create indexes for sync status queries
CREATE INDEX idx_sync_status_key ON sync_status (sync_key);
CREATE INDEX idx_sync_status_time ON sync_status (last_sync_time DESC);
CREATE INDEX idx_sync_status_status ON sync_status (status);

-- Additional helper tables for local development

-- Alliance Compatibility table (from your data models)
CREATE TABLE alliance_compatibility (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_number_1 INTEGER NOT NULL,
    team_number_2 INTEGER NOT NULL,
    compatibility_score DECIMAL(10,4) DEFAULT 0.0,
    combined_epa DECIMAL(10,4) DEFAULT 0.0,
    strength_areas TEXT[], -- Array of strength areas
    complementary_areas TEXT[], -- Array of complementary areas
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(team_number_1, team_number_2)
);

-- Event Predictions table (from your data models)
CREATE TABLE event_predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_code VARCHAR(50) NOT NULL,
    season INTEGER NOT NULL,
    match_number INTEGER NOT NULL,
    red_teams INTEGER[] NOT NULL,
    blue_teams INTEGER[] NOT NULL,
    
    -- Prediction data
    red_win_probability DECIMAL(5,4) DEFAULT 0.0,
    blue_win_probability DECIMAL(5,4) DEFAULT 0.0,
    predicted_red_score DECIMAL(10,4) DEFAULT 0.0,
    predicted_blue_score DECIMAL(10,4) DEFAULT 0.0,
    
    -- Confidence metrics
    confidence_level DECIMAL(5,4) DEFAULT 0.0,
    data_quality VARCHAR(50) DEFAULT 'unknown',
    
    -- EPA data used (stored as JSONB)
    team_epas JSONB DEFAULT '{}',
    
    -- Timestamps
    predicted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(event_code, season, match_number)
);

-- Create indexes for predictions
CREATE INDEX idx_predictions_event ON event_predictions (event_code, season);
CREATE INDEX idx_predictions_match ON event_predictions (match_number);
CREATE INDEX idx_predictions_predicted_at ON event_predictions (predicted_at DESC);

-- Views for easier querying (mimicking DynamoDB query patterns)

-- Latest EPA calculations per team
CREATE VIEW latest_epa_calculations AS
SELECT DISTINCT ON (team_number) 
    team_number,
    calculation_date,
    historical_epa,
    current_season_epa,
    season_epas,
    total_matches,
    recent_matches,
    avg_auto_points,
    avg_teleop_points,
    avg_endgame_points,
    calculation_version,
    data_quality,
    last_match_date,
    calculated_at
FROM epa_calculations 
WHERE is_latest = TRUE
ORDER BY team_number, calculation_date DESC;

-- Current season teams (2024)
CREATE VIEW current_season_teams AS
SELECT * FROM teams WHERE season = 2024;

-- Current season events (2024)
CREATE VIEW current_season_events AS
SELECT * FROM events WHERE season = 2024;

-- Current season matches (2024)
CREATE VIEW current_season_matches AS
SELECT * FROM matches WHERE season = 2024;

-- Team match statistics view
CREATE VIEW team_match_stats AS
SELECT 
    unnest(all_teams) as team_number,
    season,
    event_code,
    COUNT(*) as matches_played,
    COUNT(CASE WHEN red_score IS NOT NULL AND blue_score IS NOT NULL THEN 1 END) as scored_matches
FROM matches 
WHERE all_teams IS NOT NULL
GROUP BY unnest(all_teams), season, event_code;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ftc_dev;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ftc_dev;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO ftc_dev;
