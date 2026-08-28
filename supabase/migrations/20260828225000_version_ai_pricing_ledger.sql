-- Preserve which reviewed provider tariff catalog produced each recorded AI cost.
-- Existing pre-version records remain explicitly marked legacy; production runtime requires an
-- operator-supplied AI_PRICING_VERSION for all new records.

alter table public.ai_usage_costs
    add column if not exists pricing_version text not null default 'legacy';

alter table public.ai_usage_costs
    add constraint ai_usage_costs_pricing_version_check
        check (
            nullif(btrim(pricing_version), '') is not null
            and char_length(pricing_version) <= 80
        );

create index if not exists ai_usage_costs_pricing_version_idx
    on public.ai_usage_costs (owner_user_id, pricing_version, recorded_at desc);
