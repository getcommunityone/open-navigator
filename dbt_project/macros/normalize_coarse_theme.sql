{% macro normalize_coarse_theme(theme_column) %}
{#-
    Collapse the noisy free-text `primary_theme` into one of the 18 canonical
    COFOG theme buckets (or '__unthemed__'). SQL port of
    packages/llm/src/llm/policy_questions/coarse_theme.py (`coarse_theme` + its
    `_RULES`) and the exact-match step of
    packages/llm/src/llm/gemini/policy_themes.py (`normalize_primary_theme`).

    Logic (must match the Python exactly so behavior is identical):
      1. Case-insensitive EXACT match against the controlled vocabulary first —
         a value that is already a canonical label passes straight through
         (returning the canonical-cased label).
      2. Otherwise, lower() the input and test the ordered keyword groups; the
         FIRST keyword-substring hit wins. Specific buckets (zoning/land-use,
         housing) precede generic ones (economic development, governance), in
         the SAME order as `_RULES`.
      3. No hit => '__unthemed__'.

    `theme_column` is a SQL expression (a column ref or literal). The 18 canonical
    labels and their COFOG codes also live in the seed `policy_theme_cofog`
    (primary_theme, cofog_code) — JOIN to that seed in the model to resolve the
    code; this macro returns the label only.
-#}
{%- set canonical = [
    "Fiscal and Budget Management",
    "Infrastructure and Capital Projects",
    "Zoning and Land Use",
    "Public Safety and Emergency Services",
    "Environmental and Natural Resources",
    "Housing and Community Development",
    "Economic Development and Business",
    "Transportation and Mobility",
    "Education and Workforce",
    "Health and Human Services",
    "Civil Rights and Equity",
    "Governance and Administrative Policy",
    "Parks and Recreation",
    "Utilities and Public Works",
    "Technology and Innovation",
    "Legal and Compliance",
    "Intergovernmental Relations",
    "Public Engagement and Communications"
] -%}

{#- Ordered keyword rules — mirror coarse_theme._RULES verbatim, in order. -#}
{%- set rules = [
    (["zoning", "rezon", "land use", "variance", "subdivision", "plat", "annex",
      "setback", "easement", "parcel", "site plan"], "Zoning and Land Use"),
    (["housing", "affordable", "homeless", "shelter", "tenant"], "Housing and Community Development"),
    (["police", "fire", "public safety", "emergency", "ems", "ambulance", "crime",
      "law enforcement", "disaster", "911"], "Public Safety and Emergency Services"),
    (["transport", "transit", "traffic", "mobility", "street", "sidewalk", "road",
      "highway", "parking", "pedestrian"], "Transportation and Mobility"),
    (["water", "sewer", "stormwater", "utility", "utilities", "wastewater",
      "drainage", "public works"], "Utilities and Public Works"),
    (["infrastructure", "capital", "construction", "facility", "building project",
      "bridge", "dam"], "Infrastructure and Capital Projects"),
    (["environment", "natural resource", "sustainab", "conservation", "climate",
      "pollution", "tree", "wetland"], "Environmental and Natural Resources"),
    (["park", "recreation", "library", "arts", "culture", "museum", "trail",
      "festival"], "Parks and Recreation"),
    (["education", "school", "workforce", "student", "teacher", "college"], "Education and Workforce"),
    (["health", "human services", "social services", "senior", "welfare", "mental",
      "opioid", "medicaid"], "Health and Human Services"),
    (["budget", "fiscal", "finance", "tax", "audit", "appropriat", "millage",
      "revenue", "bond"], "Fiscal and Budget Management"),
    (["economic", "business", "development", "downtown", "tourism", "incentive",
      "redevelopment"], "Economic Development and Business"),
    (["technology", "innovation", "broadband", "cyber", "digital", "software"], "Technology and Innovation"),
    (["civil right", "equity", "diversity", "inclusion", "discrimination"], "Civil Rights and Equity"),
    (["intergovern", "regional", "county board", "state legislat"], "Intergovernmental Relations"),
    (["legal", "complian", "litigation", "ordinance review", "lawsuit"], "Legal and Compliance"),
    (["engagement", "communication", "outreach", "public comment", "transparency"],
     "Public Engagement and Communications"),
    (["governance", "administ", "personnel", "operations", "policy", "charter",
      "election", "appointment", "council rule", "government"], "Governance and Administrative Policy")
] -%}

{%- set col = theme_column -%}
case
    {#- Step 1: case-insensitive exact match against the controlled vocabulary. -#}
    {%- for label in canonical %}
    when lower(trim({{ col }})) = lower('{{ label }}') then '{{ label }}'
    {%- endfor %}
    {#- Step 2: ordered keyword groups; first substring hit wins. -#}
    {%- for keywords, target in rules %}
    when {% for kw in keywords %}lower({{ col }}) like '%{{ kw }}%'{% if not loop.last %} or {% endif %}{% endfor %} then '{{ target }}'
    {%- endfor %}
    else '__unthemed__'
end
{%- endmacro %}
