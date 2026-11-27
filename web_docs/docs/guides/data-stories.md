---
title: Data stories
description: What the data stories hub and the Data Center Story are, who spoke for and against, how the story opens on an overview then asks its question after the record, how a story screen is built, how screens move on a phone, on a wide screen and with reduced motion, the cue on the next step, the voice rules for its sentences, how the place in scope is carried, and how to add a story.
---

# Data stories

A data story opens on an **overview of the record**, shows what public meetings said one screen at a time, and only then asks its topic question so you can agree or disagree and see how other readers answered. Each screen of the record has a bold sentence computed from the data, one line of context, and a chart where every dot is a record you can open. Along the way, each contested screen asks the statement its record is about (Agree / Disagree / Not sure) and shows **where you sit** once you answer ([#981](https://github.com/getcommunityone/open-navigator/issues/981)); there is no separate challenge any more. The hub never leads with the question (#950).

The **Data Stories** item in the header scrolls to the Data stories section of the home page (`/#data-stories`), which shows the story's real counts and opens the story, the challenge and the index of every story at `/stories` ([#975](https://github.com/getcommunityone/open-navigator/issues/975)). The first story is the Data Center Story at `/stories/data-centers`.

The home page opens on the Data stories section, with search second; the line "Every local decision, in one place." now closes the page, under Impact ([#995](https://github.com/getcommunityone/open-navigator/issues/995)). The section's map draws each state as small boxes ([#1087](https://github.com/getcommunityone/open-navigator/issues/1087), described below), and hovering one shows a card quoting that state: a speaker's own words with their recorded side ("Spoke against · Business owner") where one is on record, otherwise a meeting passage chosen as described under "Which meeting a map card quotes" ([#1230](https://github.com/getcommunityone/open-navigator/issues/1230)), verbatim, with the place, date, meeting and a link to the moment in the recording. Under it, **Browse topics** opens the story's screens (who spoke, projects, decisions, environment and resources, jobs) for the page's place. On the home page, the Data stories section leads with the story's conclusion, **America hates data centers.**, with its subtitle and a line giving the real speaker counts behind it. The headline shows only while the national record backs it (see [Story statements and where you sit](../development/story-statements-where-you-sit.md#decision-conclusion-headlines-shown-only-when-the-record-backs-them-989)); otherwise the story's question shows. **Start the story** comes right under it, in view on a laptop and a phone. The hub card does the same ([#989](https://github.com/getcommunityone/open-navigator/issues/989)). The section names the story (**The Data Center Story**). It has a US map with one marker per state where a data center came up in at least one meeting; a marker's size follows that real count and clicking it opens the story for that state. The page's own place is highlighted, with its counts and a **Start the story** button named for that place. Under the box, **All data stories** lists every story there is, and says so plainly while there is only one ([#985](https://github.com/getcommunityone/open-navigator/issues/985)).

Under **Search your community**, a **Find your town** button opens the location picker ([#1179](https://github.com/getcommunityone/open-navigator/issues/1179)); once a place is set it reads "[Town, ST] · Find another town". No list of "launch cities" is hard-coded anywhere in the web app: any place the geocoder finds can be picked, and a page with no meetings for it says so (for example "No meetings on record for X") rather than the picker refusing the place. Search no longer offers "Include all of [county]", which only worked for four hard-coded cities; bringing it back from data for every city is tracked separately.

*(Home card: removed 26 Nov 2026, [#1182](https://github.com/getcommunityone/open-navigator/issues/1182); the points remain on the Data Center Story's opening screen.)* Under the headline and its subtitle, the hero's left column lists up to three numbered points, each with a round teal icon, a bold title and a line with the real figure ([#1122](https://github.com/getcommunityone/open-navigator/issues/1122)). The titles are fixed; every figure is national and comes from `GET /api/data-centers/positions`:

1. **"Communities are saying no."** The meetings (and states) where Jev read the public as mostly opposed (`lean_totals.public_against_meetings` / `public_against_states`), then (only when the meeting reading is missing) "29 speakers counted by hand in 4 states: 18 against and 3 for." from the counted speakers in `totals`, with the number of states counted from `by_state` (states with any counted speaker), never hard-coded ([#1134](https://github.com/getcommunityone/open-navigator/issues/1134)).
2. **"Projects are being stopped."** The meetings whose data center outcome Jev read as tabled or deferred, denied or a moratorium (`lean_totals.stopped_meetings`).
3. **"Officials don't always listen."** The meetings (and states) where officials sided against the public (`lean_totals.disagreement_meetings` / `disagreement_states`, the #1113 rule).

Jev's figures are labelled "AI reading", because they are a classifier's reading of the transcript, not counted speakers. A point with no data (a 0, or `lean_totals` null because `data_center_meeting_lean` isn't loaded) is left out and the rest are renumbered; a sentence with no data is dropped from point 1. On a page scoped to a place, each point uses the place's own figure where it has one and otherwise the national figure, starting **"Nationally:"** ([#1134](https://github.com/getcommunityone/open-navigator/issues/1134), see below). Under the points, a large pill **Start the story for [place] →** keeps the page's scope, and a second pill **Next story: Short-term rentals →** (from `nextStoryLink` in `storyNav.ts`) carries it too. On a phone the points stack above the map and both buttons are full width. The copy is built by the pure helper `web_app/src/utils/heroPoints.ts`, with tests; the map on the right is unchanged.

The home map is now drawn like the Explore map: each state is a grid of small square boxes in its own shape (Alaska and Hawaii where the Albers map puts them), not a pin ([#1087](https://github.com/getcommunityone/open-navigator/issues/1087)). Where speakers are on record, a state's boxes are split in bands by the real counts of those who **spoke against**, **spoke for**, **asked a question** or took **no side** (from `data_center_meeting_position`, served nationally as `by_state` on `GET /api/data-centers/positions`); a caption gives the number of speakers and states behind the split. A state with meetings but no speaker on record is one grey (**Meetings, no stance on record**) and a state with no meetings stays the empty tint, so no split is ever drawn without real counts. Hovering a box (tapping, on a phone) shows one of that state's real passages, cycling through them across its boxes, with the place, date, quote and the state's speaker counts; clicking opens that state's story. A data table under the map lists every state with its meetings and speaker counts and links to its story, for keyboard and screen readers. The hover card ends with a full-width **Open the [State] story →** button (at least 44px tall, on desktop and phones), not a line of small text ([#1187](https://github.com/getcommunityone/open-navigator/issues/1187)). Under the map the legend is compact (8px swatches, 11px text), and the note on how the split is counted sits with the data table under **How to read this map · data table**, so the first desktop screen keeps room for Browse topics. The legend itself still names the AI reading. The short-term rentals card uses the same map without a split, shaded by meetings only. Each state's outline is drawn over its boxes, and a state with meetings but no recorded stance is grey, light to dark by its real meeting count ([#1103](https://github.com/getcommunityone/open-navigator/issues/1103)). The legend has four entries: Spoke against (red), Spoke for (green), No side (purple) and Meetings with no stance on record (grey, darker = more meetings). A speaker who only asked a question is drawn as No side, while hover cards still say "asked a question" ([#1110](https://github.com/getcommunityone/open-navigator/issues/1110)). Hovering shows a quote card ([#1108](https://github.com/getcommunityone/open-navigator/issues/1108)). It carries the meeting's own recording thumbnail with "Hear it at m:ss", the place and date, the quote verbatim and large, and a speaker row: an initials avatar (never a photo), the shortened name, the side, and only the role or item on record. The meeting video popup uses the same card without the image.

Beyond counted speakers, both maps show an **AI reading** of each data center meeting ([#1117](https://github.com/getcommunityone/open-navigator/issues/1117)). Jev, a classifier, read every meeting's transcript and judged whether the members of the public who spoke, and the elected officials, were mostly against, mostly for or split (`data_center_meeting_lean`, served as `public_against_meetings` and `disagreement_meetings` on positions `by_state` and meeting-mentions `by_place`). A state or county with no counted speakers but at least one meeting where the public mostly opposed a data center (probability at least 0.7) is a lighter red, labelled **Public mostly opposed (AI reading of meetings)**; counted speakers keep their own colours. Where Jev read the public as opposed and officials as supportive, and the meeting wasn't a moratorium, a denial or an approval of rules (**officials sided against the public**), the map draws nothing extra (the owner preferred no dark outlines); it is stated in the hover card, the readout and the data table. The hover card and readout add a line such as "AI reading: the public mostly opposed in 2 meetings; officials sided against the public in 2 meetings." only when a count is above 0, and the data tables add both columns. "Supported" and "mixed" readings are never shown, because hand checks found them unreliable. The state drill-down also draws each county's border as a thin line over its dots, and it tells towns from counties the way printed maps do: towns and cities stay dark and bold beside their ring, while county governments are small, uppercase, letter-spaced grey text at the county's centre ("FAYETTE COUNTY"), placed after the towns. Method and limits: [Data center meeting lean](../development/data-center-meeting-lean.md). On a phone, one tap on a state opens its story ([#1120](https://github.com/getcommunityone/open-navigator/issues/1120)); there is no hover there, so the quote card is a desktop affordance. **Changed 26 Nov 2026 ([#1222](https://github.com/getcommunityone/open-navigator/issues/1222)):** on a phone, the first tap on a state that has a quote card now shows **that state's** card, and its **Open the [State] story →** button opens the story. The page's scope label, map highlight, state select and charts then change to that state. A tap on a state with no card, or a second tap on the state already shown, still opens its story directly. When the card's state is the page the reader is already on, the card says **You're reading the [State] story** instead of offering a button that would do nothing. Before this change a tap focused the map, the keyboard's starting state (the page's own) took the card, and the button always led back to the current page. Keyboard focus still starts on the page's state.

**Changed 26 Nov 2026 ([#1229](https://github.com/getcommunityone/open-navigator/issues/1229)):** on a phone nothing on the story maps depends on hover. The owner reported "Once I click on one dot I can't click on a different one" on the live topic story (Android Chrome): in that build the first tap focused the map, the keyboard's starting state (the page's own, Alabama) took the card, and every later tap opened another state's story in place while the Alabama card stayed pinned. #1222 fixed the pinned card; this change finishes the touch rules for all three story maps (the home and topic state box map, the Data Center Overview's national dot map and its county map):

- A tap on a state (or county) shows its card, and a tap on another switches the card, any number of times in any order. A second tap on the state already shown opens its story (narrows the Overview to it); a state with no card opens at once.
- The Overview's national dot map now works the same way on a phone: the first tap on a state with a passage shows its card with a **Show [State] →** button instead of narrowing at once with the card hidden behind the change.
- A card a tap opened closes on its **Close** button (44px tall, named "Close the [State] card" for screen readers, focus returns to the map) or on a tap anywhere outside the map and its card. Scrolling the page does not close it (a touch that turns into a scroll is not a tap). On a device that reports hover but is used with a finger, a tap still acts like a mouse; that is [#1252](https://github.com/getcommunityone/open-navigator/issues/1252). On a desktop the card still follows the mouse and has no Close button; the keyboard (#1146) is unchanged: Tab starts on the page's state, the arrows move, Enter opens and Escape hides.
- Each state's boxes carry `data-state` (the two-letter code). `web_app/e2e/map-taps.check.mjs` taps states A, B, C, B, A, D at Pixel 7 and iPhone 13, checks the card and outline follow each tap, that Close and a tap outside close it, that a second tap opens the story and later taps still switch, does the same on the Overview dot map and the county map after the drill, and checks the keyboard and mouse at 1440×900. Run it against a running app: `node e2e/map-taps.check.mjs --base http://localhost:5173`.

**Changed 27 Nov 2026 ([#1277](https://github.com/getcommunityone/open-navigator/issues/1277)), replacing the #1222 and #1229 tap cards above:** the owner asked for no popup on phones, a desktop card that plays the recording on its own and never covers the map, and a drill-down that is easier to see. This applies to all three story maps: the state box map (home cards and topic stories), and the Data Center Overview's national dot map and county map.

- **Phones and tablets** (`(hover: none)` or a coarse pointer): there is no card at all. A tap on a state opens its story at once, or narrows the Overview to it. A tap on a county only outlines it and names its count under the map, because there is no county drill. An always-visible line under the map reads **Tap a state to open its story**. The Close button and the tap-outside-to-close code are gone.
- **Desktop hover:** hovering a state outlines the whole state in a dark line, mutes the others, anchors a non-blocking teal **`<State> · Click to drill down →`** pill right beside the state on the map ([#1360](https://github.com/getcommunityone/open-navigator/issues/1360)), highlights the drill-down prompt under the map, and shows one card **beside the map, never over it**. On the home page the card fills the slot in the left text column under **Start the … story** (in place of "Pick a state on the map to open its story."), and the slot keeps its height so the page doesn't jump. On the story pages it sits directly under the map's legend. The card never follows the cursor. It is person-first: first the meeting's recording, embedded from `youtube-nocookie.com`, playing **muted from the quoted moment** with YouTube's own controls and no play-button overlay (`autoplay=1&mute=1&start=<s>&playsinline=1&controls=1`). Then come the verbatim highlighted quote, the speaker as served when one is on record ("First L." for a resident, with the role on record), then the meeting · place · date, the **Public: …** line, and a teal **Click [State] to open its story →** button pill, which goes where a click on the state goes. The state's meeting counts are no longer on the card; they stay in the line under the map. When the record has no speaker the card shows none and adds no "In the meeting" filler. A passage with no video id shows the quote without a player. The AI summary and the meeting-analysis link are left off this card to keep it small (the Meetings screens still link the analysis).
- **One player at a time, switching across a state's meetings ([#1357](https://github.com/getcommunityone/open-navigator/issues/1357)).** Hovering across different stance bands or zones within the same state walks through that state's real speaker and meeting passages (named speakers first, matching the hovered stance band when available) via contiguous zones (`web_app/src/utils/mapQuote.ts`), so small pointer moves within one meeting's zone keep its video playing while moving to another band or part of the state swaps cleanly to another meeting. Topic maps request `GET /api/topics/{id}/states?quotes_per_state=3` (default `1` unchanged) so non-data-center stories also carry multiple distinct meetings per state. Moving to another state swaps the card, and leaving the map removes it after a short pause long enough to reach its link; moving onto the card keeps it. Nothing loads from YouTube on a phone, before a hover, or from keyboard focus.
- **Reduced motion / data saving:** with `prefers-reduced-motion: reduce`, `prefers-reduced-data: reduce` or the Save-Data hint, the card shows the recording's still image with a play button, and nothing autoplays.
- **No "(AI reading)" in visible labels.** The map captions, hover lines, legend and table headers no longer say "AI reading" (owner); the note under **How to read this map** still says each meeting is read by a classifier from its transcript.
- **Keyboard:** Tab focuses the map, the arrows move between states with the same outline and card, and Enter opens the state (narrows the Overview). From keyboard focus the video does **not** autoplay; the card shows the still image and a play button, which Tab reaches and Enter/Space plays in the card. Escape hides the card.
- `web_app/e2e/map-taps.check.mjs` now checks this behaviour. At Pixel 7 and iPhone 13: the hint shows, a tap opens the state's story with no card, and a county tap lights only that county. At 1440×900: hover gives one card that does not overlap the map, whose iframe `src` has `autoplay=1&mute=1`, the state lit and outlined, the video swapping between states and gone on leaving; keyboard focus does not autoplay; Enter, a click on a state (Alabama on `/` opens the Alabama story) and the card's link drill. Run it with `node e2e/map-taps.check.mjs --base http://localhost:5173`.

### Which place a story speaks for (#1285)

Owner, 27 Nov 2026: with Tuscaloosa, AL chosen, the Overview said "A data center came up in 2 meetings in Tuscaloosa, Alabama" over the whole Alabama map, and the home map stayed national.

- **5 meetings or more for a place of its own.** `resolveStoryScope` (`web_app/src/utils/resolveStoryScope.ts`, threshold `MIN_SCOPE_MEETINGS = 5`) steps up one level at a time, city → county → state → national, to the first level with 5 or more meetings on the topic. It says why in plain words, for example "Tuscaloosa has only 2 meetings on data centers, too few to call. County counts aren't on record for this topic, so this shows Alabama (71 meetings)."
- **The county step, for data centers ([#1321](https://github.com/getcommunityone/open-navigator/issues/1321)).** A thin
  city's county comes from the city's coordinates on record, or the saved location's county when you picked the city by
  ZIP. Its meetings are the county government's plus those of every place inside it. Example: "Homewood has only 3
  meetings on data centers, too few to call. Jefferson County has 14 meetings, but figures aren't broken out by county
  yet, so this shows Alabama." Until the endpoints accept a county ([#1323](https://github.com/getcommunityone/open-navigator/issues/1323)),
  a county level is drawn at its state and the sentence says so. When the county can't be found, it says "Its county
  isn't on record". Other topics have no county grain and skip the step.
- **Where the counts come from.** City and state counts come from `GET /api/topics/{topic}/caption-facts` (`meetings` for the city, `states[]` for the state). No topic serves a county grain the story's charts can be narrowed to yet, so the county step is skipped and the line says so. The helper already handles a county count when one is passed.
- **What follows the level.** The hook `useStoryScope` (`web_app/src/hooks/useStoryScope.ts`) applies the rule on the home hero (data centers and topic cards) and on the story pages (`DataStory`, `TopicStory`). The headline, the counts, the quotes and the map then use that level. The URL keeps the reader's choice (`?state=AL&city=Tuscaloosa`). The home subtitle gives the reason. On a story page the reason sits on one line in the sticky bar under the headline.
- **The home map zooms to the place.** With a state or city in effect, the home map draws only that state, on a finer grid. The asked city is marked at the coordinate its meeting record holds (`latitude`/`longitude` on `GET /api/data-centers/meeting-mentions?state=` place counts). When no coordinate is on record, the map says "No map location on record for `<city>`." and draws no guessed pin. With National in effect it is the full US map again.
- **One click back to National.** Next to the header's place pill, **× National** resets the scope in the URL, and the label, the map and the data go national together. It shows on a desktop, in the phone bar, and as **Show National** in the phone menu. On a story page it drops `?state=&city=`. On home, where the place is the reader's town, it adds `?scope=national`, and the header then reads "National · Use Tuscaloosa, AL", one click back.
- **Plain subtitle.** When a city's title is the wider place's because too few meetings took a side, the line under it reads "Tuscaloosa, Alabama hasn't had enough public comment on data centers to call. Showing America."
- **No "AI reading" label** on the home topic-strip tiles.
- `web_app/e2e/place-scope.check.mjs` checks the zoom, the pin, the reason, "× National" and the story note at 1440×900 and Pixel 7.

### The home map at a state or city (#1307)

Owner, 27 Nov 2026, on `/?state=AL&city=Tuscaloosa` after #1285: "The Alabama map should match the drill-down one; I have no clue what this is." The zoomed home map was the national box grid cropped to the state, every box the same colour.

- **Data centers.** With home scoped to a state, or to a city that resolves to its state, the hero map is the story Overview's own state map (`StoryCountyMap`, reused). It shows the state's counties, the meeting towns as labelled rings, and the stance legend, from `GET /api/data-centers/meeting-mentions?state=` (`counts.by_place`, `items`). The chosen city's ring is bold and dark and its label bold teal, and its county stands out. The caption, legend and data table under the map are the state map's.
- **Hover and click.** On a desktop, hovering a county shows its card in the slot under **Start the … story** (the hint reads "Pick a county or a town on the map to open its story."). Clicking a county, or a town ring, opens the Data Center Story at that state, at the county's town with the most meetings on record, or at the ring's town (`/stories/data-centers?state=AL&city=Auburn`). Enter does the same from the keyboard. On a phone a tap drills.
- **Topic cards.** **Changed 27 Nov 2026 ([#1349](https://github.com/getcommunityone/open-navigator/issues/1349)):** a state-scoped topic card now draws the same county map as data centers (see [The topic county map](#the-topic-county-map-1349)). Clicking a county, or a town ring, opens the topic story at that town (`/stories/water-fluoridation?state=AL&city=Fairhope`). The state's outline, with "These meetings aren't mapped by county or town yet, so the state is drawn as its outline.", is kept only when none of the state's meetings can be placed or the place counts can't be loaded.
- `StoryCountyMap` gains two optional props for this, `cardSlot` and `onDrill`. Without them it behaves as before on the story pages.

### How the maps load (#1328)

Owner, 27 Nov 2026, on the Data Center Overview for Georgia: "it might be flashing stats in map before the map shows because of loading time; need this to be more elegant." Before this change the Overview showed the year-over-year chart and the counts in the map's place while the state's county shapes loaded, then pushed them down when the map arrived.

- **One quiet box first.** Every story and home map (the home hero, `StoryStatesMap`, `StoryDotMap`, `StoryCountyMap`) holds its final size while it loads: the national frame, or the state's own shape box from the cached state shapes (`useStateAspect`). It is a soft shimmer with no numbers, caption, legend or card (`MapSkeleton`).
- **Waiting for both shapes and data.** On the Overview, the map, the year-over-year chart and the counts wait for this scope's place counts and the map's shapes. They then arrive together in one 200 ms fade (none under reduced motion). No other scope's map or counts show first.
- **Slow or failed.** After 8 seconds, or on an error, the box says "The map is taking longer than usual." (or "could not be loaded") with **Try again**.
- **Prefetch.** The county shapes are fetched on the first hover of the national maps, so a state's map is ready when it is picked.
- **Measured.** Playwright with 1.5 s delays on the API and the map shapes, at 1440 and Pixel 7, on `/stories/data-centers?state=GA` and `/?state=GA`. Before, the Overview showed the comparison chart and counts for about 2 s before the map. After, it shows only the skeleton, then the map with its counts.

### Which meeting a map card quotes (#1230)

**Changed 26 Nov 2026 ([#1230](https://github.com/getcommunityone/open-navigator/issues/1230)).** The owner did not believe
the Alabama guns card: it quoted "Full Steve Carter Interview" (Athens, Sep 8, 2026), a passage that only says
"firearms" and comes from an interview, not a public meeting. Map cards used to quote each state's **newest** keyword
passage. They now quote it this way, server-side:

1. **Only real public meetings.** A recording Jev read as `government_other` (media briefings, ceremonies, academy
   graduations, interviews) or `not_government` (podcasts, news shows, streams) is never quoted. The reading is Jev's
   existing `meeting_kind` (transcript screen first, else the title-and-description screen), published per quoted
   recording as `public.meeting_video_kind`. A recording Jev never screened is still quoted, after the screened meetings,
   so no state loses its card for being unscreened. Title patterns ("Interview", "Candidate") were measured and not used:
   they also catch real meetings such as "City Council Special Meeting - Candidate Interviews". On the local warehouse
   (26 Nov 2026) the rule drops 131 of 18,045 topic-linked recordings and 56 of 1,859 data-center recordings; for
   Alabama guns, 12 of 386 (Montgomery police and mayor media briefings, a police academy graduation, the Athens
   interview, a podcast and a game stream). Jev has not screened 11,971 topic-linked recordings yet.
2. **Meetings where the public took a side first.** Topic stories (`GET /api/topics/{id}/states`, `newest`) pick, per
   state, the newest meeting where `topic_meeting_lean` reads the public as mostly opposed, mostly supportive or mixed;
   only when the state has none, its other meetings (screened meetings first), newest first. Each pick carries
   `public_stance` (`against`, `for`, `split`, `silent` or null, with the map's 0.7 threshold). The home data-center map
   and the Data Center Story's national map ask `GET /api/data-centers/meeting-mentions?quotes_per_state=3`: one passage
   per meeting, meetings where the public mostly opposed first (the only lean the maps serve), then newest. Counts are
   unchanged. Speakers' own words still come first on the home map.
3. **The card says where the public stood.** Under "In the meeting · `<title>`" a short line reads "Public: " and the
   topic's own position words from `web_app/src/utils/topicPositions.ts` (its "against", "for" or "Split" label, so a
   topic reworded there is reworded on the card too), or, when the reading found the public didn't speak on it, "Mentions
   `<topic>`; no public stance in this meeting". A meeting not read yet gets only "Mentions `<topic>`", with no claim
   about the public. A data-center passage (the home map and, since [#1265](https://github.com/getcommunityone/open-navigator/issues/1265), the Data Center Story's national and county maps) gets its "against" words or the no-stance line,
   and no line for the audit-only supported or mixed readings. The line never says "AI reading".

The quote stays a verbatim excerpt with the matched words marked, with the meeting title, date, place and recording
link. With the change the guns cards read: Alabama, Calera City Council, Feb 2, 2026 ("…where people are able to carry
firearms", public opposed); Texas, El Paso City Council, May 23, 2023 (split); California, Santa Monica City Council,
Aug 22, 2023, on a retail firearm sales ordinance (split). A serving copy without `meeting_video_kind` falls back to the
newest passage.

### What a meeting quote card shows (#1124)

A meeting passage's card on the story maps (the national dot map, the state's county map and the home map) adds three things from the record, each left out when the record has nothing ([#1124](https://github.com/getcommunityone/open-navigator/issues/1124)):

- **AI summary.** The meeting's own AI summary (`event_meeting.meeting_summary`), labelled "AI summary" and clamped to about three lines. It is shown as plain, escaped text. A meeting with no summary shows no block.
- **Open the meeting analysis →.** A link to the meeting page (`/meetings/<event_meeting_id>`), which has "How this summary was made". The link keeps the story's scope (`?state=&city=`). A recording that is not in `event_meeting` has no link.
- **The speaker, only when on record.** The card names a speaker as "First L.", with the recorded role, only when a counted public comment from the same meeting (`data_center_public_comment`) has a name and its whole verbatim quote (20 characters or more) is inside the passage's excerpt. If two different speakers match, no name is shown. There is no guess from timing. Otherwise the card keeps "In the meeting · `<title>`". The API also shortens any fuller name to "First L." (AGENTS.md, Privacy). **Changed 26 Nov 2026 ([#1231](https://github.com/getcommunityone/open-navigator/issues/1231)):** where no counted comment names the passage, the card names the person who introduced themselves just before it in the same recording ("my name is …", "I'm … and I live …", the chair's "our next speaker is …"). The match is the nearest introduction within about three minutes of speech, and both fragments of the excerpt must fall under it. An official of the meeting's own government is shown by name and title. Everyone else is "First L.", with the role "Resident" only when they said they live here. Speakers who say they are a student or under 18, and residents at school board meetings, get no name. No model is used. Method and limits: [Speaker names from self-introductions](../development/speaker-names-from-self-introductions.md).

The fields come from `GET /api/data-centers/meeting-mentions` as nullable `meeting_summary`, `meeting_url`, `speaker_display_name` and `speaker_role`. Each lookup is optional, so a database without `event_meeting` or `data_center_public_comment` leaves them null and the passages are still served. On the local warehouse (2026-11-26), 645 of 6,323 passages have a summary and 647 have a meeting page. Only 3 passages have a named speaker, because the public comment mart has 29 named comments and none of them has a timestamp. No transcript segment in `event_documents` carries a diarized speaker. More names need diarized transcripts (WhisperX speaker turns at each passage's start) or timed public comments.

## Which topics get a story

A story or a challenge needs meeting recordings or transcripts behind it. Figure-only data, such as census measures, is shown under Explore.

Every curated topic with at least one linked meeting has a live story at `/stories/<query_id>` ([#1133](https://github.com/getcommunityone/open-navigator/issues/1133)). The list is read at runtime from `GET /api/topics` (curated topics with a meeting count above 0, `utils/topicStories.ts`), so a topic added later goes live with no code change. `/stories/data-centers` stays on the Data Center Story (`DataStory`); every other slug is told by `TopicStory`, screen by screen in the same format as the Data Center Story since [#1224](https://github.com/getcommunityone/open-navigator/issues/1224) (see [Topic stories, screen by screen](#topic-stories-screen-by-screen-1224)); the map's quote for each state is a public meeting where the public took a side when there is one ([#1230](https://github.com/getcommunityone/open-navigator/issues/1230)). On the home **Browse topics** strip a tile is live when its topic has meetings, and selecting it shows that topic's story card above, keeping the place. Flock and license plate readers share one topic and one tile. **Starting a nonprofit** links to its guide. A tile whose topic has no meetings on record (Insurance shopping until #1079 has data) says "Coming soon". Bike lanes has its own curated topic (100007, [#1162](https://github.com/getcommunityone/open-navigator/issues/1162)) and goes live after the next seed and rebuild finds meetings for it. A curated topic with meetings that has no tile of its own gets a plain one, most meetings first, before the guides. At the end of a story, **Next story** walks the same live list. Within a story, a screen whose figures are not from recordings or transcripts (for the Data Center Story, sites on record and projects on record) is marked "For context" with its source named, and is never the story's headline claim. The opener's large counts lead with the transcript-based ones and show counts from other sources after them with their source.

Every topic story's map is the home box map with the same four-entry legend ([#1127](https://github.com/getcommunityone/open-navigator/issues/1127)). For topics other than data centers the colours come from the **AI reading of meetings** (`topic_meeting_lean`, [#1126](https://github.com/getcommunityone/open-navigator/issues/1126)), served by `GET /api/topics/{topic_id}/state-map` as distinct meetings per state, in each topic's own words since [#1200](https://github.com/getcommunityone/open-navigator/issues/1200): against (muted red, e.g. **Want limits on short-term rentals**, **Opposed the gun proposal**, **Against the courts**), for (teal, e.g. **Want to allow short-term rentals**, **Backed the gun proposal**, **For the courts**), **Split** (plum: the public spoke but was divided, or the AI could not tell which way) and **No AI reading yet, or the public didn't speak on it** (grey, darker = more meetings). The note under the map says what "for" means for the topic, and the data table adds a **Public didn't speak on it** column. A state's boxes are split in bands by those meeting counts, never by counted speakers, and the caption, hover card and data table say "AI reading of N meetings". Until the reading exists for a topic, the endpoint answers `available: false` and the map is grey with the note "No AI reading of these meetings yet; states show meetings only"; a failed request leaves the plain meetings map and claims no stance. Choosing a state (`?state=`) highlights it on the national map and narrows the whole story to it. At a state, the Overview draws the state's counties and towns since [#1349](https://github.com/getcommunityone/open-navigator/issues/1349) (next section); the box transition the Data Center Story has (#1195) is not drawn for topics.

On the home hero, **Start the story** and the next-story button stick to the bottom of the screen until their own place scrolls into view, so they are always reachable ([#1174](https://github.com/getcommunityone/open-navigator/issues/1174)). The desktop hover card ends with "Click to open the story for [state] →". Topic story cards (`GET /api/topics/{id}/states` `newest[]`) carry `speaker_display_name` and `speaker_role` from the same self-introductions (#1231), so a topic card can say who was speaking too. The map's cards prefer a named speaker's own words ("Rob D.", never a full surname): the home map asks `GET /api/data-centers/positions?per_state=3` for up to three quotes per state and side, and named speakers rank first.

### The topic county map (#1349)

Owner, 27 Nov 2026, on `/stories/water-fluoridation?state=AL`: "why do the locations of these meetings not show up on the map". Until then a topic story at a state drew the state's blank outline, because only data centers served meeting counts per government.

- **Where a meeting goes.** Each topic meeting is a recording (`topic_transcript_link.video_id`). Its government is the one the recording is filed under (`event_youtube_with_jurisdiction.jurisdiction_id`, one per video), and the `jurisdictions` mart gives that government's type, geoid and coordinates. A county government is drawn by its geoid. A city, town or school district is drawn as a ring at its coordinates, and its county is found on the map by point-in-polygon on the county shapes the map already loads, because `jurisdictions` has no city-to-county link (`county_name` is empty on cities).
- **The mart.** `topic_place_meeting` (gold, served in `public`): one row per (topic, government), PK `topic_place_meeting_id` = md5(topic_id|jurisdiction_id), FKs to `civicsearch_topic` and `jurisdictions`. It holds the distinct meetings and the AI reading of them (`topic_meeting_lean`, the same counts and thresholds as `/state-map`). A meeting counts only when its government is in `jurisdictions`, is in the same state as the topic link (a recording filed under another state's government is left out, so a town is never drawn on the wrong state), and is a county with a geoid or has coordinates.
- **The endpoint.** `GET /api/topics/{topic_id}/places?state=AL` returns `total_meetings` (the state's distinct meetings, the same as `/states`), `unplaced_meetings` (total minus the placed sum) and `by_place`, in the shape of the data-center map's `counts.by_place`: `jurisdiction_id`, `jurisdiction_name`, `jurisdiction_type`, `geoid`, `latitude`, `longitude`, `meetings`, and the reading as `speakers_against` / `speakers_for` / `speakers_neutral` (meetings read as the public mostly opposed, mostly supported or split; never counted speakers), `silent_meetings` and `disagreement_meetings`.
- **What the map shows.** `StoryCountyMap`, the Data Center Story's county map, with the topic's name in its title ("Water fluoridation meetings by county · Alabama"). Where some meeting was read, a county's dots are banded by the topic's own position words (for example **End fluoridation** and **Keep fluoride in the water**); otherwise counties are grey by meetings (**Meetings, no stance on record**). Hovering a county quotes one of its passages from What was said. Clicking a county or a ring opens the story at that town; topic stories are still counted by state, so the page keeps all of the state, highlights the town's county, and says the town on its own isn't available yet.
- **Meetings that can't be placed** are never spread or guessed: the line under the map says how many ("2 meetings couldn't be placed on the map and are not shaded."). When none can be placed, the outline above is drawn instead.
- **How many are placed** (local warehouse, 27 Nov 2026): water fluoridation 524 of 526 meetings (99.6%), short-term rentals 4,178 of 4,186 (99.8%), license plate readers 1,230 of 1,235 (99.6%), pickleball 3,988 of 4,014 (99.4%), guns 7,616 of 7,684 (99.1%). Alabama water fluoridation: all 22 meetings, across 10 governments. The unplaced remainder is almost all recordings filed under a government in another state than the topic link's.
- **The home card** at a state uses the same map, and a click opens the topic story at that town.
- **The Overview's left column** says where the topic came up once, in its headline. A subhead or lede that only restates it ("Where … came up at local meetings in …", or the generic "What local governments said about …, in the words said at the meeting.") is dropped (`web_app/src/utils/overviewLead.ts`); a lede with its own copy (guns, pickleball, short-term rentals) stays.

## Browse all topics: every major meeting topic, last year against this year (#1343, #1361)

`/browse-topics/all?state=&city=&show=&sort=` compares every major meeting topic in `civicsearch_topic` (both curated story topics and CivicSearch meeting topics, 95 topics total) in one animated dumbbell ([#1343](https://github.com/getcommunityone/open-navigator/issues/1343), [#1361](https://github.com/getcommunityone/open-navigator/issues/1361)). Each row is a topic: the hollow dot is the last full year, the filled dot is this year to date, labelled by its months (for example **Jan–Nov 2026**, through the latest dated topic meeting in the place), and the line between them is the change. Rows default to sorting by change, largest rise first (`Biggest rise`), or can be sorted by `Most discussed` (`?sort=latest`). Each value sits over its dot and the relative change is written at the end of the row with its sign (**+456%**, **−20%**). Rising rows are teal and falling rows ochre (the house theme's two data colours, a blue–yellow pair that stays distinct under red–green colour blindness), and the sign carries the direction without colour. The dots grow in and the line draws when the chart scrolls into view; under prefers-reduced-motion it is drawn in its final state. A topic filter (`?show=all|candidates|stories`) switches between **All major topics**, **Not yet a story** (rising or high-volume meeting topics without a story yet), and **Live stories**. Tapping a live story opens `/stories/<slug>?state=&city=`; tapping a topic without a story yet opens `/browse-topics?topic_id=<id>&state=&city=`. On a phone the rows use the compact dumbbell from [#1268](https://github.com/getcommunityone/open-navigator/issues/1268) (label and change on one line, values over the dots, no axis) and fit 360px with no sideways scroll.

**What the dots measure.** By default, the share of recorded meetings that discussed the topic: distinct topic meetings divided by all recorded (transcribed) meetings in the place that year (`recorded_meeting_year`). Recordings grew from 14,038 meetings in 2025 to 16,873 in 2026 nationally, so raw counts would show almost every topic rising; the share corrects for that. A toggle shows raw meeting counts instead, with a note that this year is not a full year.

**When a topic isn't compared.** A topic needs at least 5 meetings in each year (the shared minimum, `MIN_SCOPE_MEETINGS`), and the place at least 20 recorded meetings in each year (the period dumbbell's `MIN_RECORDED_MEETINGS`). Otherwise the topic is listed under **Too few meetings to compare** with its two counts, and topics with no tagged meetings in either year share one line; none of them is given a change. When one year recorded under a quarter of the other's meetings in the place, the note says so and asks the reader to read that year with care (the timeline's thin-year ratio, #1207).

**The place.** The eyebrow and the 📍 chip name the scope the numbers use (National, the state, or the city), with one-click links to broaden (city → **All of GA** → **National**), preserving the active `?show=` and `?sort=` controls. Browse Topics (**Compare all topics, last year against this year →**) and the home **Browse topics** strip (**Compare all**) link here with the place carried. It is its own route rather than the top of Browse Topics because that page opens on decision cards, and the chart wants the full width and a deep link.

**Data.** `public.topic_meeting_year` (dbt mart, `gold` → `public`, primary key `topic_meeting_year_id`, foreign key `topic_id` → `civicsearch_topic`) aggregates distinct recorded meetings per `(topic_id, state_code, jurisdiction_name, meeting_year)` across `data_center_meeting_mention` (for `data-centers`) and `int_transcript_keyword_topic` + `event_documents` (for every other topic — matching `topic_transcript_link` for curated topics and `>= 2` multi-word phrase hits for CivicSearch topics). `GET /api/topics/yoy?state=&city=&source=` (`api/routes/topic_yoy.py`) joins `public.civicsearch_topic`, `public.topic_meeting_year`, and `public.recorded_meeting_year`, returning `topic_id`, `slug`, `name`, `source` (`'curated'` or `'civicsearch'`), `has_story`, `year_a`, `year_b` (strings), `meetings_a`, `meetings_b`, `recorded_a`, `recorded_b`, `share_a`, `share_b` and `comparable`; the response adds `year_b_through`, `year_b_partial`, `thin_year`, `min_meetings` and `min_recorded_meetings`. `tests/test_api_topic_yoy.py` checks the numbers against the marts.

## Topic stories, screen by screen (#1224)

Owner, 26 Nov 2026: "All the stories should have horizontal scroll drill down with swipe like data center." Every topic
story (`/stories/guns`, `/stories/pickleball`, `/stories/water-fluoridation` and the rest) is now told one screen at a
time on the Data Center Story's screen machine (`components/stance/useStoryScreens.ts`), each screen drawn with the same
frame (`components/stance/StoryScreenFrame.tsx`), with `?screen=` deep links and the keys.

**Overview is the first screen** ([#1282](https://github.com/getcommunityone/open-navigator/issues/1282), owner, 27 Nov 2026): a story has no separate cover. It opens on Overview, with Back hidden. The points the cover used to carry (the Data Center Story's numbered points, its subhead and basis; a topic story's subhead, lede and notes) sit in Overview's left column under its headline, and the map is on the right. The big faded screen word is gone, so nothing sits behind the map or the Next button. `?screen=overview` and a plain link open the same first screen.

**Layout** (owner, 27 Nov 2026: "a right Next green button at bottom right always visible. The two buttons is
confusing."):

- **Close (×)** at the top right of the story's bar, the same box on every screen; it goes home keeping the scope
  (`/?state=CA`), and **Escape** does the same (`components/stance/StoryClose.tsx`). There is no "← Data stories" crumb
  and no "Showing: … · National only" row: the place changes only through the title's place blank.
- **One green Next →** fixed at the bottom right of every screen (`components/stance/StoryNextButton.tsx`). On a screen it
  goes to the next one; on the last screen it becomes a quiet **Done** that closes the
  story. There is no Start / Next story pair and no "Next story" button anywhere: readers pick the next story
  on home.
- **Back**: inline at the bottom of each screen's left column on a wide screen; at the left of the phone's bottom bar,
  beside the progress dots, from the second screen on.
- **Progress**: the segments in the top bar on a wide screen (each a button, "3 of 6: Who spoke"), the dots in the phone
  bar.
- `web_app/e2e/story-next.check.mjs` steps every screen at Pixel 7, iPhone 13 and 1440×900 (Next, a segment, a swipe) and
  checks Next and Close stay at the same spots.

| Screen (`?screen=`) | Shows | Left out when |
| --- | --- | --- |
| Overview (`overview`) | The caption (#1125) and the national state box map in the topic's AI-reading colours and position words (#1200); a state's boxes open the story for that state. | Never. |
| Over time (`timeline`) | The trend line with its milestone track and the period dumbbell (#1140). | No meetings on record in scope. |
| Who spoke (`positions`) | The public's position in the meetings the AI read, one bar per position in the topic's words (against, for, split, didn't speak on it), with the headline's conclusion (majority, split, or too few). Meetings, never counted speakers. | No AI reading served for the scope. |
| Companies (`companies`) | The platforms named in the record (topics with a companies list, today short-term rentals). | No company named in scope; topics without a list never have it. |
| What was said (`said`) | Meeting passages quoted from the transcript with the matched words marked, each with who spoke and the meeting's position (see "People and position on What was said" below); meetings where the public took a position first, then a vote or a named speaker, then **Mentioned in passing**; **Show more meetings**. | No meetings in scope. |
| Decisions (`decided`) | Decisions whose record mentions the topic, split into **Decisions on [topic]** and **Mentioned in passing** (see "Decisions: on the topic or in passing" below), each linking its meeting and its page, with **See all**. | None in scope. |
| Recap (`recap`) | The scope's counts and small text links on (every decision, Browse topics, all stories); Next becomes **Done**. | Never. |

A screen left out is not a step, a segment or a Next target, and the Overview says which ones and why ("Not in this story
for Ohio: decisions (none on record)."). While a screen's data loads it stays and says so; a failed request says it could
not be loaded. The single "unit matrix by who spoke" is not drawn for topics: the topic endpoints serve the AI reading as
counts per scope, not one record per meeting.

**Title controls** (owner, 27 Nov 2026): the place word in the title is the place control, and the topic is a control
that lists every live story (the Data Center Story and each topic story, never a coming-soon topic), the same list on
every story; choosing one opens it on its Overview with the place kept. With a state selected, the title names that state
from 5 meetings where its public spoke ("Alabama mostly opposes data centers."); see
[Story captions](../development/story-captions.md).

**Scope.** Topic stories are at state grain (`?state=`; city grain is #1186). Picking a city in the place dialog applies
its state, and the Overview says the city on its own isn't available yet, so the label never names a scope the data doesn't
have. At a state the title leads with the place.

**Titles and headlines** (owner, 2026-11-26): the header title is the short conclusion from the shared caption picker
(`pickCaption`, #1234), with no counts and no "AI reading" text; with nothing on record it reads "California has no
meetings on record about pickleball." Each screen's headline is a plain statement with no counts ("In California, the
public mostly wanted the pickleball courts.", "What was decided on pickleball in California."); the numbers sit in the line
under it. The Overview's headline says what the map shows and never repeats the header title.

**Swipe.** On a touch screen a quick, mostly sideways flick moves the story (left for the next screen, right for the
previous), through the same function as Next and the arrow keys
(`hooks/useSwipeNav.ts`). Vertical scrolling and scroll snap are untouched, and a flick that starts on a control, a dialog
or anything that scrolls sideways itself is left to it.

Design note: [Topic stories, screen by screen](../development/topic-story-screens.md).

### People and position on What was said (#1293)

Owner, 27 Nov 2026: "We need people and position." The Georgia water-fluoridation screen listed nine meetings newest first,
and its first card quoted staff converting a fluoride feed system with no person and no position. Each card now shows:

- **The meeting as the link.** Its name and date open the recording (or the meeting page when there is no recording), and
  on a phone the whole card is the tap target. **Watch the meeting ↗** and **Meeting page** stay as separate links. Topic
  passages carry no timestamp, so the recording opens at the start.
- **Who spoke, only from the record.** "Said by Amy N. · Resident" when the quoted passage's speaker introduced themselves
  (`meeting_passage_speaker`, #1231 / #1245); otherwise **Speaker not identified**. A second line names up to three people
  whose own words in that meeting matched the topic ("Also spoke on it: Tracy B., Lee K. and 2 more", from
  `meeting_comment.topic_ids`). Residents are "First L." at most (the API cuts any fuller name again); possible minors,
  staff and applicants, and everyone at a school-board meeting (a `school_district` jurisdiction, or a jurisdiction or title
  naming a school board, the same rule as `meeting_speaker_intro`) are never named. Officials matched to our officials
  data keep their name and title.
- **Position chips, labelled by source.** No per-speaker stance is published yet, so a chip is never the speaker's. The
  most specific real source is the meeting's AI reading (`topic_meeting_lean`, the map's thresholds): **Public at this
  meeting: …** in the topic's own words (for water fluoridation its five positions, such as "Oppose, each community
  decides", only when they agree with the lean's side), then **Council or board: …** from what the body did (`outcome_group`,
  the Votes screen's source: "Voted to keep or start fluoridation"). A meeting with neither gets no chip. A keyword false
  hit (`excluded_no_item`) has no public side and no vote.
- **Order and the summary.** With `sort=people` the list puts meetings where the public took a position first, then a vote
  or a named person, then the rest under **Mentioned in passing**, newest first within each, and a named person first
  inside a group. The line above the cards comes from the scope's real counts (`position_counts`): "Of 9 meetings: the
  public took no position at any of them. A council or board acted at 4 (4 voted to keep or start fluoridation). 5 only
  mentioned it in passing."

API: `GET /api/topics/{topic_id}/meetings?sort=newest|people` adds, per item, `speaker_display_name`, `speaker_role`,
`commenters`, `commenter_count`, `public_stance`, `public_position`, `vote`, `position`, `position_source`
(`speaker` | `meeting` | `vote`, or null), `in_passing` and `meeting_url`, and on the first page `position_counts`. All are
optional and the default order is unchanged; a serving copy without the lean, speaker or comment tables gets the plain list.

On the local warehouse (27 Nov 2026), across the 17,645 meetings of the 19 topic stories (data centers has its own story):
4,277 cards (24%) name a person (705 the quoted speaker, 4,057 at least one commenter on the topic), 1,825 (10%) carry the
meeting's public position and 2,807 (16%) a council or board action (2,169 of them as the only chip), so 3,994 (23%) have a
chip; none comes from a per-speaker stance. 10,838 (61%) are mentioned in passing. Georgia water fluoridation: 9 meetings, the public took no position at any (all read as "didn't speak on
it"), 4 have a council action (voted to keep or start fluoridation), none names a speaker, 5 are mentioned in passing.

The Data Center Story's Meetings screen does the same in its recording popup: the speaker as served and the
**Public: …** line from `data_center_meeting_lean` (only the readings the maps serve).

### Decisions: on the topic or in passing (#1293)

Owner, 27 Nov 2026, on `/stories/guns?state=AL`: "This looks suspicious on all of these. We need drill-downs to the
meetings." The list showed "Capital Improvement Plan Funds Reallocated from Firearms Training Project" (a budget move) and
"Firearms Sale Permit Granted to Dunham's Athleisure Corporation" as decisions on gun control. A keyword hit is not a
decision on the topic, so `GET /api/topics/{topic_id}/decisions?state=&city=&limit=` splits the decisions whose headline
or statement matched the topic's keywords, with deterministic rules and no model call (`api/routes/topic_relevance.py`):

1. **Off-topic wording first**: a budget move, a purchase, training, an award, a crime report, ShotSpotter, a tool called a
   gun. Always **Mentioned in passing**.
2. **Wording that names the policy** the topic's question asks about (`llm.typesafe.topic_lean.TOPICS`, its subject,
   excludes and outcomes; `utils/topicPositions.ts`): "prohibiting felons from possessing firearms", an assault-weapons
   resolution, a shooting-range rezoning, "fluoridation", "short-term rental". **Decisions on [topic]**.
3. **Wording that can be either** (a gun store's sale permit, a licence, a special use): on the topic only when the
   meeting's reading says the public took a side there. The body approving a store's permit is not enough.
4. **Anything else**, and every decision of a topic without rules: on the topic only when the meeting's reading says the
   body acted on the topic. If it can't be classified, it is in passing.

Each panel takes its form from the shared display rule (`pickDisplay`, [#1289](https://github.com/getcommunityone/open-navigator/issues/1289)): the cards for a handful, otherwise a count sentence with the newest cards under a fold, so the matched passage is never dropped. The screen's line gives the real totals ("3 decisions on gun control; 6 more mention guns in passing."). Each card's title
opens the decision page (`/decisions/:id`) and its meeting name and date open the recording (decisions carry no timestamp)
or the meeting page; **Meeting page** and **Decision details** are separate links and the whole card is the tap target.
Alabama guns on the local warehouse: 9 decisions, 3 on gun control (the Tuscaloosa legislative proposals on firearm
possession), 6 in passing (the Shelby County reallocation and the Wetumpka sale permit among them).

The Data Center Story's Decisions screen uses the same rules on `data_center_decision` headlines: its squares group into
**On a data center** and **Mentioned in passing** (`counts.on_topic`, `counts.in_passing` on
`GET /api/data-centers/decisions`), a square opens the decision page, else the meeting page, else the recording, and the
screen's line says how many are on a data center.

### Who supported and opposed each decision (#1320)

Owner, 27 Nov 2026, on the Guns Decisions screen: "still can't see who is saying this." Each decision card now lists the
people the decision record names, then the recorded vote:

- **Supported by: John Faile (City Councilor), Joseph Eatmon, Sr. (City Councilor), … +5** from
  `event_decision.competing_views.dominant_view.held_by`; **Opposed by: …** from `counter_views[].held_by`. When the record
  names supporters and lists no counter view, the card says **No opposition recorded**; a counter view with no names says
  **Opposition recorded; no names on record**. Others the record says spoke on the item (`decision_speakers`) follow as
  **Also spoke: …**. **Vote: 7–0** comes from `vote_tally` when it has a yes count.
- The names come from speaker slugs such as `john_faile_councilor_tuscaloosa` (`api/routes/decision_people.py`).
  Officials are public: a slug with an official title (councilor, mayor, commissioner, chair, chief, clerk, ...) or a name
  matching exactly one current official of the decision's own government (`person_government`, "[place] Government", same
  state) is shown by full name, with the official record's title, else the slug's title. A title heard only as a form of
  address stays in the name with no role ("Chief Sky"). Everyone else is "First L." with no role, and only when a first and
  last name are on record. Students and minors are never shown, residents are never shown for a school-board decision, and
  a slug whose name can't be told from a description or a place is left out.
- `GET /api/topics/{topic_id}/decisions` and `GET /api/data-centers/decisions` return `supported_by[]`, `opposed_by[]`,
  `spoke_on_it[]` (each `{name, role, kind: official | resident}`), `supported_view`, `opposition_recorded` and
  `vote_yes` / `vote_no`. On the Data Center Story the lines sit under each decision in the list.

Local warehouse, 27 Nov 2026: of 599 decisions behind the 19 topic stories, 306 (51%) name at least one person (248 a
supporter, 64 an opponent, 59 another speaker; 248 name at least one official), 157 say no opposition was recorded
and 231 (39%) show a vote. Of 49 data-center decisions, 16 name someone; Alabama's 10 name no one, because their records
carry no `held_by`.

## The heading is a sentence

The story is headed by the longer "What did local meetings in [place] say about [topic]?". The two blanks are the controls: the place blank opens a dialog with one search box for a city, county or ZIP code (pick a suggestion and it applies and closes), one-click **The United States** and **All of [state]**, **Use my location**, and an "Or pick a state" list. It has a close button, and Escape or a click outside closes it too; on a phone it is a bottom sheet. A county has no city grain here, so picking one applies its state and the dialog says "Stories are told by city or state; showing all of [state]". The lookup uses the same geocoder helpers as the home page location search (`web_app/src/utils/resolvePlace.ts`), picks carry the geocoder's own city name so nothing has to be typed exactly, and the choice is kept only in the address (`state` and `city`), never in the saved site-wide location, the topic blank lists the topics that have a story (today only data centers). They are underlined inline controls you can reach with the keyboard, named "Place" and "Topic", and at least 44 pixels tall on a phone. Because the story is built from meeting records, the screens that are things said in meetings (concerns, job claims, passages, agendas, decisions, company-hosted meetings) carry the sentence; sites and projects are marked "For context". The component is `web_app/src/components/stance/SentenceHeading.tsx`; it has the same props as the shared story component being built elsewhere, and the two should be merged.

## The hub

`/stories` is the index of every data story (#1203). Every link labelled **All data stories** opens it: the Browse topics "all" arrow on the home page, and the **All data stories** link at the end of the last story (`nextStoryLink` in `web_app/src/utils/storyNav.ts`). The page is `web_app/src/pages/DataStories.tsx`; the card list is `storyIndexCards` in `web_app/src/utils/storyIndex.ts`, with tests.

- **Header and place.** The heading names the place every card is read for: "All data stories · National", "All data stories · Alabama", "All data stories · Tuscaloosa, Alabama". The place is the URL's `?state=&city=`. **Your place** opens the place picker (`PlaceControl`), and **All of [state]** / **National** broaden in one click. Every Start link carries the place.
- **One card per story, in the home order.** Data centers first, then the topics in the home Browse topics strip's order (`buildTiles` in `web_app/src/utils/homeTopicTiles.ts`), then any other live curated topic, most meetings first. Guides (starting a nonprofit, insurance) are not meeting stories and are not listed.
- **A live card** names the topic, then its title from the shared caption picker (`pickCaption`), the same title the home card and the story show for the place, then the meetings on record for the place from the caption facts ("71 meetings on record in Alabama"), then **Start the [topic] story →**. A count that is not on record is not shown (never a zero); while the facts load the title's place is held so the question does not flash first.
- **Coming soon.** A topic with no meetings yet (no curated topic with linked meetings) reads "Coming soon" with no link, as on the home strip. Until the topic catalog answers, only data centers is listed; if it fails, the page says so rather than calling every topic coming soon.
- **The data center record.** The former data-center hub's counts row and **Who spoke for and against** are kept as the Data centers card's detail, **What the data center records cover**, loaded only when opened. The rules for those figures are below. Every count is the endpoint's own whole-scope total, a count that is missing or zero is left out, and under a city a count the source cannot narrow to a city (sites) is labelled with its own, wider place.

### Who spoke up

**Public and officials, and where they disagree (#1330).** The screen opens with who took which side: "Public: 6 against · 2
split (8 meetings)" and "Officials: … (N meetings); recorded votes …; named supporters N · opposers M". Where officials sided
against the public it headlines that ("In Georgia, officials sided against the public in 11 of 27 meetings where both took a
side."), and the count opens those meetings with their recordings. The hand-counted figures below are labelled "Speakers
counted by hand". Details: [Story captions](../development/story-captions.md) (#1330).

When the positions table is loaded, the Data centers card's detail on `/stories` shows what people said about data centers at local meetings in the place in scope, as five figures and one chart (under the power/water/land hook). The story's own **Who spoke up** screen always has this block:

| Figure | What it counts |
| --- | --- |
| spoke for | Public speakers who asked the body to approve a data center item |
| spoke against | Public speakers who asked the body not to |
| asked a question | Public speakers who only asked questions |
| votes for | Yes votes on data center decisions that recorded a tally |
| votes against | No votes on those decisions |

The chart has one mark per speaker, grouped and headed by what they did ("Spoke against · 23 speakers · 56%"). Each group has its own colour and its own shape, so colour is never the only cue: teal squares for, amber diamonds against, open squares for a question, and short grey bars for speakers who took no side. When there are more than 240 speakers one mark stands for several, and the line under the chart says how many ("Each dot is 10 speakers; the last dot of a group is what is left over."). One line under it says what is counted and where: "Speakers at local meetings in Alabama where a data center item was discussed. From 6 meetings and 3 decisions with a recorded vote."

Only comments about the data center item count. A comment on another item of the same meeting never does. The rule, and what it misses, is in [Who spoke up about data centers](../development/data-center-who-spoke-up.md).

A figure with no data behind it is never shown as zero:

- When no decision in scope recorded a tally, both vote figures read **not recorded**, with "Votes were not recorded for these decisions."
- When no public comment on a data center item is on record for the place, the three speaker figures read **not recorded**, with "No public comment on a data center item is on record for these meetings."
- A real zero beside real counts stays zero (nobody spoke for, eleven spoke against).
- Until the table behind these figures has been built in the database, the story screen is one quiet line, "Who spoke for and against is not loaded yet."; the `/stories` detail omits the block entirely so the care-first hook and Start stay in view (#962).

The figures come from `GET /api/data-centers/positions?state=&city=&limit=`, which sums the dbt mart `data_center_meeting_position` for the place and returns a few of the speakers' own words on each side from `data_center_public_comment`. The block is `web_app/src/components/stance/PositionsBlock.tsx`; its figures, caption and "not recorded" rules are `positionFigures` and `positionsCaption` in `web_app/src/utils/dataStory.ts`, with tests.

### Tap a number to see the records behind it (#1288)

Every figure on the **Who spoke up** screen that has records behind it is a button: tap it (or press Enter on it) and the list of those records opens. On a wide screen the list opens inline under the figures; on a phone it is a bottom sheet over the screen, with a **Close** button, a tap on the dimmed page or Escape to close it. The list is for the place in the URL (`?state=&city=`), the same scope as the figure, and its header says that scope. It loads 25 rows at a time ("Show more (25 of 60)") and ends with "All 60 shown."

| Number | The list | Endpoint |
| --- | --- | --- |
| spoke for / spoke against / asked a question | Each counted speaker: their words verbatim, with the data center words marked; "First L." when the name was heard; the place and date; **Watch this moment** at the timestamp; and why the comment counts ("Counted because the decision it was on names a data center: …") | `GET /api/data-centers/speakers?side=for\|against\|question&state=&city=&limit=&offset=` |
| votes for / votes against | Each data center decision with a recorded tally and at least one vote on that side: its headline (linking to `/decisions/:id`), the tally, the outcome, the place and date | `GET /api/data-centers/vote-decisions?side=for\|against&state=&city=&limit=&offset=` |
| the public comments line ("60 public comments at 10 local governments…"), **Mention AI**, **Name &lt;company&gt;** | Each public comment segmented from our captions that the count includes: speaker "First L." when known, the place and date, **Watch this comment** at its start, and the keywords it matched | `GET /api/data-centers/comments?year=&state=&city=&ai=&company=&limit=&offset=` |

The rule: **the list adds up to the number on the tile.** Each endpoint counts with the filter the figure's own endpoint uses (`/positions` scopes on `data_center_meeting_position`; `/comment-metrics` on `data_center_comment` with its `_where`), and pytest checks the filters are the same. A speaker figure counts rows, so the list has that many rows. A vote figure counts votes, not decisions: "8 votes for" opens "8 votes for in 1 decision", and the tallies listed sum to 8.

What doesn't open:

- A figure that is 0, "not recorded" or "—" is plain text: there is nothing to list.
- The caption comments have **no quote**. `meeting_comment` stores no comment text, on purpose (privacy by construction, #1233), so the list links to the moment in the recording instead, and says why. A comment the segmenter flagged as a possible minor is still listed, so the count adds up, but with no name, no link and no keywords.
- The overview's row of large counts (meetings, passages, agendas, jobs claims, sites, projects) and the topic story's position bars don't open yet: their endpoints return a capped list with no paging, so a list could stop short of the number. That is follow-up work, #1292.

The buttons and the list are `web_app/src/components/stance/KpiDrill.tsx` (`DrillValue`, `KpiDrillSheet`), used by `PositionsBlock.tsx` and `CommentMetricsBlock.tsx`; the client is `web_app/src/api/storyDrill.ts`; the routes are `api/routes/data_center_drill.py`.

## The Data Center Story

Up to eleven screens, in this order (a chart screen with nothing on record for the place is left out, so "N of M" counts only the screens shown). Each has a short word as its header (never a number), and each progress segment in the top bar is named after its screen ("3 of 11: Sites"). The id is what `?screen=` carries. The story opens on the record, not on the question (#950).

| Screen | Word | Id | What it shows |
| --- | --- | --- | --- |
| Opener | Overview | `overview` | A dot map of the country: each state's dots shaded by its real number of meetings where a data center came up, nationally (none stays grey). Hover or choose a state to read its count; clicking a state narrows the whole story to it (`?state=`). In a state or city scope that state stands out and the rest are muted but keep their own counts; clicking it again broadens (city → state → country), and **United States** goes straight to the country. A data table lists every state with a count. In a state or city scope the map is that state's counties instead, like the Census map's state drill-down, in the home box map's colours: where its governments have speakers on record, a county's dots are split in bands by the real counts of those who spoke against, for, asked a question or took no side; a county with meetings but no stance on record is grey, light to dark by its real meeting count; a county with none takes the empty colour, and the legend matches the home map's ([#1106](https://github.com/getcommunityone/open-navigator/issues/1106)). A county government counts by its geoid; a city, town or school district is placed by its coordinates and drawn as a ring. Hovering a county quotes one of its passages and gives its stance counts, and the data table lists counties with their governments. A government that can't be placed is named under the map, not shaded ([#1039](https://github.com/getcommunityone/open-navigator/issues/1039)). Each ring's government is named beside it in the Data Explorer's label style (dark text, white halo), largest meeting counts first, and a label that would overlap one already drawn is left out; a county government is named at its county's centre only when that spot is free. At a state or city scope the Overview headline says which way speakers leaned once at least as many are on record as the national headline needs (10): two thirds or more against reads "Arizona pushed back: 11 of 12 speakers spoke against data centers.", two thirds or more for reads "… welcomed data centers …", otherwise "… was split …"; the meeting count moves to the line under it, and with fewer speakers the neutral count stays ([#1115](https://github.com/getcommunityone/open-navigator/issues/1115)). On a phone the maps say **Tap** instead of **Hover**, and tapping a county selects it like hovering does ([#1057](https://github.com/getcommunityone/open-navigator/issues/1057)). Then the row of large real counts ([#970](https://github.com/getcommunityone/open-navigator/issues/970)) |
| Who spoke up | Who spoke up | `voices` | The five figures, one dot per speaker, and up to three of the speakers' own words on each side, each linked to the moment in the recording |
| Where they are | Sites | `sites` | Data center sites by status (one dot per site) |
| How they grew | Over time | `over-time` | For context ([#1348](https://github.com/getcommunityone/open-navigator/issues/1348)): a map of data center sites by the year of their earliest real date, a year slider that plays from the first year to the last projected one, a stacked strip of the running total by phase per year, and a card for the site tapped. See [Data centers over time](#data-centers-over-time-1348) |
| What is proposed | Proposals | `projects` | Projects by status (one dot per project) |
| What is promised | Promises | `jobs` | Jobs claims by phase (one dot per claim) |
| What is raised | Concerns | `concerns` | A dumbbell ([#1209](https://github.com/getcommunityone/open-navigator/issues/1209)): in a state or city, one row per concern, hollow dot = its share of national concern mentions, filled dot = its share of the place's, the difference in percentage points on the right (a fall in the warning colour), sorted **By [place]**, **By difference** or **Nationally**. Nationally there is one dot per concern, its share of all mentions: the records count objections per area, not per concern, so there is no second value to compare. Concerns with fewer than 2 mentions in the place are left out and the note names them. **Show data table** lists every row |
| When it comes up | Meetings | `meetings` | Meeting passages by year (one dot per passage). Hovering or focusing a dot previews the recording's thumbnail, title, place and date; clicking it (or Enter / Space) plays the recording in a dialog from the quoted moment. Nothing loads from YouTube before the hover, and the player exists only while the dialog is open: Escape, Close or a click outside removes it and returns focus to the dot ([#972](https://github.com/getcommunityone/open-navigator/issues/972)) |
| What is on the agenda | Agendas | `agendas` | Agendas for upcoming and past meetings |
| What was decided | Decisions | `decisions` | Decisions on data center items, debated or taken up without debate (one dot per decision, titled with its outcome as recorded); a debated one links to its page, one without debate to the meeting recording. "Not loaded yet" when the table isn't in the database ([#933](https://github.com/getcommunityone/open-navigator/issues/933)) |
| Where people gather | Gatherings | `gatherings` | Company-hosted meetings by kind |
| Your answer | Your answer | `verdict` | After the record: the topic question, how readers answered, then the challenge |

### Data centers over time (#1348)

The **Over time** screen (`?screen=over-time`) answers "how many data centers are there here, and since when?" from
`GET /api/data-centers/sites-timeline?state=`, backed by the dbt mart `data_center_site_timeline` (one row per site, PK and
FK `data_center_site_id`).

- **Only real dates.** A site appears in the year of its earliest date on record: the US Data Center Registry's
  announced date (it publishes day, month or year-only dates; staging now keeps the year of all three) or Epoch AI's first
  dated timeline row. The registry publishes no opening or completion date. A site with no date is never placed at a
  guessed year: the footnote counts them by status ("60 sites have no date on record …"). Coverage on 27 Nov 2026: 728 of
  2,379 sites have a date: 649 by a registry announced date (217 to the day, 322 to the month, 110 year only) and 79 by
  Epoch's first dated report. All 96 Epoch sites have an operating year, 20 of them projected (2027–2028). 2,307 sites have
  coordinates.
- **Phase in a year.** An Epoch AI site is proposed before its first dated row, under construction from it, and operating
  from its first row with a building operational; a year after this one is Epoch's projection and the screen says
  "projected". A registry site keeps its status today, because the registry has no history. The per-year totals are
  counted in SQL (`PHASE_SQL` in `api/routes/data_center_sites_timeline.py`); the dots use the same rule
  (`web_app/src/utils/siteTimeline.ts`), and a shared test fixture keeps them equal.
- **Drawing.** Operating, under construction and cancelled sites are filled dots in their colour; proposed (planned) sites
  are outlined and dashed, and hatched in the strip. A site the source gives no coordinates is counted in the strip and
  named in the footnote, not mapped.
- **Motion.** The years play once when the screen comes on view. Under `prefers-reduced-motion` there is no autoplay and no
  pop-in: the slider and the ‹ › buttons step through the years.
- **Small counts.** The shared display rule (`utils/displayFit.ts`) decides: 1–5 dated sites (or under 20 with one status)
  are a plain list with their year, status and source link, not an animation. A place with no dated site drops the screen.
- **Scope.** Sites narrow by state only, so a city's story shows its state and the screen says so.

### Recording coverage (#1348)

A story's counts are counts of our recordings, and some states have few. Under the basis line on the Overview and the
home hero, a small line states the scope's recording coverage from `GET /api/coverage/recorded-meetings?state=&city=`
(`recorded_meeting_year`): "From recordings of 29 Florida local governments (1,035 meetings). Many Florida governments
aren't in our recordings yet." Phones show the short form ("Recorded: 29 FL governments, 1,035 meetings."). It renders
nothing until the real counts load. There is no "29 of N": the `jurisdictions` mart counts census places, census-designated
places included, as cities (Florida: 956 "cities" against about 411 municipalities), so it is not a reliable count of local
governments. A denominator can be added once a Census of Governments count is loaded.

### Start, short titles, swipe and the phone Back (#1234, 26 Nov 2026)

- **Start opens the story on Overview** (since #1282 there is no cover, so a plain link opens it too). Every link that already means "start" (home's **Start the data center
  story**, the home topic cards' Start, the **Start** on each `/stories` card) goes to `/stories/<topic>?…&screen=overview`
  (`storyStartHref` in `utils/storyNav.ts`), so the reader lands on the Overview and does not press Start twice. A plain
  link (a shared URL, the topic picker, **Next story**) still opens the cover. The home map's drill-down keeps its
  navigation state (#1213). `?screen=<id>` deep links open that screen, and a progress segment pressed while the place's
  data is still arriving re-aims at the screen it names once the page settles (#1208).
- **Titles are the short conclusion only** ("America hates data centers."), with no counts and no "AI reading" text;
  at a place whose own reading is too thin, the title is the broader conclusion and the line under it starts with the
  place, which is the place control. The Overview never repeats the title. Details, wording and before/after:
  [Story captions](../development/story-captions.md#decision-26-nov-2026-1234-the-title-is-the-short-conclusion-only-no-ai-reading-text).
  This replaces the title examples in the rules below (they keep their order and thresholds).
- **Swipe between screens on a touch screen** (owner: "It should swipe left to toggle"): swipe left = next screen (on
  the cover, start), swipe right = previous. It needs a mostly sideways move (50px or more, 1.5 times more sideways than
  vertical, within 0.8s), so scrolling up and down never turns a screen, and it is off inside maps, charts, the place
  dialog and form fields (`useSwipeNav` in `web_app/src/hooks/useSwipeNav.ts`, shared with the topic stories). The git
  history shows no earlier sideways swipe in the story (the phone has moved by vertical scroll snap since #921), so this
  is new behaviour, not a restored handler.
- **The phone bottom bar has Back** (owner: "On phone back button is missing"): a round 48px ← left of the progress,
  named "Back: [previous screen]", hidden on the cover and the first screen. Desktop keeps the inline Back.
- **Close top right, Next bottom right, nothing else** (decision 27 Nov 2026; owner: "I think a right Next green button at
  bottom right always visible. The two buttons is confusing." and "This is confusing. We should have consistent Close in
  top right, probably move change state elsewhere, have Next in bottom right and move Next story somewhere super subtle
  so it doesn't cause this. Just make Close go back to home and pick next story."). This reverses #1199's removal of the
  × and replaces its Start-only cover:
  - **Close (×)** sits in the top-right corner of the story's sticky bar on every screen, 44px, named "Close story"
    (`StoryClose.tsx`, through `ScopeBar`'s `close` prop; shared with the topic stories). It goes to the home page with
    the place kept and the same story card shown (`/?state=&city=[&story=]#data-stories`, `storyCloseHref`). Escape
    closes too, unless a dialog is open.
  - The bar drops **← Data stories** and the **Showing: [place] · National only** row. The title's place control
    ("[Texas ▾] hates data centers.", or the subhead's when the title names a broader place) is the page's one place
    switcher.
  - **One green Next →** is fixed at the bottom right of the window on every screen, desktop and phone (inside the
    safe-area insets, 48px tall; `StoryNextButton.tsx`, shared). On the cover it starts the story (landing on the
    Overview); on a screen it goes to the next screen. On the last screen it is a quiet outlined **Done** in the same
    place, which closes the story: the story ends there. The cover's **Start / Next story** pair is gone, the screens'
    inline Next buttons give way to it (Back, Skip and **See every data center record** stay) and the floating bar
    (`FloatingNext`) no longer shows on the story. The page leaves 96px under its last content on a wide screen (the
    phone bar's height on a phone), so it never covers anything; on a phone it sits at the right end of the bottom bar,
    which keeps Back and the progress dots.
  - **Next story** is gone from the cover and the screens; after the last screen there is at most a small plain-text
    link, "Another story: Guns". The home page is where readers pick the next story: the home story cards keep one
    primary **Start the [topic] story →** and no Next story link.
  - `e2e/story-nav.check.mjs` (1440x900) and `e2e/story-flow.check.mjs` (Pixel 7, iPhone 13, 1440x900) check Close at the
    same top-right box and Next at the same bottom-right box on the cover and every screen, Done on the last screen, and
    that Close and Escape go home with the place kept.

### The title states the place's strongest statement (#993, #1125)

**Votes, speakers and the topic control (#1290).** A recorded vote counts by which way it went for data centers (a passed
moratorium is against), and the votes lean a way only with two thirds of the decisions. Where our captions hold public
comments but no side is counted, the page says so ("no speaker’s side is recorded …") and the **Who spoke up** figures show a
dash, not 0. The topic control is the noun in the title ("Not enough recorded activity on [data centers] to say.", "America
mostly wants [water fluoridation] ended."), never in brackets. On a phone every screen fits above the bottom bar; what doesn't
fit waits behind **More on this screen**. Details:
[Story vote direction, speaker sources and phone fit](../development/story-vote-direction-and-phone-fit.md).

The story's title, and the caption on each **Browse topics** tile on the home page, is the strongest statement the record
supports for the topic and the place in scope (`?state=&city=`), with the place and topic still clickable on the story. The
caption picker (`web_app/src/utils/storyCaption.ts`) reads `GET /api/topics/{topic}/caption-facts` for exactly that scope
and tries, in order:
0. **The place's conclusion, in the topic's words** ([#1200](https://github.com/getcommunityone/open-navigator/issues/1200)).
   Once enough meetings where the public spoke have an AI reading (50 nationally, 10 in a state, 3 in one place), the
   title states the majority position with the count: **"In Ohio, most meetings that took up gun control favored gun
   limits: 41 of 63 where the public spoke (AI reading)."**, **"America hates data centers: the public was
   against them in 283 of 341 meetings where it spoke (AI reading)."** ("hates" only for data centers, Flock and license
   plate readers, and pickleball), or **"Ohio is split on …"** when no side has more than half. A place too thin of its
   own names the broader scope that has a conclusion. With too few readings the rules below apply, and the line under
   the title says how many meetings have a reading so far ("20 of 7,623 meetings have an AI reading so far; …"). The
   words come from `utils/topicPositions.ts`; see [Story captions](../development/story-captions.md).
1. **"[America] hates [data centers]."** when the public was read as confidently against in enough meetings (an AI
   reading: at least 50 nationally, 10 in a state, 3 in one place) or the counted speakers pass the headline's gate
   (against at least twice for, at least 10 speakers). "Hates" is only for data centers, Flock and license plate readers,
   and pickleball; every other topic says plainly what the AI reading found, on the same counts: **"In 81 meetings, the
   public mostly opposed water fluoridation."**, or in a place **"In 12 meetings in Arizona, the public mostly opposed
   short-term rentals."** (gun control: "the public mostly opposed local gun-control measures"), and leads with "is divided" instead when that passes too
   ([#1182](https://github.com/getcommunityone/open-navigator/issues/1182),
   [#1190](https://github.com/getcommunityone/open-navigator/issues/1190)). The basis line under it reads "In 283 meetings
   across 32 states, the public mostly opposed data centers (AI reading of each meeting's transcript)." No title, legend
   or hover card says "leaned": the owner found it unclear (#1190).
1a. **The broader scope the map colours** ([#1182](https://github.com/getcommunityone/open-navigator/issues/1182)). When the
   place's own AI reading is too thin for rule 1, the title says what the map beside it shows: the nearest broader scope
   whose reading passes rule 1 (the state, then the country), named, with the place's own count after it. At
   `?state=AL&city=Tuscaloosa` the home title reads **"America hates data centers; Tuscaloosa, Alabama brought them up in
   2 meetings."** (Tuscaloosa has no confident public-against meeting and Alabama 6, under the state floor of 10), and the
   basis states the place's own reading truly: "Of Tuscaloosa, Alabama's 2 meetings with an AI reading, none had a public
   mostly opposed." (or, for Alabama, "Of Alabama's 71 meetings with an AI reading, 6 had a public mostly opposed, under the
   10 a title of its own needs."). A topic without "hates" reads the same way: "Across America the public mostly opposed
   water fluoridation; Tuscaloosa, Alabama brought it up in 2 meetings." A state or national claim is
   never put under a city label without naming its scope. The broader readings come from `wider` on caption-facts.
2. **"[America] is divided on [data centers]."** when officials sided against the public in at least 10 meetings (an AI
   reading; the basis says "In 23 meetings across 10 states, officials backed data centers while the public pushed back
   (AI reading).") or counted speakers split with both sides substantial.
3. **Volume with state differences.** "[California] took up [short-term rentals] in 570 meetings, more than any other
   state.", or for a near tie "California and North Carolina took up guns most: 659 and 585 meetings."; "...the 2nd most of
   any state."; for a city "...more than any other place in Florida.". There is no per-resident claim: meeting coverage
   varies too much by state.
4. **Plain volume.** "[Florida] took up [short-term rentals] in 47 meetings."
5. **The question**, when nothing is on record. Guides with no meeting record (starting a nonprofit, insurance) always
   show their question, and their tile keeps its blurb.

The home story card uses the same title. No title or basis line ever states a zero.

The home story card fits one laptop screen ([#1176](https://github.com/getcommunityone/open-navigator/issues/1176)). Its
title is at most about 46px (three or four lines beside the map; a two-clause title over 60 characters is set at about
36px), and right under the subhead and basis line come the topic-named **Start the [data center] story for [place] →**
(national: no place; `storyStartLabel` in `storyCaption.ts`, [#1182](https://github.com/getcommunityone/open-navigator/issues/1182))
and **Next story: [title] →** (the same `nextStoryLink` as the end of a story, carrying the place),
then the map hint, "Pick a state on the map to open its story." (it said "Showing Tuscaloosa, Alabama." first until
[#1206](https://github.com/getcommunityone/open-navigator/issues/1206): the title's place control now names the scope).
Every topic card has Next story, not only data centers.

**The place in the home title is a place control** ([#1206](https://github.com/getcommunityone/open-navigator/issues/1206);
owner, 26 Nov 2026: "This was better when there was a subtle drop down to choose national or state to change location in
title."). On every home story card (data centers and each topic story) the place in the title is a subtle inline control,
in the title's own font with a dotted teal underline and a small ▾: **"[America ▾] hates data centers."**,
**"[Tuscaloosa, Alabama ▾] brought up …"**. In the broader-scope title (rule 1a) the control is the place the reader
chose, the second place: **"America hates data centers; [Tuscaloosa, Alabama ▾] brought them up in 2 meetings."** A
national title whose place is not the country (rule 3 naming the leading state, or "In 81 meetings, the public mostly
opposed …") is led by **"In [the United States ▾], …"**, so the title always names the scope in effect and stays one
sentence. The words are the shared caption's (`pickCaption` / `captionText`), unchanged; `splitCaptionAtPlace`
(`web_app/src/utils/captionPlace.ts`, with tests) only says where the place sits in them. The control opens the story
pages' place dialog (`PlaceControl`, `themeClassName="home-place"`, styles in `web_app/src/styles/home-place.css`): place
search, one-click **The United States** and **All of [state]**, **Use my location** and a state list, as a bottom sheet
on a phone. A pick changes the home scope the way the header's place control does (`usePlacePick`): a city or a state
becomes the saved location and the home level follows it (City or State), so the header label, the title, the map
highlight and the Browse topics captions move together; **The United States** sets the home level to National and keeps
the saved place (as the level menu's National does), so the header still names your place. On a phone the control stays
inline; its tap target is at least 44px tall, drawn outside the text so the title's line height does not change.
The map is capped at 60% of the screen height so it never pushes the card below the fold. At 1366×768 the buttons and
the scope line are in view for the national and a city scope, and on a phone the buttons stack full width.

**The same two buttons open every story** ([#1182](https://github.com/getcommunityone/open-navigator/issues/1182)). The
stories hub's button names its topic too. Since #1224 (owner, 27 Nov 2026) a topic story's cover has no buttons of its
own: its one green Next at the bottom right starts the story (see "Topic stories, screen by screen"). On the Data Center Story the subhead, basis line, both buttons and the numbered points are
the story's opening screen, under the sticky title and progress bar and in normal flow, so they scroll away and the
sticky bar shrinks to the title and progress on every later screen; **Start** goes to the Overview. The buttons share
`web_app/src/styles/story-actions.css` (`.home-story-actions`, `.home-story-start`, `.home-story-next`); on the story
pages the folio house style squares their corners. A topic card on the home page now draws its map from the AI reading
of meetings (the topic story's four-colour split) whenever a reading exists, so a lean title and the map beside it agree;
with no reading yet it stays the plain meetings map.

The data-center home card no longer shows the three numbered points, on any screen size (owner, 26 Nov 2026: first on
phones, then "remove the numbered bullets even in desktop too much real estate";
[#1182](https://github.com/getcommunityone/open-navigator/issues/1182)). The card is the title, subhead, basis line, the
topic-named Start button and Next story, the scope line and the map, with the top of **Browse topics** in the first
laptop screen. Nothing else on the card states the points' counts; they stay on the Data Center Story's opening screen
(`storyHeroPoints` in `heroPoints.ts`). The home-only icon set (`heroPointGlyphs.tsx`) and the card's scoped positions
query went with them.
A small line under the title gives the numbers behind it, and says when coverage varies by state. Every number is a real
count for the scope; missing data falls through to the next rule. Thresholds and the reasons for them:
[Story captions](../development/story-captions.md).

### One title, with a scoped subhead and numbered points (#1134)

*(Since #1234, 26 Nov 2026: the Overview no longer repeats the title; it leads with its own count of the record. See above.)*

The home hero, the story header and the story's Overview screen state the **same** caption for the page's scope, from
`pickCaption`. On the Overview, any caption but the bare question (hates, divided, state comparison, meeting count) is
the headline and the meeting count moves to the line under it ("A data center came up in 71 meetings in Alabama. First,
where are they?"), so the Overview never makes a different or stronger claim than the title. Only when the title is the
question does the Overview fall back to its speaker-lean or meeting-count headline (#1115). The national "hates" basis
names the states the meetings span: "In 283 meetings across 32 states, Jev (an AI classifier) read the public as mostly
against data centers (AI reading)." (`public_against_states` on caption-facts). On the home hero at a state or city
scope, the numbered points wait for the place's own figures, so national figures never flash first. Hand counts in a basis always name their scope: "29
speakers counted by hand in 4 states: 18 against and 3 for." (`speakers.states` on caption-facts), never "nationwide".

Under the title, the hero and the story's opening both show:
- **a subhead about the caption's scope only** (`captionSubhead` in `storyCaption.ts`): the story's national line only
  with the national "hates" caption; for a place a sentence about that place (for example "At local meetings in Arizona,
  the public has mostly spoken against data centers."), never a national claim;
- **the basis line** from the caption;
- **three numbered points**, on the story's opening screen only (the home card dropped them, #1182) (`storyHeroPoints` in `heroPoints.ts`, from `GET /api/data-centers/positions`): each uses
  the place's own figure where it is above 0 (`scope_lean_totals`, the AI-reading totals narrowed by `state` and by `city`
  as a substring of the meeting's government name: "6 meetings in Alabama where the public mostly opposed data centers (AI reading).")
  and otherwise the national one (`lean_totals`), starting **"Nationally:"**. Point 1 is a short form, so it doesn't
  repeat the basis line word for word.

"Supported" and "mixed" readings are never evidence for a title: hand checks found them unreliable (served as
`lean_totals.public_for_meetings` / `public_mixed_meetings` for audit; see
[Data center meeting lean](../development/data-center-meeting-lean.md)).

### No zero clause in a title (#1134)

A title or point never states a zero ("0 asked a question", "and none about operations jobs"). Zero clauses are dropped
and the rest are joined plainly, larger side first where that reads better: "Of 6 people who spoke on a data center item
at local meetings in Texas, 2 spoke for it and 1 against." Questions and speakers who took no side go in the line under
the title, only when there are any ("3 took no side."). With no one for or against, the title says only how many spoke.
Recorded votes and jobs claims follow the same rule ("Recorded votes: 5 for, in 1 decision."). The helper is
`countClauses` in `web_app/src/utils/clauses.ts`.

### Statements along the way (#981)

The contested screens (Sites, Proposals, Promises, Concerns, Meetings, Agendas, Gatherings) each ask, under the headline, the statement their record is about, with **Agree**, **Disagree** and **Not sure**. A screen with no record for the place asks nothing. Answers are saved as before (`/api/stance/responses`, anonymous player id), and you can change one.

After you answer, **Where you sit** shows:
- **Readers:** one bar from Agree to Disagree with a **You** marker, for the most specific place that has reached the minimum sample (your community, then your state, then the country). Below it, the page says how many have answered and how many are needed, and shows no split.
- **Speakers at meetings:** shown only where agreeing clearly lines up with one side (for example "The jobs a data center brings are worth what it asks"). One bar from **Spoke for** through **asked a question or took no side** to **Spoke against**, from the real speaker counts for the place, with **You** on the side your answer lines up with, and the same in a sentence. Statements that don't lean (such as "Local officials discuss data centers enough") show no speaker bar, because mapping that answer onto speakers for or against data centers would be invented.

The separate Data Center Challenge is retired: `/challenge/data-centers` (and `/play`) open the story, keeping the place.

#### The minimum sample

A group's split is shown only when at least **30** people in that group have answered the statement (the API setting `STANCE_MIN_SAMPLE`). Below that the page says how many have answered so far and how many are needed, and never shows a split. **Where you sit** names the group its bar uses (your community, your state or the country), and the sentence under it says the same group.

#### Privacy

Your browser makes a random id and keeps it in local storage under `on_stance_player_id`. That is the only thing stored about you in the browser. The server stores your id, the statement, your answer and the state and community you chose. It does not store your IP address, name or email. The rate limiter keeps only a hash in memory.

## Sources and limits

Every chart has a caption that names its source and what it counts. The numbers are real counts from the Open Navigator warehouse through the `/api/data-centers/*` endpoints. If a chart has no data, the screen says "No data available" and asks no statement.

- **Meeting records are not a survey.** The charts count what appears in local meeting records (transcripts, agendas) and in news and company announcements. They do not measure what the public thinks.
- **Charts follow your place as far as their source allows.** With a state they are for that state; with a community they are for that community wherever the source can narrow to one. Data center sites are listed by state, so that chart stays at the state, and its sentence and caption say so. With no state they are national, and the caption says which.
- **Dot charts draw one dot per record,** up to 500. When there are more records than dots, the caption says "Showing the most recent 500 of N" and the group percentages are shares of the dots drawn. A dot with a link opens the source record (a meeting recording at the moment, an agenda document, an article, a site's source page).
- **Ranked bars show a count and a share of the counted total.**
- **Site data** comes from Epoch AI and the US Data Center Registry (both CC BY 4.0), each site credited to its own source. Sites no longer listed by their source stay in the list.
- The dots are small. Use the arrow keys to move between them and the data table under each chart for the group counts.

An old link to `?screen=turn` opens the last screen. An old link to `?screen=question` opens **Overview**.

### The question, after the record

The story does **not** open on its question. After the overview and the rest of the record, the last screen says "You've seen the record. Where do you stand now?" and asks the topic question, worded for the place. The answers are **Yes**, **No** and **Pause for now**; one line under them says a pause is a moratorium (no new approvals until the rules are settled).

There is no separate **Where?** screen any more ([#1134](https://github.com/getcommunityone/open-navigator/issues/1134)): the place picker is in the title sentence, and the Overview shows the question worded for the place and your answer before reading, if you gave one. An old `?screen=scope` link opens the Overview.

After you answer on the last screen it says whether your answer changed when a prior answer is on record ("You said No before. Now you say Pause for now.", "You said Yes both times.", or that you had no earlier answer). Then it shows how readers of the story answered for the country, your state and your community, as stacked bars: Yes in teal, No in amber, Pause for now in a neutral ink tone, each with its count and percentage written out and your own answer marked. Then it offers **See every data center record**.

- Answers are stored once per reader for the question (an optional earlier "before" if one exists, and "after" on the closing screen). Picking another answer replaces the stored one.
- An answer is stored with the place showing when you give it. Broadening back to the country changes nothing stored.
- A group with fewer than 30 answers shows "Not enough answers yet (N so far, 30 needed)" and no bars, exactly as the challenge does. Nothing is ever seeded: with no answers every group says so.
- The results are how readers of this story answered. It is not a poll, and the page says so next to the results.
- Nothing on these screens implies a right answer.
- If the question cannot be loaded the screen says so and the story can still be read.

The question and its answers come from the topic's pack (`question` in `api/stance_packs/data_centers.json`), so the wording and the option ids live in one place. The pure logic (the wording for a place, whether the answer changed, the bar maths for any number of options) is in `web_app/src/utils/storyQuestion.ts`, with its tests. The screens are `QuestionScreen`, `ScopeScreen` and `VerdictScreen` in `web_app/src/components/stance/StoryVoteScreens.tsx`, and the bars are `ChoiceBars.tsx`.

### How the screens move

The engine is the one the challenge uses (`web_app/src/components/stance/useActs.ts`). The story uses two of its modes (`data-mode` on the page), and a third way of showing them under reduced motion:

| Mode | When | What happens |
| --- | --- | --- |
| `pinned` | 768 pixels or wider, motion allowed | Each screen is pinned and scrubbed by the scroll: its word card slides in, the chart builds, the headline's words rise out of their masks one after another, and the screen dims and lifts as it leaves. The scroll glides to the next screen and one gesture never passes more than one. |
| `snap` | Narrower than 768 pixels, motion allowed | Each screen is exactly one frame tall (`100svh` less the two bars at the top and the story bar at the bottom) and the page uses the browser's own scroll snap with `scroll-snap-stop: always`, so a swipe lands on the next screen and stops there. As a screen arrives its headline's words rise out of their masks, its blocks rise in one after another and its chart draws; as it leaves they fade and lift; coming back plays the entrance again. |
| `snap` with `data-fade` | **prefers-reduced-motion** on, at any width | One screen at a time, as on a phone. A screen cross-fades in when it arrives and its dots appear one after another. Only opacity changes: nothing slides, scales or drifts, and nothing loops. Moving on is a jump, not a glide. |

Reduced motion is not only a setting people choose. On Android, battery saver and "Remove animations" both turn it on, so a phone in battery saver gets this version. Before #930 that version was a plain stacked page with nothing animated, which read as a page that was not working. The challenge still uses the plain `stacked` mode under reduced motion.

A phone gets scroll snap, not the pinned engine. Pinning with ScrollTrigger and Lenis depends on the page's own scroll position being rewritten every frame, which fights a phone's touch momentum and the address bar changing the window height. Scroll snap is the browser's own mechanism, so momentum and the address bar are its business, and the screens are sized in `svh` so they do not jump when the bar hides. A screen whose content cannot fit scrolls inside its own block, never the page inside a screen: you scroll to the bottom of that block first, and the gesture stops there: the block does not hand it on to the page (`overscroll-behavior-y: contain`), so reaching its end never changes the screen. Use Next, Back, a key, a progress segment or a sideways swipe to go on. A phone screen that fits still moves by one vertical swipe. With a mouse wheel or trackpad on a narrow window, one wheel gesture moves exactly one screen, except over a block that scrolls. A change of place (a map pick, the place picker, the header's National) starts the story over on its first screen, Overview, and writes `?screen=overview`, unless the same link names a screen; the long screens' own scrollers go back to the top. An open bottom sheet (a KPI drill-down) or dialog owns the wheel, touch and keys: the story behind it stays on its screen while it opens, scrolls and closes (`?screen=` is unchanged; `web_app/e2e/story-scroll.check.mjs`).

The story's motion is calm: rises, fades and a steady filled button, with no bounce. The challenge shares the same engine and layout and adds its own livelier touches (see its page).

### The state drill-down transition (#1195)

On the Overview, picking a state on the national box map (a click, a tap, or the **Show one state** select) no longer swaps the map in one jump ([#1195](https://github.com/getcommunityone/open-navigator/issues/1195)). The state's boxes lift (they grow a little and cast a shadow), then fly from their national places and re-form into the state's county box map, each easing in (exponential ease-out) to one county box, centre first with a small stagger; the other states' boxes fade and drift outward. Colours cross-fade from the national teal to the county colours as the boxes land. It takes about a second. **United States** plays the same motion backwards. Opening a state's story from the home map plays it on arrival, from the national layout: the home map's link carries a one-time navigation flag (not a URL parameter), cleared from the history entry once used, so a refresh or Back does not replay it.

Nothing is invented. The state has far fewer boxes on the national grid than on its county grid, so each county box flies from the national box nearest it on the map: one of them carries that box, the others spawn from it small and clear and grow in, and a national box with no county box under it fades where it stands. Every box that lands is one of the county map's real boxes, at its real place, size, colour and opacity (read from the county map itself), and when it is over the real map shows again.

It is drawn on a canvas over the map (`MapDrill.tsx`); the map stays in the page underneath, transparent for that second, so focus never moves, nothing extra is announced, and the map's keyboard navigation and data table work as before. A click or key press during it jumps to the end. With **prefers-reduced-motion** on there is no animation: the map swaps at once, as before. While the county counts are still loading, the state's boxes stay lifted on the national map and the flight starts when the county map is ready (it gives up after ten seconds and just shows the map). On a phone the county map is taller than the national one, so part of the flight lands below the fold. The layout math is the pure helper `web_app/src/utils/boxMorph.ts`, with tests. Design note: [State drill-down box transition](../development/story-drill-box-transition.md).

### Progress, and the next step

A strip of segments along the lower edge of the top bar has one segment per screen. The one in view fills, the ones behind it stay filled, and the words beside it say what is left ("Seven to go", "One to go", "Last one").

*(Data Center Story since #1234, 27 Nov 2026: the fixed bottom-right Next and the top-right Close replace this bar; see above.)* Every screen has one primary action: the three answers on the question and the last screen (then **See every data center record** once you have answered), and **Next →** everywhere else. On a wide screen, when that control is not in view, because it is below the fold or inside a block that scrolls, a bar pinned to the bottom of the window shows the same action, with a quieter **Back** beside it from the second screen on. It presses the real control, so there is one behaviour and one name. The bar is left out of the tab order and hidden from screen readers, because the real control is still in the page for them. The bar is `FloatingNext.tsx`; a screen marks its primary action with `data-primary`. On the hub the same bar carries **Start** whenever the card's own button has scrolled out of view, for example when you are reading the counts.

### Story navigation: one exit, one progress indicator, the next story (#1102, #1192)

*(Superseded in part by #1234, 27 Nov 2026: Close (×) is back top right as the one exit, "← Data stories" and the cover's Start / Next story pair are gone, and one fixed Next sits bottom right. See "Close top right, Next bottom right, nothing else" above.)*

**Simplified 26 Nov 2026 ([#1192](https://github.com/getcommunityone/open-navigator/issues/1192)).** A live-site audit
counted six navigation devices on the Data Center Story's opening screen (Start, a floating Next, a numbered 1–11 rail,
the segmented progress bar plus a thin fill bar, "← Data stories" and an unlabelled ×), and on a phone the progress
showed twice (top bar and bottom bar). Now:

- **On the cover, Start is the only forward action.** The floating **Next** (wide screens) and the bottom bar's **Next**
  (phones) are hidden while the cover's **Start the [topic] story →** button is in view, and appear from the Overview on.
  (The phone bar's Next on the cover also skipped the Overview, moving on from screen 0 before it was seen.) **Next
  story: [title] →** stays beside Start, both in the first screen at 1366×768, 1440×900 and on an iPhone 13.
- **One progress indicator per device.** Wide screens keep the segmented bar under the title and drop the numbered rail
  and the thin fill bar. The bar was kept rather than the rail because it sits in the sticky title bar the reader already
  looks at, it says what is left in words ("Ten to go"), and the rail took a 56px gutter from every screen and floated
  away from the title. Its segments are now buttons: each is named "N of M: [screen word]" ("3 of 11: Sites"), the
  current one is `aria-current="step"`, and a click goes to that screen (`ProgressPips` with `onJump`, a `nav` named
  "Story screens"). Phones keep only the bottom bar's dots and "N to go"; the top bar shows no progress there.
- **One exit.** The × ("Close story") is gone from the Data Center Story and the topic stories. **← Data stories** (to
  `/stories`, keeping the place) is the single way out, at least 44px tall on a phone; the topic stories gained it.
- **Topic stories' basis line** names the runner-up as "Then Ohio, 399 meetings." instead of "Next: Ohio, …", which read
  like a navigation link (`storyCaption.ts`), and "Counted from local meeting recordings and transcripts…" shows once in
  the first screen (the separate line is left out when the basis already says it).
- **The numbered points stay on the cover.** They sit under the two buttons, so they never push Start or Next story out
  of the first screen (Start and Next story end at about 412px of 768 on a 1366×768 laptop and about 435px of 664 on an
  iPhone 13).
- **No map beside the cover text.** The Overview screen, one Start away, is that same national map (or the state's county
  map); a second interactive copy on the cover would repeat the figure and add a second place picker, the opposite of
  this simplification. The cover keeps its empty right side on wide screens.

`web_app/e2e/story-nav.check.mjs` now checks the cover first (no floating Next beside Start, one progress indicator, no
×), then presses Start and checks that Next and Back line up on every screen.

The story shows how far you are and where it goes next ([#1102](https://github.com/getcommunityone/open-navigator/issues/1102)). None of this changes a screen or a map: every control below moves with the story's own screen navigation (the same `goTo` as **Next →** and the keys), so landing on a screen from the address (`?screen=`) works as before.

| Where | What | Behaviour |
| --- | --- | --- |
| Wide screens (768 pixels or wider) | The segmented bar along the lower edge of the sticky title bar, one segment per screen, with "N to go" | The screen in view and those behind it are filled. Each segment is a button named "N of M: [screen word]"; the current one is `aria-current="step"`; clicking goes to that screen. It is a `nav` named "Story screens" and the story's only progress indicator on a wide screen (#1192 removed the numbered dots on the left edge and the thin fill bar along the top). |
| After the last screen, every width | A full-width **Next story** card | It fades in as it comes into view (opacity and a short rise; opacity only under reduced motion). It reads "Next story: Short-term rentals →" while there is a following live story, and "All data stories →" (to `/stories`) at the end of the list; the list does not wrap. The link keeps the place (`?state=&city=`). Scrolling on past the last screen reaches it: the scroll no longer pulls back onto the last screen once you are past it. |
| Phones (narrower than 768 pixels) | A bar fixed to the bottom of the window, above the safe area | The phone's only progress indicator: compact progress dots with "N to go", and one prominent **Next** (hidden on the cover, where **Start** leads on): it goes to the next screen, and on the last screen it becomes **Next story** (or **All stories**). Each screen is shortened by the bar's height and the page has bottom padding of the same height, so the bar never covers a screen's controls. On phones it replaces the floating bar and each screen's own **Next →** (Back and the answers stay in the screen). |

The order of live stories is the home page's: the stories registry (`STORIES` in `web_app/src/utils/dataStory.ts`), then the topic stories (`/stories/short-term-rentals`). Stories still "coming soon" are never linked. The pure helpers (next live story, the progress share, which dot is current) are in `web_app/src/utils/storyNav.ts`, with tests; the components are in `web_app/src/components/stance/StoryProgress.tsx` (bottom bar, next-story card) and `ProgressPips.tsx` (the wide-screen segments).

### Moving between screens

Every screen of the record ends with a quieter **Back** at the left and the primary **Next →** at the right, the same kind of button as the hub's **Start the story** ([#964](https://github.com/getcommunityone/open-navigator/issues/964)). The button shows only "Next": the next screen's name ("Next: Who spoke up") is its accessible name and tooltip, because as the visible label it read like a heading and confused readers. Every screen uses the one nav row (`ScreenNav.tsx`, [#1138](https://github.com/getcommunityone/open-navigator/issues/1138)), including the question and last screens. On a wide screen the row is pinned to the bottom of the left column, so **Back** and **Next →** sit at the same place and size on every screen whatever the text or chart height. The first screen has no Back and keeps Next in that spot; on the last screen **See every data center record** takes Next's spot (same right edge, top and height) once you have answered. Because the inline row is always in view there, the floating bar does not appear beside it. Phones keep the row in the flow, with the bottom bar as before. `web_app/e2e/story-nav.check.mjs` checks this at 1440×900 (run it against a running app: `node e2e/story-nav.check.mjs --base http://localhost:5173`). These keys also move: PageDown, Space, down arrow and right arrow go on (on a topic story a sideways swipe does too, #1224); PageUp, Shift+Space, up arrow and left arrow go back; Home and End jump to the first and last screen. They do nothing while focus is in a field, a select, a table or a figure that scrolls on its own. Touch scrolling is never taken over (see "How the screens move" for the wheel). The address follows the screen in view (`?screen=sites`, replacing the entry), so a shared link opens on it.

### The place in scope

The page reads `?state=AL&city=Tuscaloosa` (a city only with a state). The sentence blank already names the place (**the United States**, a state, or a city). Under a state or city the bar also says **Showing:** that place, with one-click **All of [state]** and **National only**; under the United States it does not repeat **Showing: National** (#959). The label, the queries and the charts change together, and the place is carried to the hub and to every link at the end of the story. A screen with nothing in scope says "No data available for this place." and offers to show the state or the national data. Data center sites have no city in their source, so with a city chosen the sites screen shows the state and says so in its sentence and caption.

### The voice

Headlines and context lines come from pure functions in `web_app/src/utils/dataStory.ts`, tested in `dataStory.test.ts`.

- Use counts, rankings, shares, contrasts and change over time. Name the scope in the sentence.
- A share or a ranking is stated only from whole-scope counts the endpoint returned. A list that is capped says "most recent N" and never gives a share or a trend.
- A sentence that ends in a question leads to the next screen only when the next screen answers it.
- No sentence describes how the page is built ("one screen at a time", "each dot opens its source"). The reader gets what the record says and what comes next. The source of a "For context" screen stays on its card.
- No causes ("because", "due to", "driven by"), no forecasts, no judgments (good, bad, worrying, best, worst, should, problem, crisis) and no claim about what people in general think. The one exception is the story's question itself, which asks "Should ...?" and is not a finding. The records are meeting records, not a survey, and a concern count is a count of passages, not of people.
- A header never starts with a number, so a sentence that would start with a count starts with a word ("Of 26 data center sites in Alabama, 14 are operating, ...").
- Missing data gives a neutral description of the chart, never a filled-in number.

### Colours

The hub, the story and the challenge use the Open Navigator house theme from `web_app/src/utils/folioThemes.ts` (the one the Data explorer Matrix map defaults to), applied as custom properties on the page wrapper through `web_app/src/utils/houseTheme.ts`. The challenge's reveal bars are Agree in the teal accent, Disagree in amber and Not sure in neutral, each with a text label and count so colour is never the only cue. Dot groups use the theme's segment colours in order.

## What a chart shows

The charts are the challenge's (`ChartPanel`). The listed-record charts (meeting passages, agendas, decisions, jobs claims) are drawn as a unit matrix of squares (#1140, see the Meetings screen above); the others are dot charts, and one dot is one real record: a speaker, a meeting, an agenda, a site, a project, a jobs claim, a mention of a concern. Dots are grouped under a heading with the group's real count and share. They appear one after another when their screen arrives. Each chart has a FIG. caption with source and scope, an honest note when the list is capped, and **Show data table**. A long figure scrolls inside its own frame so the headline stays in view.

There are two kinds of dot chart, and the caption says which:

- **Listed records** (sites, projects, jobs claims, meeting passages, agendas, company-hosted meetings). The endpoint returns the records, up to 500, and each dot opens its source. When the endpoint also counts the whole scope, the heading states that count and its share and says how many are drawn ("Operating · 118 records · 60% · showing 24"). When it does not count per group (projects by status), the heading says only how many are drawn ("Planned · 5 shown") and gives no share. A share is never worked out from a capped list.
- **Counts** (who spoke up, concerns, meetings in the opener). The endpoint returns totals, not records. Up to 240 the chart draws one dot per record. Above that one dot stands for 2, 5, 10, 20, 50... records, the smallest that fits, and the caption says so ("Each dot is 10 meetings; the last dot of a group is what is left over."). The last dot of a group stands for the remainder and is drawn smaller, so the dots always add up to the real count. The arithmetic is `dotRatio` and `countDots` in `web_app/src/utils/stanceGame.ts`, with tests.

### Meetings screen: trend line, milestone track and period dumbbell (#1140)

The Meetings screen (chart `meeting-mentions`) opens with three figures, all for the place in scope:

- **Trend line.** Distinct meetings per year whose transcript discussed the topic, with the quoted passages in the tooltip. A toggle switches to the topic's **share of recorded meetings**: meetings on the topic divided by every recorded (transcribed) meeting in the same place and year (`recorded_meeting_year`). The line carries the note "Meetings in our record by year; recording coverage grew sharply in 2025–26, so the rise partly reflects coverage." A year with nothing recorded, or with no meetings on the topic and fewer than 25 recorded meetings, is a gap in the line, never a zero; the note names the gap years. A year with far fewer recorded meetings than the years around it and than the place's typical year (nationally, 2024: 932 recorded against about 13,000 a year around it) is **thin** ([#1207](https://github.com/getcommunityone/open-navigator/issues/1207)): its count is a hole in our recordings, not a drop. On the count line it is a hollow point on a dashed line and the note says "Only 932 meetings were recorded in 2024, so that year's count is not comparable." When a year is thin the chart opens on the share of recorded meetings, which is still comparable, and the Meetings toggle stays available. The year axis prints only the labels that fit the chart's width: the first and last year always, and in between every year, every 2nd, every 5th or every 10th, whichever is the smallest step that keeps the labels apart. On a phone, 2016–2026 reads 2016, 2018 … 2026. Labels are never rotated. The period dumbbell's % axis follows the same rule ([#1222](https://github.com/getcommunityone/open-navigator/issues/1222), `web_app/src/utils/axisTicks.ts`).
- **Milestone track.** Under the line, on the same year scale, one lane per kind of event: meetings where officials approved, denied, tabled or adopted a moratorium (an **AI reading** of the transcript, labelled as such on the card), and state bills enacted once `topic_legislation_bill` is served. Click a square, or select one and use the arrow keys, Home and End; the card below gives the date, place, what happened and a link to the meeting or bill. Under 560px wide the track becomes a tap list, newest first.
- **Period dumbbell.** Last year (hollow circle) against this year (filled dot) for each state in national scope, or each town in state scope, with a ±pp label and sort buttons (by this year, by change, by last year). Rows with too few recorded meetings are left out and the note says how many. **Moved earlier (26 Nov 2026, owner: "earlier in every story", [#1192](https://github.com/getcommunityone/open-navigator/issues/1192)):** in the Data Center Story it is now on the **Overview** screen, the first screen after the cover, right under the overview map (the dot map, or the state's county map), and it is no longer drawn on the Meetings screen, so it shows once. In a city scope the Overview says the comparison is drawn by state or by town within a state and points to **All of [state]**, instead of drawing nothing. The chart never disappears silently: while loading it says so, a failed request says "could not be loaded right now", and a scope with no per-year counts of recorded meetings (`recorded_meeting_year` not loaded, [#1194](https://github.com/getcommunityone/open-navigator/issues/1194)) or no rows at all reads "No comparison to draw for [scope] yet: either no meetings on the topic are on record for [year] or [year], or the yearly counts of recorded meetings per state have not been loaded."

Every other topic story (`/stories/<topic>`, for example `/stories/water-fluoridation`) shows the same trend line, milestone track and period dumbbell under its map, in a **Meetings over time** section that follows the page's state filter. That section sits directly under the state map, above the companies, meetings and decisions lists, so it is the second thing a reader sees (checked for #1192; it already sat there). Topics other than data centers count meetings from `topic_transcript_link` (no passage counts) and read their milestones from `topic_meeting_lean`.

Below them, the passages are a **unit matrix**: one square per passage, regrouped by a toggle (All, By year, By state or By town, By outcome, By who spoke). The outcome and public-lean groupings are an AI reading and say so. The decisions, agenda and jobs-claim charts use the same matrix with their own grouping first. The design and thresholds: [Story charts: timeline, dumbbell and unit matrix](../development/story-charts-timeline-dumbbell.md).

The headline names the year with the most meetings when the passage list is complete ("Data centers came up in 71 meetings in Texas, most of them in 2026 (278 quoted passages)."); when years tie or the list is capped it keeps the plain count.

### State bills, votes and the five positions (#1274)

Every topic story (`/stories/<topic>`) has two screens after **Who spoke**, and the Who spoke screen gains a chart for topics read with five positions. All three come from our own records and follow the page's state filter:

- **State bills** screen. A US map with each state coloured by the furthest any of its bills on the topic got: enacted, passed one chamber, introduced and pending, or failed. The bills are our copy of OpenStates, matched by the topic's keywords in each bill's subject tags, title and abstract. Two filters recolour it: the period (the last two years with bills, or every year) and the direction (for water fluoridation: ban, restriction, protection, study, or direction not stated). Click or tap a state, or Tab to it and press Enter, to list its bills, each linked to its OpenStates page; every state with a bill is also listed under the map. A bill whose title and abstract don't say which way it goes is shown by status only, never guessed.
- **Who spoke** screen, five positions. For a topic whose meeting reading has five positions (water fluoridation), one bar per position, counting meetings whose AI reading (Jev) put the public who spoke closest to it. Water fluoridation's five: Support, require everywhere · Support, each community decides · No opinion · Oppose, each community decides · Oppose, ban everywhere. It counts meetings, not people; meetings where the public didn't speak are given in the note. Other topics keep only the four-way breakdown.
- **Votes** screen. Meetings where, in the AI reading, the council or board voted to move the topic forward (fluoridation: keep or start it), voted to stop or limit it (end it), or tabled or put it off: totals that double as filters, a column per year, the states with most actions, and the meetings themselves, each linked to its recording with how sure the reading was.

There is no ballot-measure chart: we have no ballot-measure data on these topics yet ([#1275](https://github.com/getcommunityone/open-navigator/issues/1275)). Rules, colours and counts: [Topic legislation map, positions and local actions](../development/topic-legislation-map.md).

### Coming up, and the home page's What happens next strip (#1302)

Owner, 27 Nov 2026: upcoming meetings and legislation are "where we have the greatest impact". Every story (the topic stories and the Data Center Story) has a **Coming up** screen second, right after Overview, and it always stays in the story:

- **What, when, where, how to take part.** Each scheduled meeting or public hearing shows its date, the place, the title, why it is listed (the agenda names the topic; an official notice lists it; or "Agenda not posted yet. Gwinnett County discussed data centers on Jun 15, 2026:"), the quoted evidence with the topic's words marked, and a link: the agenda, the meeting page, the livestream or the official notice.
- **State bills still open**, dated by their last action and linked to OpenStates, furthest along first.
- **Nothing upcoming.** The screen says "Nothing upcoming on record for Georgia." and links one level up (a city to its state, a state to national) with that level's count. No stand-in items.
- **Home page.** Under the story card and its map, above Browse topics, a strip of three cards for the story and place in the URL (`?story=`, `?state=`, `?city=`): **Coming up** first and highlighted, then **Meetings** and **State bills**. Each is one real number and one line and opens that screen of the story at the same place. It scrolls sideways on a phone.

How items are found, what the warehouse holds and what is left out: [What's coming up on a topic](../development/topic-upcoming.md).

### Who's working on this: the Nonprofits screen (#1346)

Every topic story and the Data Center Story has a **Nonprofits** screen right after Coming up, and it always stays.
It lists the nonprofits in the scope tied to the topic by the record, strongest evidence first: named in one of the
topic's meetings, then a 990 mission that names it, then its name, then its IRS category. Each shows its name (a link to
its organization page), city, latest revenue with the tax year when we have one, a one-line mission, why it is listed
and the quoted evidence with the words marked (and "Watch that meeting" for a meeting mention), its website when we have
one, and a side only when its own name or mission states it. Three are listed first so they fit a phone; "Show all"
opens the rest. The counts by evidence follow the shared display rule (`pickDisplay`): a sentence for a few, bars for
more. An empty scope says "No nonprofits on record for Georgia." and links one level up with that level's count. Data
and rules: [How organizations are tied to topics](../development/topic-organizations.md).
### Who's working on this: nonprofits on a topic (#1345)

The nonprofits tied to a topic come from `public.topic_organization` (one row per topic × organization) and
`GET /api/topics/{topic}/organizations?state=&city=`. Each is tied by the record, strongest first: **named in one of the
topic's recorded meetings** in its state, word for word and near the topic's words; its **990 mission** names the topic;
its **name** does; or its **IRS (NTEE) category** is the topic's field. The API ranks them that way, then by latest
revenue, and gives each one's evidence (the meeting passage or mission with the words marked), city, mission, latest
990 or IRS revenue with its tax year, and a side only where the organization's own name or mission states one. How the
rules were chosen and checked: [How organizations are tied to topics](../development/topic-organizations.md).

### What happened next: the chain from meeting to outcome (#1314)

A **What happened** screen follows Coming up on every story. It walks from the meetings where the topic came up to what followed, one step at a time: **Meetings** → **The public** (meetings where the public spoke, mostly opposed / split / mostly supportive) → **Officials** (meetings where the council or board moved it forward, stopped or limited it, put a moratorium on it, or tabled it) → **State bills** (by status) → **Named a bill** (meetings that wrote one of the topic's state bills by number) → **What's next** (meetings and hearings ahead, bills still open). Each step is one count, a line in words and up to three linked examples. **See all** opens that step's screen. An empty step says "No recorded … yet". The flow runs top to bottom on a phone and left to right on a wide screen. The home strip gains a **Votes** card. How meetings are tied to bills: [How meetings are linked to state bills](../development/meeting-bill-links.md).

## Add a story

1. Add the screens to `web_app/src/utils/dataStory.ts` (a list like `DATA_CENTER_STORY`: an `id`, a short word, the dataset key and the kind; start with a `question` and a `scope` screen and end with a `verdict` screen) and a function per record screen that returns its headline and context from the endpoint's response. Add them to `screenText` and cover them in `dataStory.test.ts`, including the empty and failed cases and the banned wording.
2. If the story needs a dataset the charts do not have yet, add it to `chartSpec` in `web_app/src/utils/stanceGame.ts` and to `fetchChartData` in `web_app/src/api/stance.ts`, with its test.
3. Register the story in `STORIES` in `web_app/src/pages/DataStory.tsx` and add its card to the hub in `web_app/src/pages/DataStories.tsx`.
4. Add the pack (`api/stance_packs/<pack>.json`) with the story's `question` and its statements. Give each statement the story screen that asks it (`story_screen`) and, only when agreeing clearly lines up with one side of the meeting speakers, `speaker_lean` (`for` / `against`); see [Story statements and where you sit](../development/story-statements-where-you-sit.md).
5. Update this page.

## Moving to the next screen

When you stop on a screen that has a next step, the page draws your eye to it. After about six seconds with no scroll, tap or key, the main button gets a small cue: its arrow slides a few pixels and back and a light passes across it. If the button is not on screen, the bar at the bottom of the window is showing it, and the cue plays there. On a phone the story's own bottom bar (#1102) always shows **Next**, so the cue is not drawn on a phone story. This is the same on the hub (**Start**), in the story (**Next →**) and in the challenge.

- The cue repeats about every eight seconds, at most three times, then it rests.
- Anything you do (scroll, tap, type) starts the wait and the count again. So does arriving on a new screen, and there the wait begins only after the screen has finished arriving.
- It never plays while the place picker is open, while a data table is open, while you are typing in a field or selecting text, or while the tab is in the background.
- It is never shown on a group of answers: no answer is pushed.
- Focus does not move, nothing is announced to a screen reader, no control is added and nothing shifts.
- With reduced motion nothing moves: an outline inside the button shows and goes, once per cue.
- The hub cue is visual only. On the story, with **Play sound in stories** on (Settings, Site tab, or the site menu; off by default, #1319), the first idle nudge also plays one soft page-turn cue, and advancing to a new screen plays the same soft cue (after your first click or key unlocks Web Audio). Answering still plays the lock cue. The challenge is louder: its arrow hops twice and the light is brighter, and its first idle cue plays a soft sound when sound is on (#966).

| Timing | Value | Constant |
| --- | --- | --- |
| Stillness before the first cue | 6 seconds | `NUDGE_IDLE_MS` |
| Between cues | 8 seconds | `NUDGE_REPEAT_MS` |
| Cues before it rests | 3 | `NUDGE_MAX` |
| One cue | 1.4 seconds | `NUDGE_CYCLE_MS` |
| A screen's arrival, before the wait starts | 1.2 seconds | `NUDGE_ENTRANCE_MS` |

The timing is a pure function, `shouldNudge` in `web_app/src/utils/idleNudge.ts`, with tests. The hook that runs it is `web_app/src/hooks/useIdleNudge.ts`: it adds the class `is-nudging` to the button or the bar for one cue, and `stance.css` draws it. This replaced the story's separate "Scroll" / "Swipe up" cue, so there is one cue at a time. (The Data explorer's Matrix page still uses that older cue, `ScrollCue.tsx`; it has no floating bar.)
