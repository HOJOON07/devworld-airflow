{% macro generate_schema_name(custom_schema_name, node) -%}
    {#
        dbt 기본 동작: default_schema + custom_schema → "main_bronze"
        오버라이드: custom_schema가 지정되면 그대로 사용 → "bronze"
        이유: DuckLake에서 bronze/silver/gold 스키마를 정확히 사용하기 위해
    #}
    {%- if custom_schema_name is none -%}
        {{ default__generate_schema_name(custom_schema_name, node) }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
