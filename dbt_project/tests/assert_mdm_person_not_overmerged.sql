{{ config(severity='warn', tags=['mdm', 'data_quality']) }}

-- Guards against the mdm_person entity-resolution OVER-MERGE bug recurring.
--
-- master_person_id is meant to identify exactly one real person. When the
-- Splink linker over-merges, a single master_person_id absorbs many unrelated
-- people, which shows up as a high count of DISTINCT full_names under one id.
-- A legitimately-resolved person may carry a couple of spelling variants of
-- their name ("Bob" vs "Robert", typos, punctuation), so a small count is fine;
-- dozens (or hundreds) of distinct names is a bad cluster.
--
-- Threshold N = 5: more than 5 distinct full_names per master_person_id fails.
-- This is deliberately loose to tolerate honest name variation; tighten it once
-- the Splink re-run lands and the over-merge tail collapses.
--
-- SEVERITY = 'warn' on purpose: the data is currently broken (303,473 ids have
-- 2+ distinct names; one blob has 677), so this test WILL flag rows today. We
-- surface it as a WARNING rather than fail the build/CI while the bad data is
-- still live and the linker is about to be re-run. Once the re-run drops the
-- over-merge count to zero, flip severity to 'error' so it hard-fails on
-- regression.

select
    master_person_id,
    count(distinct full_name) as distinct_full_names
from {{ ref('mdm_person') }}
where master_person_id is not null
group by master_person_id
having count(distinct full_name) > 5
