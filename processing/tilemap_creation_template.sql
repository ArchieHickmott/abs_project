CREATE TABLE IF NOT EXISTS :dataset_2021_tilemap ( -- VAR dataset
    tile_id text PRIMARY KEY,
    tile_x integer NOT NULL,
    tile_y integer NOT NULL,
    geom geometry(Polygon, 3577) NOT NULL
);

DELETE FROM :dataset_2021_tilemap;

CREATE INDEX IF NOT EXISTS :dataset_2021_tilemap_geom_idx -- VAR dataset
ON :dataset_2021_tilemap -- VAR dataset
USING GIST (geom);

WITH
params AS (
    SELECT :square_length::double precision AS tile_size -- VAR precomputed optimal grid square length
),

extent AS (
    SELECT
        ST_XMin(e) AS xmin,
        ST_YMin(e) AS ymin,
        ST_XMax(e) AS xmax,
        ST_YMax(e) AS ymax
    FROM (
        SELECT ST_Extent(
            ST_Transform(geom, 3577)
        )::box2d AS e
        FROM :dataset_2021 -- VAR dataset 
    ) t
),

grid_dimensions AS (
    SELECT
        CEIL((xmax - xmin) / tile_size)::integer AS nx,
        CEIL((ymax - ymin) / tile_size)::integer AS ny,
        xmin,
        ymin,
        tile_size
    FROM extent, params
),

grid AS (
    SELECT
        x,
        y,
        xmin + x * tile_size AS x1,
        ymin + y * tile_size AS y1,
        xmin + (x + 1) * tile_size AS x2,
        ymin + (y + 1) * tile_size AS y2
    FROM grid_dimensions
    CROSS JOIN generate_series(0, nx - 1) AS x
    CROSS JOIN generate_series(0, ny - 1) AS y
)

INSERT INTO :dataset_2021_tilemap ( -- VAR dataset
    tile_id,
    tile_x,
    tile_y,
    geom
)
SELECT
    LPAD((x + 1)::text, 2, '0') ||
    LPAD((y + 1)::text, 2, '0') AS tile_id,

    x + 1 AS tile_x,
    y + 1 AS tile_y,

    ST_MakeEnvelope(
        x1,
        y1,
        x2,
        y2,
        3577
    ) AS geom
FROM grid;