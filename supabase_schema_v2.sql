-- Run this once in Supabase SQL Editor (after supabase_schema.sql).
-- Adds support for: multiple materials per operation, start/end time
-- windows, and repeating time-series log rows (Table-1/Table-2 style).

alter table operations rename column timestamp_raw to start_time_raw;
alter table operations add column if not exists end_time_raw text;

create table if not exists operation_materials (
    id bigint generated always as identity primary key,
    batch_number text not null references batches(batch_number) on delete cascade,
    operation_id text not null,
    material text not null,
    qty_used_raw text,
    page_no int,
    created_at timestamptz default now(),
    unique (batch_number, operation_id, material)
);

create table if not exists timeseries_readings (
    id bigint generated always as identity primary key,
    batch_number text not null references batches(batch_number) on delete cascade,
    operation_id text not null,
    table_name text not null,
    date_raw text,
    time_raw text,
    recorded_by text,
    value_raw text,
    page_no int,
    created_at timestamptz default now()
);

create index if not exists idx_op_materials_batch on operation_materials (batch_number);
create index if not exists idx_op_materials_material on operation_materials (material);
create index if not exists idx_timeseries_batch on timeseries_readings (batch_number);

alter table operation_materials enable row level security;
alter table timeseries_readings enable row level security;

create policy "allow all for anon - operation_materials" on operation_materials
    for all using (true) with check (true);

create policy "allow all for anon - timeseries_readings" on timeseries_readings
    for all using (true) with check (true);
