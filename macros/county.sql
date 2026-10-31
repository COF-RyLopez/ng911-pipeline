{# Attribute of the county this run builds, from the `counties` registry in dbt_project.yml:
   {{ county('name') }} -> FRESNO, {{ county('agency_domain') }} -> fresnocountyca.gov #}
{% macro county(attr) %}
    {%- set fips = var('county') | string -%}
    {%- set registry = var('counties') -%}
    {%- if fips not in registry -%}
        {{ exceptions.raise_compiler_error("county '" ~ fips ~ "' is not in the counties registry (dbt_project.yml); known: " ~ (registry.keys() | list | join(', '))) }}
    {%- endif -%}
    {{ return(registry[fips][attr]) }}
{% endmacro %}
