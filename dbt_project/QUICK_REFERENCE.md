# dbt Quick Reference

## 🚀 Common Commands

### Running Models

```bash
# Run all models
dbt run

# Run specific model
dbt run --select stg_bronze_contacts

# Run model and all downstream dependencies
dbt run --select stg_bronze_contacts+

# Run model and all upstream dependencies
dbt run --select +contact_ai

# Full refresh (rebuild from scratch)
dbt run --full-refresh

# Run specific folder
dbt run --select staging
dbt run --select marts
```

### Testing

```bash
# Run all tests
dbt test

# Test specific model
dbt test --select contact_ai

# Test specific type
dbt test --select test_type:unique
dbt test --select test_type:not_null
```

### Documentation

```bash
# Generate documentation
dbt docs generate

# Serve documentation site (opens in browser)
dbt docs serve

# Serve on specific port
dbt docs serve --port 8001
```

### Debugging

```bash
# Test database connection
dbt debug

# Compile SQL without running
dbt compile

# Show SQL for specific model
dbt compile --select contact_ai
# Then check target/compiled/...

# Preview model results
dbt show --select stg_bronze_contacts --limit 10
```

### Packages

```bash
# Install packages from packages.yml
dbt deps

# Update packages
dbt deps --upgrade
```

## 🎯 Useful Flags

```bash
# Run with specific target (dev/prod)
dbt run --target prod

# Exclude specific models
dbt run --exclude staging

# Run by tag
dbt run --select tag:daily

# Fail fast (stop on first error)
dbt run --fail-fast

# Show detailed logs
dbt run --debug
```

## 🔍 Selection Syntax

```bash
# Model name
dbt run --select my_model

# Model and downstream
dbt run --select my_model+

# Model and upstream  
dbt run --select +my_model

# Model and both directions
dbt run --select +my_model+

# All models in folder
dbt run --select staging

# All models in folder (recursive)
dbt run --select staging.*

# By tag
dbt run --select tag:daily

# By source
dbt run --select source:bronze+

# Multiple selections (OR)
dbt run --select model_a model_b

# Intersection (AND)
dbt run --select staging,tag:daily
```

## 📊 Model Configuration

```sql
-- In .sql file
{{
    config(
        materialized='incremental',
        unique_key='id',
        on_schema_change='sync_all_columns',
        tags=['daily'],
        enabled=true
    )
}}
```

```yaml
# In .yml file
models:
  - name: my_model
    config:
      materialized: table
      tags: ['hourly']
```

## 🧪 Test Examples

```yaml
# Schema tests in .yml
columns:
  - name: id
    tests:
      - unique
      - not_null
      - relationships:
          to: ref('other_table')
          field: id
      - accepted_values:
          values: ['a', 'b', 'c']
```

```sql
-- Custom test in tests/
-- Should return 0 rows (empty = pass)
SELECT * FROM {{ ref('my_model') }}
WHERE invalid_condition
```

## 🔄 Incremental Strategies

```sql
-- Append (default)
{{ config(materialized='incremental') }}

-- Delete + insert
{{
    config(
        materialized='incremental',
        unique_key='id',
        incremental_strategy='delete+insert'
    )
}}

-- Merge (upsert)
{{
    config(
        materialized='incremental',
        unique_key='id',
        incremental_strategy='merge'
    )
}}
```

## 📝 Jinja Snippets

```sql
-- Conditional logic
{% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}

-- Loop
{% for column in ['a', 'b', 'c'] %}
    {{ column }},
{% endfor %}

-- Reference model
{{ ref('other_model') }}

-- Reference source
{{ source('schema', 'table') }}

-- Use variable
{{ var('my_variable') }}

-- Use macro
{{ my_macro(argument) }}
```

## 🛠️ Macros

```sql
-- Define macro in macros/
{% macro cents_to_dollars(column_name, scale=2) %}
    ({{ column_name }} / 100)::numeric(16, {{ scale }})
{% endmacro %}

-- Use in model
SELECT {{ cents_to_dollars('price_cents') }} as price_dollars
```

## 📋 Project Setup

```bash
# Initialize new project
dbt init my_project

# Install packages
dbt deps

# Test connection
dbt debug

# Run project
dbt build  # Run + test everything
```

## 🐛 Troubleshooting

```bash
# Clear compiled files
dbt clean

# Full logs
dbt run --debug

# Compile only (no run)
dbt compile --select my_model

# Check for syntax errors
dbt parse
```

## 🎨 Common Patterns

### Safe column selection
```sql
SELECT
    {{ dbt_utils.star(from=ref('my_table'), except=['sensitive_column']) }}
FROM {{ ref('my_table') }}
```

### Generate surrogate key
```sql
{{ dbt_utils.generate_surrogate_key(['column1', 'column2']) }} as id
```

### Union tables
```sql
{{ dbt_utils.union_relations(
    relations=[ref('table1'), ref('table2')]
) }}
```

### Pivot
```sql
{{ dbt_utils.pivot(
    column='status',
    values=['pending', 'approved', 'rejected'],
    agg='sum',
    then_value='amount'
) }}
```
