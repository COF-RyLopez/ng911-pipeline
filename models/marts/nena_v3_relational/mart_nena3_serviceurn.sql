{{ config(
    materialized='table'
) }}

-- NENA v3.0 Relational Data Model: ng911.ServiceURN
SELECT 1 AS ID, 'urn:service:sos' AS ServiceURN, 'Default Emergency SOS' AS Description
UNION ALL
SELECT 2 AS ID, 'urn:service:sos.fire' AS ServiceURN, 'Fire and Rescue Service' AS Description
UNION ALL
SELECT 3 AS ID, 'urn:service:sos.police' AS ServiceURN, 'Law Enforcement / Police Service' AS Description
UNION ALL
SELECT 4 AS ID, 'urn:service:sos.ambulance' AS ServiceURN, 'Emergency Medical Services (EMS)' AS Description
