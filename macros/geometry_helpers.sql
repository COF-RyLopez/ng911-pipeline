{% macro st_aswkb(geom_col) %}
    ST_AsWKB({{ geom_col }})
{% endmacro %}

{% macro st_point(lon_col, lat_col) %}
    ST_Point({{ lon_col }}, {{ lat_col }})
{% endmacro %}

{% macro st_dwithin(geom1, geom2, distance_degrees) %}
    ST_DWithin({{ geom1 }}, {{ geom2 }}, {{ distance_degrees }})
{% endmacro %}

{% macro st_distance_meters(geom1, geom2) %}
    ST_Distance({{ geom1 }}, {{ geom2 }}) * 111320.0
{% endmacro %}

{% macro normalize_direction(dir_col) %}
    CASE upper(trim({{ dir_col }}))
        WHEN 'NORTH' THEN 'N'
        WHEN 'SOUTH' THEN 'S'
        WHEN 'EAST' THEN 'E'
        WHEN 'WEST' THEN 'W'
        WHEN 'NORTHEAST' THEN 'NE'
        WHEN 'NORTHWEST' THEN 'NW'
        WHEN 'SOUTHEAST' THEN 'SE'
        WHEN 'SOUTHWEST' THEN 'SW'
        WHEN 'N' THEN 'N'
        WHEN 'S' THEN 'S'
        WHEN 'E' THEN 'E'
        WHEN 'W' THEN 'W'
        WHEN 'NE' THEN 'NE'
        WHEN 'NW' THEN 'NW'
        WHEN 'SE' THEN 'SE'
        WHEN 'SW' THEN 'SW'
        ELSE NULL
    END
{% endmacro %}

{% macro normalize_street_type(type_col) %}
    CASE upper(trim({{ type_col }}))
        WHEN 'STREET' THEN 'ST'
        WHEN 'AVENUE' THEN 'AVE'
        WHEN 'BOULEVARD' THEN 'BLVD'
        WHEN 'ROAD' THEN 'RD'
        WHEN 'DRIVE' THEN 'DR'
        WHEN 'LANE' THEN 'LN'
        WHEN 'WAY' THEN 'WAY'
        WHEN 'COURT' THEN 'CT'
        WHEN 'PLACE' THEN 'PL'
        WHEN 'CIRCLE' THEN 'CIR'
        WHEN 'HIGHWAY' THEN 'HWY'
        WHEN 'PARKWAY' THEN 'PKWY'
        WHEN 'TRAIL' THEN 'TRL'
        WHEN 'LOOP' THEN 'LOOP'
        ELSE upper(trim({{ type_col }}))
    END
{% endmacro %}
