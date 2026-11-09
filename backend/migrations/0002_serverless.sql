-- 0002_serverless:Vercel 無狀態架構需要的持久化工作、派發、限流與價格觀測。只新增,不改舊欄位。

CREATE TABLE tr_jobs (
	id VARCHAR(32) PRIMARY KEY,
	user_id INTEGER REFERENCES tr_users (id),
	kind VARCHAR(20) NOT NULL,
	status VARCHAR(16) NOT NULL DEFAULT 'queued',
	priority INTEGER NOT NULL DEFAULT 0,
	config JSON NOT NULL DEFAULT '{}',
	cursor JSON NOT NULL DEFAULT '{}',
	error TEXT NOT NULL DEFAULT '',
	stop_requested BOOLEAN NOT NULL DEFAULT false,
	attempts INTEGER NOT NULL DEFAULT 0,
	max_attempts INTEGER NOT NULL DEFAULT 3,
	claimed_by VARCHAR(40) NOT NULL DEFAULT '',
	claim_token VARCHAR(32),
	heartbeat_at TIMESTAMP WITH TIME ZONE,
	available_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	dedupe_key VARCHAR(120),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	started_at TIMESTAMP WITH TIME ZONE,
	finished_at TIMESTAMP WITH TIME ZONE,
	CONSTRAINT tr_jobs_dedupe_key_key UNIQUE (dedupe_key)
);
CREATE INDEX ix_jobs_claim ON tr_jobs (status, priority, available_at);
CREATE INDEX ix_jobs_user_status ON tr_jobs (user_id, status);
CREATE INDEX ix_tr_jobs_finished_at ON tr_jobs (finished_at);

CREATE TABLE tr_job_events (
	id BIGSERIAL PRIMARY KEY,
	job_id VARCHAR(32) NOT NULL REFERENCES tr_jobs (id) ON DELETE CASCADE,
	seq INTEGER NOT NULL DEFAULT 0,
	event JSON NOT NULL DEFAULT '{}',
	created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	CONSTRAINT uq_job_event_seq UNIQUE (job_id, seq)
);
CREATE INDEX ix_tr_job_events_created_at ON tr_job_events (created_at);

CREATE TABLE tr_crawl_frontier (
	id BIGSERIAL PRIMARY KEY,
	job_id VARCHAR(32) NOT NULL REFERENCES tr_jobs (id) ON DELETE CASCADE,
	url_hash VARCHAR(40) NOT NULL,
	url TEXT NOT NULL,
	depth INTEGER NOT NULL DEFAULT 0,
	status VARCHAR(10) NOT NULL DEFAULT 'pending',
	CONSTRAINT uq_frontier_url UNIQUE (job_id, url_hash)
);
CREATE INDEX ix_frontier_next ON tr_crawl_frontier (job_id, status, id);

CREATE TABLE tr_price_observations (
	id BIGSERIAL PRIMARY KEY,
	user_id INTEGER REFERENCES tr_users (id),
	url VARCHAR(1000) NOT NULL,
	url_hash VARCHAR(40) NOT NULL,
	source VARCHAR(16) NOT NULL DEFAULT '',
	source_id VARCHAR(40) NOT NULL DEFAULT '',
	price_twd INTEGER NOT NULL DEFAULT 0,
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
CREATE INDEX ix_price_obs_lookup ON tr_price_observations (user_id, url_hash, observed_at);
CREATE INDEX ix_tr_price_observations_observed_at ON tr_price_observations (observed_at);

CREATE TABLE tr_rate_limits (
	key VARCHAR(255) PRIMARY KEY,
	hits INTEGER NOT NULL DEFAULT 0,
	expires_at DOUBLE PRECISION NOT NULL DEFAULT 0
);
CREATE INDEX ix_tr_rate_limits_expires_at ON tr_rate_limits (expires_at);

CREATE TABLE tr_cron_state (
	name VARCHAR(40) PRIMARY KEY,
	next_run_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	last_run_at TIMESTAMP WITH TIME ZONE
);

-- 排程 / 監看的派發與認領欄位
ALTER TABLE tr_schedules
	ADD COLUMN next_run_at TIMESTAMP WITH TIME ZONE,
	ADD COLUMN claimed_at TIMESTAMP WITH TIME ZONE,
	ADD COLUMN claim_job_id VARCHAR(32);
CREATE INDEX ix_tr_schedules_next_run_at ON tr_schedules (next_run_at);

ALTER TABLE tr_watches
	ADD COLUMN next_run_at TIMESTAMP WITH TIME ZONE,
	ADD COLUMN claimed_at TIMESTAMP WITH TIME ZONE,
	ADD COLUMN claim_job_id VARCHAR(32);
CREATE INDEX ix_tr_watches_next_run_at ON tr_watches (next_run_at);

-- 整站爬項目去重(舊資料 dedupe_key 為 NULL,不受唯一限制影響)
ALTER TABLE tr_crawl_items ADD COLUMN dedupe_key VARCHAR(40);
CREATE UNIQUE INDEX ux_crawl_items_dedupe ON tr_crawl_items (run_id, dedupe_key);
