{{ config(materialized='table') }}

-- NENA v3.0 Relational Data Model: ng911.RdClass (NENA road class registry values)
SELECT * FROM (VALUES
    (1, 'Primary'), (2, 'Secondary'), (3, 'Local'), (4, 'Ramp'), (5, 'Service Drive'),
    (6, 'Vehicular Trail'), (7, 'Walkway'), (8, 'Stairway'), (9, 'Alley'), (10, 'Private'),
    (11, 'Parking Lot'), (12, 'Trail'), (13, 'Bridle Path'), (14, 'Other')
) t(ID, RdClass)
