#!/usr/bin/env python3
"""
Copy the local ``public`` SERVING schema to a Neon ``public`` schema.

What this is
------------
The "prod deployment" database step. It mirrors the **already-built** local
``public`` serving objects (the dbt serving views over ``gold`` + the few real
serving tables) into Neon's ``public`` as plain tables. It does NOT rebuild
anything with dbt on Neon — the ``gold`` upstreams the views read don't exist
there — it just ships the materialized rows. Local ``public`` is 29 views + a
handful of tables; each is copied verbatim into a real table on the target.

What it deliberately does NOT copy (CRITICAL)
---------------------------------------------
1. **Runtime / auth tables** (see :data:`RUNTIME_OWNED`). Those are written by
   the *running prod app* — the real user accounts, OAuth flow state, social
   graph, feed prefs, and the on-demand meeting-gap cache live in the TARGET,
   not here. Copying our (usually empty local) copies over them would wipe
   production users. They are excluded from the copy and never touched.

2. **The nonprofit / 990 money + MDM graph** (see :data:`NON_SERVING`). Local
   ``public`` exposes the *entire* ``gold`` warehouse as views, including
   ``grant`` (~2.3 GB), ``mdm_organization`` (~1.7 GB), the org↔jurisdiction
   bridge (~0.8 GB) and friends — ~5 GB of "follow-the-money" / entity-resolution
   data. Neon's free tier caps the **whole project at 512 MB**, so this graph
   cannot be served from Neon at any scope; ``grant`` alone is 4.5× the cap.
   The deployment is civic-only, so we copy an explicit **allow-list** of
   civic-serving objects (:data:`CIVIC_SERVING`, ~240 MB) and skip everything
   else. Any ``public`` object that is in neither list is logged loudly and
   skipped, so a newly-added object can never silently blow the cap again.

Per-object safety
------------------
The prod API reads ``public`` while this runs, so each object is loaded into a
``<name>__load`` staging table first, then swapped in one transaction
(drop the old view/table CASCADE → rename staging into place). The "missing
table" window is just the rename txn, not the whole COPY.

Target
------
Defaults to **prod** (``NEON_DATABASE_URL``) because this is the prod-deploy
tool. ``--target dev`` uses ``NEON_DATABASE_URL_DEV`` for a safe rehearsal.

Usage::

    python -m hosting.neon.sync_public_to_neon                 # -> prod Neon public
    python -m hosting.neon.sync_public_to_neon --target dev     # -> dev Neon public
    python -m hosting.neon.sync_public_to_neon --dry-run        # list what would copy
    python -m hosting.neon.sync_public_to_neon --only event jurisdictions  # subset
"""
from __future__ import annotations

import argparse
import io
import os
import socket
import sys
import tempfile
import time
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

LOCAL_DB_URL = os.getenv(
    "LOCAL_DATABASE_URL",
    "postgresql://postgres:password@localhost:5433/open_navigator",
)

# Runtime / app-owned tables that live in public but are NOT serving data. The
# running prod app owns these in the TARGET; copying our local copies over them
# would destroy production users / OAuth state / feed prefs. NEVER mirror them.
RUNTIME_OWNED = frozenset(
    {
        "user",
        "contact_oauth_state",
        "social_follows",
        "user_lens_prefs",
        "user_locations",
        "user_signal_prefs",
        "meeting_document_gap_cache",
    }
)

# Civic-serving objects that ARE mirrored to Neon, but NOT by this generic
# copy — they have a dedicated loader that ships a slim/derived form. Listing
# them here keeps them off the unclassified-warning AND out of the full-view
# copy (the bug this guards against: local public.event_documents is a VIEW over
# gold carrying the FULL transcript text — ~13.7 GB — so a blunt copy busts the
# 512 MB cap). The slim path keeps ALL analyzed meetings as cues-only rows
# (excerpt + segment timings, content/content_tsv NULLed) → ~108 MB.
#   event_documents -> hosting/neon/sync_event_documents_to_neon.py
DEDICATED_LOADER = frozenset(
    {
        "event_documents",
    }
)

# The nonprofit / 990 money + MDM entity-resolution graph. These public objects
# are views over the FULL gold warehouse — together ~5 GB of materialized rows
# (grant ~2.3 GB, mdm_organization ~1.7 GB, mdm_bridge_org_jurisdiction ~0.8 GB,
# mdm_organization_nonprofit ~0.4 GB, nonprofit_sector_revenue). Neon's free
# tier caps the WHOLE project at 512 MB, so none of this can be served from
# Neon; grant alone is 4.5x the cap. The deployment is civic-only — these are
# never mirrored. Documented here (not just absent from CIVIC_SERVING) so the
# reason a heavy object is dropped is explicit at the skip site.
NON_SERVING = frozenset(
    {
        "grant",
        "mdm_organization",
        "mdm_organization_nonprofit",
        "mdm_bridge_org_jurisdiction",
        "nonprofit_sector_revenue",
        # raw OpenStates bills — 1.55M bills (~592 MB) + 5.7M sponsorships
        # (~1.18 GB), together ~3.5x the whole cap. The bill MAP is served by
        # rpt_bill_map_aggregate (allow-listed), so the raw rows aren't needed.
        "bills",
        "bill_sponsorship",
    }
)

# Explicit allow-list of civic-serving public objects to mirror to Neon
# (~240 MB total — comfortably under the 512 MB free-tier cap). This is an
# allow-list, not a deny-list, on purpose: under a HARD project-size cap a new
# object must default to *excluded* so it can't silently blow the budget. When
# a genuinely civic object is added to public, add it here (the run warns about
# any unclassified object so it gets surfaced). The federal grants.gov
# opportunities mart (`grant_opportunity`) is civic and distinct from the 990
# `grant` money graph above; `tag` ships its node table only.
CIVIC_SERVING = frozenset(
    {
        # events & AI analysis
        "event",
        "event_decision",
        "event_decision_place",
        "event_place_geocoded",
        "event_financial_item",
        "event_bill",
        "event_topic",
        "event_meeting",
        "event_meeting_document",
        # event_documents is intentionally absent — see DEDICATED_LOADER above
        # (slim cues-only, loaded by sync_event_documents_to_neon.py).
        "meeting_document",
        "mdm_bridge_event_analysis",
        # people & officials
        "contact_official",
        "person_government",
        # jurisdictions
        "jurisdictions",
        "civic_jurisdiction",
        "jurisdiction_document",
        "jurisdiction_mapping_analysis",
        "jurisdiction_state_aggregate",
        "jurisdiction_minutes_publish_lag",
        # bills, grants opportunities, feed, taxonomy
        "grant_opportunity",
        "rpt_bill_map_aggregate",
        "item_interestingness",
        "item_flags",
        "tag",
        # policy-question registry — the curated "Big questions" homepage section
        # reads the featured rows from policy_question; the detail page + related
        # endpoints read the other three (empty for curated rows, but the queries
        # still target the tables, so they must exist on Neon). Served via
        # /api/policy-question/*.
        "policy_question",
        "policy_question_relation",
        "canonical_argument",
        "question_instance",
        # reference series — annual CPI for the real-dollar / inflation toggle
        # (tiny: ~15 rows/series). Served via /api/cpi/annual.
        "cpi_annual",
        # --- triaged 2026-06-14: small civic marts, ~26 MB combined ---
        # browse counts + directory (homepage / browse surfaces)
        "browse_directory_summary",
        "browse_transcript_count",
        "browse_entity_state_transcript_count",
        # meeting-grain browse + topic/question linkage (Browse Topics/Questions)
        "meeting_browse",
        "meeting_question_link",
        "question_transcript_link",
        "civicsearch_topic",
        "topic_money_and_talk",
        "policy_question_trend",
        # decision detail + arguments
        "decision_speakers",
        "instance_argument",
        # finance / money lenses (small per-jurisdiction series)
        "jurisdiction_finance",
        "jurisdiction_property_tax_rate",
        "state_sales_tax_rate",
        "opportunity_atlas_mobility",
        "opportunity_atlas_mobility_national",
        # NOTE: meeting_topic_link (60 MB) + jurisdiction_finance_category (40 MB)
        # are deliberately deferred (budget headroom); add when on a larger tier.
    }
)


def _target_url(target: str) -> Optional[str]:
    if target == "prod":
        return os.getenv("NEON_DATABASE_URL")
    if target == "dev":
        return os.getenv("NEON_DATABASE_URL_DEV")
    raise ValueError(f"unknown target {target!r}")


def _same_database(url_a: str, url_b: str) -> bool:
    """True if two libpq URLs point at the same host:port/database.

    Guards against the footgun where the target resolves to the LOCAL warehouse
    (e.g. NEON_DATABASE_URL_DEV is set to localhost:5433): copying public ->
    itself would DROP the local serving views and self-deadlock the COPY read
    lock against its own DROP. We refuse rather than corrupt the source.
    """
    a, b = urlparse(url_a), urlparse(url_b)
    norm = lambda h: (h or "localhost").lower()
    return (
        norm(a.hostname) == norm(b.hostname)
        and (a.port or 5432) == (b.port or 5432)
        and (a.path or "").lstrip("/") == (b.path or "").lstrip("/")
    )


#: marker substrings of a DNS / name-resolution failure across psycopg2/libc.
_DNS_FAILURE_HINTS = (
    "could not translate host name",
    "name or service not known",
    "temporary failure in name resolution",
    "nodename nor servname provided",
)


def _vpn_dns_message(host: str, detail: str) -> str:
    """Operator-facing message for a host that won't resolve.

    The dominant cause in this dev setup is a **VPN (or split-DNS) intercepting
    name resolution** — frequently seen on WSL2 — not a dead Neon endpoint. We
    say so plainly with the fix, instead of leaking a psycopg2 traceback.
    """
    return (
        f"🌐 Cannot resolve Neon host '{host}' — {detail}\n"
        "      This is almost always a VPN / split-DNS issue intercepting name "
        "resolution (common on WSL2), NOT a Neon outage.\n"
        "      Fix: disconnect (or reconnect) the VPN, confirm with "
        f"`nslookup {host}`, then retry. Nothing on Neon was touched."
    )


def _preflight_resolves(url: str) -> Optional[str]:
    """Resolve the target host before we try to connect.

    Returns ``None`` if the host resolves, or a ready-to-log operator message if
    it does not (so the caller can fail fast and clean rather than mid-copy)."""
    parsed = urlparse(url)
    host, port = parsed.hostname, parsed.port or 5432
    if not host:
        return None
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return None
    except socket.gaierror as exc:
        return _vpn_dns_message(host, str(exc))


def _is_dns_failure(exc: BaseException) -> bool:
    return any(h in str(exc).lower() for h in _DNS_FAILURE_HINTS)


def _serving_objects(local_conn) -> List[str]:
    """Civic-serving local public relations to mirror, sorted.

    Returns only objects on the :data:`CIVIC_SERVING` allow-list. Under Neon's
    hard 512 MB project cap a blunt "everything in public minus a deny-list"
    copy ships the ~5 GB nonprofit/MDM money graph and fails object-by-object;
    so we copy an explicit civic allow-list instead. Any public object that is
    classified by *neither* the allow-list nor the runtime/non-serving
    deny-lists is logged as a warning and skipped, so a newly-added object is
    surfaced for triage rather than silently busting the cap.
    """
    with local_conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v', 'm')
            ORDER BY c.relname
            """
        )
        present = [r[0] for r in cur.fetchall()]

    unclassified = [
        r
        for r in present
        if r not in CIVIC_SERVING
        and r not in RUNTIME_OWNED
        and r not in NON_SERVING
        and r not in DEDICATED_LOADER
    ]
    if unclassified:
        logger.warning(
            "❓ {} unclassified public object(s) — NOT copied (add to CIVIC_SERVING "
            "if civic-serving, else NON_SERVING): {}",
            len(unclassified),
            ", ".join(unclassified),
        )

    missing = sorted(CIVIC_SERVING - set(present))
    if missing:
        logger.warning(
            "⚠️  {} allow-listed object(s) absent from local public (not built?): {}",
            len(missing),
            ", ".join(missing),
        )

    return [r for r in present if r in CIVIC_SERVING]


def _column_defs(local_conn, name: str) -> List[Tuple[str, str]]:
    """(column_name, formatted_type) for a public relation, in column order.

    ``format_type`` gives the exact target DDL type (``character varying(4)``,
    ``jsonb``, ``numeric(10,2)``, ``text[]`` …) so the staging table matches the
    source's shape exactly and the COPY round-trips cleanly.
    """
    with local_conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            WHERE a.attrelid = ('public.' || quote_ident(%s))::regclass
              AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
            """,
            (name,),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


def _copy_one(local_conn, neon_conn, name: str) -> int:
    """Mirror one local public object into the target as a table. Returns rows."""
    cols = _column_defs(local_conn, name)
    if not cols:
        logger.warning("⏭️  {} has no columns — skipping", name)
        return 0
    col_ddl = ", ".join(f'"{c}" {t}' for c, t in cols)
    load_tbl = f"{name}__load"

    # 1. Pull all rows out of local via COPY into a spillable buffer (memory for
    #    small relations, disk for big ones like event_documents).
    buf = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024, mode="w+b")
    with local_conn.cursor() as cur:
        cur.copy_expert(f'COPY (SELECT * FROM public."{name}") TO STDOUT', buf)
    nbytes = buf.tell()
    buf.seek(0)
    logger.debug("   ⬇️  {} — pulled {:.1f} MB from local", name, nbytes / 1e6)

    # 2. Build a fresh staging table on the target and COPY the rows in.
    with neon_conn.cursor() as cur:
        cur.execute(f'DROP TABLE IF EXISTS public."{load_tbl}"')
        cur.execute(f'CREATE TABLE public."{load_tbl}" ({col_ddl})')
        cur.copy_expert(f'COPY public."{load_tbl}" FROM STDIN', buf)
        cur.execute(f'SELECT count(*) FROM public."{load_tbl}"')
        rows = cur.fetchone()[0]
        logger.debug("   ⬆️  {} — staged {:,} rows on target, swapping…", name, rows)

        # 3. Atomic swap: drop whatever public.<name> is now (view OR table),
        #    rename staging into place. Window without the object = this txn only.
        cur.execute(
            "SELECT relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            (name,),
        )
        existing = cur.fetchone()
        if existing and existing[0] == "v":
            cur.execute(f'DROP VIEW IF EXISTS public."{name}" CASCADE')
        elif existing and existing[0] == "m":
            cur.execute(f'DROP MATERIALIZED VIEW IF EXISTS public."{name}" CASCADE')
        elif existing:
            cur.execute(f'DROP TABLE IF EXISTS public."{name}" CASCADE')
        cur.execute(f'ALTER TABLE public."{load_tbl}" RENAME TO "{name}"')
    neon_conn.commit()
    buf.close()
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Copy local public serving objects to a Neon public schema.",
    )
    parser.add_argument(
        "--target",
        choices=["prod", "dev"],
        default="prod",
        help="Neon target: prod=NEON_DATABASE_URL (default), dev=NEON_DATABASE_URL_DEV.",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Restrict to these object names (default: all serving objects).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the objects that would be copied and exit.",
    )
    parser.add_argument(
        "--lock-timeout",
        default="30s",
        help=(
            "Postgres lock_timeout for the target session (default 30s). The "
            "atomic swap's DROP needs AccessExclusive on public.<name>; if the "
            "live prod API is reading it the DROP would otherwise hang forever. "
            "With a timeout it fails that one object loudly and the run continues."
        ),
    )
    args = parser.parse_args(argv)

    logger.info("📡 Connecting to local warehouse...")
    local_conn = psycopg2.connect(LOCAL_DB_URL)
    # Reads must not hold AccessShareLocks across the whole run, or a concurrent
    # dbt rebuild of local public (DROP VIEW … AccessExclusiveLock) blocks behind
    # us. Autocommit releases each COPY's lock as soon as it finishes.
    local_conn.autocommit = True

    if args.only:
        # Explicit --only bypasses the civic allow-list (escape hatch for
        # targeted copies / a paid target), but never the runtime deny-list.
        wanted = set(args.only)
        skipped_runtime = wanted & RUNTIME_OWNED
        if skipped_runtime:
            logger.warning(
                "🚫 Refusing runtime/app-owned table(s): {} — these are never mirrored.",
                ", ".join(sorted(skipped_runtime)),
            )
        forced_heavy = wanted & NON_SERVING
        if forced_heavy:
            logger.warning(
                "⚠️  --only includes non-serving money/MDM object(s): {} — these "
                "exceed the 512 MB free-tier cap and will fail there.",
                ", ".join(sorted(forced_heavy)),
            )
        objects = sorted(wanted - RUNTIME_OWNED)
        logger.info("🗂️  {} object(s) to copy (--only override)", len(objects))
    else:
        objects = _serving_objects(local_conn)
        logger.info(
            "🗂️  {} civic-serving object(s) to copy "
            "(runtime + nonprofit/MDM money graph excluded)",
            len(objects),
        )

    if args.dry_run:
        for o in objects:
            logger.info("   • {}", o)
        local_conn.close()
        return 0

    neon_url = _target_url(args.target)
    if not neon_url:
        env = "NEON_DATABASE_URL" if args.target == "prod" else "NEON_DATABASE_URL_DEV"
        logger.error("❌ {} not set — cannot target Neon {}", env, args.target)
        local_conn.close()
        return 1

    if _same_database(neon_url, LOCAL_DB_URL):
        logger.error(
            "🛑 Target ({}) resolves to the LOCAL warehouse — refusing. Copying "
            "public onto itself would drop the local serving views. Point "
            "{} at a real remote Neon host.",
            urlparse(neon_url).hostname,
            "NEON_DATABASE_URL" if args.target == "prod" else "NEON_DATABASE_URL_DEV",
        )
        local_conn.close()
        return 1

    # Preflight: resolve the Neon host before doing anything. A VPN/split-DNS
    # blip (common on WSL2) makes the hostname unresolvable; catch it here and
    # exit with a clear operator message instead of a mid-run psycopg2 traceback.
    dns_err = _preflight_resolves(neon_url)
    if dns_err:
        logger.error(dns_err)
        local_conn.close()
        return 3  # distinct exit code: network/DNS, not a data error

    logger.warning(
        "🚀 Copying local public → Neon **{}** public ({} objects)",
        args.target.upper(),
        len(objects),
    )
    # Connect with a few quick retries: a transient resolver hiccup right after a
    # clean preflight just means the VPN flapped — back off briefly and retry.
    neon_conn = None
    for attempt in range(1, 4):
        try:
            neon_conn = psycopg2.connect(neon_url, connect_timeout=15)
            break
        except psycopg2.OperationalError as exc:
            if _is_dns_failure(exc):
                logger.error(_vpn_dns_message(urlparse(neon_url).hostname, str(exc).strip()))
                local_conn.close()
                return 3
            if attempt == 3:
                logger.error("❌ Could not connect to Neon after {} tries: {}", attempt, exc)
                local_conn.close()
                return 1
            logger.warning("⏳ Neon connect attempt {}/3 failed ({}); retrying…", attempt, exc)
            time.sleep(2 * attempt)
    # Bound how long the swap waits to acquire a lock. The DROP CASCADE on
    # public.<name> needs AccessExclusive; behind a live prod-API read it would
    # hang indefinitely. lock_timeout turns that into a fast, logged per-object
    # failure (the next run retries it) instead of a silent stall. It does NOT
    # cap a legitimately long COPY — only the wait to grab a lock.
    with neon_conn.cursor() as cur:
        cur.execute("SET lock_timeout = %s", (args.lock_timeout,))
    neon_conn.commit()

    ok, failed = 0, 0
    t_run = time.perf_counter()
    try:
        for i, name in enumerate(objects, 1):
            logger.info("▶️  [{}/{}] {} — copying…", i, len(objects), name)
            t0 = time.perf_counter()
            try:
                rows = _copy_one(local_conn, neon_conn, name)
                logger.success(
                    "✅ [{}/{}] {} — {:,} rows in {:.1f}s",
                    i, len(objects), name, rows, time.perf_counter() - t0,
                )
                ok += 1
            except Exception as exc:  # noqa: BLE001 — isolate per-object failure
                # A VPN flap mid-run kills the live socket; every remaining object
                # would fail the same way. Detect it, say so once, and abort the
                # rest rather than logging N identical broken-connection errors.
                if _is_dns_failure(exc) or getattr(neon_conn, "closed", 0):
                    logger.error(_vpn_dns_message(urlparse(neon_url).hostname, str(exc).strip()))
                    logger.error(
                        "🛑 Aborting after {}/{} objects (connection lost). "
                        "Re-run once the VPN/DNS is stable; copied objects persist.",
                        i - 1, len(objects),
                    )
                    failed += 1
                    break
                try:
                    neon_conn.rollback()
                except Exception:  # noqa: BLE001 — rollback on a dead conn is moot
                    pass
                logger.error(
                    "❌ [{}/{}] {} failed after {:.1f}s: {}",
                    i, len(objects), name, time.perf_counter() - t0, exc,
                )
                failed += 1
    finally:
        local_conn.close()
        neon_conn.close()

    logger.info(
        "📊 Copied {} ok, {} failed in {:.1f}s", ok, failed, time.perf_counter() - t_run
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
