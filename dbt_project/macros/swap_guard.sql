{% macro swap_guard(lock_timeout='10s') -%}
{#-
    Pre-hook SQL that keeps a `table` rebuild from blocking readers or overlapping itself (#935).
    Pair it with swap_guard_release() as an after-commit post_hook.

    dbt's table materialization builds <model>__dbt_tmp, then renames the live table to
    __dbt_backup and renames the tmp table in. The renames take ACCESS EXCLUSIVE locks. Two
    things made that hurt:

      * The renames queue behind any running reader, and every new reader queues behind them,
        with no limit. lock_timeout caps the wait: if the swap can't get its lock in time, the
        model fails fast (re-run it) instead of freezing every query on the table.
      * Two builds of the same model overlapping (two sessions, a re-run on top of a slow run)
        doubled the IO and the lock chains. A session advisory lock lets only one build per
        relation run; a second one raises at once.

    SESSION scope, not SET LOCAL / xact locks: measured on this dbt (1.13), a SET LOCAL from a
    hook is gone by the next statement (the probe read lock_timeout = 0), and an xact advisory
    lock is released just as fast, so neither covered the swap. Session settings last until
    swap_guard_release() runs after the commit. If the build fails before that, they last
    until dbt closes the connection at the end of the invocation.

        pre_hook=["{{ swap_guard() }}"],
        post_hook=[{'sql': "{{ swap_guard_release() }}", 'transaction': false}]

    It does not fix indexes built in post_hooks: those run after the renames, inside the swap.
    Declare indexes in the model's `indexes` config instead, which dbt builds on the tmp table
    before the swap. See web_docs/docs/development/non-blocking-table-rebuilds.md.
-#}
do $swap_guard$
begin
    if not pg_try_advisory_lock(hashtext('{{ this }}')) then
        raise exception 'swap_guard: another build of {{ this }} is running; not starting a second one';
    end if;
end
$swap_guard$;
set lock_timeout = '{{ lock_timeout }}'
{%- endmacro %}


{% macro swap_guard_release() -%}
{#- After-commit post_hook for swap_guard(): end the session lock_timeout and release the lock. -#}
reset lock_timeout;
select pg_advisory_unlock(hashtext('{{ this }}'))
{%- endmacro %}
