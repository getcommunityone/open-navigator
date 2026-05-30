{{
  config(
    materialized='view',
    tags=['staging', 'persons', 'contacts', 'quality']
  )
}}

/*
Staging view for bronze_persons_scraped (scraped person / contact rows).

Adds name-quality classification and a recovered `name_clean` so downstream
models can filter junk WITHOUT mutating the raw bronze landing table. Nothing is
deleted here (one row in -> one row out); rows are SOFT-FLAGGED via name_quality
/ invalid_reason and the convenience boolean is_usable_person.

name_quality:
  - ok        : looks like a real person name
  - recovered : had a strippable prefix ("Portrait of <name>") that yielded a name
  - missing   : name is null/empty (often still carries a usable email)
  - invalid   : not a person (see invalid_reason)

invalid_reason (only when name_quality = 'invalid'):
  - non_latin       : non-Latin script (Thai/CJK/Cyrillic/Arabic/...) — translate-widget or spam
  - markup_or_file  : HTML/markup, a URL/path, or an image/file name
  - has_digits      : contains a digit or underscore (usernames, dated headings)
  - org_or_place    : an org / place / building, not a person ("City of Rockmart", "City Hall")
  - ui_label        : page chrome / CTA / nav / language switcher ("Get In Touch", "Bill Pay", "German")
  - role_only       : a bare role with no person ("Mayor", "City Clerk", ...)
  - not_capitalized : all-lowercase Latin text — template/markup debris ("end news-entries")
  - sentence        : a paragraph / blurb (too long or too many words)

Source: bronze_persons_scraped (open_navigator.bronze schema)
*/

WITH source AS (
    SELECT * FROM {{ source('bronze', 'bronze_persons_scraped') }}
),

cleaned AS (
    SELECT
        *,
        -- Recover a name from "Portrait/Photo/Headshot/Image/Picture of <name>".
        NULLIF(
            BTRIM(
                REGEXP_REPLACE(
                    name,
                    '^(portrait|photo|headshot|image|picture)\s+of\s+',
                    '', 'i'
                )
            ),
            ''
        ) AS name_destripped,
        -- Normalized probe for anchored label/role matching: strip leading and
        -- trailing non-alphanumerics (zero-width spaces, "+ ", "​", "- ", ":")
        -- and collapse internal whitespace, so chrome like "+ READ MORE" or
        -- "​ Mayor" still matches the ^anchored patterns below. Latin only —
        -- non-Latin scripts are caught earlier and left untouched here.
        BTRIM(
            REGEXP_REPLACE(
                REGEXP_REPLACE(name, '^[^[:alnum:]]+|[^[:alnum:]]+$', '', 'g'),
                '\s+', ' ', 'g'
            )
        ) AS name_probe
    FROM source
),

classified AS (
    SELECT
        *,
        CASE
            WHEN name IS NULL OR BTRIM(name) = '' THEN 'missing'

            -- Non-Latin script (Thai, CJK, Japanese kana, Hangul, Cyrillic,
            -- Arabic, Hebrew). In a US municipal dataset these are translate-
            -- widget text or spam, never an officer's name.
            WHEN name ~ '[ก-๿一-鿿぀-ヿ가-힣Ѐ-ӿ؀-ۿ֐-׿]' THEN 'invalid_non_latin'

            -- HTML / markup / URL-path / image or document file name, logo
            -- alt-text ("AKML Logo white"), or bare image/layout debris
            -- ("Image", "Header Triangle") — these only ever name an asset.
            WHEN name ~ '[<>{}|/\\@]'
                 OR name ~* '\.(png|jpe?g|gif|webp|svg|pdf)\s*$'
                 OR name ~* '\m(logo|header|footer|banner|thumbnail|placeholder|icon)\M'
                 OR name_probe ~* '^image$' THEN 'invalid_markup_or_file'

            -- Contains a digit or underscore: usernames ("admin_CoNS2025"),
            -- dated announcements ("Meeting Time Change 05-Mar-2025"). Real
            -- personal names carry no Arabic numerals or underscores.
            WHEN name ~ '[0-9_]' THEN 'invalid_has_digits'

            -- Org / place / building / governing body, not a person
            -- ("City of Rockmart", "The City of Weaver Alabama", "City Hall",
            -- "City Council", "PVPC Team", "Village Improvement Fund").
            WHEN name_probe ~* '^(the\s+)?(city|town|village|borough|township|county|municipality|district)\s+(of|hall)\M'
                 OR name_probe ~* '\m(city|town|village|county|municipal|board)\s+(hall|council|commission|administration|government|building|board|department|office)\M'
                 OR name_probe ~* '\m(community center|public library|police department|fire department)\M'
                 OR name_probe ~* '\m(team|fund|authority|association|foundation|chamber|committee|coalition|partnership|corporation)$' THEN 'invalid_org_or_place'

            -- Page chrome / call-to-action / nav labels / language switcher.
            -- Matched against name_probe so leading symbols ("+ READ MORE",
            -- "​ Mayor", "Click to ...") don't defeat the ^anchor.
            WHEN name_probe ~* '^(e-?mail|contact|create email|staff directory|directory|departments?|divisions?|visitors?|residents?|business(es)?|government|services|resources|menu|home|search|read more|learn more|click|view profile|for immediate release|covid|log ?in|log ?out|sign ?up|sign ?in|register|subscribe|newsletter|translate|select language|skip to|back to top|share this|print|sitemap|accessibility|privacy policy|terms of use|faqs?|how do i|notify me|quick links|helpful links|related links|online services|open records?|records? request|pay ?(online|bill|your bill)?|bill pay|state of the city|stay informed|stay connected|stay up to date|get in touch|get involved|follow us|view all|see all|more info|read on|in this section|news|announcements?|events?|calendar|agendas?)\M'
                 OR name_probe ~* '\m(contact us|contact info|contact information|contact me|contact by email|email us|email the webmaster|email webmaster|our office|mayor''s office|staff directory|news[- ]entries?)\M'
                 OR name_probe ~* '^(facebook|twitter|instagram|youtube|linkedin|nextdoor|pinterest|flickr|vimeo|tiktok|social media)$'
                 OR name_probe ~* '^(english|spanish|german|french|chinese|simplified chinese|traditional chinese|vietnamese|korean|japanese|tagalog|russian|arabic|portuguese|italian|polish|hindi|haitian creole|hmong|somali|ukrainian|farsi|persian)$' THEN 'invalid_ui_label'

            -- A bare role / title with no personal name, with optional rank or
            -- jurisdiction prefix and an optional trailing qualifier
            -- ("Mayor", "City Clerk", "Executive Assistant", "Council Member -
            -- President", "Mayor Pro Tem").
            WHEN name_probe ~* '^((deputy|assistant|asst\.?|interim|acting|chief|senior|sr\.?|jr\.?|executive|finance|public works|city|town|county|village|borough|township|vice|first|second)\s+)*(mayor|vice[ -]?mayor|commissioner|council ?member|councilman|councilwoman|councilor|councillor|alderman|alderwoman|alderperson|clerk|treasurer|manager|administrator|attorney|prosecutor|engineer|planner|coordinator|secretary|recorder|auditor|assessor|marshal|sheriff|supervisor|superintendent|trustee|director|chair(man|woman|person)?|president|assistant|board of [a-z ]+|department of [a-z ]+|office of [a-z ]+)(\s*[-,]?\s*(pro[ -]?tem|president|vice[ -]?president|chair(man|woman|person)?|secretary|treasurer|elect))?\s*$' THEN 'invalid_role_only'

            -- All-lowercase Latin text — scraped names are Title/UPPER case, so
            -- bare lowercase is template/markup debris ("end news-entries").
            WHEN name ~ '[a-z]' AND name !~ '[A-Z]' THEN 'invalid_not_capitalized'

            -- A sentence / blurb rather than a name
            WHEN LENGTH(name) > 60
                 OR ARRAY_LENGTH(REGEXP_SPLIT_TO_ARRAY(BTRIM(name), '\s+'), 1) > 8 THEN 'invalid_sentence'

            -- A prefix was stripped and a plausible name remained
            WHEN name_destripped IS DISTINCT FROM name AND name_destripped ~ '\S' THEN 'recovered'
            ELSE 'ok'
        END AS name_status
    FROM cleaned
)

SELECT
    -- Identity / grain
    id AS bronze_person_id,
    scrape_batch_id,
    jurisdiction_id,
    state_code,
    ocd_id,

    -- Provenance
    NULLIF(BTRIM(source_page_url), '') AS source_page_url,
    NULLIF(BTRIM(page_classification), '') AS page_classification,
    NULLIF(BTRIM(extraction_method), '') AS extraction_method,
    NULLIF(BTRIM(contact_source), '') AS contact_source,

    -- Raw + cleaned name
    name AS name_raw,
    CASE
        WHEN name_status IN ('ok', 'recovered') THEN
            BTRIM(REGEXP_REPLACE(COALESCE(name_destripped, name), '\s+', ' ', 'g'))
        ELSE NULL
    END AS name_clean,

    -- Quality classification
    CASE WHEN name_status LIKE 'invalid%' THEN 'invalid' ELSE name_status END AS name_quality,
    CASE WHEN name_status LIKE 'invalid_%' THEN SUBSTRING(name_status FROM 9) END AS invalid_reason,
    (name_status IN ('ok', 'recovered')) AS is_usable_person,

    -- Other person/contact fields
    NULLIF(BTRIM(role), '') AS role,
    NULLIF(BTRIM(organization), '') AS organization,
    NULLIF(BTRIM(email), '') AS email,
    NULLIF(BTRIM(phone), '') AS phone,
    NULLIF(BTRIM(mailing_address), '') AS mailing_address,
    NULLIF(BTRIM(profile_url), '') AS profile_url,
    (email IS NOT NULL AND BTRIM(email) <> '') AS has_email,
    contact_details,

    -- Timestamps
    scraped_at,
    loaded_at

FROM classified
