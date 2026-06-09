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
Local ``public`` also holds the live application's **runtime / auth** tables
(see :data:`RUNTIME_OWNED`). Those are written by the *running prod app* — the
real user accounts, OAuth flow state, social graph, feed prefs, and the
on-demand meeting-gap cache live in the TARGET, not here. Copying our (usually
empty local) copies over them would wipe production users. They are excluded
from the copy and never touched on the target.

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
    """Local public relations to mirror: ordinary tables, views, matviews —
    minus the runtime/app-owned deny-list. Returns names sorted."""
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
        return [r[0] for r in cur.fetchall() if r[0] not in RUNTIME_OWNED]


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

    objects = _serving_objects(local_conn)
    if args.only:
        wanted = set(args.only)
        skipped_runtime = wanted & RUNTIME_OWNED
        if skipped_runtime:
            logger.warning(
                "🚫 Refusing runtime/app-owned table(s): {} — these are never mirrored.",
                ", ".join(sorted(skipped_runtime)),
            )
        objects = [o for o in objects if o in wanted]

    logger.info(
        "🗂️  {} serving object(s) to copy (runtime/auth tables excluded: {})",
        len(objects),
        ", ".join(sorted(RUNTIME_OWNED)),
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
