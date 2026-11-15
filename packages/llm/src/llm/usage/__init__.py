"""Usage records for model calls and GPU steps (#262).

    llm.usage.calls        one row per model call: tokens, thinking tokens, latency, attempts
    llm.usage.gpu          one row per GPU step: wall time, GPU-hours, utilization, memory, energy
    llm.usage.prices       prices.yaml, and the cost of a row at those prices
    llm.usage.report       python -m llm.usage.report: totals by day and model
    llm.usage.load_bronze  python -m llm.usage.load_bronze: the logs, into Postgres

Rows are appended to JSON-lines files under ``LLM_USAGE_LOG_DIR`` (default
``data/logs/llm_usage/``). Recording never raises into the caller, and
``LLM_USAGE_LOG=0`` turns it off.
"""
