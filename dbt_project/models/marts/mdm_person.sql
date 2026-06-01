{{ config(materialized='table') }}

/*
    Mart (MDM Layer 5): the canonical public person table — one row per usable
    person occurrence from the conformed pool. Replaces the retired
    contacts_search_ai model (the old contacts_search / civic_person feed).

    Grain TODAY is the source occurrence (PK person_uid), filtered to real people
    (entity_type = 'person' and the is_probable_person quality flag), so org-shaped
    owner/contributor names and UI-chrome strings stay out. This mirrors the grain
    of the existing person bridges (mdm_bridge_person_address, mdm_person_source_link),
    which key on the same person_uid.

    Golden-record dedup (one row per RESOLVED person) lands later the same way it
    did for organizations: insert an int_persons__clustered model between
    int_persons__unioned and this mart and swap the upstream ref + add a
    master_person_id. Until that exists there is no person cluster to survivor-pick
    from, so we serve the conformed occurrences directly.

    Serve person search/browse from here; tie to addresses via
    mdm_bridge_person_address and to the source page via mdm_person_source_link.
*/

-- person_uid (md5 of source_system|source_pk) is not unique in the pool: one
-- source key can emit several name-occurrence rows. Collapse to the most-complete
-- occurrence per key so person_uid is a true PK.
select distinct on (person_uid)
    person_uid,
    -- Splink resolution (from int_persons__clustered): the canonical person this
    -- occurrence resolves to, and how strongly it merged. master_person_id falls
    -- back to person_uid (singleton) until the linker is re-run.
    master_person_id,
    match_confidence,
    -- Flag weak matches in place (the record stays served, FKs from the bridges
    -- stay valid) so a reviewer can confirm them via pending_mdm_person.
    -- 'needs_review' = predicted as a candidate but below the 0.99 auto-merge bar.
    case
        when match_confidence is not null and match_confidence < 0.99
            then 'needs_review'
        else 'auto_accepted'
    end                                         as review_status,
    source_system,
    source_pk,
    full_name,
    name_norm,
    given_name_norm,
    family_name_norm,
    name_phonetic_first,
    name_phonetic_last,
    email,
    phone,
    city_norm,
    state_code,
    zip5
from {{ ref('int_persons__clustered') }}
where entity_type = 'person'
  and is_probable_person
order by
    person_uid,
    (email is not null) desc,
    (phone is not null) desc,
    (given_name_norm is not null and family_name_norm is not null) desc,
    (city_norm is not null) desc,
    full_name
