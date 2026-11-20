ALTER TABLE agent_runs ADD COLUMN model TEXT;
ALTER TABLE agent_runs ADD COLUMN effort TEXT;
ALTER TABLE agent_runs ADD COLUMN input_tokens INTEGER CHECK(input_tokens IS NULL OR input_tokens >= 0);
ALTER TABLE agent_runs ADD COLUMN output_tokens INTEGER CHECK(output_tokens IS NULL OR output_tokens >= 0);
ALTER TABLE agent_runs ADD COLUMN cost_usd REAL CHECK(cost_usd IS NULL OR cost_usd >= 0);
