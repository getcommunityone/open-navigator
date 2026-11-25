{% macro swap_guard(lock_timeout='10s') -%}
{#-
    In-transaction pre-hook that keeps a `table` rebuild from blocking readers or overlapping itself
    (#935, #938). Pair it with swap_guard_check() as the FIRST in-transaction post_hook.

    dbt's table materialization runs, in ONE transaction: the in-transaction pre_hooks, the build of
    <model>__dbt_tmp and its `indexes`, the rename of the live table to __dbt_backup, the rename of
    the tmp table in, the in-transaction post_hooks, and COMMIT. The renames take ACCESS EXCLUSIVE
    locks. Two things made that hurt:

      * The renames queue behind any running reader, and every new reader queues behind them, with
        no limit. A lock_timeout on the RENAMES caps that wait: if the swap can't get its lock in
        time, the transaction rolls back (the old table keeps serving) instead of freezing readers.
      * Two builds of the same model overlapping doubled the IO and the lock chains.
        pg_try_advisory_xact_lock lets only one build per relation hold the transaction; a second
        one raises at once.

    The timeout is NOT set here. A model with contract foreign keys creates its tmp table with
    `references <parent>`, which takes SHARE ROW EXCLUSIVE on the parent and waits for sibling models
    building against the same parent; a timeout over the whole build would fail them for no reason.
    This hook only records the timeout (transaction-local setting swap_guard.lock_timeout); the
    project's postgres__rename_relation applies it immediately before each rename, and only in a
    transaction this hook started.

    NEVER give such a model a before-begin hook ({'sql': ..., 'transaction': false} in pre_hook).
    dbt runs a literal `commit;` before those, after which psycopg2 never opens a transaction
    again: every later statement autocommits, the renames stop being atomic (a reader between them
    gets "relation does not exist"), and transaction-local settings / xact locks end with their own
    statement. swap_guard_check() catches that. Statements that lock OTHER tables (adding a foreign
    key) belong in after-commit post_hooks ({'sql': ..., 'transaction': false} in post_hook), so they
    never wait while holding the swapped table's lock.
    See web_docs/docs/development/non-blocking-table-rebuilds.md.

        pre_hook=["{{ swap_guard() }}"],
        post_hook=["{{ swap_guard_check() }}"]
-#}
select set_config('swap_guard.txid', txid_current()::text, true),
       set_config('swap_guard.lock_timeout', '{{ lock_timeout }}', true);
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
    In-transaction post_hook for swap_guard(), and it must be the FIRST post_hook: it runs right after
    the renames, before COMMIT.

      * It fails the build if the swap did not run in the transaction swap_guard() started (the txid
        it recorded with a transaction-local setting is gone or different), which means the renames
        were not atomic.
      * It ends the rename timeout (lock_timeout back to default, swap_guard.lock_timeout cleared), so
        nothing after the renames inherits it.
-#}
do $swap_guard_check$
begin
    if coalesce(current_setting('swap_guard.txid', true), '') <> txid_current()::text then
        raise exception 'swap_guard_check: {{ this }} was swapped outside the guarded transaction (a before-begin hook?); the renames were not atomic';
    end if;
end
$swap_guard_check$;
set local lock_timeout to default;
select set_config('swap_guard.lock_timeout', '', true)
{%- endmacro %}


{% macro postgres__rename_relation(from_relation, to_relation) -%}
{#-
    dbt's rename, plus swap_guard's timeout (#938): when the current transaction was started by
    swap_guard() (it recorded swap_guard.lock_timeout), the rename waits at most that long for its
    lock and otherwise fails, rolling the swap back. In any other transaction the setting is empty
    and this is exactly dbt's default__rename_relation.
-#}
  {% set target_name = adapter.quote_as_configured(to_relation.identifier, 'identifier') %}
  {% call statement('rename_relation') -%}
    select set_config('lock_timeout', current_setting('swap_guard.lock_timeout', true), true)
    where coalesce(current_setting('swap_guard.lock_timeout', true), '') <> '';
    alter table {{ from_relation.render() }} rename to {{ target_name }}
  {%- endcall %}
{% endmacro %}
