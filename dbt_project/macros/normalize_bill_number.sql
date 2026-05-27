{% macro normalize_bill_number(bill_number_column) %}
    /*
        Normalize bill numbers for matching
        
        Examples:
            'HB 123' -> 'HB123'
            'House Bill 123' -> 'HB123'
            'S.B. 456' -> 'SB456'
            
        Usage:
            {% raw %}{{ normalize_bill_number('official_number') }}{% endraw %}
    */
    UPPER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    {{ bill_number_column }},
                    'HOUSE BILL', 'HB', 'gi'
                ),
                'SENATE BILL', 'SB', 'gi'
            ),
            '[^A-Z0-9]', '', 'g'
        )
    )
{% endmacro %}
