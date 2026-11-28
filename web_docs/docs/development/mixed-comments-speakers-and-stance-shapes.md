---
title: Mixed comments - speakers, stance shapes, attribution and heat
description: Why the speaker, not the caption segment, is the counted unit; how merged speakers are re-split; the seven stance shapes; the confidence rules for every attributed name; and the 1-5 heat rating with its calibration.
---

# Mixed comments: speakers, stance shapes, attribution and heat

Issue: [#1386](https://github.com/getcommunityone/open-navigator/issues/1386). Decided 2026-11-27. Builds on #1233 (comment
segments), #1231 / #1245 (speaker names from self-introductions) and #1327 (decision supporters and opposers).

## The question

A caption comment that reads as both for and against is one of two things: two people merged into one segment, or one
person making a qualified statement ("I support data centers, but not at this site", "only if they pay their share of
water"). The owner asked how to handle it better than a raw exclude, then made the speaker the core grain: "we should have
attempted to aggregate and determine speakers the first time."

## Decisions

1. **The speaker is the counted unit.** `meeting_speaker_position` has one row per meeting x speaker, `meeting_speaker_turn`
   one row per meeting x turn, and `meeting_comment` (the caption segment) keeps its detail role with an FK to its turn.
   Site counts are distinct speakers ("62 speakers"); segments are detail. A speaker is never linked across meetings: the
   key is the meeting plus the name key.
2. **Re-split merged speakers, free and deterministic.** The segmenter (version 1.3.0, `ingestion.meetings.comment_segments`)
   now cuts a stretch where a second voice starts: a `>>` caption marker, a chair hand-off ("thank you, sir", "thank you,
   Mr. X"), or a later self-introduction found by `find_intros`. A cut needs at least 30 words on both sides, so `>>` noise
   inside a sentence does not make a comment.
3. **A piece split off with no introduction is a public comment only inside an opened public-comment section.** Outside one
   it is council or staff talk. This keeps speaker counts from filling with council chatter (the first cut of this work
   tripled the segment count before the rule).
4. **Same speaker, two statements: classify the shape, not just the side.** Cue rules in the seed
   `comment_stance_shape_terms`, run by the `stance_shape_sql` macro once per segment and once over all of a speaker's text:

   | `stance_shape` | meaning |
   |---|---|
   | `for_concept_against_project` | supports the idea, objects to this site ("support ... but not here / not this site") |
   | `conditional` | a side plus "only if", "as long as", "provided that", "with conditions" |
   | `against_concept_open_to_terms` | opposes, but "unless", "open to", "would reconsider" |
   | `clear_for` / `clear_against` | one side's cue only |
   | `concerns_only` | no side, but a water / noise / tax / grid concern |
   | `unclear` | no cue, or both sides with no shape cue (may be more than one speaker) |

   The first matching cue phrase is stored verbatim (`shape_cue_text`, at most 160 characters). A shape is counted on its own,
   never as both sides. At meeting grain, several people who disagreed is still "both sides spoke". `unclear` replaces the
   "Unclear (may be more than one speaker)" label.
5. **Every attributed name carries its provenance.** See below.
6. **Heat (1-5) is carried with its method.** See below.

## Attribution: method, confidence, evidence, version

Columns on `meeting_speaker_turn`, `meeting_speaker_position` and `meeting_passage_speaker`: `attribution_method`,
`attribution_confidence` (0-1), `attribution_tier`, `attribution_evidence` (the verbatim cue, never the name, with where it
was heard), `attribution_version` (`speaker_attribution/1`, bumped when the rules change) and `attributed_at`. The decision
supporters and opposers API (`api/routes/decision_people.py`) returns the same fields per person.

Methods: `self_intro`, `chair_call`, `caption_marker_turn`, `official_roster_match`, `ai_extraction_held_by`, and
`voice_diarization` (reserved for a future pyannote / WhisperX run, #1251; not run, no rule yet).

Tiers: **high** at 0.80 and above, **medium** at 0.50 and above, **low** below. The rules live in the seed
`speaker_attribution_rules` (one source of truth; tests check the API constants against it):

| rule | method | confidence | tier |
|---|---|---|---|
| `self_intro_in_turn`: "my name is X" / "I'm X and I live" inside the speaker's own turn | self_intro | 0.90 | high |
| `official_roster_match`: the introduced name equals exactly one current official of the meeting's government | official_roster_match | 0.90 | high |
| `self_intro_greeting`: "this is X from", "good evening, X here" inside the turn | self_intro | 0.60 | medium |
| `chair_call_name`: the chair names the speaker ("next speaker is X") and that turn starts | chair_call | 0.60 | medium |
| `self_intro_name_withheld`: an introduction was heard but the name is not served (minor, student, school board, not a known given name) | self_intro | 0.50 | medium (no name) |
| `turn_marker_only`: a `>>` starts the turn, no name said: "Speaker N", turn confidence only | caption_marker_turn | 0.50 | medium (no name) |
| `chair_call_turn`: the chair's call starts the turn, no name said: "Speaker N" | chair_call | 0.50 | medium (no name) |
| `nearest_earlier_intro`: no introduction in the turn; the nearest earlier one within 180 s (about 2,500 characters of speech) with no turn marker between | self_intro | 0.35 | low |
| `passage_intro_near` / `passage_intro_window` / `passage_chair_call_window` / `passage_after_turn_marker`: quoted passages (`meeting_passage_speaker`) by distance to the introduction (600 / 2,500 characters) and whether a `>>` sits between | self_intro or chair_call | 0.80 / 0.60 / 0.60 / 0.35 | high / medium / medium / low |
| `ai_held_by_roster`: an AI `held_by` slug equal to one current official | official_roster_match | 0.90 | high |
| `ai_held_by_official_title`: an AI slug naming an official title, not on the roster | ai_extraction_held_by | 0.60 | medium |
| `ai_held_by_resident`: an AI slug with a first and last name, shown as "First L." | ai_extraction_held_by | 0.50 | medium |

A speaker's row takes the best-supported segment's method and confidence. A `held_by` slug is AI-extracted, so it never
reaches high unless the roster also matches.

### What the UI does

- **High:** the name, plus a small "How we know" control.
- **Medium:** the name with a subtle "likely" marker and a tooltip ("Matched from the chair calling the speaker"), plus "How we know".
- **Low:** "Speaker not identified", with an opt-in "Possibly First L." only when privacy allows. A possible minor, a student
  or a school-board resident never has a name or a candidate. The topic and data-center quote APIs already drop low-tier
  passage names.

### Privacy

Names stay "First L." for private residents; officials are public. A minor, student or school-board resident is
"Speaker N" with no cue phrase. Evidence strings quote the cue ("my name is ...") and never the name. Speaker identities are
never linked across meetings.

## Heat (1-5)

`meeting_speaker_position.heat` (nullable), `heat_method` (`ai_meeting_analysis` | `rules` | `classifier`),
`heat_confidence`, `heat_version` (`heat/1`).

- **`ai_meeting_analysis`:** the AI meeting analysis's rating (`public_comment.heat`) of a comment in the same meeting whose
  verbatim quote (`stance_evidence`, 40+ characters) sits inside one of the speaker's segments; several matches give the
  rounded mean. `public_comment` has no timestamps, so the quote is the only reliable join. Confidence 0.80.
- **`rules`:** a free baseline (the `comment_heat_terms` lexicon, "!" and ALL-CAPS words). Calibrated against the 178 AI-rated
  comments whose quote lands in the segment layer (of 1,416 rated; the rest are in meetings the segmenter did not cut):
  exact match 37.6%, within +-1 78.1%, Spearman 0.33. A constant guess of "2" scores 37.6% exact and 87.6% within +-1 on the
  same sample (the ratings are skewed to 1-2), so the +-1 test does not tell a signal from the prior. **The rules heat is
  therefore off** (`heat_rules_enabled: false`) and the column stays null for those speakers; one variable turns it on if the
  owner wants it despite this. Applause and crowd-noise tags are stripped by the segmenter's tokenizer, and chair
  interventions are only read inside the speaker's own stretch, so two of the requested signals are not available.
- **`classifier`:** reserved. A paid pass is described in the issue and has not been run.

Display: 1-5 flame icons, aria label "Heat 4 of 5", a tooltip with the method, nothing when null. A summary shows the average
and peak only when at least 3 speakers have a rating.

## Free versus paid

Everything here is free and deterministic. An optional TypeSafe Jev pass per speaker (a yes/no screen, so heat would be
asked as a ladder of thresholds, about 5 questions) would cost, at the sourced rate of $0.042 per 1M input tokens
(`llm.usage` prices, read 2026-11-15): about **$0.4** for the 2,421 data-center speakers of 2026 (about 2.0M input tokens per
question including prompt overhead), and about **$22** for all 76,592 public speakers. It would add heat for the
~99% of speakers with none and a side (for / against) for the `unclear` and `concerns_only` majority. Not run: it needs the
owner's yes.

## Known limits

- Many data-center speakers are `concerns_only`: captions rarely say "I oppose", so a side often cannot be read from wording.
- `conditional` and `against_concept_open_to_terms` cues ("as long as", "unless") are matched anywhere in a speaker's text;
  precision is not yet measured and some are about other subjects.
- Unnamed `>>` pieces inside a public-comment section may still include council questions.
- The caption segmenter only finds comments anchored by an introduction or a chair call.
