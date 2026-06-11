{% macro state_fips_to_code(state_fips_column) %}
    /*
        Map a 2-digit US state/territory FIPS code to its 2-letter postal code.
        Companion to state_code_to_name(); use together to derive both
        state_code (2-letter) and state (full name) from a bare FIPS, e.g.

            {% raw %}{{ state_fips_to_code('state_fips') }} as state_code{% endraw %}

        Falls back to the FIPS value itself when unknown.
    */
    case lpad(trim({{ state_fips_column }}::text), 2, '0')
        when '01' then 'AL' when '02' then 'AK' when '04' then 'AZ' when '05' then 'AR'
        when '06' then 'CA' when '08' then 'CO' when '09' then 'CT' when '10' then 'DE'
        when '11' then 'DC' when '12' then 'FL' when '13' then 'GA' when '15' then 'HI'
        when '16' then 'ID' when '17' then 'IL' when '18' then 'IN' when '19' then 'IA'
        when '20' then 'KS' when '21' then 'KY' when '22' then 'LA' when '23' then 'ME'
        when '24' then 'MD' when '25' then 'MA' when '26' then 'MI' when '27' then 'MN'
        when '28' then 'MS' when '29' then 'MO' when '30' then 'MT' when '31' then 'NE'
        when '32' then 'NV' when '33' then 'NH' when '34' then 'NJ' when '35' then 'NM'
        when '36' then 'NY' when '37' then 'NC' when '38' then 'ND' when '39' then 'OH'
        when '40' then 'OK' when '41' then 'OR' when '42' then 'PA' when '44' then 'RI'
        when '45' then 'SC' when '46' then 'SD' when '47' then 'TN' when '48' then 'TX'
        when '49' then 'UT' when '50' then 'VT' when '51' then 'VA' when '53' then 'WA'
        when '54' then 'WV' when '55' then 'WI' when '56' then 'WY'
        when '60' then 'AS' when '66' then 'GU' when '69' then 'MP' when '72' then 'PR'
        when '78' then 'VI'
        else lpad(trim({{ state_fips_column }}::text), 2, '0')
    end
{% endmacro %}
