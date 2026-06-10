"""
CLI: run the full Phase-1 pipeline end to end (embed -> questions -> arguments).

    python -m llm.policy_questions.run_pipeline                 # no-LLM validation run
    python -m llm.policy_questions.run_pipeline --use-llm       # real labeled run (billed)
"""

from __future__ import annotations

import argparse

from loguru import logger

from llm.policy_questions import cluster_arguments, cluster_questions, embed_instances


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the policy-question registry end to end.")
    ap.add_argument("--use-llm", action="store_true")
    ap.add_argument("--min-cluster-size", type=int, default=5)
    ap.add_argument("--arg-min-cluster-size", type=int, default=4)
    ap.add_argument("--max-llm-calls", type=int, default=600)
    ap.add_argument("--full-refresh", action="store_true")
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args()

    logger.info("=== Step 1/3: embed ===")
    embed_instances.run(full_refresh=args.full_refresh, database_url=args.database_url)
    logger.info("=== Step 2/3: cluster questions ===")
    q = cluster_questions.run(use_llm=args.use_llm, min_cluster_size=args.min_cluster_size,
                              max_llm_calls=args.max_llm_calls, database_url=args.database_url)
    logger.info("=== Step 3/3: cluster arguments ===")
    a = cluster_arguments.run(use_llm=args.use_llm, min_cluster_size=args.arg_min_cluster_size,
                              max_llm_calls=args.max_llm_calls, database_url=args.database_url)
    logger.success("Pipeline done: {} questions, {} instances, {} arguments, {} LLM calls",
                   q["questions"], q["instances"], a["arguments"], q["llm_calls"] + a["llm_calls"])


if __name__ == "__main__":
    main()
