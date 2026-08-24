-- pg_net is required by pg_cron to invoke the document workers asynchronously.
create extension if not exists pg_net;
