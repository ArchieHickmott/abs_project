CREATE TABLE IF NOT EXISTS :dataset_2021_tilemap (
    tile_id text PRIMARY KEY,
    tile_x integer NOT NULL,
    tile_y integer NOT NULL,
    geom geometry(Polygon, 3577) NOT NULL,
    centroid geometry(Point, 3577) NOT NULL
);

CREATE TABLE IF NOT EXISTS :dataset_2021_tilemap_polygons (
    tile_id text NOT NULL,
    polygon_gid bigint NOT NULL,

    PRIMARY KEY (tile_id, polygon_gid),

    FOREIGN KEY (tile_id)
        REFERENCES :dataset_2021_tilemap(tile_id)
        ON DELETE CASCADE,

    FOREIGN KEY (polygon_gid)
        REFERENCES :dataset_2021(gid)
        ON DELETE CASCADE
);

DELETE FROM :dataset_2021_tilemap_polygons;
DELETE FROM :dataset_2021_tilemap;

CREATE INDEX IF NOT EXISTS :dataset_2021_tilemap_geom_idx
ON :dataset_2021_tilemap
USING GIST (geom);

CREATE INDEX IF NOT EXISTS :dataset_2021_geom_idx
ON :dataset_2021
USING GIST (geom);

CREATE INDEX IF NOT EXISTS :dataset_2021_tilemap_xy_idx
ON :dataset_2021_tilemap (tile_x, tile_y);

INSERT INTO :dataset_2021_tilemap (
    tile_id,
    tile_x,
    tile_y,
    geom,
    centroid
)
WITH
params AS (
    SELECT :square_length::double precision AS tile_size
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
        FROM :dataset_2021
        WHERE geom IS NOT NULL
    ) t
),

grid AS (
    SELECT
        x AS tile_x,
        y AS tile_y,
        e.xmin,
        e.ymin,
        params.tile_size
    FROM extent e
    CROSS JOIN params

    CROSS JOIN LATERAL generate_series(
        0,
        CEIL(
            (e.xmax - e.xmin) / params.tile_size
        )::integer - 1
    ) AS x

    CROSS JOIN LATERAL generate_series(
        0,
        CEIL(
            (e.ymax - e.ymin) / params.tile_size
        )::integer - 1
    ) AS y
)

SELECT
    (tile_x + 1)::text || '_' || (tile_y + 1)::text AS tile_id,

    tile_x,
    tile_y,

    ST_MakeEnvelope(
        xmin + tile_x * tile_size,
        ymin + tile_y * tile_size,
        xmin + (tile_x + 1) * tile_size,
        ymin + (tile_y + 1) * tile_size,
        3577
    ) AS geom,

    ST_Centroid(
        ST_MakeEnvelope(
            xmin + tile_x * tile_size,
            ymin + tile_y * tile_size,
            xmin + (tile_x + 1) * tile_size,
            ymin + (tile_y + 1) * tile_size,
            3577
        )
    ) AS centroid

FROM grid;

INSERT INTO :dataset_2021_tilemap_polygons (
    tile_id,
    polygon_gid
)

WITH
params AS (
    SELECT :square_length::double precision AS tile_size
),

extent AS (
    SELECT
        ST_XMin(e) AS xmin,
        ST_YMin(e) AS ymin
    FROM (
        SELECT ST_Extent(
            ST_Transform(geom, 3577)
        )::box2d AS e
        FROM :dataset_2021
        WHERE geom IS NOT NULL
    ) t
),

polygon_bounds AS (
    SELECT
        p.gid,
        ST_Transform(p.geom, 3577) AS geom
    FROM :dataset_2021 AS p
    WHERE p.geom IS NOT NULL
),

candidate_ranges AS (
    SELECT
        p.gid,
        p.geom,

        FLOOR(
            (ST_XMin(p.geom) - e.xmin) / params.tile_size
        )::integer AS min_tile_x,

        FLOOR(
            (ST_XMax(p.geom) - e.xmin) / params.tile_size
        )::integer AS max_tile_x,

        FLOOR(
            (ST_YMin(p.geom) - e.ymin) / params.tile_size
        )::integer AS min_tile_y,

        FLOOR(
            (ST_YMax(p.geom) - e.ymin) / params.tile_size
        )::integer AS max_tile_y

    FROM polygon_bounds p
    CROSS JOIN extent e
    CROSS JOIN params
),

candidates AS (
    SELECT
        r.gid,
        r.geom,
        x AS tile_x,
        y AS tile_y

    FROM candidate_ranges r

    CROSS JOIN LATERAL generate_series(
        r.min_tile_x,
        r.max_tile_x
    ) AS x

    CROSS JOIN LATERAL generate_series(
        r.min_tile_y,
        r.max_tile_y
    ) AS y
)

SELECT
    t.tile_id,
    c.gid AS polygon_gid

FROM candidates c

JOIN :dataset_2021_tilemap AS t
    ON t.tile_x = c.tile_x
   AND t.tile_y = c.tile_y

WHERE ST_Intersects(
    t.geom,
    c.geom
);