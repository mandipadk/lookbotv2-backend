-- Enable UUID and other required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- Create enum types
CREATE TYPE IF NOT EXISTS order_side AS ENUM ('buy', 'sell');
CREATE TYPE IF NOT EXISTS timeframe AS ENUM ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1mo');
CREATE TYPE IF NOT EXISTS option_type AS ENUM ('call', 'put');

-- Create non-timeseries tables first
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    api_key TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    UNIQUE(user_id, provider)
);

CREATE TABLE IF NOT EXISTS watchlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL CHECK (type IN ('ticker', 'topic', 'sector', 'industry')),
    priority INTEGER DEFAULT 0,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    watchlist_id UUID REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol TEXT,
    topic TEXT,
    source TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    last_seen_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    mention_count INTEGER DEFAULT 1,
    sentiment_score DECIMAL(5,2),
    alert_settings JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    CONSTRAINT symbol_or_topic CHECK (
        (symbol IS NOT NULL AND topic IS NULL) OR
        (symbol IS NULL AND topic IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS news_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT,
    url TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    sentiment_score DECIMAL(5,2),
    relevance_score DECIMAL(5,2),
    impact_score DECIMAL(5,2),
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS article_symbols (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES news_articles(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    mention_count INTEGER DEFAULT 1,
    sentiment_score DECIMAL(5,2),
    context_snippet TEXT,
    metadata JSONB DEFAULT '{}',
    UNIQUE(article_id, symbol)
);

CREATE TABLE IF NOT EXISTS article_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES news_articles(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    mention_count INTEGER DEFAULT 1,
    sentiment_score DECIMAL(5,2),
    relevance_score DECIMAL(5,2),
    metadata JSONB DEFAULT '{}',
    UNIQUE(article_id, topic)
);

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    is_read BOOLEAN DEFAULT false,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now())
);

-- Create timeseries tables (without indexes or unique constraints initially)
CREATE TABLE IF NOT EXISTS market_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe timeframe NOT NULL,
    open DECIMAL(20,6),
    high DECIMAL(20,6),
    low DECIMAL(20,6),
    close DECIMAL(20,6),
    volume BIGINT,
    vwap DECIMAL(20,6),
    number_of_trades INTEGER,
    source TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS technical_indicators (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe timeframe NOT NULL,
    indicator_type TEXT NOT NULL,
    values JSONB NOT NULL,
    parameters JSONB,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS order_flow (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    price DECIMAL(20,6) NOT NULL,
    size INTEGER NOT NULL,
    side order_side NOT NULL,
    is_aggressive BOOLEAN DEFAULT false,
    is_block_trade BOOLEAN DEFAULT false,
    exchange TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS volume_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe timeframe NOT NULL,
    price_level DECIMAL(20,6) NOT NULL,
    volume BIGINT NOT NULL,
    buy_volume BIGINT,
    sell_volume BIGINT,
    delta BIGINT,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS dark_pool_trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    venue TEXT NOT NULL,
    price DECIMAL(20,6) NOT NULL,
    size BIGINT NOT NULL,
    side order_side,
    is_block_trade BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS options_flow (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    expiration_date DATE NOT NULL,
    strike DECIMAL(20,6) NOT NULL,
    option_type option_type NOT NULL,
    price DECIMAL(20,6) NOT NULL,
    size INTEGER NOT NULL,
    premium DECIMAL(20,6) NOT NULL,
    open_interest INTEGER,
    implied_volatility DECIMAL(10,4),
    delta DECIMAL(10,4),
    gamma DECIMAL(10,4),
    theta DECIMAL(10,4),
    vega DECIMAL(10,4),
    is_sweep BOOLEAN DEFAULT false,
    is_block BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    signal_type TEXT NOT NULL,
    timeframe timeframe NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short', 'neutral')),
    strength DECIMAL(5,2),
    confidence DECIMAL(5,2),
    metadata JSONB DEFAULT '{}'
);

-- Create hypertables for time-series data
SELECT create_hypertable('market_data', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('technical_indicators', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('order_flow', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('volume_profiles', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('dark_pool_trades', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('options_flow', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('signals', 'timestamp', if_not_exists => TRUE);

-- Create indexes for non-timeseries tables
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_provider ON api_keys(user_id, provider);
CREATE INDEX IF NOT EXISTS idx_watchlists_user ON watchlists(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlists_type ON watchlists(type);
CREATE INDEX IF NOT EXISTS idx_watchlist_items_watchlist ON watchlist_items(watchlist_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_items_symbol ON watchlist_items(symbol) WHERE symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_watchlist_items_topic ON watchlist_items(topic) WHERE topic IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_news_articles_published ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_articles_source ON news_articles(source);
CREATE INDEX IF NOT EXISTS idx_article_symbols_article ON article_symbols(article_id);
CREATE INDEX IF NOT EXISTS idx_article_symbols_symbol ON article_symbols(symbol);
CREATE INDEX IF NOT EXISTS idx_article_topics_article ON article_topics(article_id);
CREATE INDEX IF NOT EXISTS idx_article_topics_topic ON article_topics(topic);
CREATE INDEX IF NOT EXISTS idx_notifications_user_time ON notifications(user_id, created_at DESC);

-- Create indexes for timeseries tables
CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_symbol ON technical_indicators(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_order_flow_symbol ON order_flow(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_volume_profiles_symbol ON volume_profiles(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_dark_pool_trades_symbol ON dark_pool_trades(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_options_flow_symbol ON options_flow(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol, timestamp DESC);

-- Create JSONB indexes
CREATE INDEX IF NOT EXISTS idx_users_settings ON users USING gin(settings);
CREATE INDEX IF NOT EXISTS idx_watchlists_settings ON watchlists USING gin(settings);
CREATE INDEX IF NOT EXISTS idx_watchlist_items_alert_settings ON watchlist_items USING gin(alert_settings);
CREATE INDEX IF NOT EXISTS idx_watchlist_items_metadata ON watchlist_items USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_news_articles_metadata ON news_articles USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_article_symbols_metadata ON article_symbols USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_article_topics_metadata ON article_topics USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_market_data_metadata ON market_data USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_values ON technical_indicators USING gin(values);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_parameters ON technical_indicators USING gin(parameters);
CREATE INDEX IF NOT EXISTS idx_order_flow_metadata ON order_flow USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_volume_profiles_metadata ON volume_profiles USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_dark_pool_trades_metadata ON dark_pool_trades USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_options_flow_metadata ON options_flow USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_signals_metadata ON signals USING gin(metadata);

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE news_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_symbols ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE technical_indicators ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_flow ENABLE ROW LEVEL SECURITY;
ALTER TABLE volume_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE dark_pool_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE options_flow ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- Create policies for authenticated users
CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON users
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON api_keys
    FOR SELECT TO authenticated USING (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON watchlists
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON watchlist_items
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON news_articles
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON article_symbols
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON article_topics
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON market_data
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON technical_indicators
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON order_flow
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON volume_profiles
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON dark_pool_trades
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON options_flow
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read for authenticated users" ON signals
    FOR SELECT TO authenticated USING (true);

CREATE POLICY IF NOT EXISTS "Allow read own notifications" ON notifications
    FOR SELECT TO authenticated USING (user_id = auth.uid());

-- Create policies for service role
CREATE POLICY IF NOT EXISTS "Allow all for service role" ON users
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON api_keys
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON watchlists
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON watchlist_items
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON news_articles
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON article_symbols
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON article_topics
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON market_data
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON technical_indicators
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON order_flow
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON volume_profiles
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON dark_pool_trades
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON options_flow
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON signals
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow all for service role" ON notifications
    FOR ALL TO service_role USING (true) WITH CHECK (true);
