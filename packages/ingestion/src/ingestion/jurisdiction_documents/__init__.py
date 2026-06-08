"""Jurisdiction-grain civic documents (frameworks, plans, ordinance codes).

A jurisdiction-grain document belongs to a JURISDICTION rather than a single
meeting, so it cannot be linked through ``event_meeting_document`` (which matches
on jurisdiction + date + body). It links directly to the jurisdiction, and to
civic data (decisions, bills) via ordinance numbers. See ``registry`` for the
curated source list and ``bronze`` for the loader.
"""
