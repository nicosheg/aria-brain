-- Pin the trigger function's search path to avoid object-shadowing risks.
-- The function only assigns lower(NEW.email), so pg_catalog builtins remain sufficient.
ALTER FUNCTION public.lowercase_email() SET search_path = ''; 
