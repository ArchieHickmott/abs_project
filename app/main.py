from flask import Flask, render_template, jsonify, request
import psycopg

import os
import sys

TILE_RENDER_RADIUS= {1:2, 2:2, 3:5, 4:10}

app = Flask(__name__)

@app.route("/typescript-test")
def typescript_test():
    return render_template("typescript_test.html")

@app.route("/")
def index():
    level = int(request.args.get("level", default=4))
    app.logger.debug(level)
    if not level in [1, 2, 3, 4]:
        level = 4

    return render_template("index.html", area_level=level)

@app.get("/get-tile-geometries")
def get_tile_geometries():
    simplification_level = {4:"0.03",3:"0.004",2:"0.0008",1:"0.00015"}

    level = int(request.args.get("level", default=4))

    if level not in [1, 2, 3, 4]:
        level = 4

    tile_id = request.args.get("tile-id")

    conninfo = (
        f"host={os.getenv('PGHOST', '192.168.0.141')} "
        f"port={os.getenv('PGPORT', '5432')} "
        f"dbname={os.getenv('PGDATABASE', 'gisdb')} "
        f"user={os.getenv('PGUSER', 'archie')} "
        f"password={os.getenv('PGPASSWORD')}"
    )

    query = f"""
        SELECT
            p.gid,
            p.sa{level}_code21,
            ST_AsGeoJSON(
                ST_SimplifyPreserveTopology(ST_Transform(p.geom, 4326), {simplification_level[level]})
            )::json AS geometry
        FROM sa{level}_2021_tilemap_polygons tp
        JOIN sa{level}_2021 p
            ON p.gid = tp.polygon_gid
        WHERE tp.tile_id = CAST(%s AS text);
    """

    app.logger.info("Connecting to database")

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            app.logger.info("Querying geometries for tiles: %s", tile_id)

            cur.execute(query, (tile_id,))

            rows = cur.fetchall()

            app.logger.info(
                "Returned %d geometries",
                len(rows)
            )

    features = []

    for gid, code, geometry in rows:
        features.append({
            "type": "Feature",
            "id": gid,
            "properties": {
                f"sa{level}_code": code,
            },
            "geometry": geometry
        })

    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })

@app.get("/get-area-geometry")
def get_area_geometry():
    level = int(request.args.get("level"))
    app.logger.debug(level)
    if not level in [1, 2, 3, 4]:
        app.logger.debug('OOPS')
        level = 4

    conninfo = (
        f"host={os.getenv('PGHOST', '192.168.0.141')} "
        f"port={os.getenv('PGPORT', '5432')} "
        f"dbname={os.getenv('PGDATABASE', 'gisdb')} "
        f"user={os.getenv('PGUSER', 'archie')} "
        f"password={os.getenv('PGPASSWORD')}"
    )

    query = f"""
        SELECT
            sa{level}_code21,
            sa{level}_name21,
            ST_AsGeoJSON(
                geom
            )::json AS geometry
        FROM sa{level}_2021;
    """

    app.logger.info("Connecting to database")

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:

            app.logger.info("Querying data")

            cur.execute(query)

            rows = cur.fetchall()

            app.logger.info(f"Returned %d SA{level}s", len(rows))

    features = []
    
    for sa4_code, sa4_name, geometry in rows:
        features.append({
            "type": "Feature",
            "properties": {
                f"sa{level}_code": sa4_code,
                f"sa{level}_name": sa4_name
            },
            "geometry": geometry
        })

    app.logger.info("Encoding data")

    result = jsonify({
        "type": "FeatureCollection",
        "features": features
    })

    app.logger.debug(sys.getsizeof(result))
    return result

@app.get("/get-tilemap")
def get_tilemap():
    level = int(request.args.get("level"))
    app.logger.debug(level)
    if not level in [1, 2, 3, 4]:
        app.logger.debug('OOPS')
        level = 4

    conninfo = (
        f"host={os.getenv('PGHOST', '192.168.0.141')} "
        f"port={os.getenv('PGPORT', '5432')} "
        f"dbname={os.getenv('PGDATABASE', 'gisdb')} "
        f"user={os.getenv('PGUSER', 'archie')} "
        f"password={os.getenv('PGPASSWORD')}"
    )

    query = f"""
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', json_agg(
                json_build_object(
                    'type', 'Feature',
                    'id', tile_id,
                    'properties', json_build_object(
                        'tile_x', tile_x,
                        'tile_y', tile_y
                    ),
                    'geometry',
                    ST_AsGeoJSON(
                        ST_Transform(geom, 4326)
                    )::json
                )
            )
        )
        FROM sa{level}_2021_tilemap;
    """

    app.logger.info("Connecting to database")

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:

            app.logger.info("Querying data")

            cur.execute(query)

            rows = cur.fetchall()

            app.logger.info(f"Returned %d SA{level}s", len(rows))

    app.logger.info("Encoding data")

    result = jsonify(rows[0][0])
    app.logger.debug(sys.getsizeof(result))
    return result

@app.get("/tilemap-cache")
def get_tilemap_cache():
    simplification_level = {4:"0.03",3:"0.004",2:"0.0008",1:"0.00015"}

    position = (float(request.args.get("x")), float(request.args.get("y")))
    level = int(request.args.get("level"))
    if not level in [1, 2, 3, 4]:
        app.logger.debug('OOPS')
        level = 4

    conninfo = (
        f"host={os.getenv('PGHOST', '192.168.0.141')} "
        f"port={os.getenv('PGPORT', '5432')} "
        f"dbname={os.getenv('PGDATABASE', 'gisdb')} "
        f"user={os.getenv('PGUSER', 'archie')} "
        f"password={os.getenv('PGPASSWORD')}"
    )
    sql = f"""
        SELECT tile_id
        FROM sa{level}_2021_tilemap
        WHERE ST_Covers(geom, ST_Transform(ST_Point({position[0]}, {position[1]}, 4326), 3577))
    """

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            app.logger.info(rows)
            
    if not rows:
        return jsonify(None)
    
    centre_tile: str = rows[0][0]
    centre_x, centre_y = map(int, centre_tile.split("_"))
    load_radius = TILE_RENDER_RADIUS[level]
    load_radius_squared = load_radius ** 2
    tiles = []

    for x in range(centre_x - load_radius, centre_x + load_radius + 1):
        if x < 0:
            continue
        for y in range(centre_y - load_radius, centre_y + load_radius + 1):
            if y < 0:
                continue
            dx = x - centre_x
            dy = y - centre_y
            distance = dx ** 2 + dy ** 2

            if distance <= load_radius_squared:
                tiles.append(f"{x}_{y}")

    query = f"""
        SELECT DISTINCT ON (p.gid)
            p.gid,
            p.sa{level}_code21,
            ST_AsGeoJSON(
                ST_SimplifyPreserveTopology(
                    ST_Transform(p.geom, 4326),
                    {simplification_level[level]}
                )
            )::json AS geometry
        FROM sa{level}_2021_tilemap_polygons tp
        JOIN sa{level}_2021 p
            ON p.gid = tp.polygon_gid
        WHERE tp.tile_id = ANY(%s);
    """

    app.logger.info("Connecting to database")

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            app.logger.info("Querying geometries for tiles: %s", tiles)

            cur.execute(query, (tiles,))

            rows = cur.fetchall()

            app.logger.info(
                "Returned %d geometries",
                len(rows)
            )

    features = []

    for gid, code, geometry in rows:
        features.append({
            "type": "Feature",
            "id": gid,
            "properties": {
                f"sa{level}_code": code,
            },
            "geometry": geometry
        })

    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })

if __name__ == "__main__":
    app.run("0.0.0.0", debug=True)