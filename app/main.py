from flask import Flask, render_template, jsonify, request
import psycopg

import os
import sys

app = Flask(__name__)

@app.route("/")
def index():
    level = int(request.args.get("level", default=4))
    app.logger.debug(level)
    if not level in [1, 2, 3, 4]:
        level = 4

    return render_template("index.html", area_level=level)

@app.get("/get-json")
def get_geojson():
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

@app.route("/get-tilemap")
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

if __name__ == "__main__":
    app.run("0.0.0.0", debug=True)