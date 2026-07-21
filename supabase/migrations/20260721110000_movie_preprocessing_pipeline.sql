-- Durable source-of-truth for the movie preprocessing pipeline. Video blobs live
-- in object storage; these records deliberately retain only their storage keys.
create table if not exists movies (
  id uuid primary key,
  content_hash text not null unique,
  title text,
  original_filename text not null,
  mime_type text not null,
  source_storage_key text not null,
  status text not null check (status in ('uploaded', 'processing', 'completed', 'partial', 'failed')),
  model_versions jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists movie_chunks (
  id uuid primary key,
  movie_id uuid not null references movies(id) on delete cascade,
  sequence_number integer not null check (sequence_number >= 0),
  start_seconds double precision not null check (start_seconds >= 0),
  end_seconds double precision not null check (end_seconds > start_seconds),
  duration_seconds double precision not null check (duration_seconds > 0),
  content_hash text not null,
  storage_key text not null,
  status text not null check (status in ('pending', 'processing', 'completed', 'failed')),
  model_versions jsonb not null default '{}'::jsonb,
  gemini_visual_json jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (movie_id, sequence_number)
);

create table if not exists movie_scenes (
  id uuid primary key,
  movie_id uuid not null references movies(id) on delete cascade,
  chunk_id uuid not null unique references movie_chunks(id) on delete cascade,
  canonical_json jsonb not null,
  confidence text not null,
  model_versions jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists movie_search_context (
  id uuid primary key,
  movie_id uuid not null references movies(id) on delete cascade,
  chunk_id uuid not null references movie_chunks(id) on delete cascade,
  entity text not null,
  entity_kind text not null,
  query text not null,
  results jsonb not null default '[]'::jsonb,
  confidence double precision not null default 0 check (confidence >= 0 and confidence <= 1),
  created_at timestamptz not null default now()
);

create table if not exists movie_processing_attempts (
  id uuid primary key,
  movie_id uuid not null references movies(id) on delete cascade,
  chunk_id uuid references movie_chunks(id) on delete cascade,
  stage text not null check (stage in ('chunking', 'gemini', 'google_search', 'openai', 'storage')),
  attempt integer not null check (attempt >= 1),
  status text not null check (status in ('started', 'succeeded', 'failed')),
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists movie_chunks_movie_time_idx on movie_chunks (movie_id, start_seconds);
create index if not exists movie_search_context_chunk_idx on movie_search_context (chunk_id);
create index if not exists movie_processing_attempts_movie_idx on movie_processing_attempts (movie_id, created_at desc);
