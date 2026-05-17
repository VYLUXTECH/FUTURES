-- Migration: user_settings table
-- Allows per-user configuration of trading parameters

CREATE TABLE IF NOT EXISTS user_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    max_daily_trades int NOT NULL DEFAULT 5,
    risk_percent float NOT NULL DEFAULT 5.0,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Ensure one row per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);

-- RLS policies
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own settings"
    ON user_settings FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own settings"
    ON user_settings FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own settings"
    ON user_settings FOR UPDATE
    USING (auth.uid() = user_id);

-- Service role can read all settings (for the bot)
CREATE POLICY "Service role can read all settings"
    ON user_settings FOR SELECT
    USING (true);
