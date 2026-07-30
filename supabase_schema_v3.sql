-- Run after supabase_schema.sql and supabase_schema_v2.sql.
-- Persists every parameter observation (e.g. Reflux Temperature, RPM,
-- Drying Hours) so they can be trended across batches for APQR /
-- annual product quality review and other data analysis.

create table if not exists parameter_observations (
    id bigint generated always as identity primary key,
    batch_number text not null references batches(batch_number) on delete cascade,
    operation_id text,
    page_no int,
    parameter text not null,
    spec_instruction text,
    written_value text,
    status text,
    deviation_type text,
    model_used text,
    created_at timestamptz default now(),
    unique (batch_number, operation_id, parameter)
);

create index if not exists idx_param_obs_batch on parameter_observations (batch_number);
create index if not exists idx_param_obs_parameter on parameter_observations (parameter);

alter table parameter_observations enable row level security;

create policy "allow all for anon - parameter_observations" on parameter_observations
    for all using (true) with check (true);
