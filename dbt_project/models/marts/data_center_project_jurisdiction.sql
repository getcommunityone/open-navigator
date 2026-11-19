{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Governments a data center project sits in (#531, the #445 mapping carried to
    projects). Grain: one row per (project_id, jurisdiction_id). Built in
    int_data_center_project__jurisdiction (see there for each basis).
*/

select l.*
from {{ ref('int_data_center_project__jurisdiction') }} as l
inner join {{ ref('data_center_project') }} as p on p.project_id = l.project_id
