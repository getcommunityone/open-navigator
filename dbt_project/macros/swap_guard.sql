{% macro swap_guard(lock_timeout='10s') -%}
{#-
    In-transaction pre-hook that keeps a `table` rebuild from blocking readers or overlapping itself
    (#935). Pair it with swap_guard_check() as an in-transaction post_hook.

    dbt's table materialization runs, in ONE transaction: the in-transaction pre_hooks, the build of
    <model>__dbt_tmp and its `indexes`, the rename of the live table to __dbt_backup, the rename of
    the tmp table in, the in-transaction post_hooks, and COMMIT. The renames take ACCESS EXCLUSIVE
    locks. Two things made that hurt:

      * The renames queue behind any running reader, and every new reader queues behind them, with
        no limit. SET LOCAL lock_timeout caps the wait: if the swap can't get its lock in time, the
        transaction rolls back (the old table keeps serving) instead of freezing every query.
      * Two builds of the same model overlapping doubled the IO and the lock chains.
        pg_try_advisory_xact_lock lets only one build per relation hold the transaction; a second
        one raises at once.

    Both end at the swap's COMMIT, so they never apply to the backup drop or to other models.

    NEVER give such a model a before-begin hook ({'sql': ..., 'transaction': false} in pre_hook).
    dbt runs a literal `commit;` before those, after which psycopg2 never opens a transaction
    again: every later statement autocommits, the renames stop being atomic (a reader between them
    gets "relation does not exist"), and SET LOCAL / xact locks end with their own statement.
    swap_guard_check() catches that. See web_docs/docs/development/non-blocking-table-rebuilds.md.

        pre_hook=["{{ swap_guard() }}"],
        post_hook=["{{ swap_guard_check() }}"]
-#}
set local lock_timeout = '{{ lock_timeout }}';
select set_config('swap_guard.txid', txid_current()::text, true);
do $swap_guard$
begin
    if not pg_try_advisory_xact_lock(hashtext('{{ this }}')) then
        raise exception 'swap_guard: another build of {{ this }} is running; not starting a second one';
    end if;
end
$swap_guard$
{%- endmacro %}


{% macro swap_guard_check() -%}
{#-
    In-transaction post_hook for swap_guard(): runs after the renames, before COMMIT. Fails the build
    if the swap did not run in the transaction swap_guard() started (the txid it recorded with a
    transaction-local setting is gone or different), which means the renames were not atomic.
-#}
do $swap_guard_check$
begin
    if coalesce(current_setting('swap_guard.txid', true), '') <> txid_current()::text then
        raise exception 'swap_guard_check: {{ this }} was swapped outside the guarded transaction (a before-begin hook?); the renames were not atomic';
    end if;
end
$swap_guard_check$
{%- endmacro %}
