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
    CASE rtrim(upper(trim({{ type_col }})), '.')
        WHEN 'STREET' THEN 'ST'
        WHEN 'STR' THEN 'ST'
        WHEN 'AVENUE' THEN 'AVE'
        WHEN 'AV' THEN 'AVE'  -- Kern writes 'CHESTER AV'
        WHEN 'BOULEVARD' THEN 'BLVD'
        WHEN 'BL' THEN 'BLVD'  -- Alameda: 'FREMONT BL'
        WHEN 'ROAD' THEN 'RD'
        WHEN 'DRIVE' THEN 'DR'
        WHEN 'LANE' THEN 'LN'
        WHEN 'WAY' THEN 'WAY'
        WHEN 'WY' THEN 'WAY'  -- Alameda: 'DWIGHT WY'
        WHEN 'COURT' THEN 'CT'
        WHEN 'CRT' THEN 'CT'
        WHEN 'PLACE' THEN 'PL'
        WHEN 'CIRCLE' THEN 'CIR'
        WHEN 'CIRC' THEN 'CIR'
        WHEN 'COVE' THEN 'CV'
        WHEN 'HIGHWAY' THEN 'HWY'
        WHEN 'PARKWAY' THEN 'PKWY'
        WHEN 'PW' THEN 'PKWY'  -- Alameda: 'PASEO PADRE PW'
        WHEN 'TRAIL' THEN 'TRL'
        WHEN 'LOOP' THEN 'LOOP'
        ELSE rtrim(upper(trim({{ type_col }})), '.')
    END
{% endmacro %}

{% macro dirs() %}
    ('N','S','E','W','NE','NW','SE','SW','NORTH','SOUTH','EAST','WEST','NORTHEAST','NORTHWEST','SOUTHEAST','SOUTHWEST',
     'NB','SB','EB','WB','AL')  -- travel-direction and alley codes: peeled like the old county staging, normalize_direction() maps them to NULL
{% endmacro %}

{% macro street_types() %}
    ('ST','STREET','AVE','AV','AVENUE','BLVD','BOULEVARD','RD','ROAD','DR','DRIVE','LN','LANE','WAY','CT','COURT',
     'PL','PLACE','CIR','CIRCLE','HWY','HIGHWAY','PKWY','PARKWAY','TRL','TRAIL','LOOP','TER','TERRACE','ALY','ALLEY',
     'EXPY','EXPRESSWAY','FWY','FREEWAY','PLZ','PLAZA','SQ','SQUARE','CV','COVE','PATH','WALK','ROW','RUN','XING',
     -- additional types used in Fresno County's STR_TYPE field
     'SR','ON','OFF','ONRP','OFRP','GRD','FTRD','TRFY','BYP','MALL','VW','PT','CRT','STR','BKRT','CIRC','AVE.')
{% endmacro %}

{% macro parity(from_col, to_col) %}
    CASE
        WHEN {{ from_col }} IS NULL AND {{ to_col }} IS NULL THEN 'Z'
        WHEN {{ from_col }} % 2 = 0 AND {{ to_col }} % 2 = 0 THEN 'E'
        WHEN {{ from_col }} % 2 = 1 AND {{ to_col }} % 2 = 1 THEN 'O'
        ELSE 'B'
    END
{% endmacro %}

{# Which side of a road line a point is on, looking along the line's digitized direction
   (from its first vertex to its last): 'L' or 'R'. NULL for multi-part lines. #}
{% macro road_side(line, pt) -%}
(CASE WHEN ST_GeometryType({{ line }}) = 'LINESTRING' THEN
  CASE WHEN
      (ST_X(ST_LineInterpolatePoint({{ line }}, least(ST_LineLocatePoint({{ line }}, {{ pt }}) + 0.001, 1.0)))
     - ST_X(ST_LineInterpolatePoint({{ line }}, greatest(ST_LineLocatePoint({{ line }}, {{ pt }}) - 0.001, 0.0))))
    * (ST_Y({{ pt }}) - ST_Y(ST_LineInterpolatePoint({{ line }}, greatest(ST_LineLocatePoint({{ line }}, {{ pt }}) - 0.001, 0.0))))
    - (ST_Y(ST_LineInterpolatePoint({{ line }}, least(ST_LineLocatePoint({{ line }}, {{ pt }}) + 0.001, 1.0)))
     - ST_Y(ST_LineInterpolatePoint({{ line }}, greatest(ST_LineLocatePoint({{ line }}, {{ pt }}) - 0.001, 0.0))))
    * (ST_X({{ pt }}) - ST_X(ST_LineInterpolatePoint({{ line }}, greatest(ST_LineLocatePoint({{ line }}, {{ pt }}) - 0.001, 0.0))))
  > 0 THEN 'L' ELSE 'R' END
END)
{%- endmacro %}

{#- Street name padded with spaces and with ordinal words as numbers ("N EIGHTH" -> " N 8TH "), for
    whole-word name matching where one source spells numbered streets out and the other doesn't.
    ponytail: covers FIRST..TWENTIETH; add words if higher spelled-out ordinals show up as misses. -#}
{% macro street_match_key(expr) -%}
{%- set ordinals = ['FIRST','SECOND','THIRD','FOURTH','FIFTH','SIXTH','SEVENTH','EIGHTH','NINTH','TENTH',
                    'ELEVENTH','TWELFTH','THIRTEENTH','FOURTEENTH','FIFTEENTH','SIXTEENTH','SEVENTEENTH',
                    'EIGHTEENTH','NINETEENTH','TWENTIETH'] -%}
{%- set suffix = {1: 'ST', 2: 'ND', 3: 'RD'} -%}
{%- set ns = namespace(sql="' ' || " ~ expr ~ " || ' '") -%}
{%- for w in ordinals -%}
{%- set n = loop.index -%}
{%- set ns.sql = "replace(" ~ ns.sql ~ ", ' " ~ w ~ " ', ' " ~ n ~ (suffix.get(n, 'TH') if n not in (11, 12, 13) else 'TH') ~ " ')" -%}
{%- endfor -%}
{{ ns.sql }}
{%- endmacro %}

{#- Area in km² of a lon/lat geometry: degree² scaled by 111.32 km per degree and cos(latitude).
    No ST_Transform, whose axis-order handling differs between DuckDB versions.
    ponytail: within ~0.5% of an equal-area projection for city-sized polygons; use ST_Transform
    to EPSG:3310 if exact areas matter. -#}
{% macro area_km2(geom) -%}
(ST_Area({{ geom }}) * 12392.1 * cos(radians(ST_Y(ST_Centroid({{ geom }})))))
{%- endmacro %}

{#- Where to fix an open-data record at its source.
    osm_edit_url('w1192336214@1') -> https://www.openstreetmap.org/edit?way=1192336214 (NULL if not OSM)
    oa_source_url('us/ca/fresno') -> the OpenAddresses source entry Overture republished (NULL otherwise) -#}
{% macro osm_edit_url(record_id) -%}
CASE WHEN regexp_matches({{ record_id }}, '^[nwr][0-9]+')
     THEN 'https://www.openstreetmap.org/edit?'
          || CASE left({{ record_id }}, 1) WHEN 'n' THEN 'node' WHEN 'w' THEN 'way' ELSE 'relation' END
          || '=' || regexp_extract({{ record_id }}, '^[nwr]([0-9]+)', 1) END
{%- endmacro %}

{% macro oa_source_url(dataset) -%}
CASE WHEN regexp_matches({{ dataset }}, '^[a-z]{2}/[a-z0-9_/]+$')
     THEN 'https://github.com/openaddresses/openaddresses/blob/master/sources/' || {{ dataset }} || '.json' END
{%- endmacro %}
