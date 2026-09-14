CREATE TABLE IF NOT EXISTS :dataset_2021_tilemap ( -- VAR dataset
    tile_id text PRIMARY KEY,
    tile_x integer NOT NULL,
    tile_y integer NOT NULL,
    geom geometry(Polygon, 3577) NOT NULL,
    centroid geometry(Point, 3577) NOT NULL
);

CREATE TABLE IF NOT EXISTS :dataset_2021_tilemap_polygons ( -- VAR dataset
    tile_id text NOT NULL,
    polygon_gid bigint NOT NULL,

    PRIMARY KEY (tile_id, polygon_gid),

    FOREIGN KEY (tile_id)
        REFERENCES :dataset_2021_tilemap(tile_id) -- VAR dataset
        ON DELETE CASCADE,

    FOREIGN KEY (polygon_gid)
        REFERENCES :dataset_2021(gid) -- VAR dataset
        ON DELETE CASCADE
);

DELETE FROM :dataset_2021_tilemap_polygons; -- VAR dataset
DELETE FROM :dataset_2021_tilemap; -- VAR dataset

CREATE INDEX IF NOT EXISTS :dataset_2021_tilemap_geom_idx -- VAR dataset
ON :dataset_2021_tilemap -- VAR dataset
USING GIST (geom);

WITH
params AS (
    SELECT :square_length::double precision AS tile_size -- VAR square_length (precomputed optimal grid square length)
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
    geom,
    centroid
)

SELECT
    (x + 1)::text || '_' || (y + 1)::text AS tile_id,

    x + 1 AS tile_x,
    y + 1 AS tile_y,

    tile_geom AS geom,

    ST_Centroid(tile_geom) AS centroid
FROM (
    SELECT
        x,
        y,
        ST_MakeEnvelope(
            x1,
            y1,
            x2,
            y2,
            3577
        ) AS tile_geom
    FROM grid
) g;

INSERT INTO :dataset_2021_tilemap_polygons ( -- VAR dataset
    tile_id,
    polygon_gid
)
SELECT
    t.tile_id,
    p.gid
FROM :dataset_2021_tilemap AS t -- VAR dataset
JOIN :dataset_2021 AS p -- VAR dataset
    ON t.geom && p.centroid
   AND ST_Covers(t.geom, p.centroid);