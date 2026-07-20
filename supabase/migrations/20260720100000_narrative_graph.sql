-- Production storage for graphs produced by the offline preprocessing pipeline.
create table if not exists narrative_graphs (
  content_id text primary key,
  content_type text not null check (content_type in ('movie', 'book')),
  title text not null,
  schema_version integer not null default 1,
  graph jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists narrative_graphs_type_idx on narrative_graphs (content_type);
