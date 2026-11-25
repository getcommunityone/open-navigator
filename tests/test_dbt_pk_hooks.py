"""Static checks on how dbt models attach primary keys in hooks (#941).

1. gold_pk_post_hook must be passed as a STRING ("{{ gold_pk_post_hook('…') }}"). Called directly inside
   config() it renders at parse time, when {{ this }} is public.<model>, not the gold table.
2. No hook (and not the macro) may add a primary key under a fixed name: post_hooks run after dbt renames the
   old table to __dbt_backup, which still owns <model>_pkey, so a fixed name fails every rebuild after the first.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "dbt_project" / "models"
MACRO = ROOT / "dbt_project" / "macros" / "gold_pk_post_hook.sql"

# a call not inside a Jinja expression string: preceded by "[", "(", "+", "," or start of line, not by {{
DIRECT_CALL = re.compile(r"(?<!\{\{ )(?<![\w'\"])gold_pk_post_hook\(")
NAMED_PK = re.compile(r"add\s+constraint\s+\S+\s+primary\s+key", re.IGNORECASE)


def _config_block(text: str) -> str:
    m = re.search(r"\{\{\s*config\((.*?)\)\s*\}\}", text, re.DOTALL)
    return m.group(1) if m else ""


def test_gold_pk_post_hook_is_passed_as_a_string() -> None:
    offenders = []
    for path in MODELS.rglob("*.sql"):
        cfg = _config_block(path.read_text())
        for line in cfg.splitlines():
            if DIRECT_CALL.search(line) and "{{ gold_pk_post_hook(" not in line:
                offenders.append(f"{path.relative_to(ROOT)}: {line.strip()}")
    assert not offenders, "call gold_pk_post_hook as a string, \"{{ gold_pk_post_hook('…') }}\":\n" + "\n".join(offenders)


def test_no_hook_adds_a_named_primary_key() -> None:
    offenders = [
        str(p.relative_to(ROOT))
        for p in [*MODELS.rglob("*.sql"), MACRO]
        if NAMED_PK.search(_config_block(p.read_text()) if p != MACRO else p.read_text())
    ]
    assert not offenders, "add primary keys without a fixed name (#941): " + ", ".join(offenders)


def test_the_checks_catch_the_old_forms() -> None:
    assert DIRECT_CALL.search("    post_hook=[gold_pk_post_hook('word')]")
    assert not DIRECT_CALL.search("""    post_hook=["{{ gold_pk_post_hook('word') }}"]""")
    assert NAMED_PK.search('"ALTER TABLE {{ this }} ADD CONSTRAINT x_pkey PRIMARY KEY (id)"')
    assert not NAMED_PK.search("alter table {{ this }} add primary key (id)")
