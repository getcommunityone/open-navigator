"""
IBM-Debater ArgKP (Argument Key Point) ingestion.

Lands the ArgKP-2021 argument -> key-point matching dataset
(``NLP-Debater-Project/IBM-Debater-ArgKP`` on the Hugging Face Hub) into
``bronze.bronze_argkp_pairs``. ArgKP is the canonical reference corpus for **Key
Point Analysis** — the method the policy-question registry uses to collapse raw
civic argument snippets into canonical "key points" with stance. We ingest it so
it can serve as labeled eval data and as few-shot grounding for the argument
labeler (``llm.policy_questions.cluster_arguments``).

Run::

    python -m ingestion.argkp.load            # full dataset (~81.6k pairs)
    python -m ingestion.argkp.load --limit 1000
"""

from __future__ import annotations
