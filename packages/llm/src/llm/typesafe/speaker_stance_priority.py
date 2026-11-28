"""The run order for the speaker stance pass (#1391): which topics are trending, heated or divided (free, no model).

Owner, 2026-11-27: "sort by the most trending topics with heat or different opinions." Per topic, three signals, each
min-max normalized to 0-1 across the topics, summed with equal weights:

- ``rise``: the topic's share of recorded meetings in this year to date over its share last full year
  (``public.topic_meeting_year`` / ``public.recorded_meeting_year``, the numbers behind /api/topics/yoy);
- ``contention``: of the meetings where a public speaker's own words named the topic, the share where at least one such
  speaker had a 'for' cue shape and another an 'against' one (``stance_shape``, free cue rules); where the topic has a
  per-meeting Jev reading (``public.topic_meeting_lean``), the mean of that share and the share of read meetings where
  the public was split or officials sided against the public;
- ``heat``: the mean AI meeting-analysis heat (``gold.public_comment.heat``, 1-5) over comments in those meetings;
  a topic with fewer than 5 rated comments gets the median of the others (not 0, not a guess at a value: the signal is
  simply neutral for it).

Data centers runs first regardless (owner). Prints the table; :data:`llm.typesafe.speaker_stance.PRIORITY` holds the
order it produced, and the decision page records the numbers.

    python -m llm.typesafe.speaker_stance_priority
"""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from typing import Any

from llm.typesafe import speaker_stance as ss

FOR_SHAPES = {"clear_for", "conditional", "for_concept_against_project"}
AGAINST_SHAPES = {"clear_against", "against_concept_open_to_terms"}
MIN_HEAT_COMMENTS = 5


def norm(values: dict[str, float | None]) -> dict[str, float]:
    got = [v for v in values.values() if v is not None]
    lo, hi = (min(got), max(got)) if got else (0.0, 0.0)
    return {k: (0.0 if v is None or hi == lo else (v - lo) / (hi - lo)) for k, v in values.items()}


def score_topics(rise: dict[str, float | None], contention: dict[str, float | None],
                 heat: dict[str, float | None]) -> list[tuple[str, float]]:
    r, c, h = norm(rise), norm(contention), norm(heat)
    scores = {k: round(r[k] + c[k] + h[k], 3) for k in rise}
    first = [("data-centers", scores.pop("data-centers"))] if "data-centers" in scores else []
    return first + sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def main() -> int:
    import psycopg2

    from llm.typesafe.screen_transcripts import _database_url

    topics = list(ss.TOPICS.values())
    conn = psycopg2.connect(_database_url(""))
    try:
        patterns = ss.topic_patterns(conn, topics)
        with conn.cursor() as cur:
            cur.execute("SELECT meeting_speaker_id, stance_shape FROM gold.meeting_speaker_position")
            shapes = dict(cur.fetchall())
            cur.execute("""
                WITH r AS (SELECT sum(recorded_meetings) FILTER (WHERE meeting_year = 2025) ra,
                                  sum(recorded_meetings) FILTER (WHERE meeting_year = 2026) rb
                           FROM public.recorded_meeting_year)
                SELECT t.topic_id,
                       (sum(t.meetings) FILTER (WHERE meeting_year = 2026)::numeric / r.rb)
                       / nullif(sum(t.meetings) FILTER (WHERE meeting_year = 2025)::numeric / r.ra, 0)
                FROM public.topic_meeting_year t CROSS JOIN r GROUP BY t.topic_id, r.ra, r.rb""")
            rise_by_id = {int(a): (float(b) if b is not None else None) for a, b in cur.fetchall()}
            cur.execute("""
                SELECT topic_id, avg((public_lean IN ('mixed','split')
                                      OR (official_lean IS NOT NULL AND public_lean IN ('mostly_supportive','mostly_opposed')
                                          AND official_lean IN ('mostly_supportive','mostly_opposed')
                                          AND official_lean <> public_lean))::int)
                FROM public.topic_meeting_lean WHERE public_lean IS NOT NULL AND public_lean <> 'did_not_speak'
                GROUP BY topic_id""")
            lean_by_id = {int(a): float(b) for a, b in cur.fetchall()}
            cur.execute("SELECT video_id, heat FROM gold.public_comment WHERE heat BETWEEN 1 AND 5")
            heat_rows = cur.fetchall()
        speakers = ss.load_speakers(conn)
    finally:
        conn.close()
    heats_by_video: dict[str, list[int]] = defaultdict(list)
    for vid, h in heat_rows:
        heats_by_video[vid].append(int(h))
    sides: dict[str, dict[str, set[str]]] = {t.slug: defaultdict(set) for t in topics}
    for sid, vid, _d, txt in speakers:
        for t in topics:
            p = patterns[t.slug]
            if p is not None and txt and p.search(txt):
                shape = shapes.get(sid, "unclear")
                sides[t.slug][vid].add("for" if shape in FOR_SHAPES else "against" if shape in AGAINST_SHAPES else "-")
    rise, contention, heat, rows = {}, {}, {}, []
    for t in topics:
        meetings = sides[t.slug]
        both = sum(1 for s in meetings.values() if {"for", "against"} <= s)
        cue_share = both / len(meetings) if meetings else None
        lean = lean_by_id.get(t.topic_id)
        contention[t.slug] = (cue_share + lean) / 2 if (cue_share is not None and lean is not None) else cue_share
        hs = [h for vid in meetings for h in heats_by_video.get(vid, [])]
        heat[t.slug] = statistics.mean(hs) if len(hs) >= MIN_HEAT_COMMENTS else None
        rise[t.slug] = rise_by_id.get(t.topic_id)
        rows.append((t.slug, len(meetings), rise[t.slug], cue_share, lean, contention[t.slug], len(hs), heat[t.slug]))
    med = statistics.median([v for v in heat.values() if v is not None])
    heat = {k: (v if v is not None else med) for k, v in heat.items()}
    ranked = score_topics(rise, contention, heat)
    info: dict[str, Any] = {r[0]: r for r in rows}
    print("| # | topic | meetings | rise | both-cue share | Jev split/disagree | contention | rated comments | heat | score |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for i, (slug, sc) in enumerate(ranked, 1):
        _, m, ri, cs, ln, ct, nh, hv = info[slug]
        f = lambda v, d=2: "-" if v is None else f"{v:.{d}f}"
        print(f"| {i} | {slug} | {m:,} | {f(ri)} | {f(cs)} | {f(ln)} | {f(ct)} | {nh} | {f(hv)} | {sc:.3f} |")
    print("PRIORITY = " + repr(tuple(s for s, _ in ranked)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
