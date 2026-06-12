"""
Policy-question / canonical-argument registry pipeline.

Builds the cross-jurisdiction middle layer over civic choices: a registry of
jurisdiction-neutral **policy questions** that both local ``event_decision`` rows
and (Phase 2) state ``bills`` map into, with a **canonical-argument** library
underneath (built via the Key Point Analysis method) and Boydstun **frame**
dimension tags for cross-question comparability.

Four-layer stack:

    CAP topic (borrowed)  ->  policy_question (minted)
                          ->  canonical_argument (minted, Key Point Analysis)
                          ->  policy_frame dimension (borrowed, Boydstun)

Python here does ML + orchestration only (embed, cluster, LLM-label) and writes
``bronze.*`` landing tables. dbt promotes those to the ``public`` serving marts
with PK/FK constraints. The LLM labeling is bounded to ~1 Gemini call per cluster
(never per row) and is gated behind ``--use-llm``; the default path labels each
cluster deterministically from real in-data text so the full stack can be
validated at zero API cost.

CLIs (run from the workspace venv)::

    python -m llm.policy_questions.embed_instances
    python -m llm.policy_questions.cluster_questions   [--use-llm]
    python -m llm.policy_questions.cluster_arguments   [--use-llm]
    python -m llm.policy_questions.assign_instances    # incremental, LLM-free
    python -m llm.policy_questions.run_pipeline        [--use-llm]
"""

from __future__ import annotations
