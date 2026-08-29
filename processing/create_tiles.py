import psycopg
from dotenv import load_dotenv

import math
import os
import sys
import logging

load_dotenv()

# Initial search interval, INITIAL_INTERVAL[1] must be > INITIAL_INTERVAL[0]
OPTIMISATION_ACURACY = 5
INITIAL_INTERVAL: tuple[float, float] = (40, 50)
INITIAL_SQUARE_LENGTH = 50_000 # kilometers 
GOLDEN_RATIO = (1 + math.sqrt(5)) / 2

# Set up logging
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

psycopg_logger = logging.getLogger("psycopg")
psycopg_logger.setLevel(logging.DEBUG)
psycopg_logger.addHandler(stdout_handler)

class OptimisationEnginge:
    _BASE_SQL = """
        WITH counts AS (
            SELECT
                floor((ST_X(centroid) - :x0) / :square_length) AS grid_x,
                floor((ST_Y(centroid) - :y0) / :square_length) AS grid_y,
                COUNT(*) AS polygon_count
            FROM sa1_2021
            GROUP BY grid_x, grid_y
        )
        SELECT
            AVG(polygon_count),
            STDDEV_POP(polygon_count),
            STDDEV_POP(polygon_count) / NULLIF(AVG(polygon_count), 0)
        FROM counts;
    """

    def __init__(self, conn):
        self._conn = conn
        self._x0, self._y0 = self._get_origin()

    def _get_origin(self):
        sql = """
            SELECT
                ST_X(p) AS x0,
                ST_Y(p) AS y0
            FROM (
                SELECT ST_Transform(
                    ST_SetSRID(
                        ST_MakePoint(
                            115.75000757470102,
                            -10.41234330991432
                        ),
                        4326
                    ),
                    3577
                ) AS p
            ) t;
        """

        with self._conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()

    def _statistics(self, square_length: float):
        sql = self._BASE_SQL.replace(":x0", str(self._x0)).replace(":y0", str(self._y0)).replace(":square_length", str(square_length))

        with self._conn.cursor() as cur:
            cur.execute(sql)
            mean, stddev, cv = cur.fetchone()

        return float(mean), float(stddev), float(cv)

    def _mean(self, square_length):
        return self._statistics(square_length)[0]

    def _standard_deviation(self, square_length):
        return self._statistics(square_length)[1]

    def _score(self, square_length):
        return self._statistics(square_length)[2]

    def calculate_square_length(self): 
        logger.info("starting optimisation process")
        logger.debug(self._mean(INITIAL_SQUARE_LENGTH))
        bounds = [INITIAL_SQUARE_LENGTH * math.sqrt(goal / self._mean(INITIAL_SQUARE_LENGTH)) 
                                                            for goal in INITIAL_INTERVAL]
        # logger.debug(bounds)
        lower_bound, upper_bound = bounds
        uncertainty_level: float = upper_bound - lower_bound

        x_1 = lower_bound + uncertainty_level / (GOLDEN_RATIO ** 2)
        x_2 = lower_bound + uncertainty_level / GOLDEN_RATIO

        while uncertainty_level >= OPTIMISATION_ACURACY:
            logger.info(f"starting optimisation round with uncertainty level: {uncertainty_level}")
            score_1 = self._score(x_1)
            score_2 = self._score(x_2)

            if score_1 > score_2:
                lower_bound = x_1
                x_1 = x_2
                uncertainty_level = upper_bound - lower_bound
                x_2 = lower_bound + uncertainty_level / GOLDEN_RATIO
            else:
                upper_bound = x_2
                x_2 = x_1
                uncertainty_level = upper_bound - lower_bound
                x_1 = lower_bound + uncertainty_level / (GOLDEN_RATIO ** 2)

        return (lower_bound + upper_bound) / 2

conninfo = (
    f"host={os.getenv('PGHOST', '192.168.0.141')} "
    f"port={os.getenv('PGPORT', '5432')} "
    f"dbname={os.getenv('PGDATABASE', 'gisdb')} "
    f"user={os.getenv('PGUSER', 'archie')} "
    f"password={os.getenv('PGPASSWORD')}"
)

logger.info("Connecting to database")
with psycopg.connect(conninfo) as conn:
    optimiser = OptimisationEnginge(conn)
    logger.info(f"final square length {optimiser.calculate_square_length()}")