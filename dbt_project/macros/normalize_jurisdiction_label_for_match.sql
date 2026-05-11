{% macro normalize_jurisdiction_label_for_match(expr) -%}
NULLIF(
    REGEXP_REPLACE(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                LOWER(TRIM({{ expr }})),
                                '^\\s*st\\.\\s+',
                                'saint ',
                                'gi'
                            ),
                            '(^|[^[:alpha:]])st\\.\\s+',
                            '\\1saint ',
                            'gi'
                        ),
                        '^(city|town|village|borough|county|township|parish) of\\s+',
                        '',
                        'gi'
                    ),
                    '\\s+(city|town|village|borough|county|township|parish)$',
                    '',
                    'gi'
                ),
                '\\s+parish$',
                ' county',
                'gi'
            ),
            '[^a-z0-9]+',
            ' ',
            'g'
        ),
        '\\s+',
        ' ',
        'g'
    ),
    ''
)
{%- endmacro %}
