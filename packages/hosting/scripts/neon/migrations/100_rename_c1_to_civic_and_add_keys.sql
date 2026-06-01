-- Migration: rename the ``c1_*`` ("communityone") civic-core entity family to
-- ``civic_*`` and add the primary/foreign keys that were missing.
--
-- Why
-- ---
-- The ``c1_`` prefix (introduced in migration 048) stood for "communityone" and
-- was cryptic: it reads like a versioned/internal namespace rather than what the
-- tables actually are -- the canonical OCD/Popolo *civic* entities (jurisdictions,
-- organizations, people, events, elections, candidacies, ballot measures, votes).
-- ``civic_*`` describes the domain accurately. No table here is a legislative
-- "bill"; the singular ``bill_id`` column on civic_eventrelatedentity is an OCD
-- back-reference, not a table in this family.
--
-- Every table already had a PRIMARY KEY (mostly on ``id``; civic_event /
-- civic_jurisdiction / civic_person / civic_organization on the integer
-- ``legacy_id``). This migration keeps those PKs, renames their constraints for
-- consistency, and adds the FOREIGN KEYS that the schema implies.
--
-- Foreign keys -- what is enforced and what is NOT (data-validated 2026-05-31)
-- --------------------------------------------------------------------------
-- The varchar ``*_id`` columns were designed to reference each parent's varchar
-- ``id``. Live data only supports a subset of those as enforced constraints:
--
--   * civic_event.id and civic_jurisdiction.id are fully non-null + unique, so we
--     promote them to real UNIQUE constraints (the pre-existing unique indexes are
--     PARTIAL -- ``WHERE id IS NOT NULL`` -- and a partial index cannot be an FK
--     target). The redundant partial indexes are dropped.
--   * Within the elections domain (division/election/contest/candidacy/measure +
--     *source) and the event-child tables, every reference whose target keyspace
--     matches is added VALID. Two columns (civic_candidatecontest.election_id and
--     civic_candidacy.election_id) resolve except for 4 legacy dangling rows each,
--     so they are added NOT VALID -- enforced going forward, the historical
--     orphans skipped until reconciled (then VALIDATE CONSTRAINT).
--
-- The following relationships are INTENTIONALLY left without an FK because the
-- live data cannot satisfy one; each is documented via COMMENT so the gap is
-- greppable and can be closed once the upstream ids are reconciled:
--
--   * -> civic_person(id): civic_person.id has NULLs and duplicates (149 null /
--     2463 distinct of 2612) so it is not a valid unique FK target. Affects
--     civic_candidacy.person_id, civic_eventparticipant.person_id,
--     civic_eventrelatedentity.person_id, civic_personvote.voter_id and the
--     civic_person* child tables (person_id).
--   * -> civic_organization(id): civic_organization.id is 100% NULL (the OCD id was
--     never assigned; PK is legacy_id), so it cannot be an FK target at all.
--     Affects civic_eventparticipant.organization_id,
--     civic_eventrelatedentity.organization_id, civic_organization.parent_id.
--   * civic_event.jurisdiction_id (slug keyspace, e.g. 'adams_18001') and
--     civic_person.current_jurisdiction_id (OCD-string keyspace, e.g.
--     'ocd-jurisdiction/country:us/...') do NOT match civic_jurisdiction.id
--     (stringified legacy_id, e.g. '5157') -- 100% orphaned. These three
--     populated columns reference three different keyspaces and need an upstream
--     remapping before an FK can be enforced.
--   * civic_eventrelatedentity.bill_id / vote_event_id and
--     civic_personvote.vote_event_id have no parent table in this family.
--
-- Reversible? Yes (rename-only + additive constraints). A down-migration would
-- rename civic_* -> c1_*, drop the new FKs/UNIQUE constraints, and restore the
-- partial unique indexes.
--
-- Apply:
--   ./packages/hosting/scripts/neon/psql_resolved.sh -f packages/hosting/scripts/neon/migrations/100_rename_c1_to_civic_and_add_keys.sql

BEGIN;

-- =====================================================================
-- 1. Rename PRIMARY KEY / existing FOREIGN KEY constraints (pre-table-rename,
--    so they still reference the c1_ table names).
-- =====================================================================
ALTER TABLE public.c1_ballotmeasure       RENAME CONSTRAINT c1_ballotmeasure_pkey       TO civic_ballotmeasure_pkey;
ALTER TABLE public.c1_ballotmeasuresource RENAME CONSTRAINT c1_ballotmeasuresource_pkey TO civic_ballotmeasuresource_pkey;
ALTER TABLE public.c1_candidacy           RENAME CONSTRAINT c1_candidacy_pkey           TO civic_candidacy_pkey;
ALTER TABLE public.c1_candidatecontest    RENAME CONSTRAINT c1_candidatecontest_pkey    TO civic_candidatecontest_pkey;
ALTER TABLE public.c1_division            RENAME CONSTRAINT c1_division_pkey            TO civic_division_pkey;
ALTER TABLE public.c1_election            RENAME CONSTRAINT c1_election_pkey            TO civic_election_pkey;
ALTER TABLE public.c1_electionsource      RENAME CONSTRAINT c1_electionsource_pkey      TO civic_electionsource_pkey;
ALTER TABLE public.c1_event               RENAME CONSTRAINT events_search_pkey          TO civic_event_pkey;
ALTER TABLE public.c1_eventagendaitem     RENAME CONSTRAINT c1_eventagendaitem_pkey     TO civic_eventagendaitem_pkey;
ALTER TABLE public.c1_eventagendamedia    RENAME CONSTRAINT c1_eventagendamedia_pkey    TO civic_eventagendamedia_pkey;
ALTER TABLE public.c1_eventagendamedia    RENAME CONSTRAINT c1_eventagendamedia_agenda_item_id_fkey TO civic_eventagendamedia_agenda_item_id_fkey;
ALTER TABLE public.c1_eventdocument       RENAME CONSTRAINT c1_eventdocument_pkey       TO civic_eventdocument_pkey;
ALTER TABLE public.c1_eventmedia          RENAME CONSTRAINT c1_eventmedia_pkey          TO civic_eventmedia_pkey;
ALTER TABLE public.c1_eventparticipant    RENAME CONSTRAINT c1_eventparticipant_pkey    TO civic_eventparticipant_pkey;
ALTER TABLE public.c1_eventrelatedentity  RENAME CONSTRAINT c1_eventrelatedentity_pkey  TO civic_eventrelatedentity_pkey;
ALTER TABLE public.c1_eventrelatedentity  RENAME CONSTRAINT c1_eventrelatedentity_agenda_item_id_fkey TO civic_eventrelatedentity_agenda_item_id_fkey;
ALTER TABLE public.c1_jurisdiction        RENAME CONSTRAINT jurisdictions_search_pkey   TO civic_jurisdiction_pkey;
ALTER TABLE public.c1_person              RENAME CONSTRAINT c1_person_pkey              TO civic_person_pkey;
ALTER TABLE public.c1_personidentifier    RENAME CONSTRAINT c1_personidentifier_pkey    TO civic_personidentifier_pkey;
ALTER TABLE public.c1_personlink          RENAME CONSTRAINT c1_personlink_pkey          TO civic_personlink_pkey;
ALTER TABLE public.c1_personname          RENAME CONSTRAINT c1_personname_pkey          TO civic_personname_pkey;
ALTER TABLE public.c1_personsource        RENAME CONSTRAINT c1_personsource_pkey        TO civic_personsource_pkey;
ALTER TABLE public.c1_personvote          RENAME CONSTRAINT c1_personvote_pkey          TO civic_personvote_pkey;

-- =====================================================================
-- 2. Rename the c1_-prefixed indexes (index-name based; order independent).
-- =====================================================================
ALTER INDEX public.idx_c1_person_ein                     RENAME TO idx_civic_person_ein;
ALTER INDEX public.idx_c1_person_name_search             RENAME TO idx_civic_person_name_search;
ALTER INDEX public.idx_c1_person_org_name_search         RENAME TO idx_civic_person_org_name_search;
ALTER INDEX public.idx_c1_person_role                    RENAME TO idx_civic_person_role;
ALTER INDEX public.idx_c1_person_state                   RENAME TO idx_civic_person_state;
ALTER INDEX public.ix_c1_ballotmeasure_election_id       RENAME TO ix_civic_ballotmeasure_election_id;
ALTER INDEX public.ix_c1_ballotmeasure_jurisdiction_id   RENAME TO ix_civic_ballotmeasure_jurisdiction_id;
ALTER INDEX public.ix_c1_ballotmeasure_state_code        RENAME TO ix_civic_ballotmeasure_state_code;
ALTER INDEX public.ix_c1_candidacy_contest_id            RENAME TO ix_civic_candidacy_contest_id;
ALTER INDEX public.ix_c1_candidacy_election_id           RENAME TO ix_civic_candidacy_election_id;
ALTER INDEX public.ix_c1_candidacy_jurisdiction_id       RENAME TO ix_civic_candidacy_jurisdiction_id;
ALTER INDEX public.ix_c1_candidacy_state_code            RENAME TO ix_civic_candidacy_state_code;
ALTER INDEX public.ix_c1_candidatecontest_election_id    RENAME TO ix_civic_candidatecontest_election_id;
ALTER INDEX public.ix_c1_candidatecontest_jurisdiction_id RENAME TO ix_civic_candidatecontest_jurisdiction_id;
ALTER INDEX public.ix_c1_candidatecontest_state_code     RENAME TO ix_civic_candidatecontest_state_code;
ALTER INDEX public.ix_c1_division_jurisdiction_id        RENAME TO ix_civic_division_jurisdiction_id;
ALTER INDEX public.ix_c1_division_parent_id              RENAME TO ix_civic_division_parent_id;
ALTER INDEX public.ix_c1_division_state_code             RENAME TO ix_civic_division_state_code;
ALTER INDEX public.ix_c1_election_division_id            RENAME TO ix_civic_election_division_id;
ALTER INDEX public.ix_c1_election_election_date          RENAME TO ix_civic_election_election_date;
ALTER INDEX public.ix_c1_election_jurisdiction_id        RENAME TO ix_civic_election_jurisdiction_id;
ALTER INDEX public.ix_c1_election_state_code             RENAME TO ix_civic_election_state_code;
ALTER INDEX public.ix_c1_event_dedupe_key_unique         RENAME TO ix_civic_event_dedupe_key_unique;
ALTER INDEX public.ix_c1_event_id_unique                 RENAME TO ix_civic_event_id_unique;
ALTER INDEX public.ix_c1_eventagendaitem_event_id        RENAME TO ix_civic_eventagendaitem_event_id;
ALTER INDEX public.ix_c1_eventagendaitem_order           RENAME TO ix_civic_eventagendaitem_order;
ALTER INDEX public.ix_c1_eventagendamedia_agenda_item_id RENAME TO ix_civic_eventagendamedia_agenda_item_id;
ALTER INDEX public.ix_c1_eventdocument_classification    RENAME TO ix_civic_eventdocument_classification;
ALTER INDEX public.ix_c1_eventdocument_event_id          RENAME TO ix_civic_eventdocument_event_id;
ALTER INDEX public.ix_c1_eventmedia_event_id             RENAME TO ix_civic_eventmedia_event_id;
ALTER INDEX public.ix_c1_eventparticipant_event_id       RENAME TO ix_civic_eventparticipant_event_id;
ALTER INDEX public.ix_c1_eventparticipant_organization_id RENAME TO ix_civic_eventparticipant_organization_id;
ALTER INDEX public.ix_c1_eventparticipant_person_id      RENAME TO ix_civic_eventparticipant_person_id;
ALTER INDEX public.ix_c1_eventrelatedentity_agenda_item_id RENAME TO ix_civic_eventrelatedentity_agenda_item_id;
ALTER INDEX public.ix_c1_eventrelatedentity_bill_id      RENAME TO ix_civic_eventrelatedentity_bill_id;
ALTER INDEX public.ix_c1_eventrelatedentity_organization_id RENAME TO ix_civic_eventrelatedentity_organization_id;
ALTER INDEX public.ix_c1_eventrelatedentity_person_id    RENAME TO ix_civic_eventrelatedentity_person_id;
ALTER INDEX public.ix_c1_organization_classification     RENAME TO ix_civic_organization_classification;
ALTER INDEX public.ix_c1_organization_ein                RENAME TO ix_civic_organization_ein;
ALTER INDEX public.ix_c1_organization_ein_unique         RENAME TO ix_civic_organization_ein_unique;
ALTER INDEX public.ix_c1_organization_legacy_id          RENAME TO ix_civic_organization_legacy_id;
ALTER INDEX public.ix_c1_organization_name               RENAME TO ix_civic_organization_name;
ALTER INDEX public.ix_c1_organization_slug               RENAME TO ix_civic_organization_slug;
ALTER INDEX public.ix_c1_organization_source             RENAME TO ix_civic_organization_source;
ALTER INDEX public.ix_c1_organization_state              RENAME TO ix_civic_organization_state;
ALTER INDEX public.ix_c1_personidentifier_person_id      RENAME TO ix_civic_personidentifier_person_id;
ALTER INDEX public.ix_c1_personidentifier_scheme_identifier RENAME TO ix_civic_personidentifier_scheme_identifier;
ALTER INDEX public.ix_c1_personlink_person_id            RENAME TO ix_civic_personlink_person_id;
ALTER INDEX public.ix_c1_personname_person_id            RENAME TO ix_civic_personname_person_id;
ALTER INDEX public.ix_c1_personsource_person_id          RENAME TO ix_civic_personsource_person_id;
ALTER INDEX public.ix_c1_personvote_vote_event_id        RENAME TO ix_civic_personvote_vote_event_id;
ALTER INDEX public.ix_c1_personvote_voter_id             RENAME TO ix_civic_personvote_voter_id;
ALTER INDEX public.ux_c1_ballotmeasure_dedupe_key        RENAME TO ux_civic_ballotmeasure_dedupe_key;
ALTER INDEX public.ux_c1_ballotmeasuresource_unique      RENAME TO ux_civic_ballotmeasuresource_unique;
ALTER INDEX public.ux_c1_candidacy_dedupe_key            RENAME TO ux_civic_candidacy_dedupe_key;
ALTER INDEX public.ux_c1_candidatecontest_dedupe_key     RENAME TO ux_civic_candidatecontest_dedupe_key;
ALTER INDEX public.ux_c1_election_dedupe_key             RENAME TO ux_civic_election_dedupe_key;
ALTER INDEX public.ux_c1_electionsource_unique           RENAME TO ux_civic_electionsource_unique;

-- =====================================================================
-- 3. Rename the tables c1_* -> civic_*.
--    FKs, indexes, the events_recent view, and any triggers follow the table
--    by OID -- no further action needed for those dependents.
-- =====================================================================
ALTER TABLE public.c1_ballotmeasure       RENAME TO civic_ballotmeasure;
ALTER TABLE public.c1_ballotmeasuresource RENAME TO civic_ballotmeasuresource;
ALTER TABLE public.c1_candidacy           RENAME TO civic_candidacy;
ALTER TABLE public.c1_candidatecontest    RENAME TO civic_candidatecontest;
ALTER TABLE public.c1_division            RENAME TO civic_division;
ALTER TABLE public.c1_election            RENAME TO civic_election;
ALTER TABLE public.c1_electionsource      RENAME TO civic_electionsource;
ALTER TABLE public.c1_event               RENAME TO civic_event;
ALTER TABLE public.c1_eventagendaitem     RENAME TO civic_eventagendaitem;
ALTER TABLE public.c1_eventagendamedia    RENAME TO civic_eventagendamedia;
ALTER TABLE public.c1_eventdocument       RENAME TO civic_eventdocument;
ALTER TABLE public.c1_eventmedia          RENAME TO civic_eventmedia;
ALTER TABLE public.c1_eventparticipant    RENAME TO civic_eventparticipant;
ALTER TABLE public.c1_eventrelatedentity  RENAME TO civic_eventrelatedentity;
ALTER TABLE public.c1_jurisdiction        RENAME TO civic_jurisdiction;
ALTER TABLE public.c1_organization        RENAME TO civic_organization;
ALTER TABLE public.c1_person              RENAME TO civic_person;
ALTER TABLE public.c1_personidentifier    RENAME TO civic_personidentifier;
ALTER TABLE public.c1_personlink          RENAME TO civic_personlink;
ALTER TABLE public.c1_personname          RENAME TO civic_personname;
ALTER TABLE public.c1_personsource        RENAME TO civic_personsource;
ALTER TABLE public.c1_personvote          RENAME TO civic_personvote;

-- =====================================================================
-- 4. Promote civic_event.id / civic_jurisdiction.id to full UNIQUE constraints
--    so they can serve as FK targets, then drop the now-redundant PARTIAL
--    unique indexes. (id is fully non-null + unique on both tables.)
-- =====================================================================
ALTER TABLE public.civic_event        ADD CONSTRAINT civic_event_id_key        UNIQUE (id);
DROP INDEX public.ix_civic_event_id_unique;
ALTER TABLE public.civic_jurisdiction ADD CONSTRAINT civic_jurisdiction_id_key UNIQUE (id);
DROP INDEX public.uq_jurisdiction_jurisdiction_id;

-- =====================================================================
-- 5. Add foreign keys (only those the live data can satisfy -- see header).
--    Composition / child-of relationships cascade on parent delete; lookup
--    references use the default NO ACTION. The elections-domain
--    ``*.jurisdiction_id`` columns are NOT given an FK here: every value is in a
--    slug keyspace (e.g. 'huachuca_city_0434120') that does not match
--    civic_jurisdiction.id -- see the COMMENTs in section 6.
-- =====================================================================

-- Elections domain (division / election / contest / measure references).
ALTER TABLE public.civic_division
  ADD CONSTRAINT civic_division_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.civic_division(id);

ALTER TABLE public.civic_election
  ADD CONSTRAINT civic_election_division_id_fkey FOREIGN KEY (division_id) REFERENCES public.civic_division(id);

ALTER TABLE public.civic_electionsource
  ADD CONSTRAINT civic_electionsource_election_id_fkey FOREIGN KEY (election_id) REFERENCES public.civic_election(id) ON DELETE CASCADE;

ALTER TABLE public.civic_candidacy
  ADD CONSTRAINT civic_candidacy_contest_id_fkey FOREIGN KEY (contest_id) REFERENCES public.civic_candidatecontest(id);

ALTER TABLE public.civic_ballotmeasure
  ADD CONSTRAINT civic_ballotmeasure_election_id_fkey FOREIGN KEY (election_id) REFERENCES public.civic_election(id);

ALTER TABLE public.civic_ballotmeasuresource
  ADD CONSTRAINT civic_ballotmeasuresource_ballotmeasure_id_fkey FOREIGN KEY (ballotmeasure_id) REFERENCES public.civic_ballotmeasure(id) ON DELETE CASCADE;

-- election_id is a real reference, but 4 legacy rows in each table dangle. Add
-- NOT VALID so the constraint is enforced for new/updated rows without failing
-- on the historical orphans (run VALIDATE CONSTRAINT after the orphans are fixed).
ALTER TABLE public.civic_candidatecontest
  ADD CONSTRAINT civic_candidatecontest_election_id_fkey FOREIGN KEY (election_id) REFERENCES public.civic_election(id) NOT VALID;

ALTER TABLE public.civic_candidacy
  ADD CONSTRAINT civic_candidacy_election_id_fkey FOREIGN KEY (election_id) REFERENCES public.civic_election(id) NOT VALID;

-- Jurisdiction / organization references (both currently all-NULL -> vacuously valid).
ALTER TABLE public.civic_jurisdiction
  ADD CONSTRAINT civic_jurisdiction_division_id_fkey FOREIGN KEY (division_id) REFERENCES public.civic_division(id);

ALTER TABLE public.civic_organization
  ADD CONSTRAINT civic_organization_jurisdiction_id_fkey FOREIGN KEY (jurisdiction_id) REFERENCES public.civic_jurisdiction(id);

-- Event-child composition (cascade on event delete)
ALTER TABLE public.civic_eventagendaitem
  ADD CONSTRAINT civic_eventagendaitem_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.civic_event(id) ON DELETE CASCADE;

ALTER TABLE public.civic_eventdocument
  ADD CONSTRAINT civic_eventdocument_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.civic_event(id) ON DELETE CASCADE;

ALTER TABLE public.civic_eventmedia
  ADD CONSTRAINT civic_eventmedia_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.civic_event(id) ON DELETE CASCADE;

ALTER TABLE public.civic_eventparticipant
  ADD CONSTRAINT civic_eventparticipant_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.civic_event(id) ON DELETE CASCADE;

-- =====================================================================
-- 6. Document the relationships left WITHOUT an FK (data cannot satisfy them).
-- =====================================================================
-- The *.jurisdiction_id columns below are all in a slug keyspace
-- (e.g. 'huachuca_city_0434120') and are 100% orphaned against
-- civic_jurisdiction.id (stringified legacy_id, e.g. '5157'). They need an
-- upstream remapping before an FK can be enforced.
COMMENT ON COLUMN public.civic_division.jurisdiction_id IS
  '[no-fk] slug keyspace; 100% orphaned against civic_jurisdiction.id. Needs upstream remapping.';
COMMENT ON COLUMN public.civic_election.jurisdiction_id IS
  '[no-fk] slug keyspace; 100% orphaned against civic_jurisdiction.id. Needs upstream remapping.';
COMMENT ON COLUMN public.civic_candidatecontest.jurisdiction_id IS
  '[no-fk] slug keyspace; 100% orphaned against civic_jurisdiction.id. Needs upstream remapping.';
COMMENT ON COLUMN public.civic_candidacy.jurisdiction_id IS
  '[no-fk] slug keyspace; 100% orphaned against civic_jurisdiction.id. Needs upstream remapping.';
COMMENT ON COLUMN public.civic_ballotmeasure.jurisdiction_id IS
  '[no-fk] slug keyspace; 100% orphaned against civic_jurisdiction.id. Needs upstream remapping.';
COMMENT ON COLUMN public.civic_event.jurisdiction_id IS
  '[no-fk] slug keyspace (e.g. adams_18001); does not match civic_jurisdiction.id (stringified legacy_id). Needs upstream remapping before an FK can be enforced.';
COMMENT ON COLUMN public.civic_person.current_jurisdiction_id IS
  '[no-fk] OCD-string keyspace (ocd-jurisdiction/...); does not match civic_jurisdiction.id. Needs upstream remapping.';
COMMENT ON COLUMN public.civic_organization.parent_id IS
  '[no-fk] target civic_organization.id is 100% NULL (OCD id never assigned; PK is legacy_id).';
COMMENT ON COLUMN public.civic_candidacy.person_id IS
  '[no-fk] target civic_person.id is not unique (has NULLs + duplicates).';
COMMENT ON COLUMN public.civic_eventparticipant.person_id IS
  '[no-fk] target civic_person.id is not unique; civic_eventparticipant.organization_id target civic_organization.id is all-NULL.';
COMMENT ON COLUMN public.civic_eventrelatedentity.person_id IS
  '[no-fk] target civic_person.id not unique; organization_id target all-NULL; bill_id / vote_event_id have no parent table in this family.';
COMMENT ON COLUMN public.civic_personvote.voter_id IS
  '[no-fk] target civic_person.id is not unique; vote_event_id has no parent table in this family.';

COMMIT;
