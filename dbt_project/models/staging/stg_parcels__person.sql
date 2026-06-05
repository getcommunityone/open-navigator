{{ config(materialized='view') }}

/*
    Staging (MDM person conformance): parcel owners from bronze_addresses.owner_name,
    mapped onto the shared person contract. Pairs with stg_parcels__address (same
    source rows, the address side).

    owner_name is "SURNAME FIRSTNAME" with NO comma. normalize_person_name only
    flips comma-delimited "Last, First", so here we flip person names explicitly by
    moving the first token (surname) to the end -> "GIVEN SURNAME". This fixes the
    display name (full_name), the first/last phonetic keys, AND makes parcels
    consistent with the comma-flipped contributor names for cross-source matching.
    Organizations (City Of X, ... LLC) keep their order and route to
    stg_parcels__org — this model never emits them. Surname/given are also split
    out from the original (surname = first token).

    --------------------------------------------------------------------------
    JOINT-OWNER SPLITTING (parcel-LOCAL; do not lift into the shared feeders)
    --------------------------------------------------------------------------
    A single owner_name field often holds MULTIPLE people joined by `&`, `;`, or
    the standalone word ` AND ` (e.g. "SMITH JOHN & JANE", "TUNNELL WANDA J &
    MORRIS LEWIS TUNNELL JR"). Left intact these explode to 6+ tokens and are
    dropped by the shared is_probable_person gate (2-5 token, digit-free) in
    int_persons__unioned, so the co-owners never become searchable persons
    (~114k nationwide, ~3.6k in Tuscaloosa AL).

    We split here so EACH co-owner becomes its own person occurrence:

      1. SPLIT owner_name on the joint-owner separators `&`, `;`, and whole-word
         ` AND ` (case-insensitive). `\sand\s` is whole-word so it never splits
         surnames like "ANDERSON". regexp_split_to_table ... WITH ORDINALITY gives
         one row per segment plus its 1-based owner_index.

      2. SURNAME INHERITANCE (names are surname-first). The PRIMARY (index 1)
         segment's leading token is the shared surname. For each LATER segment we
         decide whether it carries its own surname or only given name(s), using a
         token count taken AFTER stripping generational suffixes (jr/sr/ii/iii/iv)
         and single-letter middle initials so they do not inflate the count:
           - cleaned segment has >= 2 meaningful tokens  -> assume it is a full
             standalone name already in surname-first form; keep as-is.
             e.g. "MORRIS LEWIS TUNNELL JR" / "SUSAN WATKINS" stand alone.
           - cleaned segment has exactly 1 meaningful token -> given-name-only
             co-owner; PREPEND the primary surname -> "SURNAME GIVEN"
             (surname-first), matching the dataset format.
             e.g. "SMITH JOHN & JANE" -> "SMITH JOHN" + "SMITH JANE".
         ASSUMPTIONS (documented false-negatives we accept rather than over-fit):
           - a later segment of two GIVEN names with no surname ("... & MARY ANN")
             is treated as standalone and will not inherit the surname; rare.
           - the primary segment's first token is always taken as the surname,
             per the dataset's surname-first convention.

      3. DROP degenerate / non-person segments: blank, "ET AL"/"ETAL",
         "TRUSTEE(S)", "%INT" and fractional/percentage interest fragments
         ("1/3 INT", "50% INT"), bare "OR", life-estate noise, and any segment
         that itself contains an organization keyword (so an org name buried in a
         later segment, e.g. "... & DEVELOPMENT CO", is not coerced into a person).

      4. DISTINCT STABLE source_pk: the original parcel id plus the owner_index
         suffix ("<id>#<n>"). Two co-owners on one parcel therefore get distinct
         person_uid (md5(source_system|source_pk)) and are NOT deduped into one.

    name_norm / given / family / phonetic are re-derived from the SPLIT (and
    surname-inherited) name, so each occurrence is re-tokenized and the legitimate
    2-5 token, digit-free co-owners now pass the downstream is_probable_person
    gate unchanged. The shared gate and the other five feeders are untouched.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2; Watch-outs: name order).
    Template: source -> classified -> segments -> resolved -> flipped -> parsed -> filtered.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_addresses') }}
),

classified as (
    select
        *,
        {{ classify_name_entity_type('owner_name') }} as entity_type
    from source
    -- person routing is whole-string: org-shaped owners go to stg_parcels__org and
    -- are never split here.
    where {{ classify_name_entity_type('owner_name') }} = 'person'
),

-- 1. one row per co-owner segment, with its 1-based owner_index.
segments as (
    select
        c.id,
        c.owner_name,
        c.city,
        c.state_abbr,
        c.state_code,
        c.postal_code,
        btrim(seg.val)  as segment_raw,
        seg.idx         as owner_index
    from classified c,
    lateral regexp_split_to_table(
        btrim(c.owner_name),
        '(?i)\s*(?:&|;|\sand\s)\s*'
    ) with ordinality as seg(val, idx)
),

-- primary surname = first token of the index-1 segment, per parcel id.
primary_surname as (
    select
        id,
        nullif(split_part(segment_raw, ' ', 1), '') as surname
    from segments
    where owner_index = 1
),

cleaned as (
    select
        s.*,
        ps.surname as primary_surname,
        -- token count AFTER removing generational suffixes and single-letter
        -- middle initials, so "FOSTER LEE JR" counts as 2 and "WANDA J" as 1.
        coalesce(
            array_length(
                string_to_array(
                    btrim(
                        regexp_replace(
                            regexp_replace(
                                s.segment_raw,
                                '(?i)\y(jr|sr|ii|iii|iv|v|trustee|trustees)\y', '', 'g'
                            ),
                            '\y[a-zA-Z]\y', '', 'g'   -- drop lone middle initials
                        )
                    ),
                    ' '
                ),
                1
            ),
            0
        ) as meaningful_token_count
    from segments s
    left join primary_surname ps on ps.id = s.id
),

-- 3. drop degenerate / non-person segments.
kept as (
    select * from cleaned
    where segment_raw is not null
      and segment_raw <> ''
      -- non-person noise fragments
      and segment_raw !~* '\yet ?al\y'
      and segment_raw !~* '\y(trustee|trustees)\y'
      and segment_raw !~* '%|\yint\y|\d+\s*/\s*\d+|life est'
      and lower(segment_raw) not in ('or', 'and', 'etux', 'et ux', 'etvir', 'et vir')
      -- an org keyword buried in a later segment: route OUT of the person pool.
      and {{ classify_name_entity_type('segment_raw') }} = 'person'
      -- must retain at least one meaningful name token after suffix stripping
      and meaningful_token_count >= 1
),

-- 2. surname inheritance: 1-token later segments inherit the primary surname.
resolved as (
    select
        id,
        owner_name,                                   -- original (for raw_name)
        owner_index,
        city,
        state_abbr,
        state_code,
        postal_code,
        case
            when owner_index = 1 then segment_raw      -- primary: keep as-is
            when meaningful_token_count >= 2 then segment_raw  -- standalone full name
            when primary_surname is not null           -- given-only: inherit surname
                then primary_surname || ' ' || segment_raw
            else segment_raw
        end as owner_segment
    from kept
),

flipped as (
    select
        *,
        -- move first token (surname) to the end -> "GIVEN SURNAME"
        regexp_replace(btrim(owner_segment), '^([^ ]+) +(.+)$', '\2 \1')        as owner_name_display,
        nullif(lower(unaccent(split_part(btrim(owner_segment), ' ', 1))), '')   as family_norm,
        nullif(lower(unaccent(regexp_replace(btrim(owner_segment), '^[^ ]+ +', ''))), '') as given_norm
    from resolved
),

parsed as (
    select
        'bronze_addresses'                                     as source_system,
        -- 4. DISTINCT stable pk per co-owner: "<parcel_id>#<owner_index>"
        (id::text || '#' || owner_index::text)                 as source_pk,
        'person'::text                                         as entity_type,

        owner_name                                             as raw_name,  -- original (surname-first, full joint string)
        {{ normalize_person_name('owner_name_display') }}      as name_norm,
        given_norm                                             as given_name_norm,
        family_norm                                            as family_name_norm,
        {{ name_phonetic_first('owner_name_display') }}        as name_phonetic_first,
        {{ name_phonetic_key('owner_name_display') }}          as name_phonetic_last,

        null::text                                             as email,
        null::text                                             as phone,
        null::text                                             as ein,
        null::text                                             as external_id,

        nullif(lower(trim(unaccent(city))), '')                as city_norm,
        upper(left(trim(coalesce(state_abbr, state_code)), 2)) as state_code,
        {{ zip5('postal_code') }}                              as zip5
    from flipped
),

filtered as (
    select * from parsed where name_norm is not null
),

final as (
    select * from filtered
)

select * from final
