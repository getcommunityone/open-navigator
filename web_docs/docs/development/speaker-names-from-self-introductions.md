---
title: Speaker names from self-introductions
description: How story-map quote cards name who was speaking, using only what the speaker said on the record ("my name is ..."), with residents shortened to "First L." and no names for students, minors or school board residents.
---

# Speaker names from self-introductions

Issue: [#1231](https://github.com/getcommunityone/open-navigator/issues/1231). Decided 2026-11-26.

## The problem

The owner asked: "Why do I still not see names of people speaking on popup?" Story-map quote cards quote a meeting
verbatim, but almost never say who was speaking. Our transcripts are YouTube captions with timed text and no speaker
labels. Until now a card was named only when a hand-counted public comment (`data_center_public_comment`) matched the
passage word for word, which named 3 of 6,323 data-center passages. Topic stories had no speaker field at all.

## The decision: read self-introductions, no model

The owner chose the free option. Public commenters nearly always say who they are first, and that is on the record.
A regex extractor finds those introductions. It doesn't use TypeSafe, Jev, Gemini or a GPU, and it doesn't guess from
timing alone.

| Pattern (`pattern_id`) | Example in captions | Confidence |
|---|---|---|
| `my_name_is` | "my name is jane doe and i live on elm street" | 0.9 |
| `i_am_live` | "I'm Robert Lee and I live at the end of Oak Road" | 0.8 |
| `this_is_from` | "this is derek olson from the neighborhood association" (first and last name required) | 0.6 |
| `greeting_name` | "Good evening, Ana Ruiz here, 4120 Pine Street" | 0.6 |
| `next_speaker` | the chair: "our next speaker is sam lee" | 0.5 |

The patterns ignore case and tolerate caption noise ("uh", ">>", "[Music]"). A match is dropped when its first word
isn't a name, such as a function word, a role or a filler: "my name is on the list", "I'm here and I live nearby",
"this is consistent with". Trailing words are trimmed ("jane doe and i" becomes `jane doe`). A leading title is
dropped ("Dr. Jane Doe" becomes `jane doe`). A title with only a surname ("Dr. Doe") is rejected, because a surname
must never be shown as a first name. The rules and their tests are in
`packages/ingestion/src/ingestion/youtube/speaker_intros.py` and `packages/ingestion/tests/test_speaker_intros.py`.

## Pipeline

1. **Extract (Python, bronze).** `python -m ingestion.youtube.speaker_intros [--story-passages] [--video-id X]`
   reads `bronze.bronze_event_youtube_transcript.raw_text`. That text is `event_documents.content`, and for timed rows
   it is exactly the `segments` joined by spaces. The extractor writes `bronze.bronze_meeting_speaker_intro`, one row
   per introduction, PK `(video_id, char_offset, pattern_id)`, with:
   - the character offset of the introduction;
   - seconds, when the transcript is timed;
   - the raw name tokens;
   - the matched words;
   - `mentions_minor`, set when the 200 characters before the introduction or the 300 after it mention a student, a
     grade, a school or an age under 18 ("I'm 16", "sixteen years old").

   It writes only to the local warehouse (`OPEN_NAVIGATOR_DATABASE_URL`). Re-running it replaces each video's rows.
   The PK uses `char_offset` rather than `start_seconds`, because most transcripts have no usable timing (caption
   text with two timestamps, or untimed text). Offsets work for every transcript.
2. **Stage (dbt).** `stg_bronze_meeting_speaker_intro` types the rows. It sets `says_resident` when the introduction
   says the speaker lives here.
3. **Who it is (dbt mart `meeting_speaker_intro`, gold only).** One row per introduction, in the form we may show:

   | `speaker_kind` | When | Shown |
   |---|---|---|
   | `suppressed` | The speaker said they are a student, in a grade or a school, or under 18 (`student_or_minor`); or a resident speaking at a school board meeting (`jurisdiction_type = school_district`; a jurisdiction named for a school, ISD, USD or board of education; or a title naming a school(s) board, school district, school committee, board of ed, BOE, USD/ISD or students: `school_board_meeting`) | Nothing |
   | `unrecognized` | The first word heard is not a known given name: one carried by at least 4 people in the person master (`mdm_person.given_name_norm`, an aggregate of first names only), or an official's first name. Captions are lower-case, so this is what keeps "my name is spelled wrong" from becoming "Spelled W." | Nothing |
   | `official` | A "my name is" or "I'm … I live" introduction (never a greeting or a chair call, which can name someone else) whose first and last name equal exactly **one** current official of the meeting's own government in `person_government` (office `government`, same state, jurisdiction "*Name* Government") | Full name and title, from our officials data |
   | `resident` | Everyone else | "First L." from the words heard (two words give "Jane D."; one or three words give the first name only, so a middle name is never shown as a surname). Role "Resident" only when they said they live here; otherwise no role |

   The mart has no column with a private person's full name. The raw tokens stay in bronze and staging, in the
   private warehouse.
4. **Which passage (dbt mart `meeting_passage_speaker`, served in `public`).** A quoted passage is placed in the
   transcript by finding the first 80 characters of each ts_headline fragment (with the `<mark>` tags removed) in
   `event_documents.content`. A fragment that can't be found, or whose words occur more than once in the transcript
   (a motion read twice), gets no speaker. Each fragment takes the **nearest preceding** introduction in the same recording within
   **2,500 characters**. That is about three minutes of speech: a usual public-comment limit, and the window
   `int_data_center_transcript__passage` already uses for untimed text. A later introduction always ends the earlier
   one's window. A two-fragment excerpt is named only when both fragments take the same introduction. If the nearest
   introduction is suppressed or unrecognized, the passage is served with no name, never an older speaker's name.
   The nearest introduction is found in one ordered pass per recording (a running count of introductions), not by a
   scan per passage.
   FKs: `meeting_speaker_intro_id`, `topic_transcript_link_id`, `data_center_meeting_mention_id`.
5. **API.** `GET /api/topics/{id}/states` `newest[]` gains `speaker_display_name` and `speaker_role`.
   `GET /api/data-centers/meeting-mentions` uses this as a fallback when no hand-counted comment names the passage.
   Both shorten any resident name to "First L." again. Officials keep their name and title. A database without
   `meeting_passage_speaker` leaves the fields null.
6. **UI.** `HomeTopicStoryCard` and `TopicStory` pass the fields to the `StoryStatesMap` quote card as
   `speakerName` / `role`, as the data-center cards already did.

## Privacy

This follows [Privacy and data ethics](privacy-and-data-ethics.md) and
[People in meetings](people-claim-and-privacy.md):

- A name is shown only when the transcript itself says it. Nothing is looked up about a resident, and nothing is
  added from elsewhere.
- Residents are "First L." in served data, at most.
- No name is served for a speaker who says they are a student or under 18. No resident is named at a school board
  meeting. The minor check is conservative: "a senior at", "high school" and "my daughter's elementary" all suppress.
- No sensitive trait is attached to a name. The role is "Resident", an official's title, or nothing.
- The "Is this you?" hide and remove requests (#1064) will need to suppress these names too, once that store exists.

## Coverage on the local warehouse (2026-11-27)

The extractor ran over the 18,090 transcripts behind story-map quotes (`--story-passages`). It found 51,221
introductions in 10,660 recordings: 42,986 "my name is", 4,881 chair calls, 2,033 "I'm … I live", 745 greetings and
576 "this is … from". It flagged 4,494 as student or minor.

| | Passages | Named | Residents | Officials | Withheld (student, minor, school board) | First word not a known name |
|---|---|---|---|---|---|---|
| Topic passages (`topic_transcript_link`) | 16,459 | 847 (5.1%) | 847 | 0 | 98 | 122 |
| Data-center passages (`data_center_meeting_mention`) | 6,323 | 696 (11.0%) | 696 | 0 | 40 | 118 |
| Topic map cards (newest passage per topic and state) | 284 | 19 | 19 | 0 | | |

Only 5 introductions matched an official, and none of them is next to a story quote. The officials data has about
550 local officials.

## Known limits

- **Attribution is by position, not by voice.** A council member who replies within three minutes of a resident's
  introduction, without introducing themselves, would be attributed to that resident. The 2,500-character window
  and the two-fragment rule keep this rare, but it is not diarization. WhisperX diarization (GPU, on hold) would
  replace the window with real speaker turns.
- **Officials data is thin.** Only about 550 local officials (`office = government`) are in `person_government`, so
  most officials who introduce themselves show as "First L." with no role.
- **Caption spelling.** Names are as the captions heard them ("Mccclure"), so only the first name and an initial are
  shown for residents.
- **Coverage.** Only topic passages and data-center passages whose recording has an introduction nearby can be named.
  Run the extractor over every transcript (no flag) to cover new story passages as they are added.
