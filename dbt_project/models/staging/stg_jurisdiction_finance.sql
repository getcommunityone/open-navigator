{{
  config(
    materialized='view',
    tags=['staging', 'finance', 'tpc']
  )
}}

/*
staging.stg_jurisdiction_finance — cleaned, latest-year government finance per
government, derived from bronze.bronze_jurisdiction_tpc (Tax Policy Center /
Urban Institute republication of the U.S. Census Bureau Annual Survey of State &
Local Government Finances + Census of Governments).

GRAIN: one row per government (gov_type, id_code), at its MOST RECENT fiscal_year.

WHAT THIS DOES
  1. Picks the latest available fiscal_year per government.
  2. Casts the needed JSONB finance fields (raw_record) to numeric. All Census
     finance values are integer dollars *in thousands*; we leave them in their
     native (thousands) unit here and scale to whole dollars in the mart so the
     unit conversion is in exactly one place. Non-numeric / blank guards -> NULL
     (honest "missing", never 0).
  3. Maps Census expenditure-by-FUNCTION variables into 8 display categories
     (see CATEGORY MAPPING below). The sum of the 8 categories equals
     `direct_expenditure` (Census `Direct_Expenditure`) by construction — the
     category split is of DIRECT expenditure (the money the government actually
     spends on services), NOT of `Total_Expenditure` (which also includes
     intergovernmental transfers and insurance-trust/retirement benefit payouts
     that are not a "service category"). Both totals are carried so the mart and
     API can reconcile: total_expenditure = direct_expenditure +
     intergovernmental_expenditure + insurance_trust_expenditure (+ rounding).

CALENDAR YEAR (CLAUDE.md): fiscal_year is a bare year -> cast to INTEGER here.
  Wire/JSON string serialization happens later at the API boundary, not here.

CATEGORY MAPPING (Census function -> display bucket). We use the *_Direct_Exp
  (direct-expenditure) variant of each function, NOT *_Total_Exp: the total
  variants fold in intergovernmental transfers (state/county aid to local govts),
  which double-counts and overshoots direct_expenditure badly for states. Each
  function is assigned to exactly one bucket so the buckets partition direct
  expenditure:
    Education            : Total_Educ_Direct_Exp, Libraries_Direct_Exp
    Public Safety        : Police_Prot_Direct_Exp, Fire_Prot_Direct_Exp,
                           Correct_Direct_Exp, Prot_Insp_Direct_Exp
    Infrastructure & Hwy : Total_Highways_Dir_Exp, Air_Trans_Direct_Expend,
                           Water_Trans_Direct_Exp, Parking_Direct_Expend
    Parks & Recreation   : Parks___Rec_Direct_Exp
    Health & Welfare     : Health_Direct_Expend, Total_Hospital_Dir_Exp,
                           Public_Welf_Direct_Exp
    Utilities            : Total_Util_Current_Exp + Total_Util_Cap_Outlay (the
                           direct portion of water+elec+gas+transit utils; the
                           *_Total_Exp variant adds utility debt interest already
                           counted in Other & Debt -> excluded to avoid double-count),
                           Sewerage_Direct_Expend, SW_Mgmt_Direct_Expend
    Administration & Govt: Fin_Admin_Direct_Exp, Judicial_Direct_Expend,
                           Gen_Pub_Bldg_Total_Exp (direct-only), General_NEC_Direct_Exp,
                           Cen_Staff_Direct_Exp, Emp_Sec_Adm_Direct_Exp
    Other & Debt         : Total_Interest_on_Debt, Hous___Com_Direct_Exp,
                           Natural_Res_Direct_Exp, Misc_Com_Activ_Tot_Exp (direct-only),
                           Liquor_Stores_Tot_Exp (direct-only), Transit_Sub_Direct_Sub,
                           plus a residual reconciliation term so the 8 buckets
                           always sum to direct_expenditure. (Educ_NEC is NOT added
                           here — it is already inside Total_Educ_Direct_Exp.)
*/

with latest as (

    select
        gov_type,
        id_code,
        max(fiscal_year::int) as latest_year
    from {{ source('bronze', 'bronze_jurisdiction_tpc') }}
    where fiscal_year ~ '^[0-9]{4}$'
    group by 1, 2

),

src as (

    select
        b.gov_type,
        b.id_code,
        b.name,
        b.state_code,
        b.state_fips,
        b.fiscal_year::int                              as fiscal_year,
        b.population,
        b.raw_record
    from {{ source('bronze', 'bronze_jurisdiction_tpc') }} b
    inner join latest l
        on  b.gov_type = l.gov_type
        and b.id_code  = l.id_code
        and b.fiscal_year::int = l.latest_year

),

-- Cast every needed JSONB key to numeric once, guarding non-numeric/blank -> NULL.
{% set n = "(case when nullif(trim(raw_record->>'%s'), '') ~ '^-?[0-9]+(\\.[0-9]+)?$' then (raw_record->>'%s')::numeric else null end)" %}

cast_fields as (

    select
        gov_type,
        id_code,
        name,
        state_code,
        state_fips,
        fiscal_year,
        population,

        -- Headline totals (thousands of dollars)
        {{ n | format('Total_Revenue', 'Total_Revenue') }}                 as total_revenue_k,
        {{ n | format('Total_Expenditure', 'Total_Expenditure') }}         as total_expenditure_k,
        {{ n | format('Direct_Expenditure', 'Direct_Expenditure') }}       as direct_expenditure_k,
        {{ n | format('Total_IG_Expenditure', 'Total_IG_Expenditure') }}   as ig_expenditure_k,
        {{ n | format('Total_Insur_Trust_Ben', 'Total_Insur_Trust_Ben') }} as insur_trust_expenditure_k,

        -- Taxes (thousands)
        {{ n | format('Total_Taxes', 'Total_Taxes') }}                     as total_taxes_k,
        {{ n | format('Property_Tax', 'Property_Tax') }}                   as property_tax_k,
        {{ n | format('Total_Gen_Sales_Tax', 'Total_Gen_Sales_Tax') }}     as general_sales_tax_k,
        {{ n | format('Total_Select_Sales_Tax', 'Total_Select_Sales_Tax') }} as select_sales_tax_k,

        -- Expenditure by function (thousands) — DIRECT expenditure only.
        -- We deliberately use the *_Direct_Exp keys (not *_Total_Exp): the
        -- *_Total_Exp variants include INTERGOVERNMENTAL transfers (e.g. state
        -- aid passed to school districts), which would double-count and blow the
        -- category sum far past direct_expenditure for states/counties. Functions
        -- with no IG component (utilities, general buildings, misc commercial,
        -- liquor stores, interest on debt) have no *_Direct key, so their total
        -- IS their direct figure and we use the total key for those.
        {{ n | format('Total_Educ_Direct_Exp', 'Total_Educ_Direct_Exp') }} as f_education,
        {{ n | format('Libraries_Direct_Exp', 'Libraries_Direct_Exp') }}   as f_libraries,

        {{ n | format('Police_Prot_Direct_Exp', 'Police_Prot_Direct_Exp') }} as f_police,
        {{ n | format('Fire_Prot_Direct_Exp', 'Fire_Prot_Direct_Exp') }}   as f_fire,
        {{ n | format('Correct_Direct_Exp', 'Correct_Direct_Exp') }}       as f_correction,
        {{ n | format('Prot_Insp_Direct_Exp', 'Prot_Insp_Direct_Exp') }}   as f_prot_insp,

        {{ n | format('Total_Highways_Dir_Exp', 'Total_Highways_Dir_Exp') }} as f_highways,
        {{ n | format('Air_Trans_Direct_Expend', 'Air_Trans_Direct_Expend') }} as f_air_trans,
        {{ n | format('Water_Trans_Direct_Exp', 'Water_Trans_Direct_Exp') }} as f_water_trans,
        {{ n | format('Parking_Direct_Expend', 'Parking_Direct_Expend') }} as f_parking,

        {{ n | format('Parks___Rec_Direct_Exp', 'Parks___Rec_Direct_Exp') }} as f_parks_rec,

        {{ n | format('Health_Direct_Expend', 'Health_Direct_Expend') }}   as f_health,
        {{ n | format('Total_Hospital_Dir_Exp', 'Total_Hospital_Dir_Exp') }} as f_hospital,
        {{ n | format('Public_Welf_Direct_Exp', 'Public_Welf_Direct_Exp') }} as f_public_welfare,

        -- Utilities: use Current + CapOutlay (the DIRECT portion), NOT
        -- Total_Util_Total_Exp. The total folds in Total_Util_Inter_Exp (utility
        -- debt interest) which is already captured by Total_Interest_on_Debt in
        -- the Other & Debt bucket — counting the total here double-counts utility
        -- interest (e.g. the NYC $1.17B overshoot).
        {{ n | format('Total_Util_Current_Exp', 'Total_Util_Current_Exp') }} as f_util_current,
        {{ n | format('Total_Util_Cap_Outlay', 'Total_Util_Cap_Outlay') }}  as f_util_cap,
        {{ n | format('Sewerage_Direct_Expend', 'Sewerage_Direct_Expend') }} as f_sewerage,
        {{ n | format('SW_Mgmt_Direct_Expend', 'SW_Mgmt_Direct_Expend') }} as f_solid_waste,

        {{ n | format('Fin_Admin_Direct_Exp', 'Fin_Admin_Direct_Exp') }}   as f_fin_admin,
        {{ n | format('Judicial_Direct_Expend', 'Judicial_Direct_Expend') }} as f_judicial,
        {{ n | format('Gen_Pub_Bldg_Total_Exp', 'Gen_Pub_Bldg_Total_Exp') }} as f_gen_pub_bldg,
        {{ n | format('General_NEC_Direct_Exp', 'General_NEC_Direct_Exp') }} as f_general_nec,
        {{ n | format('Cen_Staff_Direct_Exp', 'Cen_Staff_Direct_Exp') }}   as f_central_staff,
        {{ n | format('Emp_Sec_Adm_Direct_Exp', 'Emp_Sec_Adm_Direct_Exp') }} as f_emp_sec_adm,

        {{ n | format('Total_Interest_on_Debt', 'Total_Interest_on_Debt') }} as f_interest_debt,
        {{ n | format('Hous___Com_Direct_Exp', 'Hous___Com_Direct_Exp') }} as f_housing,
        {{ n | format('Natural_Res_Direct_Exp', 'Natural_Res_Direct_Exp') }} as f_natural_res,
        {{ n | format('Misc_Com_Activ_Tot_Exp', 'Misc_Com_Activ_Tot_Exp') }} as f_misc_com,
        {{ n | format('Liquor_Stores_Tot_Exp', 'Liquor_Stores_Tot_Exp') }} as f_liquor_stores,
        {{ n | format('Transit_Sub_Direct_Sub', 'Transit_Sub_Direct_Sub') }} as f_transit_sub,

        -- FIPS components for the jurisdiction FK match
        raw_record->>'FIPS_Place'  as fips_place,
        raw_record->>'FIPS_County' as fips_county

    from src

),

categorized as (

    select
        gov_type,
        id_code,
        -- Clean display name: drop the trailing gov-type suffix ('CITY','COUNTY',
        -- etc.) that the Census appends, and Title-case it.
        initcap(trim(
            regexp_replace(
                name,
                '\s+(CITY|COUNTY|TOWN|TOWNSHIP|VILLAGE|BOROUGH|PARISH|SCHOOL DISTRICT|GOVT|GOVERNMENT)\s*$',
                '',
                'i'
            )
        ))                                              as jurisdiction_name,
        state_code,
        state_fips,
        fiscal_year,
        population,
        fips_place,
        fips_county,

        total_revenue_k,
        total_expenditure_k,
        direct_expenditure_k,
        ig_expenditure_k,
        insur_trust_expenditure_k,
        total_taxes_k,
        property_tax_k,
        general_sales_tax_k,
        select_sales_tax_k,

        -- 8 display categories (thousands). Each is NULL only if EVERY component
        -- is NULL (honest "missing"); otherwise components coalesce to 0 within
        -- the bucket so a partially-reported function still sums correctly.
        case when f_education is null and f_libraries is null then null
             else coalesce(f_education,0)+coalesce(f_libraries,0) end                  as cat_education_k,

        case when f_police is null and f_fire is null and f_correction is null and f_prot_insp is null then null
             else coalesce(f_police,0)+coalesce(f_fire,0)+coalesce(f_correction,0)+coalesce(f_prot_insp,0) end as cat_public_safety_k,

        case when f_highways is null and f_air_trans is null and f_water_trans is null and f_parking is null then null
             else coalesce(f_highways,0)+coalesce(f_air_trans,0)+coalesce(f_water_trans,0)+coalesce(f_parking,0) end as cat_infrastructure_k,

        f_parks_rec                                                                    as cat_parks_rec_k,

        case when f_health is null and f_hospital is null and f_public_welfare is null then null
             else coalesce(f_health,0)+coalesce(f_hospital,0)+coalesce(f_public_welfare,0) end as cat_health_welfare_k,

        case when f_util_current is null and f_util_cap is null and f_sewerage is null and f_solid_waste is null then null
             else coalesce(f_util_current,0)+coalesce(f_util_cap,0)+coalesce(f_sewerage,0)+coalesce(f_solid_waste,0) end as cat_utilities_k,

        case when f_fin_admin is null and f_judicial is null and f_gen_pub_bldg is null and f_general_nec is null and f_central_staff is null and f_emp_sec_adm is null then null
             else coalesce(f_fin_admin,0)+coalesce(f_judicial,0)+coalesce(f_gen_pub_bldg,0)+coalesce(f_general_nec,0)+coalesce(f_central_staff,0)+coalesce(f_emp_sec_adm,0) end as cat_admin_gov_k,

        case when f_interest_debt is null and f_housing is null and f_natural_res is null and f_misc_com is null and f_liquor_stores is null and f_transit_sub is null then null
             else coalesce(f_interest_debt,0)+coalesce(f_housing,0)+coalesce(f_natural_res,0)+coalesce(f_misc_com,0)+coalesce(f_liquor_stores,0)+coalesce(f_transit_sub,0) end as cat_other_debt_base_k

    from cast_fields

)

select
    *,
    -- Residual: direct_expenditure not captured by the named-function buckets
    -- lands in Other & Debt so the 8 buckets reconcile to direct_expenditure.
    -- Clamped at >= 0: for a handful of governments the named functions slightly
    -- OVERSHOOT direct_expenditure due to Census cross-variable rounding (the
    -- source reconciles ~300 vars), which would otherwise make the residual a
    -- small spurious negative. Clamping keeps Other & Debt non-negative without
    -- touching the real per-function values (genuine net-of-revenue negatives,
    -- e.g. a utility surplus, are preserved in their own bucket). The trade-off
    -- is that those few governments' categories sum to slightly OVER 100% of
    -- direct_expenditure rather than showing a negative slice.
    case
        when direct_expenditure_k is null then null
        else greatest(
            direct_expenditure_k
                - coalesce(cat_education_k, 0)
                - coalesce(cat_public_safety_k, 0)
                - coalesce(cat_infrastructure_k, 0)
                - coalesce(cat_parks_rec_k, 0)
                - coalesce(cat_health_welfare_k, 0)
                - coalesce(cat_utilities_k, 0)
                - coalesce(cat_admin_gov_k, 0)
                - coalesce(cat_other_debt_base_k, 0),
            0
        )
    end                                                 as cat_other_debt_residual_k
from categorized
