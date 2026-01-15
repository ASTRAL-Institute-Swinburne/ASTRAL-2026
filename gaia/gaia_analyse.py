#!/usr/bin/env python3
"""
gaia_local.py — Load/query a local Gaia-like PostgreSQL+Q3C table or CSV file.

Features
- Load CSV into Postgres using fast COPY (psycopg3)
- Query CSV files directly using DuckDB (use --csv-file option)
- Count rows
- Cone search using Q3C (q3c_radial_query) or angular distance (CSV mode)
- Fetch first N brightest stars by phot_g_mean_mag
- Semicolon-separated shortlist queries via `query` subcommand
- Generate diagnostic plots via `diagnose` subcommand

Assumptions
- Database has extension: q3c
- Table schema matches the columns below (parallax appears once)
- CSV has a header row with these column names:
  source_id,ra,dec,parallax,bp_rp,phot_g_mean_mag,pmra,pmra_error,pmdec,pmdec_error,
  l,b,parallax_over_error,radial_velocity,radial_velocity_error,ruwe,
  phot_g_mean_flux,phot_g_mean_flux_over_error

Install
  pip install "psycopg[binary]" duckdb

Examples
  # Count rows in database
  python gaia_local.py count --host localhost --port 5432 --db gaia_local --user postgres --password postgres

  # Count rows in CSV file
  python gaia_local.py count --csv-file ./data/gaia_subset.csv

  # Load a CSV into database (append; use --truncate to wipe existing rows first)
  python gaia_local.py load ./data/gaia_subset.csv --truncate

  # Cone search on database (RA/Dec in degrees, radius in degrees)
  python gaia_local.py cone 83.6331 22.0145 0.1 --limit 20

  # Cone search on CSV file
  python gaia_local.py cone 83.6331 22.0145 0.1 --limit 20 --csv-file ./data/gaia_subset.csv

  # Brightest N (smallest phot_g_mean_mag) from database
  python gaia_local.py brightest 50

  # Brightest N from CSV file
  python gaia_local.py brightest 50 --csv-file ./data/gaia_subset.csv

  # Shortlist query (semicolon-separated) on database
  python gaia_local.py query "cone_eq 83.6331 22.0145 0.1; brighter_than 16; ruwe_less_than 1.4" --limit 50 --brightest-first

  # Shortlist query on CSV file
  python gaia_local.py query "cone_eq 83.6331 22.0145 0.1; brighter_than 16; ruwe_less_than 1.4" --limit 50 --brightest-first --csv-file ./data/gaia_subset.csv

  # Cone search using SIMBAD source name (resolves coordinates via SIMBAD TAP)
  python gaia_local.py query "cone_source M1 0.5; brighter_than 18" --limit 100
  python gaia_local.py query "cone_source NGC 6121 1.0; brighter_than 16" --limit 50 --brightest-first
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import psycopg
from psycopg import sql, errors

import csv
import io
from collections import OrderedDict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import duckdb
import pandas as pd
import pyvo as vo


def celestial_to_cartesian(ra: float, dec: float, parallax: float) -> Tuple[float, float, float]:
    """
    Convert celestial coordinates to Cartesian coordinates.

    Parameters:
    -----------
    ra : float
        Right Ascension in degrees
    dec : float
        Declination in degrees
    parallax : float
        Parallax in milliarcseconds (mas)

    Returns:
    --------
    x, y, z : float
        Cartesian coordinates in parsecs
    """
    if parallax is None or parallax <= 0:
        return None, None, None

    # Convert parallax to distance (in parsecs)
    distance = 1000.0 / parallax

    # Convert RA and DEC to radians
    ra_rad = np.radians(ra)
    dec_rad = np.radians(dec)

    # Calculate Cartesian coordinates
    x = np.cos(dec_rad) * np.cos(ra_rad)
    y = np.cos(dec_rad) * np.sin(ra_rad)
    z = distance * np.sin(dec_rad)

    return x, y, z


def build_column_index(header: list[str]) -> dict[str, int]:
    """
    Map column name -> first index in the header (handles duplicate names by keeping first).
    """
    idx: dict[str, int] = {}
    for i, name in enumerate(header):
        name = name.strip()
        if name and name not in idx:
            idx[name] = i
    return idx


# ----------------------------- Config -----------------------------

TABLE_COLUMNS = [
    "source_id",
    "ra",
    "dec",
    "parallax",
    "bp_rp",
    "phot_g_mean_mag",
    "pmra",
    "pmra_error",
    "pmdec",
    "pmdec_error",
    "l",
    "b",
    "parallax_over_error",
    "radial_velocity",
    "radial_velocity_error",
    "ruwe",
    "phot_g_mean_flux",
    "phot_g_mean_flux_over_error",
]

REQUIRED_COLS: Sequence[str] = tuple(TABLE_COLUMNS)

DEFAULT_TABLE = "gaia_source_subset"
CACHE_FILE = ".gaia_load_cache.txt"


@dataclass(frozen=True)
class DBConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str

    @staticmethod
    def from_args_env(args: argparse.Namespace) -> "DBConfig":
        # Env fallbacks: PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD
        host = args.host or os.getenv("PGHOST", "localhost")
        port = int(args.port or os.getenv("PGPORT", "5432"))
        dbname = args.db or os.getenv("PGDATABASE", "gaia_local")
        user = args.user or os.getenv("PGUSER", "postgres")
        password = args.password or os.getenv("PGPASSWORD", "postgres")
        return DBConfig(host=host, port=port, dbname=dbname, user=user, password=password)

    def dsn(self) -> str:
        return f"host={self.host} port={self.port} dbname={self.dbname} user={self.user} password={self.password}"


# ----------------------------- Utilities -----------------------------

def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def get_simbad_coordinates(target: str) -> Tuple[float, float]:
    """
    Query SIMBAD TAP service to get RA/Dec for a named target.

    Parameters:
    -----------
    target : str
        Target name (e.g., "M1", "NGC 6121", "Betelgeuse")

    Returns:
    --------
    ra, dec : float
        Right Ascension and Declination in degrees

    Raises:
    -------
    ValueError if target not found or coordinates cannot be retrieved
    """
    print(f"Connecting to SIMBAD TAP to resolve '{target}'...")
    service = vo.dal.TAPService("https://simbad.u-strasbg.fr/simbad/sim-tap")
    command = f"SELECT ra, dec FROM basic JOIN ident ON oidref = oid WHERE id = '{target}'"
    print(f"  Query: {command}")
    print("  Sending request...")

    try:
        data = service.search(command)
        if len(data) == 0:
            raise ValueError(f"Target '{target}' not found in SIMBAD")

        ra = float(data['ra'][0])
        dec = float(data['dec'][0])
        
        print(f"  Resolved: RA={ra:.6f}, Dec={dec:.6f}")
        return ra, dec
    except Exception as e:
        raise ValueError(f"Error getting RA/Dec of '{target}' from SIMBAD: {e}")


def connect(cfg: DBConfig) -> psycopg.Connection:
    # autocommit False so COPY is one transaction
    return psycopg.connect(cfg.dsn())


def execute_csv_query(csv_path: str, query: str, params: Optional[List] = None) -> List[Tuple]:
    """
    Execute a SQL query on a CSV file using DuckDB.
    Replace table identifier with CSV file path and %s placeholders with $1, $2, etc.
    """
    if not os.path.exists(csv_path):
        die(f"CSV file not found: {csv_path}")

    # DuckDB uses $1, $2, etc. for parameters, not %s
    # Replace %s with $1, $2, etc.
    if params:
        for i in range(len(params)):
            query = query.replace('%s', f'${i+1}', 1)

    # Replace table name with CSV reading function
    # Load CSV into a temp table with proper type casting for all numeric columns
    csv_path_escaped = csv_path.replace('\\', '/')  # DuckDB prefers forward slashes

    con = duckdb.connect(':memory:')

    # First, read the CSV to get actual column names
    temp_result = con.execute(f"SELECT * FROM read_csv('{csv_path_escaped}', header=true, all_varchar=true, nullstr='null') LIMIT 0").description
    actual_columns = [col[0] for col in temp_result]

    # Define expected columns and their types
    expected_columns = {
        'source_id': 'BIGINT',
        'ra': 'DOUBLE',
        'dec': 'DOUBLE',
        'parallax': 'DOUBLE',
        'bp_rp': 'DOUBLE',
        'phot_g_mean_mag': 'DOUBLE',
        'pmra': 'DOUBLE',
        'pmra_error': 'DOUBLE',
        'pmdec': 'DOUBLE',
        'pmdec_error': 'DOUBLE',
        'l': 'DOUBLE',
        'b': 'DOUBLE',
        'parallax_over_error': 'DOUBLE',
        'radial_velocity': 'DOUBLE',
        'radial_velocity_error': 'DOUBLE',
        'ruwe': 'DOUBLE',
        'phot_g_mean_flux': 'DOUBLE',
        'phot_g_mean_flux_over_error': 'DOUBLE',
    }

    # Build SELECT clause only for columns that exist in CSV
    select_clauses = []
    for col_name, col_type in expected_columns.items():
        if col_name in actual_columns:
            # Quote 'dec' since it's a reserved keyword
            quoted_name = f'"{col_name}"' if col_name == 'dec' else col_name
            select_clauses.append(f"TRY_CAST(NULLIF({quoted_name}, 'null') AS {col_type}) AS {quoted_name}")

    # Create a view with proper type casting
    view_sql = f"""
        CREATE VIEW gaia_data AS
        SELECT
            {', '.join(select_clauses)}
        FROM read_csv('{csv_path_escaped}', header=true, all_varchar=true, nullstr='null')
    """
    con.execute(view_sql)

    query = query.replace('{table}', 'gaia_data')

    if params:
        result = con.execute(query, params).fetchall()
    else:
        result = con.execute(query).fetchall()

    con.close()
    return result


def ensure_table_and_indexes(conn: psycopg.Connection, table: str) -> None:
    """
    Creates the table if missing (matching requested columns) and adds Q3C index.
    Safe to run repeatedly.
    """
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS q3c;")

        cur.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {table} (
                  source_id                      BIGINT PRIMARY KEY,
                  ra                             DOUBLE PRECISION NOT NULL,
                  dec                            DOUBLE PRECISION NOT NULL,
                  l                              DOUBLE PRECISION,
                  b                              DOUBLE PRECISION,

                  parallax                       REAL,
                  parallax_over_error            REAL,

                  pmra                           REAL,
                  pmra_error                     REAL,
                  pmdec                          REAL,
                  pmdec_error                    REAL,

                  radial_velocity                REAL,
                  radial_velocity_error          REAL,

                  bp_rp                          REAL,
                  phot_g_mean_mag                REAL,

                  ruwe                           REAL,

                  phot_g_mean_flux               DOUBLE PRECISION,
                  phot_g_mean_flux_over_error    REAL
                );
                """
            ).format(table=sql.Identifier(table))
        )

        # Q3C sky index
        cur.execute(
            sql.SQL(
                """
                CREATE INDEX IF NOT EXISTS {idx}
                ON {table} (q3c_ang2ipix(ra, dec));
                """
            ).format(
                idx=sql.Identifier(f"{table}_q3c_idx"),
                table=sql.Identifier(table),
            )
        )

        # Helpful indexes for brightness and quality cuts
        cur.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {idx} ON {table} (phot_g_mean_mag);").format(
                idx=sql.Identifier(f"{table}_gmag_idx"),
                table=sql.Identifier(table),
            )
        )
        cur.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {idx} ON {table} (ruwe);").format(
                idx=sql.Identifier(f"{table}_ruwe_idx"),
                table=sql.Identifier(table),
            )
        )

        cur.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {idx} ON {table} (bp_rp);").format(
                idx=sql.Identifier(f"{table}_bp_rp_idx"),
                table=sql.Identifier(table),
            )
        )

    conn.commit()


def get_row_count(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT COUNT(*) FROM {t};").format(t=sql.Identifier(table)))
        (n,) = cur.fetchone()
        return int(n)


def load_completed_files(cache_file: str) -> set[str]:
    """Load the set of completed CSV files from the cache file."""
    if not os.path.exists(cache_file):
        return set()

    with open(cache_file, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def add_completed_file(cache_file: str, csv_path: str) -> None:
    """Add a CSV file to the list of completed files."""
    # Normalize the path to avoid duplicates from different path formats
    normalized_path = os.path.normpath(os.path.abspath(csv_path))

    with open(cache_file, "a", encoding="utf-8") as f:
        f.write(normalized_path + "\n")


# ----------------------------- Shortlist parser -----------------------------

def _as_float(tok: str, what: str) -> float:
    try:
        return float(tok)
    except Exception:
        raise ValueError(f"Expected a number for {what}, got: {tok!r}")


def parse_shortlist_commands(cmds: str) -> Tuple[List[sql.SQL], List[object]]:
    """
    Parse semicolon-separated commands and produce:
      - list of SQL WHERE fragments (sql.SQL objects)
      - list of parameters for placeholders

    Supported commands:

      cone_eq <ra> <dec> <radius>
      cone_gal <gl> <gb> <radius>
      cone_source <name> <radius>  - resolve name via SIMBAD TAP
      brighter_than <value>
      fainter_than <value>
      further_than <value_in_pc>
      closer_than <value_in_pc>
      color_greater_than <value>
      color_less_than <value>
      ruwe_greater_than <value>
      ruwe_less_than <value>
      parallax significance <value>
      proper motion significance <value>
    """
    where_parts: List[sql.SQL] = []
    params: List[object] = []

    for raw in (c.strip() for c in cmds.split(";")):
        if not raw:
            continue

        toks = raw.split()
        ltoks = [t.lower() for t in toks]

        # --- cones ---
        if ltoks[0] == "cone_eq":
            if len(toks) != 4:
                raise ValueError("cone_eq requires: cone_eq <ra> <dec> <radius>")
            ra = _as_float(toks[1], "ra")
            dec = _as_float(toks[2], "dec")
            rad = _as_float(toks[3], "radius")
            where_parts.append(sql.SQL("q3c_radial_query(ra, dec, %s, %s, %s)"))
            params.extend([ra, dec, rad])
            continue

        if ltoks[0] == "cone_gal":
            if len(toks) != 4:
                raise ValueError("cone_gal requires: cone_gal <gl> <gb> <radius>")
            gl = _as_float(toks[1], "gl")
            gb = _as_float(toks[2], "gb")
            rad = _as_float(toks[3], "radius")
            where_parts.append(sql.SQL("q3c_radial_query(l, b, %s, %s, %s)"))
            params.extend([gl, gb, rad])
            continue

        if ltoks[0] == "cone_source":
            # cone_source <name> <radius>
            # Name can contain spaces, so everything except last token is the name
            if len(toks) < 3:
                raise ValueError("cone_source requires: cone_source <name> <radius>")
            rad = _as_float(toks[-1], "radius")
            # Join all middle tokens as the source name
            source_name = " ".join(toks[1:-1])
            try:
                ra, dec = get_simbad_coordinates(source_name)

            except ValueError as e:
                raise ValueError(f"cone_source error: {e}")
            where_parts.append(sql.SQL("q3c_radial_query(ra, dec, %s, %s, %s)"))
            params.extend([ra, dec, rad])
            continue

        # --- magnitude cuts ---
        if ltoks[0] == "brighter_than":
            if len(toks) != 2:
                raise ValueError("brighter_than requires: brighter_than <gmag>")
            v = _as_float(toks[1], "phot_g_mean_mag")
            where_parts.append(sql.SQL("phot_g_mean_mag IS NOT NULL AND phot_g_mean_mag < %s"))
            params.append(v)
            continue

        if ltoks[0] == "fainter_than":
            if len(toks) != 2:
                raise ValueError("fainter_than requires: fainter_than <gmag>")
            v = _as_float(toks[1], "phot_g_mean_mag")
            where_parts.append(sql.SQL("phot_g_mean_mag IS NOT NULL AND phot_g_mean_mag > %s"))
            params.append(v)
            continue

        # --- distance cuts using d ~ 1000/parallax(mas) ---
        if ltoks[0] == "closer_than":
            if len(toks) != 2:
                raise ValueError("closer_than requires: closer_than <pc>")
            pc = _as_float(toks[1], "pc")
            where_parts.append(
                sql.SQL("parallax IS NOT NULL AND parallax > 0 AND (1000.0 / parallax) < %s")
            )
            params.append(pc)
            continue

        if ltoks[0] == "further_than":
            if len(toks) != 2:
                raise ValueError("further_than requires: further_than <pc>")
            pc = _as_float(toks[1], "pc")
            where_parts.append(
                sql.SQL("parallax IS NOT NULL AND parallax > 0 AND (1000.0 / parallax) > %s")
            )
            params.append(pc)
            continue

        # --- color cuts ---
        if ltoks[0] == "color_greater_than":
            if len(toks) != 2:
                raise ValueError("color_greater_than requires: color_greater_than <bp_rp>")
            v = _as_float(toks[1], "bp_rp")
            where_parts.append(sql.SQL("bp_rp IS NOT NULL AND bp_rp > %s"))
            params.append(v)
            continue

        if ltoks[0] == "color_less_than":
            if len(toks) != 2:
                raise ValueError("color_less_than requires: color_less_than <bp_rp>")
            v = _as_float(toks[1], "bp_rp")
            where_parts.append(sql.SQL("bp_rp IS NOT NULL AND bp_rp < %s"))
            params.append(v)
            continue

        # --- RUWE cuts ---
        if ltoks[0] == "ruwe_greater_than":
            if len(toks) != 2:
                raise ValueError("ruwe_greater_than requires: ruwe_greater_than <ruwe>")
            v = _as_float(toks[1], "ruwe")
            where_parts.append(sql.SQL("ruwe IS NOT NULL AND ruwe > %s"))
            params.append(v)
            continue

        if ltoks[0] == "ruwe_less_than":
            if len(toks) != 2:
                raise ValueError("ruwe_less_than requires: ruwe_less_than <ruwe>")
            v = _as_float(toks[1], "ruwe")
            where_parts.append(sql.SQL("ruwe IS NOT NULL AND ruwe < %s"))
            params.append(v)
            continue

        # Also accept "parallax_significance <value>"
        if ltoks[0] == "parallax_significance":
            if len(toks) != 2:
                raise ValueError("parallax_significance requires: parallax_significance <value>")
            v = _as_float(toks[1], "parallax_over_error")
            where_parts.append(sql.SQL("parallax_over_error IS NOT NULL AND parallax_over_error > %s"))
            params.append(v)
            continue


        # Also accept "proper_motion_significance <value>"
        if ltoks[0] == "proper_motion_significance":
            if len(toks) != 2:
                raise ValueError("proper_motion_significance requires: proper_motion_significance <value>")
            v = _as_float(toks[1], "proper motion significance")
            where_parts.append(
                sql.SQL(
                    """
                    (
                      pmra IS NOT NULL AND pmra_error IS NOT NULL AND NULLIF(pmra_error, 0) IS NOT NULL
                      AND pmdec IS NOT NULL AND pmdec_error IS NOT NULL AND NULLIF(pmdec_error, 0) IS NOT NULL
                      AND (ABS(pmra) / NULLIF(pmra_error, 0)) > %s
                      AND (ABS(pmdec) / NULLIF(pmdec_error, 0)) > %s
                    )
                    """
                )
            )
            params.extend([v, v])
            continue

        raise ValueError(f"Unknown/unsupported shortlist command: {raw!r}")

    return where_parts, params


SHORTLIST_HELP = """
Shortlist Query Commands
========================

Combine multiple commands with semicolons, e.g.:
  "cone_source M4 0.5; brighter_than 16; ruwe_less_than 1.4"

CONE SEARCHES (select one):
  cone_eq <ra> <dec> <radius>      Cone search at equatorial coords (all in degrees)
  cone_gal <l> <b> <radius>        Cone search at galactic coords (all in degrees)
  cone_source <name> <radius>      Cone search using SIMBAD name resolution
                                   Name can have spaces, e.g. "cone_source NGC 6121 1.0"

MAGNITUDE CUTS:
  brighter_than <mag>              phot_g_mean_mag < value (smaller = brighter)
  fainter_than <mag>               phot_g_mean_mag > value

DISTANCE CUTS (from parallax):
  closer_than <pc>                 Distance < value parsecs
  further_than <pc>                Distance > value parsecs

COLOR CUTS:
  color_greater_than <bp_rp>       BP-RP color > value (redder)
  color_less_than <bp_rp>          BP-RP color < value (bluer)

QUALITY CUTS:
  ruwe_less_than <value>           RUWE < value (good astrometry typically < 1.4)
  ruwe_greater_than <value>        RUWE > value
  parallax_significance <value>    parallax/parallax_error > value
  proper_motion_significance <v>   |pmra|/pmra_error > v AND |pmdec|/pmdec_error > v

EXAMPLES:
  # Stars within 0.5 deg of M4, brighter than mag 16
  "cone_source M4 0.5; brighter_than 16"

  # Stars near Orion Nebula with good astrometry
  "cone_eq 83.82 -5.39 1.0; ruwe_less_than 1.4; parallax_significance 5"

  # Nearby red stars
  "closer_than 100; color_greater_than 1.5; brighter_than 12"
"""


def print_shortlist_help() -> None:
    """Print help for shortlist query commands."""
    print(SHORTLIST_HELP)


# ----------------------------- Core commands -----------------------------

def cmd_count(cfg: Optional[DBConfig], table: str, csv_file: Optional[str] = None) -> None:
    if csv_file:
        query = "SELECT COUNT(*) FROM {table}"
        result = execute_csv_query(csv_file, query)
        print(result[0][0])
    else:
        with connect(cfg) as conn:
            n = get_row_count(conn, table)
            print(n)


def cmd_load(
    cfg: DBConfig,
    table: str,
    csv_path: str,
    truncate: bool,
    create_if_missing: bool,
    use_cache: bool,
) -> None:
    if not os.path.exists(csv_path):
        die(f"CSV not found: {csv_path}")

    # Normalize path for cache lookup
    normalized_path = os.path.normpath(os.path.abspath(csv_path))

    # Check if this file was already loaded
    if use_cache:
        completed_files = load_completed_files(CACHE_FILE)
        if normalized_path in completed_files:
            print(f"Skipping {csv_path} (already loaded, found in cache)")
            print("Use --no-cache to force reload")
            return

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            die("CSV is empty")

        header = [h.strip() for h in header]
        col_to_first_idx = build_column_index(header)

        # load only columns we care about that exist in the CSV (first occurrence)
        load_cols = [c for c in TABLE_COLUMNS if c in col_to_first_idx]
        if "source_id" not in load_cols:
            die("CSV must contain 'source_id' column")

        load_indices = [col_to_first_idx[c] for c in load_cols]

    print(f"Will load {len(load_cols)} columns: {load_cols}")

    with connect(cfg) as conn:
        if create_if_missing:
            ensure_table_and_indexes(conn, table)

        try:
            with conn.cursor() as cur:
                if truncate:
                    cur.execute(sql.SQL("TRUNCATE TABLE {t};").format(t=sql.Identifier(table)))

                copy_sql = sql.SQL(
                    "COPY {t} ({cols}) FROM STDIN WITH (FORMAT csv)"
                ).format(
                    t=sql.Identifier(table),
                    cols=sql.SQL(", ").join(sql.Identifier(c) for c in load_cols),
                )

                with open(csv_path, newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    _ = next(reader)  # consume header

                    with cur.copy(copy_sql) as copy:
                        buf = io.StringIO()
                        writer = csv.writer(buf, lineterminator="\n")

                        rows_in_buf = 0
                        FLUSH_EVERY = 50_000

                        for row in reader:
                            out = []
                            for idx in load_indices:
                                if idx < len(row):
                                    v = row[idx].strip()
                                else:
                                    v = ""
                                if v.lower() in ("nan", "null", "none"):
                                    v = ""
                                out.append(v)
                            writer.writerow(out)
                            rows_in_buf += 1

                            if rows_in_buf >= FLUSH_EVERY:
                                copy.write(buf.getvalue().encode("utf-8"))
                                buf.seek(0)
                                buf.truncate(0)
                                rows_in_buf = 0

                        if buf.tell() > 0:
                            copy.write(buf.getvalue().encode("utf-8"))

            with conn.cursor() as cur:
                cur.execute(sql.SQL("ANALYZE {t};").format(t=sql.Identifier(table)))

            conn.commit()

            n = get_row_count(conn, table)
            print(f"Load complete. Row count now: {n}")

        except errors.UniqueViolation as e:
            conn.rollback()
            print(f"Skipping {csv_path} (contains duplicate data already in database)")
            print(f"Detail: {e}")

        # Add to cache after successful load or duplicate detection
        if use_cache:
            add_completed_file(CACHE_FILE, csv_path)
            print(f"Added {csv_path} to cache")


def cmd_cone(
    cfg: Optional[DBConfig],
    table: str,
    ra_deg: float,
    dec_deg: float,
    radius_deg: float,
    limit: int,
    brightest_first: bool,
    output_file: Optional[str] = None,
    csv_file: Optional[str] = None,
) -> None:
    if csv_file:
        # DuckDB doesn't have q3c, so use angular distance formula
        # Angular distance ≈ sqrt((ra1-ra2)^2*cos(dec)^2 + (dec1-dec2)^2)
        order = "phot_g_mean_mag ASC" if brightest_first else "source_id ASC"
        query = f"""
            SELECT
              source_id, ra, dec, phot_g_mean_mag, parallax, pmra, pmdec, ruwe
            FROM {{table}}
            WHERE SQRT(
                POWER((ra - %s) * COS(RADIANS(%s)), 2) +
                POWER(dec - %s, 2)
            ) <= %s
            ORDER BY {order}
            LIMIT %s
        """
        rows = execute_csv_query(csv_file, query, [ra_deg, dec_deg, dec_deg, radius_deg, limit])
    else:
        with connect(cfg) as conn:
            order = sql.SQL("phot_g_mean_mag ASC") if brightest_first else sql.SQL("source_id ASC")

            q = sql.SQL(
                """
                SELECT
                  source_id, ra, dec, phot_g_mean_mag, parallax, pmra, pmdec, ruwe
                FROM {t}
                WHERE q3c_radial_query(ra, dec, %s, %s, %s)
                ORDER BY {order}
                LIMIT %s;
                """
            ).format(t=sql.Identifier(table), order=order)

            with conn.cursor() as cur:
                cur.execute(q, (ra_deg, dec_deg, radius_deg, limit))
                rows = cur.fetchall()

    # Output to file or console
    if output_file:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['source_id', 'ra', 'dec', 'phot_g_mean_mag', 'parallax', 'pmra', 'pmdec', 'ruwe'])
            for r in rows:
                writer.writerow(['' if v is None else v for v in r])
        print(f"Saved {len(rows)} rows to {output_file}")
    else:
        print("source_id\tra\tdec\tphot_g_mean_mag\tparallax\tpmra\tpmdec\truwe")
        for r in rows:
            print("\t".join("" if v is None else str(v) for v in r))


def cmd_brightest(cfg: Optional[DBConfig], table: str, n: int, require_gmag: bool,  output_file: str, csv_file: Optional[str] = None) -> None:
    # Threshold for using parallel execution (adjust based on testing)
    PARALLEL_THRESHOLD = 100000

    if csv_file:
        where = "WHERE phot_g_mean_mag IS NOT NULL" if require_gmag else ""
        query = f"""
            SELECT
              source_id, ra, dec, parallax, bp_rp, phot_g_mean_mag,
              pmra, pmra_error, pmdec, pmdec_error,
              l, b, parallax_over_error,
              radial_velocity, radial_velocity_error, ruwe,
              phot_g_mean_flux, phot_g_mean_flux_over_error
            FROM {{table}}
            {where}
            ORDER BY phot_g_mean_mag ASC NULLS LAST
            LIMIT %s
        """
        rows = execute_csv_query(csv_file, query, [n])
    else:
        with connect(cfg) as conn:
            where = sql.SQL("WHERE phot_g_mean_mag IS NOT NULL") if require_gmag else sql.SQL("")

            # Choose query strategy based on N
            if n >= PARALLEL_THRESHOLD:
                # Large N: Use two-step approach for parallel execution
                print(f"Fetching {n:,} brightest stars using parallel execution...")

                with conn.cursor() as cur:
                    # Step 1: Find the magnitude threshold (uses index, very fast)
                    print(f"  Step 1: Finding magnitude threshold...")
                    threshold_query = sql.SQL(
                        """
                        SELECT phot_g_mean_mag
                        FROM {t}
                        WHERE phot_g_mean_mag IS NOT NULL
                        ORDER BY phot_g_mean_mag
                        OFFSET %s LIMIT 1
                        """
                    ).format(t=sql.Identifier(table))

                    cur.execute(threshold_query, (n - 1,))
                    result = cur.fetchone()
                    if not result:
                        die(f"Not enough stars with magnitude data (requested {n})")

                    threshold = result[0]
                    print(f"  Threshold: phot_g_mean_mag <= {threshold:.3f}")

                    # Step 2: Fetch all stars brighter than threshold (parallel execution)
                    print(f"  Step 2: Fetching all stars brighter than {threshold:.3f} using parallel workers...")

                    # Force parallel execution by disabling index scan for this query
                    cur.execute("SET LOCAL enable_indexscan = off;")
                    cur.execute("SET LOCAL enable_indexonlyscan = off;")

                    parallel_query = sql.SQL(
                        """
                        SELECT
                          source_id, ra, dec, parallax, bp_rp, phot_g_mean_mag,
                          pmra, pmra_error, pmdec, pmdec_error,
                          l, b, parallax_over_error,
                          radial_velocity, radial_velocity_error, ruwe,
                          phot_g_mean_flux, phot_g_mean_flux_over_error
                        FROM {t}
                        WHERE phot_g_mean_mag IS NOT NULL
                          AND phot_g_mean_mag <= %s
                        ORDER BY phot_g_mean_mag ASC
                        """
                    ).format(t=sql.Identifier(table))

                    cur.execute(parallel_query, (threshold,))
                    rows = cur.fetchall()
                    print(f"  Retrieved {len(rows):,} stars")
            else:
                # Small N: Use direct index scan (fast for small N)
                q = sql.SQL(
                    """
                    SELECT
                      source_id, ra, dec, parallax, bp_rp, phot_g_mean_mag,
                      pmra, pmra_error, pmdec, pmdec_error,
                      l, b, parallax_over_error,
                      radial_velocity, radial_velocity_error, ruwe,
                      phot_g_mean_flux, phot_g_mean_flux_over_error
                    FROM {t}
                    {where}
                    ORDER BY phot_g_mean_mag ASC NULLS LAST
                    LIMIT %s;
                    """
                ).format(t=sql.Identifier(table), where=where)

                with conn.cursor() as cur:
                    cur.execute(q, (n,))
                    rows = cur.fetchall()

    # Save to CSV file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'source_id', 'ra', 'dec', 'parallax', 'bp_rp', 'phot_g_mean_mag',
            'pmra', 'pmra_error', 'pmdec', 'pmdec_error',
            'l', 'b', 'parallax_over_error',
            'radial_velocity', 'radial_velocity_error', 'ruwe',
            'phot_g_mean_flux', 'phot_g_mean_flux_over_error'
        ])
        for r in rows:
            writer.writerow(['' if v is None else v for v in r])

    print(f"Saved {len(rows):,} stars to {output_path}")


def cmd_query(
    cfg: Optional[DBConfig],
    table: str,
    shortlist: str,
    limit: int,
    brightest_first: bool,
    csv_file: Optional[str] = None,
) -> None:
    if shortlist.strip().lower() == "help":
        print_shortlist_help()
        return

    try:
        where_parts, params = parse_shortlist_commands(shortlist)
    except ValueError as e:
        die(str(e))

    if csv_file:
        # Build query for DuckDB/CSV
        where_clauses = []
        for part in where_parts:
            # Convert sql.SQL to string
            clause_str = part.as_string(None)
            where_clauses.append(clause_str)

        where_sql = "TRUE" if not where_clauses else " AND ".join(where_clauses)
        order = "phot_g_mean_mag ASC NULLS LAST" if brightest_first else "source_id ASC"

        query = f"""
            SELECT
              source_id, ra, dec, l, b,
              phot_g_mean_mag, bp_rp,
              parallax, parallax_over_error,
              pmra, pmra_error, pmdec, pmdec_error,
              ruwe
            FROM {{table}}
            WHERE {where_sql}
            ORDER BY {order}
            LIMIT %s
        """
        rows = execute_csv_query(csv_file, query, [*params, limit])
    else:
        where_sql = sql.SQL("TRUE") if not where_parts else sql.SQL(" AND ").join(where_parts)
        order = sql.SQL("phot_g_mean_mag ASC NULLS LAST") if brightest_first else sql.SQL("source_id ASC")

        q = sql.SQL(
            """
            SELECT
              source_id, ra, dec, l, b,
              phot_g_mean_mag, bp_rp,
              parallax, parallax_over_error,
              pmra, pmra_error, pmdec, pmdec_error,
              ruwe
            FROM {t}
            WHERE {where}
            ORDER BY {order}
            LIMIT %s;
            """
        ).format(
            t=sql.Identifier(table),
            where=where_sql,
            order=order,
        )

        with connect(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(q, [*params, limit])
                rows = cur.fetchall()

    print(
        "source_id\tra\tdec\tl\tb\tphot_g_mean_mag\tbp_rp\tparallax\tparallax_over_error\tpmra\tpmra_error\tpmdec\tpmdec_error\truwe"
    )
    for r in rows:
        print("\t".join("" if v is None else str(v) for v in r))


def create_diagnostic_plots(rows: list, output_dir: Path) -> None:
    """
    Create diagnostic plots from query results.

    Row format: (source_id, ra, dec, parallax, bp_rp, phot_g_mean_mag,
                 pmra, pmra_error, pmdec, pmdec_error,
                 l, b, parallax_over_error,
                 radial_velocity, radial_velocity_error, ruwe,
                 phot_g_mean_flux, phot_g_mean_flux_over_error)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract data columns with correct indices
    data = {
        'source_id': [r[0] for r in rows],
        'ra': [r[1] for r in rows if r[1] is not None],
        'dec': [r[2] for r in rows if r[2] is not None],
        'parallax': [r[3] for r in rows if r[3] is not None],
        'bp_rp': [r[4] for r in rows if r[4] is not None],
        'phot_g_mean_mag': [r[5] for r in rows if r[5] is not None],
        'pmra': [r[6] for r in rows if r[6] is not None],
        'pmdec': [r[8] for r in rows if r[8] is not None],
        'l': [r[10] for r in rows if r[10] is not None],
        'b': [r[11] for r in rows if r[11] is not None],
        'parallax_over_error': [r[12] for r in rows if r[12] is not None],
        'radial_velocity': [r[13] for r in rows if r[13] is not None],
    }

    # Calculate distances from parallax (d = 1000/parallax, parallax in mas)
    distances = [1000.0 / p for p in data['parallax'] if p > 0]

    # Calculate total proper motion
    pm_total = [np.sqrt(pmra**2 + pmdec**2)
                for pmra, pmdec in zip([r[6] for r in rows if r[6] is not None and r[8] is not None],
                                       [r[8] for r in rows if r[6] is not None and r[8] is not None])]

    # 1. Histogram of distances
    if distances:
        plt.figure(figsize=(10, 6))
        plt.hist(distances, bins=50, edgecolor='black', alpha=0.7)
        plt.xlabel('Distance')
        plt.ylabel('Number of Stars')
        plt.title('Histogram of Parallax Distances')
        plt.grid(True, alpha=0.3)
        plt.savefig(output_dir / 'distance_histogram.png', dpi=150, bbox_inches='tight')
        plt.close()

    # 2. Proper motion histograms
    _, axes = plt.subplots(1, 3, figsize=(15, 5))

    if data['pmra']:
        axes[0].hist(data['pmra'], bins=50, edgecolor='black', alpha=0.7, color='blue')
        axes[0].set_xlabel('PM RA (mas/yr)')
        axes[0].set_ylabel('Number of Stars')
        axes[0].set_title('Proper Motion in RA')
        axes[0].grid(True, alpha=0.3)

    if data['pmdec']:
        axes[1].hist(data['pmdec'], bins=50, edgecolor='black', alpha=0.7, color='green')
        axes[1].set_xlabel('PM Dec (mas/yr)')
        axes[1].set_ylabel('Number of Stars')
        axes[1].set_title('Proper Motion in Dec')
        axes[1].grid(True, alpha=0.3)

    if pm_total:
        axes[2].hist(pm_total, bins=50, edgecolor='black', alpha=0.7, color='red')
        axes[2].set_xlabel('Total PM (mas/yr)')
        axes[2].set_ylabel('Number of Stars')
        axes[2].set_title('Total Proper Motion')
        axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / 'proper_motion_histograms.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 3. Radial velocity histogram
    if data['radial_velocity']:
        plt.figure(figsize=(10, 6))
        plt.hist(data['radial_velocity'], bins=50, edgecolor='black', alpha=0.7, color='purple')
        plt.xlabel('Radial Velocity (km/s)')
        plt.ylabel('Number of Stars')
        plt.title('Histogram of Radial Velocities')
        plt.grid(True, alpha=0.3)
        plt.savefig(output_dir / 'radial_velocity_histogram.png', dpi=150, bbox_inches='tight')
        plt.close()

    # 4. PM RA vs PM Dec
    if data['pmra'] and data['pmdec']:
        pmra_with_dec = [r[6] for r in rows if r[6] is not None and r[8] is not None]
        pmdec_with_ra = [r[8] for r in rows if r[6] is not None and r[8] is not None]

        plt.figure(figsize=(10, 10))
        plt.scatter(pmra_with_dec, pmdec_with_ra, alpha=0.5, s=10)
        plt.xlabel('PM RA (mas/yr)')
        plt.ylabel('PM Dec (mas/yr)')
        plt.title('Proper Motion: RA vs Dec')
        plt.grid(True, alpha=0.3)
        plt.axhline(y=0, color='k', linestyle='--', linewidth=0.5)
        plt.axvline(x=0, color='k', linestyle='--', linewidth=0.5)
        plt.axis('equal')
        plt.savefig(output_dir / 'pm_ra_vs_pm_dec.png', dpi=150, bbox_inches='tight')
        plt.close()

    # 5. Color-magnitude diagram (with absolute magnitude)
    if data['bp_rp'] and data['phot_g_mean_mag'] and data['parallax']:
        # Calculate absolute magnitude for stars with good parallax measurements
        # Filter: parallax_over_error > 10
        bp_rp_filtered = []
        absmag_filtered = []

        for r in rows:
            bp_rp = r[4]
            phot_g_mean_mag = r[5]
            parallax = r[3]
            parallax_over_error = r[12]

            # Apply filter: parallax_over_error > 10 and all values present
            if (bp_rp is not None and phot_g_mean_mag is not None and
                parallax is not None and parallax > 0 and
                parallax_over_error is not None and parallax_over_error > 10):

                # Calculate distance in parsecs and absolute magnitude
                distance = 1000.0 / parallax  # parallax in mas -> distance in pc
                absmag = phot_g_mean_mag - 5 * np.log10(distance) + 5

                bp_rp_filtered.append(bp_rp)
                absmag_filtered.append(absmag)

        if bp_rp_filtered and absmag_filtered:
            plt.figure(figsize=(12, 8))
            plt.scatter(bp_rp_filtered, absmag_filtered, s=0.5, color='sienna', alpha=0.7)
            plt.xlabel('BP - RP (mag)')
            plt.ylabel('Absolute Magnitude (mag)')
            plt.title('Color-Magnitude Diagram (parallax_over_error > 10)')
            plt.gca().invert_yaxis()  # Brighter stars at top
            plt.grid(True, alpha=0.3)
            plt.savefig(output_dir / 'color_magnitude_diagram.png', dpi=150, bbox_inches='tight')
            plt.close()

    # 6. RA vs Dec sky plot
    if data['ra'] and data['dec']:
        plt.figure(figsize=(12, 6))
        plt.scatter(data['ra'], data['dec'], alpha=0.5, s=10)
        plt.xlabel('RA (degrees)')
        plt.ylabel('Dec (degrees)')
        plt.title('Sky Position (Equatorial Coordinates)')
        plt.grid(True, alpha=0.3)
        plt.savefig(output_dir / 'ra_vs_dec.png', dpi=150, bbox_inches='tight')
        plt.close()

    # 7. l vs b sky plot
    if data['l'] and data['b']:
        plt.figure(figsize=(12, 6))
        plt.scatter(data['l'], data['b'], alpha=0.5, s=10, color='orange')
        plt.xlabel('Galactic Longitude (degrees)')
        plt.ylabel('Galactic Latitude (degrees)')
        plt.title('Sky Position (Galactic Coordinates)')
        plt.grid(True, alpha=0.3)
        plt.savefig(output_dir / 'l_vs_b.png', dpi=150, bbox_inches='tight')
        plt.close()

    print(f"Saved diagnostic plots to {output_dir}")


def cmd_diagnose(
    cfg: Optional[DBConfig],
    table: str,
    shortlist: str,
    limit: Optional[int],
    brightest_first: bool,
    output_dir: str,
    csv_file: Optional[str] = None,
    cartesian: bool = False,
    scale: float = 1.0,
) -> None:
    """
    Run query and generate diagnostic plots plus CSV output.

    Parameters:
    -----------
    cartesian : bool
        If True, save an additional cartesian.csv with x, y, z coordinates
    scale : float
        Scale factor to apply to cartesian coordinates before writing
    """
    if shortlist.strip().lower() == "help":
        print_shortlist_help()
        return

    try:
        where_parts, params = parse_shortlist_commands(shortlist)
    except ValueError as e:
        die(str(e))

    if csv_file:
        # Build query for DuckDB/CSV - select all table columns
        where_clauses = []
        for part in where_parts:
            clause_str = part.as_string(None)
            where_clauses.append(clause_str)

        where_sql = "TRUE" if not where_clauses else " AND ".join(where_clauses)
        order = "phot_g_mean_mag ASC NULLS LAST" if brightest_first else "source_id ASC"

        limit_clause = f"LIMIT %s" if limit is not None else ""
        query = f"""
            SELECT
              source_id, ra, dec, parallax, bp_rp, phot_g_mean_mag,
              pmra, pmra_error, pmdec, pmdec_error,
              l, b, parallax_over_error,
              radial_velocity, radial_velocity_error, ruwe,
              phot_g_mean_flux, phot_g_mean_flux_over_error
            FROM {{table}}
            WHERE {where_sql}
            ORDER BY {order}
            {limit_clause}
        """
        query_params = [*params, limit] if limit is not None else params
        rows = execute_csv_query(csv_file, query, query_params)
    else:
        where_sql = sql.SQL("TRUE") if not where_parts else sql.SQL(" AND ").join(where_parts)
        order = sql.SQL("phot_g_mean_mag ASC NULLS LAST") if brightest_first else sql.SQL("source_id ASC")

        # Build query with optional LIMIT
        if limit is not None:
            q = sql.SQL(
                """
                SELECT
                  source_id, ra, dec, parallax, bp_rp, phot_g_mean_mag,
                  pmra, pmra_error, pmdec, pmdec_error,
                  l, b, parallax_over_error,
                  radial_velocity, radial_velocity_error, ruwe,
                  phot_g_mean_flux, phot_g_mean_flux_over_error
                FROM {t}
                WHERE {where}
                ORDER BY {order}
                LIMIT %s;
                """
            ).format(
                t=sql.Identifier(table),
                where=where_sql,
                order=order,
            )
            query_params = [*params, limit]
        else:
            q = sql.SQL(
                """
                SELECT
                  source_id, ra, dec, parallax, bp_rp, phot_g_mean_mag,
                  pmra, pmra_error, pmdec, pmdec_error,
                  l, b, parallax_over_error,
                  radial_velocity, radial_velocity_error, ruwe,
                  phot_g_mean_flux, phot_g_mean_flux_over_error
                FROM {t}
                WHERE {where}
                ORDER BY {order};
                """
            ).format(
                t=sql.Identifier(table),
                where=where_sql,
                order=order,
            )
            query_params = params

        with connect(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(q, query_params)
                rows = cur.fetchall()

    if not rows:
        print("No rows returned from query.")
        return

    print(f"Retrieved {len(rows)} rows")

    # Create output directory
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Save CSV with all table columns
    csv_path = out_path / 'shortlist.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'source_id', 'ra', 'dec', 'parallax', 'bp_rp', 'phot_g_mean_mag',
            'pmra', 'pmra_error', 'pmdec', 'pmdec_error',
            'l', 'b', 'parallax_over_error',
            'radial_velocity', 'radial_velocity_error', 'ruwe',
            'phot_g_mean_flux', 'phot_g_mean_flux_over_error'
        ])
        for r in rows:
            writer.writerow(['' if v is None else v for v in r])

    print(f"Saved CSV to {csv_path}")

    # Save Cartesian coordinates if requested
    if cartesian:
        cartesian_path = out_path / 'cartesian.csv'
        cartesian_coords = []  # Store for plotting

        with open(cartesian_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['source_id', 'x', 'y', 'z'])

            for r in rows:
                source_id = r[0]
                ra = r[10]
                dec = r[11]
                parallax = r[3]

                x, y, z = celestial_to_cartesian(ra, dec, parallax)

                # Apply scale factor
                if x is not None and y is not None and z is not None:
                    x_scaled = x / scale
                    y_scaled = y / scale
                    z_scaled = z / scale
                    writer.writerow([source_id, x_scaled, y_scaled, z_scaled])
                    cartesian_coords.append((x_scaled, y_scaled, z_scaled))
                else:
                    # Write empty values for stars with invalid parallax
                    writer.writerow([source_id, '', '', ''])

        print(f"Saved Cartesian coordinates to {cartesian_path}")

        # Create corner plot for Cartesian coordinates
        if cartesian_coords:
            cartesian_array = np.array(cartesian_coords)
            x_coords = cartesian_array[:, 0]
            y_coords = cartesian_array[:, 1]
            z_coords = cartesian_array[:, 2]

            # Create 3x3 corner plot
            fig, axes = plt.subplots(3, 3, figsize=(12, 12))

            # Diagonal: histograms
            axes[0, 0].hist(x_coords, bins=50, edgecolor='black', alpha=0.7, color='blue')
            axes[0, 0].set_ylabel('Count')
            axes[0, 0].set_title('X distribution')
            axes[0, 0].grid(True, alpha=0.3)

            axes[1, 1].hist(y_coords, bins=50, edgecolor='black', alpha=0.7, color='green')
            axes[1, 1].set_ylabel('Count')
            axes[1, 1].set_title('Y distribution')
            axes[1, 1].grid(True, alpha=0.3)

            axes[2, 2].hist(z_coords, bins=50, edgecolor='black', alpha=0.7, color='red')
            axes[2, 2].set_xlabel('Z')
            axes[2, 2].set_ylabel('Count')
            axes[2, 2].set_title('Z distribution')
            axes[2, 2].grid(True, alpha=0.3)

            # Lower triangle: scatter plots
            axes[1, 0].scatter(x_coords, y_coords, alpha=0.3, s=1)
            axes[1, 0].set_xlabel('X')
            axes[1, 0].set_ylabel('Y')
            axes[1, 0].grid(True, alpha=0.3)
            axes[1, 0].set_aspect('equal', adjustable='box')

            axes[2, 0].scatter(x_coords, z_coords, alpha=0.3, s=1)
            axes[2, 0].set_xlabel('X')
            axes[2, 0].set_ylabel('Z')
            axes[2, 0].grid(True, alpha=0.3)
            axes[2, 0].set_aspect('equal', adjustable='box')

            axes[2, 1].scatter(y_coords, z_coords, alpha=0.3, s=1)
            axes[2, 1].set_xlabel('Y')
            axes[2, 1].set_ylabel('Z')
            axes[2, 1].grid(True, alpha=0.3)
            axes[2, 1].set_aspect('equal', adjustable='box')

            # Upper triangle: remove or show 3D info
            axes[0, 1].text(0.5, 0.5, f'N = {len(cartesian_coords)}\nscale = {scale}',
                          ha='center', va='center', fontsize=12, transform=axes[0, 1].transAxes)
            axes[0, 1].axis('off')

            axes[0, 2].axis('off')
            axes[1, 2].axis('off')

            plt.suptitle('Cartesian Coordinates Corner Plot', fontsize=14, y=0.995)
            plt.tight_layout()
            plt.savefig(out_path / 'cartesian_corner_plot.png', dpi=150, bbox_inches='tight')
            plt.close()

            print(f"Saved Cartesian corner plot to {out_path / 'cartesian_corner_plot.png'}")

    # Create diagnostic plots
    create_diagnostic_plots(rows, out_path)

    print(f"Diagnosis complete. Results saved to {output_dir}")


# ----------------------------- CLI -----------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local Gaia-like Postgres+Q3C loader and query tool.")
    p.add_argument("--csv-file", default=None, help="Use CSV file instead of database (DuckDB)")
    p.add_argument("--host", default=None, help="DB host (default: env PGHOST or localhost)")
    p.add_argument("--port", default=None, help="DB port (default: env PGPORT or 5432)")
    p.add_argument("--db", default=None, help="DB name (default: env PGDATABASE or gaia_local)")
    p.add_argument("--user", default=None, help="DB user (default: env PGUSER or postgres)")
    p.add_argument("--password", default=None, help="DB password (default: env PGPASSWORD or postgres)")
    p.add_argument("--table", default=DEFAULT_TABLE, help=f"Table name (default: {DEFAULT_TABLE})")

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("count", help="Print number of rows in the table")

    c_load = sub.add_parser("load", help="Load CSV into table using COPY")
    c_load.add_argument("csv", help="Path to CSV file on the host")
    c_load.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading")
    c_load.add_argument(
        "--no-create",
        action="store_true",
        help="Do not create table/indexes (assume they already exist)",
    )
    c_load.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching (load file even if already completed before)",
    )

    c_cone = sub.add_parser("cone", help="Cone search with Q3C; prints TSV or saves to CSV")
    c_cone.add_argument("ra", type=float, help="RA (deg)")
    c_cone.add_argument("dec", type=float, help="Dec (deg)")
    c_cone.add_argument("radius", type=float, help="Radius (deg)")
    c_cone.add_argument("--limit", type=int, default=100, help="Max rows (default 100)")
    c_cone.add_argument(
        "--brightest-first",
        action="store_true",
        help="Order by phot_g_mean_mag ascending within the cone",
    )
    c_cone.add_argument(
        "--output",
        default=None,
        help="Output CSV file path (if not specified, prints to console)",
    )

    c_bright = sub.add_parser("brightest", help="Get first N brightest by phot_g_mean_mag; saves to CSV")
    c_bright.add_argument("n", type=int, help="Number of stars to return")
    c_bright.add_argument(
        "--require-gmag",
        action="store_true",
        help="Exclude rows with NULL phot_g_mean_mag",
    )
    c_bright.add_argument(
        "--output",
        default="brightest.csv",
        help="Output CSV file path (default: brightest.csv)",
    )

    c_query = sub.add_parser("query", help="Semicolon-separated shortlist query; prints TSV")
    c_query.add_argument(
        "shortlist",
        help='Shortlist string, e.g. "cone_eq 83.6 22.0 0.1; brighter_than 16; ruwe_less_than 1.4"',
    )
    c_query.add_argument("--limit", type=int, default=100, help="Max rows (default 100)")
    c_query.add_argument(
        "--brightest-first",
        action="store_true",
        help="Order by phot_g_mean_mag ascending (NULLS LAST)",
    )

    c_diagnose = sub.add_parser("diagnose", help="Run query and generate diagnostic plots + CSV")
    c_diagnose.add_argument(
        "shortlist",
        help='Shortlist string, e.g. "cone_eq 83.6 22.0 0.1; brighter_than 16; ruwe_less_than 1.4"',
    )
    c_diagnose.add_argument("--limit", type=int, default=None, help="Max rows (optional, no limit by default)")
    c_diagnose.add_argument(
        "--brightest-first",
        action="store_true",
        help="Order by phot_g_mean_mag ascending (NULLS LAST)",
    )
    c_diagnose.add_argument(
        "--output-dir",
        default="./diagnostic_output",
        help="Output directory for plots and CSV (default: ./diagnostic_output)",
    )
    c_diagnose.add_argument(
        "--cartesian",
        action="store_true",
        help="Save an additional cartesian.csv with x, y, z coordinates converted from ra, dec, parallax",
    )
    c_diagnose.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale factor to apply to Cartesian coordinates (default: 1.0)",
    )

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    csv_file = args.csv_file

    # Only require DB config if not using CSV
    if csv_file:
        cfg = None
        if args.cmd == "load":
            die("Cannot use 'load' command with --csv-file option")
    else:
        cfg = DBConfig.from_args_env(args)

    table = args.table

    if args.cmd == "count":
        cmd_count(cfg, table, csv_file=csv_file)
    elif args.cmd == "load":
        cmd_load(
            cfg=cfg,
            table=table,
            csv_path=args.csv,
            truncate=args.truncate,
            create_if_missing=(not args.no_create),
            use_cache=(not args.no_cache),
        )
    elif args.cmd == "cone":
        cmd_cone(
            cfg=cfg,
            table=table,
            ra_deg=args.ra,
            dec_deg=args.dec,
            radius_deg=args.radius,
            limit=args.limit,
            brightest_first=args.brightest_first,
            output_file=args.output,
            csv_file=csv_file,
        )
    elif args.cmd == "brightest":
        cmd_brightest(cfg, table, args.n, require_gmag=args.require_gmag, output_file=args.output, csv_file=csv_file)
    elif args.cmd == "query":
        cmd_query(
            cfg=cfg,
            table=table,
            shortlist=args.shortlist,
            limit=args.limit,
            brightest_first=args.brightest_first,
            csv_file=csv_file,
        )
    elif args.cmd == "diagnose":
        cmd_diagnose(
            cfg=cfg,
            table=table,
            shortlist=args.shortlist,
            limit=args.limit,
            brightest_first=args.brightest_first,
            output_dir=args.output_dir,
            csv_file=csv_file,
            cartesian=args.cartesian,
            scale=args.scale,
        )
    else:
        die("Unknown command")


if __name__ == "__main__":
    main()
