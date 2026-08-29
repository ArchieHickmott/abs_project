import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
import logging
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ABS_FILES = {
    "sa1": (
        "https://www.abs.gov.au/statistics/standards/"
        "australian-statistical-geography-standard-asgs/"
        "edition-3-july-2021-june-2026/access-and-downloads/"
        "digital-boundary-files/SA1_2021_AUST_SHP_GDA2020.zip"
    ),
    "sa2": (
        "https://www.abs.gov.au/statistics/standards/"
        "australian-statistical-geography-standard-asgs/"
        "edition-3-july-2021-june-2026/access-and-downloads/"
        "digital-boundary-files/SA2_2021_AUST_SHP_GDA2020.zip"
    ),
    "sa3": (
        "https://www.abs.gov.au/statistics/standards/"
        "australian-statistical-geography-standard-asgs/"
        "edition-3-july-2021-june-2026/access-and-downloads/"
        "digital-boundary-files/SA3_2021_AUST_SHP_GDA2020.zip"
    ),
    "sa4": (
        "https://www.abs.gov.au/statistics/standards/"
        "australian-statistical-geography-standard-asgs/"
        "edition-3-july-2021-june-2026/access-and-downloads/"
        "digital-boundary-files/SA4_2021_AUST_SHP_GDA2020.zip"
    ),
}

class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "",
        logging.INFO: "",     
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",    # red
        logging.CRITICAL: "\033[35m", # magenta
    }

    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"

logger = logging.getLogger("SimpleLogger")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler("ingest.jsonl")
file_handler.setLevel(logging.INFO)
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)

jsonl_formatter = logging.Formatter(
    fmt='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%d %H:%M:%S",
)
human_formatter = ColoredFormatter(
    fmt="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(jsonl_formatter)
stdout_handler.setFormatter(human_formatter)

logger.addHandler(file_handler)
logger.addHandler(stdout_handler)

def download_file(url: str, destination: Path) -> None:
    logger.info(f"Downloading: {url} -> {destination}")

    response = requests.get(
        url,
        stream=True,
        timeout=60,
        headers={
            "User-Agent": "abs-project/1.0",
        },
    )
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    downloaded = 0

    last_percent = -1

    with destination.open("wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue

            f.write(chunk)
            downloaded += len(chunk)

            if total:
                percent = int(downloaded * 100 / total)

                if percent >= last_percent + 5:
                    logger.debug(
                        f"Download progress: {percent}% "
                        f"({downloaded / 1024 / 1024:.1f} MB)"
                    )
                    last_percent = percent
            else:
                logger.debug(
                    f"Downloaded: "
                    f"{downloaded / 1024 / 1024:.1f} MB"
                )

    logger.info("Download complete.")


def extract_zip(zip_path: Path, destination: Path) -> Path:
    """Extract a ZIP file containing a single shapefile from filesystem and return the directory containing the expected shapefile."""

    logger.info(f"Extracting {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(destination)

    shapefiles = list(destination.rglob("*.shp"))

    if not shapefiles:
        raise RuntimeError(
            f"No .shp file found after extracting {zip_path}"
        )

    if len(shapefiles) > 1:
        logger.warning("multiple shapefiles found:")
        for shp in shapefiles:
            logger.info(f"  {shp}")

    shapefile = shapefiles[0]

    logger.info(f"  Shapefile: {shapefile}")

    return shapefile


def import_shapefile(
    shapefile: Path,
    table_name: str,
    host: str,
    port: str,
    database: str,
    user: str,
    password: str,
    schema: str,
    overwrite: bool,
) -> None:
    """Import shapefile into postgis"""

    ogr2ogr = shutil.which("ogr2ogr")

    if ogr2ogr is None:
        raise RuntimeError(
            "ogr2ogr was not found in PATH.\n"
            "Make sure GDAL is included in your nix-shell."
        )

    logger.info(f"Importing shapefile into PostgreSQL Database: {database} Host: {host} Schema: {schema} Table: {table_name}")

    env = os.environ.copy()
    env["PGPASSWORD"] = password

    connection = (
        f"PG:host={host} "
        f"port={port} "
        f"dbname={database} "
        f"user={user}"
    )

    command = [
        ogr2ogr,

        # postgres/postgis output
        "-f",
        "PostgreSQL",

        connection,

        # input shapefile
        str(shapefile),

        # Destination table
        "-nln",
        f"{schema}.{table_name}",

        # abs boundaries are polygon geometries.
        # Promote to multipolygon where necessary.
        "-nlt",
        "PROMOTE_TO_MULTI",

        # Geometry column name
        "-lco",
        "GEOMETRY_NAME=geom",

        # Primary key/fid column
        "-lco",
        "FID=gid",

        # Create a gist spatial index
        "-lco",
        "SPATIAL_INDEX=GIST",

        # Use utf-8
        "--config",
        "SHAPE_ENCODING",
        "UTF-8",

        # Preserve source crs (GDA2020)
        "-a_srs",
        "EPSG:7844",

        # Useful during import
        "-progress",
    ]

    if overwrite:
        command.append("-overwrite")
    else:
        command.append("-append")

    logger.info("Running ogr2ogr...")

    result = subprocess.run(
        command,
        env=env,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"ogr2ogr failed for {table_name} "
            f"with exit code {result.returncode}"
        )

    logger.info(f"Successfully imported {schema}.{table_name}")


def check_database_connection(
    host: str,
    port: str,
    database: str,
    user: str,
    password: str,
) -> None:
    """Check that ogr2ogr can see the postgresql server."""

    ogrinfo = shutil.which("ogrinfo")

    if ogrinfo is None:
        raise RuntimeError("ogrinfo was not found in PATH.")

    env = os.environ.copy()
    env["PGPASSWORD"] = password

    connection = (
        f"PG:host={host} "
        f"port={port} "
        f"dbname={database} "
        f"user={user}"
    )

    logger.debug("Testing postgresql connection...")

    result = subprocess.run(
        [
            ogrinfo,
            connection,
            "--config",
            "CPL_DEBUG",
            "OFF",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        logger.error(result.stderr)
        raise RuntimeError(
            "Could not connect to postgresql.\n"
            "Check your host, port, database, username, password "
            "and pg_hba.conf."
        )

    logger.info("postgresql connection successful.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and import ABS 2021 statistical area boundaries."
    )

    parser.add_argument(
        "areas",
        nargs="*",
        choices=["sa1", "sa2", "sa3", "sa4", "all"],
        default=["all"],
        help="Areas to import. Default: all",
    )

    parser.add_argument(
        "--host",
        default=os.getenv("PGHOST", "192.168.0.141"),
    )

    parser.add_argument(
        "--port",
        default=os.getenv("PGPORT", "5432"),
    )

    parser.add_argument(
        "--database",
        default=os.getenv("PGDATABASE", "gisdb"),
    )

    parser.add_argument(
        "--user",
        default=os.getenv("PGUSER", "archie"),
    )

    parser.add_argument(
        "--password",
        default=os.getenv("PGPASSWORD"),
    )

    parser.add_argument(
        "--schema",
        default=os.getenv("PGSCHEMA", "public"),
    )

    parser.add_argument(
        "--keep-downloads",
        action="store_true",
        help="Keep downloaded ZIP files after importing.",
    )

    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Append instead of replacing existing tables.",
    )

    args = parser.parse_args()

    if not args.password:
        logger.error(
            "ERROR: PostgreSQL password not supplied.\n\n"
            "Set it with:\n\n"
            "    export PGPASSWORD='your-password'\n"
        )
        return 1

    # Expand "all".
    requested = args.areas

    if not requested or "all" in requested:
        areas = ["sa1", "sa2", "sa3", "sa4"]
    else:
        areas = requested

    try:
        check_database_connection(
            args.host,
            args.port,
            args.database,
            args.user,
            args.password,
        )

        with tempfile.TemporaryDirectory(
            prefix="abs_boundaries_"
        ) as temp_dir:

            temp = Path(temp_dir)

            for area in areas:
                url = ABS_FILES[area]

                zip_path = temp / f"{area}_2021.zip"
                extract_dir = temp / area

                extract_dir.mkdir(parents=True, exist_ok=True)

                download_file(url, zip_path)

                shapefile = extract_zip(
                    zip_path,
                    extract_dir,
                )
                
                import_shapefile(
                    shapefile=shapefile,
                    table_name=f"{area}_2021",
                    host=args.host,
                    port=args.port,
                    database=args.database,
                    user=args.user,
                    password=args.password,
                    schema=args.schema,
                    overwrite=not args.no_overwrite,
                )

                if args.keep_downloads:
                    download_dir = Path("data/abs")
                    download_dir.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    destination = (
                        download_dir / zip_path.name
                    )

                    shutil.copy2(
                        zip_path,
                        destination,
                    )

                    logger.info(
                        f"Saved ZIP to {destination}"
                    )

        logger.info("ABS boundary import completed successfully")
        return 0

    except requests.RequestException as e:
        logger.error(f"Download error: {e}")
        return 1

    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {e}")
        return 1

    except Exception as e:
        logger.error(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())