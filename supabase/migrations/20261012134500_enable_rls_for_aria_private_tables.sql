-- ARIA private data tables are accessed by the server-side Postgres connection.
-- Do not add broad browser-facing policies for agent state or connection credentials.
-- The production server currently connects as the postgres role (BYPASSRLS); direct server
-- queries continue to work while exposed PostgREST access is blocked without explicit policies.
ALTER TABLE public.aria_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.aria_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.aria_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.aria_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.aria_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.aria_feedback ENABLE ROW LEVEL SECURITY;
