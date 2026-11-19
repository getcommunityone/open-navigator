{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Every stated figure about a data center project, each with its own source (#531).
    Grain: one row per (project, metric, source, value). Built in
    int_data_center_project__figure; served here with a foreign key to data_center_project.
*/

select f.*
from {{ ref('int_data_center_project__figure') }} as f
inner join {{ ref('data_center_project') }} as p on p.project_id = f.project_id
