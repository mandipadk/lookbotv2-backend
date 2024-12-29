-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);
CREATE INDEX idx_users_username ON users(username);

-- Create watchlists table
CREATE TABLE watchlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL CHECK (type IN ('ticker', 'topic')),
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);
CREATE INDEX idx_watchlists_type ON watchlists(type);
CREATE INDEX idx_watchlists_priority ON watchlists(priority);

-- Create watchlist_items table
CREATE TABLE watchlist_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    watchlist_id UUID REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol TEXT,
    topic TEXT,
    source TEXT NOT NULL,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    mention_count INTEGER DEFAULT 1,
    sentiment_score DECIMAL(5,2),
    CONSTRAINT symbol_or_topic CHECK (
        (symbol IS NOT NULL AND topic IS NULL) OR
        (symbol IS NULL AND topic IS NOT NULL)
    )
);
CREATE INDEX idx_watchlist_items_watchlist ON watchlist_items(watchlist_id);
CREATE INDEX idx_watchlist_items_symbol ON watchlist_items(symbol) WHERE symbol IS NOT NULL;
CREATE INDEX idx_watchlist_items_topic ON watchlist_items(topic) WHERE topic IS NOT NULL;
CREATE INDEX idx_watchlist_items_sentiment ON watchlist_items(sentiment_score);

-- Create news_articles table
CREATE TABLE news_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT,
    url TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    sentiment_score DECIMAL(5,2),
    relevance_score DECIMAL(5,2)
);
CREATE INDEX idx_news_articles_published ON news_articles(published_at DESC);
CREATE INDEX idx_news_articles_source ON news_articles(source);
CREATE INDEX idx_news_articles_url ON news_articles(url);
CREATE INDEX idx_news_articles_sentiment ON news_articles(sentiment_score);
CREATE INDEX idx_news_articles_relevance ON news_articles(relevance_score);

-- Create article_symbols table
CREATE TABLE article_symbols (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES news_articles(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    mention_count INTEGER DEFAULT 1,
    sentiment_score DECIMAL(5,2),
    UNIQUE(article_id, symbol)
);
CREATE INDEX idx_article_symbols_article ON article_symbols(article_id);
CREATE INDEX idx_article_symbols_symbol ON article_symbols(symbol);
CREATE INDEX idx_article_symbols_sentiment ON article_symbols(sentiment_score);

-- Create article_topics table
CREATE TABLE article_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES news_articles(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    mention_count INTEGER DEFAULT 1,
    sentiment_score DECIMAL(5,2),
    UNIQUE(article_id, topic)
);
CREATE INDEX idx_article_topics_article ON article_topics(article_id);
CREATE INDEX idx_article_topics_topic ON article_topics(topic);
CREATE INDEX idx_article_topics_sentiment ON article_topics(sentiment_score);

-- Create market_data table
CREATE TABLE market_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open DECIMAL(20,6),
    high DECIMAL(20,6),
    low DECIMAL(20,6),
    close DECIMAL(20,6),
    volume BIGINT,
    source TEXT NOT NULL,
    UNIQUE(symbol, timestamp, source)
);
CREATE INDEX idx_market_data_symbol_time ON market_data(symbol, timestamp DESC);
CREATE INDEX idx_market_data_source ON market_data(source);
CREATE INDEX idx_market_data_timestamp ON market_data(timestamp DESC);

-- Create technical_indicators table
CREATE TABLE technical_indicators (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    indicator_type TEXT NOT NULL,
    value DECIMAL(20,6),
    parameters JSONB,
    UNIQUE(symbol, timestamp, indicator_type, parameters)
);
CREATE INDEX idx_technical_indicators_symbol_time ON technical_indicators(symbol, timestamp DESC);
CREATE INDEX idx_technical_indicators_type ON technical_indicators(indicator_type);
CREATE INDEX idx_technical_indicators_params ON technical_indicators USING gin(parameters);

-- Create RLS (Row Level Security) Policies
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE news_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_symbols ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE technical_indicators ENABLE ROW LEVEL SECURITY;

-- Create policies for authenticated users
CREATE POLICY "Allow read for authenticated users" ON users
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow read for authenticated users" ON watchlists
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow read for authenticated users" ON watchlist_items
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow read for authenticated users" ON news_articles
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow read for authenticated users" ON article_symbols
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow read for authenticated users" ON article_topics
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow read for authenticated users" ON market_data
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow read for authenticated users" ON technical_indicators
    FOR SELECT
    TO authenticated
    USING (true);

-- Create policies for service role (our backend application)
CREATE POLICY "Allow all for service role" ON users
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow all for service role" ON watchlists
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow all for service role" ON watchlist_items
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow all for service role" ON news_articles
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow all for service role" ON article_symbols
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow all for service role" ON article_topics
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow all for service role" ON market_data
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow all for service role" ON technical_indicators
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
