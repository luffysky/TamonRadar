-- 0001_baseline:與舊版正式環境相同的結構(表名、欄名不變),由 ORM 產生後人工檢視。
-- 舊版 _ensure_columns 以 ALTER TABLE 補上的欄位在既有資料列可能是 NULL,這裡一律可為 NULL 並保留當時的 DEFAULT,才能完整匯入舊資料。

CREATE TABLE tr_announcements (
	id SERIAL NOT NULL,
	title VARCHAR(200) NOT NULL,
	body TEXT NOT NULL,
	level VARCHAR(20) NOT NULL,
	active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);


CREATE TABLE tr_app_settings (
	key VARCHAR(80) NOT NULL,
	value TEXT NOT NULL,
	PRIMARY KEY (key)
);


CREATE TABLE tr_audit (
	id SERIAL NOT NULL,
	admin_email VARCHAR(255) NOT NULL,
	action VARCHAR(80) NOT NULL,
	target_type VARCHAR(40) DEFAULT '',
	target VARCHAR(255) NOT NULL,
	detail TEXT NOT NULL,
	changes JSON,
	ip VARCHAR(64) DEFAULT '',
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_tr_audit_created_at ON tr_audit (created_at);

CREATE TABLE tr_bot_chat_log (
	id SERIAL NOT NULL,
	platform VARCHAR(20) NOT NULL,
	platform_user VARCHAR(120) NOT NULL,
	question TEXT NOT NULL,
	answer TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_tr_bot_chat_log_created_at ON tr_bot_chat_log (created_at);

CREATE TABLE tr_crawl_items (
	id SERIAL NOT NULL,
	run_id VARCHAR(32) NOT NULL,
	payload JSON NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_tr_crawl_items_run_id ON tr_crawl_items (run_id);

CREATE TABLE tr_scheduled_broadcasts (
	id SERIAL NOT NULL,
	title VARCHAR(200) NOT NULL,
	body TEXT NOT NULL,
	url VARCHAR(1000) NOT NULL,
	channels JSON NOT NULL,
	segment VARCHAR(20) NOT NULL,
	run_at TIMESTAMP WITH TIME ZONE NOT NULL,
	sent BOOLEAN NOT NULL,
	result JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_tr_scheduled_broadcasts_run_at ON tr_scheduled_broadcasts (run_at);

CREATE TABLE tr_users (
	id SERIAL NOT NULL,
	email VARCHAR(255) NOT NULL,
	username VARCHAR(60) DEFAULT '',
	password_hash VARCHAR(255) NOT NULL,
	provider VARCHAR(32) DEFAULT 'local',
	plan VARCHAR(20) DEFAULT 'free',
	privileged BOOLEAN DEFAULT false,
	banned BOOLEAN DEFAULT false,
	email_verified BOOLEAN DEFAULT false,
	token_version INTEGER DEFAULT 0,
	ai_used INTEGER DEFAULT 0,
	admin_note TEXT DEFAULT '',
	tags JSON,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_tr_users_email ON tr_users (email);

CREATE TABLE tr_ai_chat_log (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	kind VARCHAR(20) NOT NULL,
	question TEXT NOT NULL,
	answer TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_ai_chat_log_created_at ON tr_ai_chat_log (created_at);
CREATE INDEX ix_tr_ai_chat_log_user_id ON tr_ai_chat_log (user_id);

CREATE TABLE tr_ai_cost (
	id SERIAL NOT NULL,
	user_id INTEGER,
	actor VARCHAR(80) DEFAULT '',
	provider VARCHAR(20) NOT NULL,
	model VARCHAR(80) NOT NULL,
	in_tokens INTEGER NOT NULL,
	out_tokens INTEGER NOT NULL,
	cost_usd DOUBLE PRECISION NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_ai_cost_created_at ON tr_ai_cost (created_at);
CREATE INDEX ix_tr_ai_cost_user_id ON tr_ai_cost (user_id);

CREATE TABLE tr_bind_codes (
	code VARCHAR(12) NOT NULL,
	user_id INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (code),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_bind_codes_user_id ON tr_bind_codes (user_id);

CREATE TABLE tr_favorites (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	url VARCHAR(1000) NOT NULL,
	title VARCHAR(300) NOT NULL,
	image_url VARCHAR(1000) NOT NULL,
	domain VARCHAR(200) NOT NULL,
	price VARCHAR(50) NOT NULL,
	target_twd INTEGER,
	last_price_twd INTEGER,
	last_checked TIMESTAMP WITH TIME ZONE,
	last_error TEXT DEFAULT '',
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_fav_user_url UNIQUE (user_id, url),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_favorites_user_id ON tr_favorites (user_id);

CREATE TABLE tr_notifications (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	title VARCHAR(200) NOT NULL,
	body TEXT NOT NULL,
	url VARCHAR(1000) NOT NULL,
	read BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_notifications_created_at ON tr_notifications (created_at);
CREATE INDEX ix_tr_notifications_user_id ON tr_notifications (user_id);

CREATE TABLE tr_posts (
	id SERIAL NOT NULL,
	slug VARCHAR(200) NOT NULL,
	title VARCHAR(300) NOT NULL,
	excerpt VARCHAR(500) NOT NULL,
	content TEXT NOT NULL,
	cover_image VARCHAR(1000) NOT NULL,
	category VARCHAR(50) NOT NULL,
	series VARCHAR(100) DEFAULT '',
	tags JSON NOT NULL,
	published BOOLEAN NOT NULL,
	featured BOOLEAN DEFAULT false,
	likes INTEGER DEFAULT 0,
	views INTEGER DEFAULT 0,
	password VARCHAR(100) DEFAULT '',
	preview_token VARCHAR(40) DEFAULT '',
	author_id INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(author_id) REFERENCES tr_users (id)
);

CREATE UNIQUE INDEX ix_tr_posts_slug ON tr_posts (slug);

CREATE TABLE tr_push_subs (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	endpoint VARCHAR(500) NOT NULL,
	p256dh VARCHAR(255) NOT NULL,
	auth VARCHAR(255) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id),
	UNIQUE (endpoint)
);

CREATE INDEX ix_tr_push_subs_user_id ON tr_push_subs (user_id);

CREATE TABLE tr_reports (
	id SERIAL NOT NULL,
	target_type VARCHAR(20) NOT NULL,
	target_id INTEGER NOT NULL,
	reason VARCHAR(500) NOT NULL,
	reporter_id INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(reporter_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_reports_created_at ON tr_reports (created_at);
CREATE INDEX ix_tr_reports_reporter_id ON tr_reports (reporter_id);

CREATE TABLE tr_runs (
	id VARCHAR(32) NOT NULL,
	user_id INTEGER NOT NULL,
	status VARCHAR(32) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	finished_at TIMESTAMP WITH TIME ZONE NOT NULL,
	keywords JSON NOT NULL,
	summary JSON NOT NULL,
	records JSON NOT NULL,
	shared BOOLEAN DEFAULT false,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_runs_user_id ON tr_runs (user_id);

CREATE TABLE tr_schedules (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	keywords JSON NOT NULL,
	provider VARCHAR(32) NOT NULL,
	pages INTEGER NOT NULL,
	max_detail INTEGER NOT NULL,
	scrape_details BOOLEAN NOT NULL,
	interval_hours INTEGER NOT NULL,
	enabled BOOLEAN NOT NULL,
	last_run TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_schedules_user_id ON tr_schedules (user_id);

CREATE TABLE tr_subscriptions (
	id SERIAL NOT NULL,
	subscriber_id INTEGER NOT NULL,
	author_id INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_sub UNIQUE (subscriber_id, author_id),
	FOREIGN KEY(subscriber_id) REFERENCES tr_users (id),
	FOREIGN KEY(author_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_subscriptions_author_id ON tr_subscriptions (author_id);
CREATE INDEX ix_tr_subscriptions_subscriber_id ON tr_subscriptions (subscriber_id);

CREATE TABLE tr_threads (
	id SERIAL NOT NULL,
	category VARCHAR(50) NOT NULL,
	title VARCHAR(300) NOT NULL,
	content TEXT NOT NULL,
	author_id INTEGER NOT NULL,
	author_email VARCHAR(255) NOT NULL,
	reply_count INTEGER NOT NULL,
	likes INTEGER DEFAULT 0,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	last_reply_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(author_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_threads_author_id ON tr_threads (author_id);
CREATE INDEX ix_tr_threads_category ON tr_threads (category);

CREATE TABLE tr_usage (
	user_id INTEGER NOT NULL,
	day VARCHAR(10) NOT NULL,
	ai INTEGER NOT NULL,
	search INTEGER NOT NULL,
	PRIMARY KEY (user_id, day),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);


CREATE TABLE tr_user_settings (
	user_id INTEGER NOT NULL,
	discord_webhook TEXT NOT NULL,
	discord_user_id VARCHAR(40) DEFAULT '',
	telegram_token TEXT NOT NULL,
	telegram_chat_id TEXT NOT NULL,
	openai_key TEXT DEFAULT '',
	anthropic_key TEXT DEFAULT '',
	gemini_key TEXT DEFAULT '',
	groq_key TEXT DEFAULT '',
	openrouter_key TEXT DEFAULT '',
	ai_provider VARCHAR(20) DEFAULT '',
	daily_digest BOOLEAN DEFAULT false,
	PRIMARY KEY (user_id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);


CREATE TABLE tr_watches (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	name VARCHAR(200) NOT NULL,
	url VARCHAR(1000) NOT NULL,
	available_keywords JSON NOT NULL,
	unavailable_keywords JSON NOT NULL,
	interval_minutes INTEGER NOT NULL,
	enabled BOOLEAN NOT NULL,
	last_status VARCHAR(20) NOT NULL,
	last_checked TIMESTAMP WITH TIME ZONE,
	target_price INTEGER,
	last_price_twd INTEGER,
	mode VARCHAR(20) DEFAULT 'stock',
	snapshot JSON,
	notify_on JSON,
	cta_text VARCHAR(60) DEFAULT '',
	cta_url VARCHAR(1000) DEFAULT '',
	last_error TEXT DEFAULT '',
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_watches_user_id ON tr_watches (user_id);

CREATE TABLE tr_post_comments (
	id SERIAL NOT NULL,
	post_id INTEGER NOT NULL,
	author_id INTEGER NOT NULL,
	author_name VARCHAR(120) NOT NULL,
	content TEXT NOT NULL,
	status VARCHAR(10) NOT NULL,
	parent_id INTEGER,
	like_count INTEGER DEFAULT 0,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(post_id) REFERENCES tr_posts (id),
	FOREIGN KEY(author_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_post_comments_created_at ON tr_post_comments (created_at);
CREATE INDEX ix_tr_post_comments_parent_id ON tr_post_comments (parent_id);
CREATE INDEX ix_tr_post_comments_post_id ON tr_post_comments (post_id);

CREATE TABLE tr_post_likes (
	id SERIAL NOT NULL,
	post_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_postlike UNIQUE (post_id, user_id),
	FOREIGN KEY(post_id) REFERENCES tr_posts (id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_post_likes_post_id ON tr_post_likes (post_id);
CREATE INDEX ix_tr_post_likes_user_id ON tr_post_likes (user_id);

CREATE TABLE tr_post_reactions (
	id SERIAL NOT NULL,
	post_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	emoji VARCHAR(8) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_reaction UNIQUE (post_id, user_id, emoji),
	FOREIGN KEY(post_id) REFERENCES tr_posts (id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_post_reactions_post_id ON tr_post_reactions (post_id);
CREATE INDEX ix_tr_post_reactions_user_id ON tr_post_reactions (user_id);

CREATE TABLE tr_replies (
	id SERIAL NOT NULL,
	thread_id INTEGER NOT NULL,
	content TEXT NOT NULL,
	author_id INTEGER NOT NULL,
	author_email VARCHAR(255) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(thread_id) REFERENCES tr_threads (id),
	FOREIGN KEY(author_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_replies_thread_id ON tr_replies (thread_id);

CREATE TABLE tr_post_comment_likes (
	id SERIAL NOT NULL,
	comment_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_clike UNIQUE (comment_id, user_id),
	FOREIGN KEY(comment_id) REFERENCES tr_post_comments (id),
	FOREIGN KEY(user_id) REFERENCES tr_users (id)
);

CREATE INDEX ix_tr_post_comment_likes_comment_id ON tr_post_comment_likes (comment_id);
CREATE INDEX ix_tr_post_comment_likes_user_id ON tr_post_comment_likes (user_id);
