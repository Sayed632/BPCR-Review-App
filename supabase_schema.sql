-- Run this once in Supabase: Project -> SQL Editor -> New Query -> paste -> Run

create table if not exists batches (
    id bigint generated always as identity primary key,
    batch_number text unique not null,
    product_name text not null,
    spec_version text,
    created_at timestamptz default now()
);

create table if not exists operations (
    id bigint generated always as identity primary key,
    batch_number text not null references batches(batch_number) on delete cascade,
    operation_id text not null,
    description text,
    page_no int,
    operator text,
    timestamp_raw text,       -- exactly as extracted/transcribed, unparsed
    qty_used text,            -- raw string; parsed at query time (handles ILLEGIBLE/BLANK)
    material_used text,
    model_used text,
    created_at timestamptz default now(),
    unique (batch_number, operation_id)
);

-- Indexes for the two ALCOA queries we actually run
create index if not exists idx_operations_operator on operations (operator);
create index if not exists idx_operations_material on operations (material_used);
create index if not exists idx_operations_batch on operations (batch_number);

-- Row Level Security: enabled, with a permissive policy for the anon/public key.
-- This is an internal single-user tool, so anon = you. If this ever becomes
-- multi-user or gets a wider audience, tighten these policies (e.g. scope by
-- an authenticated user id) before that happens.
alter table batches enable row level security;
alter table operations enable row level security;

create policy "allow all for anon - batches" on batches
    for all using (true) with check (true);

create policy "allow all for anon - operations" on operations
    for all using (true) with check (true);
