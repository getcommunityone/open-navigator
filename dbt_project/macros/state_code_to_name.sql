{% macro state_code_to_name(state_code_column) %}
    /*
        Map a 2-letter US state code to its full state name.

        Reproduces the inline CASE in consolidate_to_master() from the archived
        scripts/datasources/master_data/create_jurisdiction_master.py. Falls back
        to the code itself when unknown (the Python `ELSE jc.state_code`).

        Usage:
            {% raw %}{{ state_code_to_name('state_code') }}{% endraw %}
    */
    case upper(trim({{ state_code_column }}))
        when 'AL' then 'Alabama'
        when 'AK' then 'Alaska'
        when 'AZ' then 'Arizona'
        when 'AR' then 'Arkansas'
        when 'CA' then 'California'
        when 'CO' then 'Colorado'
        when 'CT' then 'Connecticut'
        when 'DE' then 'Delaware'
        when 'FL' then 'Florida'
        when 'GA' then 'Georgia'
        when 'HI' then 'Hawaii'
        when 'ID' then 'Idaho'
        when 'IL' then 'Illinois'
        when 'IN' then 'Indiana'
        when 'IA' then 'Iowa'
        when 'KS' then 'Kansas'
        when 'KY' then 'Kentucky'
        when 'LA' then 'Louisiana'
        when 'ME' then 'Maine'
        when 'MD' then 'Maryland'
        when 'MA' then 'Massachusetts'
        when 'MI' then 'Michigan'
        when 'MN' then 'Minnesota'
        when 'MS' then 'Mississippi'
        when 'MO' then 'Missouri'
        when 'MT' then 'Montana'
        when 'NE' then 'Nebraska'
        when 'NV' then 'Nevada'
        when 'NH' then 'New Hampshire'
        when 'NJ' then 'New Jersey'
        when 'NM' then 'New Mexico'
        when 'NY' then 'New York'
        when 'NC' then 'North Carolina'
        when 'ND' then 'North Dakota'
        when 'OH' then 'Ohio'
        when 'OK' then 'Oklahoma'
        when 'OR' then 'Oregon'
        when 'PA' then 'Pennsylvania'
        when 'RI' then 'Rhode Island'
        when 'SC' then 'South Carolina'
        when 'SD' then 'South Dakota'
        when 'TN' then 'Tennessee'
        when 'TX' then 'Texas'
        when 'UT' then 'Utah'
        when 'VT' then 'Vermont'
        when 'VA' then 'Virginia'
        when 'WA' then 'Washington'
        when 'WV' then 'West Virginia'
        when 'WI' then 'Wisconsin'
        when 'WY' then 'Wyoming'
        when 'DC' then 'District of Columbia'
        when 'PR' then 'Puerto Rico'
        else upper(trim({{ state_code_column }}))
    end
{% endmacro %}
