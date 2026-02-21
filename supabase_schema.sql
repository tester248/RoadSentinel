-- SentinelRoad - Supabase Database Schema
-- Run this SQL in your Supabase SQL Editor to create all required tables

-- Traffic data table
CREATE TABLE IF NOT EXISTS traffic_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    current_speed DOUBLE PRECISION,
    free_flow_speed DOUBLE PRECISION,
    current_travel_time INTEGER,
    free_flow_travel_time INTEGER,
    confidence DOUBLE PRECISION,
    road_closure BOOLEAN DEFAULT FALSE,
    road_name TEXT,
    road_type TEXT,
    road_id BIGINT
);

-- Weather data table
CREATE TABLE IF NOT EXISTS weather_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    condition TEXT,
    description TEXT,
    temperature DOUBLE PRECISION,
    feels_like DOUBLE PRECISION,
    humidity INTEGER,
    visibility INTEGER,
    wind_speed DOUBLE PRECISION,
    clouds INTEGER
);

-- Risk scores table
CREATE TABLE IF NOT EXISTS risk_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL,
    risk_level TEXT NOT NULL,
    traffic_component DOUBLE PRECISION,
    weather_component DOUBLE PRECISION,
    infrastructure_component DOUBLE PRECISION,
    traffic_score DOUBLE PRECISION,
    poi_component DOUBLE PRECISION DEFAULT 0,
    poi_score DOUBLE PRECISION DEFAULT 0,
    weather_score DOUBLE PRECISION,
    infrastructure_score DOUBLE PRECISION,
    road_name TEXT,
    road_type TEXT,
    road_id BIGINT
);

-- Create indices for better query performance
CREATE INDEX IF NOT EXISTS idx_traffic_location ON traffic_data(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_traffic_timestamp ON traffic_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_weather_timestamp ON weather_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_risk_location ON risk_scores(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_risk_timestamp ON risk_scores(timestamp);
CREATE INDEX IF NOT EXISTS idx_risk_score ON risk_scores(risk_score);

-- Enable Row Level Security (optional, uncomment if needed)
-- ALTER TABLE traffic_data ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE weather_data ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE risk_scores ENABLE ROW LEVEL SECURITY;

-- Grant permissions (adjust as needed)
-- If using anonymous access, create a policy like:
-- CREATE POLICY "Allow anonymous insert" ON traffic_data FOR INSERT TO anon WITH CHECK (true);
-- CREATE POLICY "Allow anonymous insert" ON weather_data FOR INSERT TO anon WITH CHECK (true);
-- CREATE POLICY "Allow anonymous insert" ON risk_scores FOR INSERT TO anon WITH CHECK (true);
