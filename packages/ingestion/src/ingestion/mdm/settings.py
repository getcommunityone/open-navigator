"""Splink settings for the address and person resolution pools.

Encodes the spec in web_docs/docs/dbt/entity-resolution-mdm.md (Layer 3):
blocking rules run in sequence, ordered comparison levels mixing string metrics
with Double Metaphone, partial-credit ZIP, exact-or-null street number, and
term-frequency adjustments on the high-cardinality fields.

Targets Splink >= 4.0. If a comparison/level class name differs in the installed
version, adjust the imports below — the structure (which fields, which levels) is
the contract, not the exact class names.
"""

from __future__ import annotations

import splink.comparison_level_library as cll
import splink.comparison_library as cl
from splink import SettingsCreator, block_on


def address_settings() -> SettingsCreator:
    """Dedupe int_addresses__unioned. unique id = address_uid."""
    return SettingsCreator(
        link_type="dedupe_only",
        unique_id_column_name="address_uid",
        # Sequential blocking — a typo in one field is still caught by another.
        # All multi-column so pairs don't explode: a bare zip5 / city+state block
        # compares every address in a ZIP (or state) pairwise (quadratic).
        # All ZIP-scoped (or exact-key) so every block is small and bounded.
        # A nationwide street_number+street_name block would lump every "100 main
        # street" together; left out deliberately for the first pass.
        blocking_rules_to_generate_predictions=[
            block_on("address_match_key"),              # exact mailable address (tiny blocks)
            block_on("zip5", "street_name"),            # same street within a ZIP
            block_on("zip5", "street_number"),          # same number within a ZIP
        ],
        comparisons=[
            # Street number: a wrong number is a different house -> exact or null only.
            cl.CustomComparison(
                output_column_name="street_number",
                comparison_levels=[
                    cll.NullLevel("street_number"),
                    cll.ExactMatchLevel("street_number"),
                    cll.ElseLevel(),
                ],
            ),
            # Street name / city: typo-tolerant, term-frequency adjusted.
            # NB: the Postgres backend has no Jaro-Winkler, so we use Levenshtein
            # (edit distance) via fuzzystrmatch. Thresholds are distances, not ratios.
            cl.LevenshteinAtThresholds("street_name", [1, 2]).configure(
                term_frequency_adjustments=True
            ),
            cl.LevenshteinAtThresholds("city_norm", [1]).configure(
                term_frequency_adjustments=True
            ),
            # ZIP: partial credit — exact, then first-3-digits, then mismatch.
            cl.CustomComparison(
                output_column_name="zip5",
                comparison_levels=[
                    cll.NullLevel("zip5"),
                    cll.ExactMatchLevel("zip5"),
                    cll.CustomLevel(
                        "substr(zip5_l, 1, 3) = substr(zip5_r, 1, 3)",
                        label_for_charts="first 3 ZIP digits",
                    ),
                    cll.ElseLevel(),
                ],
            ),
            # Geocode proximity as a corroborating signal (nulls handled internally).
            cl.DistanceInKMAtThresholds("lat", "lon", [0.1, 1.0, 10.0]),
        ],
        retain_intermediate_calculation_columns=True,
    )


def person_settings() -> SettingsCreator:
    """Dedupe int_persons__unioned. unique id = person_uid.

    Token order differs across sources, so name matching does NOT rely on a single
    surname key: blocking uses BOTH the first- and last-token Double Metaphone
    keys, and the name comparison ladders exact -> phonetic -> fuzzy on name_norm.
    """
    return SettingsCreator(
        link_type="dedupe_only",
        unique_id_column_name="person_uid",
        # Tight multi-column blocks. A single phonetic token + state is degenerate
        # for short codes (surname-sound "K" in AL = 10k people, 296M pairs); the
        # explosion comes from middle-initial-as-surname. Requiring BOTH name
        # sounds bounds it (max block 603, ~23M pairs total).
        blocking_rules_to_generate_predictions=[
            block_on("external_id"),                              # strong id
            block_on("email"),                                    # strong id
            block_on("name_phonetic_last", "name_phonetic_first"),# both name sounds
            block_on("family_name_norm", "state_code"),           # exact surname + state
            # Exact given+family name. Replaces a loose name_phonetic_last+zip5 block:
            # on parcel-owner-heavy ZIPs that surname-sound+ZIP rule built dense
            # candidate blocks that, via the old either-token phonetic level, fused
            # unrelated owners in the same ZIP. An exact first+last block corroborates
            # identity instead of geography and keeps blocks small.
            block_on("family_name_norm", "given_name_norm"),      # exact first + last name
        ],
        comparisons=[
            # Name ladder on the normalized full name.
            cl.CustomComparison(
                output_column_name="name_norm",
                comparison_levels=[
                    cll.NullLevel("name_norm"),
                    cll.ExactMatchLevel("name_norm").configure(
                        tf_adjustment_column="name_norm"
                    ),
                    # Double Metaphone agreement on BOTH tokens (catches order swaps +
                    # spelling, e.g. "Jon"/"John" + "Smith"/"Smyth").
                    # WHY BOTH, not either: a single shared metaphone code is far too
                    # weak. Many distinct given names collapse to the same code
                    # ("Gene"/"Jean"/"Jane"/"John"/"Jon" -> JN), so an "either token"
                    # level let one shared sound link strangers; under single-linkage
                    # clustering those edges chained whole ZIPs into mega-clusters
                    # (303k masters over-merged 2+ distinct full_names; one blob held
                    # 677 names). Requiring first AND last to agree breaks the chain
                    # while exact/levenshtein levels above still score true matches.
                    cll.CustomLevel(
                        "(name_phonetic_last_l = name_phonetic_last_r"
                        " and name_phonetic_first_l = name_phonetic_first_r)",
                        label_for_charts="phonetic match (both tokens)",
                    ),
                    cll.LevenshteinLevel("name_norm", 2),  # postgres backend: no Jaro-Winkler
                    cll.ElseLevel(),
                ],
            ),
            # Explicit given/family where a source provides them (else null -> no info).
            cl.LevenshteinAtThresholds("family_name_norm", [1]).configure(
                term_frequency_adjustments=True
            ),
            # Strong identifiers.
            cl.ExactMatch("email").configure(term_frequency_adjustments=True),
            cl.ExactMatch("external_id"),
            # Geography corroboration.
            cl.ExactMatch("state_code"),
            cl.CustomComparison(
                output_column_name="zip5",
                comparison_levels=[
                    cll.NullLevel("zip5"),
                    cll.ExactMatchLevel("zip5"),
                    cll.ElseLevel(),
                ],
            ),
        ],
        retain_intermediate_calculation_columns=True,
    )
