{% macro ensure_declared_foreign_keys(dry_run=false) %}
{#-
    #783: put back every foreign key that a dbt model declares but Postgres lacks.

    dbt rebuilds a table and then drops the old relation with `drop ... cascade`
    (dbt/include/global_project/macros/relations/drop.sql). The CASCADE silently
    removes every child foreign key that pointed at the rebuilt parent, so keys
    declared in `schema.yml` vanish after a `dbt run`. Incremental models that are
    never dropped keep theirs, which is why the loss looks random.

    This reads `graph.nodes` (model-level `constraints:` and column-level
    `constraints:` of `type: foreign_key`) and adds each missing key with
    `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ...`.

    It never deletes rows. A key is skipped, with a logged warning that names the
    table and the count, when:
      - the child or the parent relation does not exist yet;
      - the parent has no unique index or primary key on exactly `to_columns`
        (Postgres would reject the constraint);
      - the child has orphan rows (a non-null key with no matching parent row).
    A key that already exists on the same child columns and the same parent is left
    alone, whatever it is named.

    Runs from on-run-end after every `dbt run` and by hand:

        dbt run-operation ensure_declared_foreign_keys
        dbt run-operation ensure_declared_foreign_keys --args '{dry_run: true}'

    `to:` is read as `ref('model')` or `ref('package', 'model')`; any other form
    (a free-text `expression:`) is logged and skipped.
-#}
{%- if not execute -%}{{ return('') }}{%- endif -%}
{%- if target.type != 'postgres' -%}{{ return('') }}{%- endif -%}

{#- Collect (child node, columns, parent model name, parent columns) from the graph. -#}
{%- set specs = [] -%}
{%- for node in graph.nodes.values() if node.resource_type == 'model' and node.config.materialized in ('table', 'incremental') -%}
  {%- for c in node.constraints if c.type == 'foreign_key' -%}
    {%- do specs.append({'node': node, 'cols': c.columns or [], 'to': c.to, 'to_cols': c.to_columns or []}) -%}
  {%- endfor -%}
  {%- for col in node.columns.values() -%}
    {%- for c in col.constraints if c.type == 'foreign_key' -%}
      {%- do specs.append({'node': node, 'cols': [col.name], 'to': c.to, 'to_cols': c.to_columns or []}) -%}
    {%- endfor -%}
  {%- endfor -%}
{%- endfor -%}

{%- set added = [] -%}
{%- set present = [] -%}
{%- set skipped = [] -%}

{%- for s in specs -%}
  {%- set child = s.node -%}
  {%- set child_rel = child.schema ~ '.' ~ (child.alias or child.name) -%}
  {%- set label = child_rel ~ '(' ~ (s.cols | join(', ')) ~ ')' -%}

  {#- Resolve `to: ref('x')` to the parent model node. -#}
  {%- set found = namespace(node=none) -%}
  {%- set to_txt = (s.to or '') | trim -%}
  {%- if to_txt.startswith('ref(') and to_txt.endswith(')') -%}
    {%- set ref_args = to_txt[4:-1].split(',') -%}
    {%- set parent_name = (ref_args[-1] | trim(" '\"")) -%}
    {%- for n in graph.nodes.values() if n.resource_type == 'model' and n.name == parent_name -%}
      {%- set found.node = n -%}
    {%- endfor -%}
  {%- endif -%}

  {%- set parent = found.node -%}
  {%- if parent is none or not s.cols or not s.to_cols or (s.cols | length) != (s.to_cols | length) -%}
    {%- do skipped.append(label ~ ': cannot resolve parent or columns from "' ~ (s.to or '') ~ '"') -%}
  {%- else -%}
    {%- set parent_rel = parent.schema ~ '.' ~ (parent.alias or parent.name) -%}
    {%- set both = run_query("select to_regclass('" ~ child_rel ~ "') is not null and to_regclass('" ~ parent_rel ~ "') is not null") -%}
    {%- if not (both and both.rows and both.rows[0][0]) -%}
      {%- do skipped.append(label ~ ': child or parent table not built yet') -%}
    {%- else -%}
      {%- set cols_arr = "array['" ~ (s.cols | join("','")) ~ "']::name[]" -%}
      {%- set pcols_arr = "array['" ~ (s.to_cols | join("','")) ~ "']::name[]" -%}

      {#- Already there under any name? Same child columns, same parent. -#}
      {%- set exists_sql -%}
        select 1
        from pg_constraint c
        where c.contype = 'f'
          and c.conrelid = '{{ child_rel }}'::regclass
          and c.confrelid = '{{ parent_rel }}'::regclass
          and (select array_agg(a.attname order by k.ord)
               from unnest(c.conkey) with ordinality k(attnum, ord)
               join pg_attribute a on a.attrelid = c.conrelid and a.attnum = k.attnum
              ) = {{ cols_arr }}
        limit 1
      {%- endset -%}
      {%- set have = run_query(exists_sql) -%}
      {%- if have and have.rows | length > 0 -%}
        {%- do present.append(label) -%}
      {%- else -%}
        {#- Postgres needs a unique non-partial index (or PK) on the parent columns. -#}
        {%- set uniq_sql -%}
          select 1
          from pg_index ix
          where ix.indrelid = '{{ parent_rel }}'::regclass
            and ix.indisunique
            and ix.indpred is null
            and (select array_agg(a.attname order by k.ord)
                 from unnest(ix.indkey) with ordinality k(attnum, ord)
                 join pg_attribute a on a.attrelid = ix.indrelid and a.attnum = k.attnum
                ) = {{ pcols_arr }}
          limit 1
        {%- endset -%}
        {%- set has_unique = run_query(uniq_sql) -%}
        {%- if not (has_unique and has_unique.rows | length > 0) -%}
          {%- do skipped.append(label ~ ': ' ~ parent_rel ~ ' has no unique key on (' ~ (s.to_cols | join(', ')) ~ ')') -%}
        {%- else -%}
          {#- Orphans: a fully non-null child key with no parent row. Never delete them. -#}
          {%- set orphan_sql -%}
            select count(*)
            from {{ child_rel }} c
            where {% for col in s.cols %}c.{{ adapter.quote(col) }} is not null{% if not loop.last %} and {% endif %}{% endfor %}
              and not exists (
                select 1 from {{ parent_rel }} p
                where {% for col in s.cols %}p.{{ adapter.quote(s.to_cols[loop.index0]) }} = c.{{ adapter.quote(col) }}{% if not loop.last %} and {% endif %}{% endfor %}
              )
          {%- endset -%}
          {%- set orphans = run_query(orphan_sql) -%}
          {%- set n_orphans = orphans.rows[0][0] | int -%}
          {%- if n_orphans > 0 -%}
            {%- do skipped.append(label ~ ' -> ' ~ parent_rel ~ ': ' ~ n_orphans ~ ' orphan row(s); not added') -%}
          {%- else -%}
            {%- set cname = ((child.alias or child.name) ~ '_' ~ (s.cols | join('_')) ~ '_fkey')[:63] -%}
            {%- if not dry_run -%}
              {%- do run_query(
                  'alter table ' ~ child_rel ~ ' add constraint ' ~ adapter.quote(cname)
                  ~ ' foreign key (' ~ (s.cols | join(', '))
                  ~ ') references ' ~ parent_rel ~ ' (' ~ (s.to_cols | join(', ')) ~ ')'
              ) -%}
            {%- endif -%}
            {%- do added.append(label ~ ' -> ' ~ parent_rel) -%}
          {%- endif -%}
        {%- endif -%}
      {%- endif -%}
    {%- endif -%}
  {%- endif -%}
{%- endfor -%}

{{ log('ensure_declared_foreign_keys' ~ (' (dry run)' if dry_run else '') ~ ': ' ~ (added | length) ~ ' added, ' ~ (present | length) ~ ' already present, ' ~ (skipped | length) ~ ' skipped', info=true) }}
{%- for a in added %}{{ log('  + ' ~ a, info=true) }}{%- endfor %}
{%- for k in skipped %}{{ log('  ! skipped ' ~ k, info=true) }}{%- endfor %}
{%- do return('') -%}
{% endmacro %}
