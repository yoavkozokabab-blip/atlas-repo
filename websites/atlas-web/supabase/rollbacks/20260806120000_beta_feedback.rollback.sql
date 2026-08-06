-- Rollback for 20260806120000_beta_feedback.sql.
--
-- The table is new and additive, so dropping it restores the prior schema
-- exactly. It destroys any feedback already submitted, so export first if the
-- rows matter:
--   select * from public.beta_feedback order by created_at;

drop index if exists public.beta_feedback_created_at_idx;
drop table if exists public.beta_feedback;
