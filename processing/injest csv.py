from typing import List, Iterator, Generator

import csv, sys, os
import logging
import re

from dotenv import load_dotenv
from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy import Column, Text, insert
from sqlalchemy.orm import Session

load_dotenv()

# Configuration
BATCH_SIZE = 5000

# utilities
metadata = MetaData()

def read_csv_batches(filepath: str, batch_size: int = BATCH_SIZE,
                    ) -> Iterator[tuple[list[str], list[list[str]]]]:
    """
    Stream a CSV file in batches.

    Yields:
        (headers, batch)
    """

    try:
        with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)

            try:
                headers = next(reader)
            except StopIteration:
                logger.warning(
                    "Empty CSV file: %s",
                    filepath,
                )
                return

            batch = []

            for row in reader:
                batch.append(row)

                if len(batch) >= batch_size:
                    yield headers, batch
                    batch = []

            if batch:
                yield headers, batch

    except UnicodeDecodeError:
        logger.warning(
            "File is not valid UTF-8: %s",
            filepath,
        )

    except csv.Error as e:
        logger.warning(
            "Invalid CSV format '%s': %s",
            filepath,
            e,
        )

    except OSError as e:
        logger.warning(
            "Could not read '%s': %s",
            filepath,
            e,
        )

def create_table(title: str, headers: list[str],
                 ) -> Table:
    """Create a SQLAlchemy table definition."""

    if not headers:
        raise ValueError(
            f"Cannot create '{title}': no columns found"
        )

    if len(headers) != len(set(headers)):
        raise ValueError(
            f"Cannot create '{title}': duplicate column names"
        )

    if any(not header.strip() for header in headers):
        raise ValueError(
            f"Cannot create '{title}': blank column name"
        )

    columns = [
        Column(column_name, Text)
        for column_name in headers
    ]

    table = Table(
        title,
        metadata,
        *columns,
    )

    metadata.create_all(
        engine,
        tables=[table],
    )

    return table


def commit_table(title: str, filepath: str,
                 ) -> int:
    """
    Create a database table and stream CSV data into it.

    Returns:
        Number of rows inserted.
    """

    table = None
    row_count = 0

    with engine.begin() as connection:
        for headers, batch in read_csv_batches(filepath):
            # The first batch gives us the headers.
            if table is None:
                table = create_table(
                    title,
                    headers,
                )

                logger.debug(
                    "Created table '%s' with %d columns",
                    title,
                    len(headers),
                )

            # Convert only the current batch.
            rows = [
                dict(zip(headers, row))
                for row in batch
            ]

            connection.execute(
                table.insert(),
                rows,
            )

            row_count += len(rows)

            logger.debug(
                "%s: %d rows inserted",
                title,
                row_count,
            )

    return row_count

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

# connecting to database
engine = create_engine(
    os.environ["DATABASE_URL"]
)

# begin ingestion
logger.info("starting ingestion")
base_path = input("Enter data path: ").strip()

if not os.path.isdir(base_path):
    logger.error(f"path: '{base_path}' cannot be found")
    raise RuntimeError(f"path '{base_path}' does not exist")

# Change Directory
os.chdir(base_path)

available_csv: Generator[str] = (
    os.path.join(root, file)
    for root, _, files in os.walk('.') 
    for file in files 
    if file.endswith('.csv')
)
logger.debug(f"Files Found: {available_csv}")

pattern = re.compile(
    r"^(?P<year>\d{4})Census_(?P<table>G[A-Za-z0-9]+)_AUST_(?P<area>[A-Za-z0-9]+)\.csv$"
)

for filepath in available_csv:
    filename = os.path.basename(filepath)

    match = pattern.fullmatch(filename)
    if match is None:
        logger.warning(
            "Rejected filename: %s",
            filename,
        )
        continue

    table_name = match.group("table")
    area = match.group("area")

    name = f"{table_name}_{area}"

    logger.info(
        "Loading %s as '%s'",
        filepath.replace("\\", "/"),
        name,
    )

    try:
        row_count = commit_table(
            name,
            filepath,
        )

    except Exception:
        logger.exception(
            "Failed to ingest %s",
            filepath,
        )
        continue

    logger.info(
        "Loaded %s as '%s' (%d rows)",
        filename,
        name,
        row_count,
    )