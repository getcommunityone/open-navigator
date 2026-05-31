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
        blocking_rules_to_generate_predictions=[
            block_on("address_match_key"),          # exact mailable address
            block_on("zip5"),                        # same ZIP
            block_on("street_name"),                 # same street
            block_on("city_norm", "state_code"),     # same locality
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
            cl.JaroWinklerAtThresholds("street_name", [0.92, 0.85]).configure(
                term_frequency_adjustments=True
            ),
            cl.JaroWinklerAtThresholds("city_norm", [0.9]).configure(
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
        blocking_rules_to_generate_predictions=[
            block_on("external_id"),                          # strong id
            block_on("email"),                                # strong id
            block_on("name_phonetic_last", "state_code"),     # surname sound + state
            block_on("name_phonetic_first", "state_code"),    # given sound + state (order-agnostic)
            block_on("zip5"),                                 # same ZIP
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
                    # Double Metaphone agreement on either token (catches order swaps + spelling).
                    cll.CustomLevel(
                        "(name_phonetic_last_l = name_phonetic_last_r"
                        " or name_phonetic_first_l = name_phonetic_first_r)",
                        label_for_charts="phonetic match (either token)",
                    ),
                    cll.JaroWinklerLevel("name_norm", 0.88),
                    cll.ElseLevel(),
                ],
            ),
            # Explicit given/family where a source provides them (else null -> no info).
            cl.JaroWinklerAtThresholds("family_name_norm", [0.9]).configure(
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
