-- 001_initial_schema.sql — full VolterraAI schema, generated from db/models.py.
-- Run with: psql $DATABASE_URL -f backend/db/migrations/001_initial_schema.sql
-- Existing databases: the ALTER TABLE statements at the bottom upgrade
-- a Week-1 schema in place (all guarded with IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS alert_log (
	id SERIAL NOT NULL, 
	user_id UUID NOT NULL, 
	tickers VARCHAR[], 
	sent_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS digest_log (
	id SERIAL NOT NULL, 
	sent_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	recipient_count INTEGER, 
	tickers_included VARCHAR[], 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS flow_scans (
	id SERIAL NOT NULL, 
	ticker VARCHAR NOT NULL, 
	scan_date DATE NOT NULL, 
	call_volume INTEGER, 
	put_volume INTEGER, 
	oi_ratio FLOAT, 
	avg_strike FLOAT, 
	avg_expiry DATE, 
	iv_rank FLOAT, 
	price_at_scan FLOAT, 
	raw_data JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS user_profiles (
	id UUID NOT NULL, 
	email VARCHAR NOT NULL, 
	tier VARCHAR DEFAULT 'free' NOT NULL, 
	strategy_tags VARCHAR[], 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS ai_summaries (
	id SERIAL NOT NULL, 
	flow_scan_id INTEGER NOT NULL, 
	setup_summary TEXT, 
	flow_interpretation TEXT, 
	risk_note TEXT, 
	news_used JSON, 
	model_version VARCHAR, 
	strategy_tags VARCHAR[], 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(flow_scan_id) REFERENCES flow_scans (id)
);

CREATE TABLE IF NOT EXISTS journal_entries (
	id SERIAL NOT NULL, 
	user_id UUID NOT NULL, 
	ticker VARCHAR NOT NULL, 
	ai_summary_id INTEGER, 
	user_notes TEXT, 
	entry_price FLOAT, 
	strategy_type VARCHAR, 
	expiry_date DATE, 
	outcome VARCHAR, 
	outcome_pnl_pct FLOAT, 
	saved_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user_profiles (id), 
	FOREIGN KEY(ai_summary_id) REFERENCES ai_summaries (id)
);


-- Upgrades for databases created before these columns existed
ALTER TABLE ai_summaries ADD COLUMN IF NOT EXISTS strategy_tags VARCHAR[];
ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

-- Helpful indexes for the hot query paths
CREATE INDEX IF NOT EXISTS idx_flow_scans_scan_date ON flow_scans (scan_date);
CREATE INDEX IF NOT EXISTS idx_flow_scans_ticker_date ON flow_scans (ticker, scan_date);
CREATE INDEX IF NOT EXISTS idx_ai_summaries_flow_scan ON ai_summaries (flow_scan_id);
CREATE INDEX IF NOT EXISTS idx_journal_entries_user ON journal_entries (user_id, saved_at);
