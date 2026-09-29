import pyarrow.parquet as pq
from pathlib import Path
import os
import shutil


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path(
    r"D:\solana\solarchive\txs\2025-11-01\000000000000.parquet"
)

OUTPUT_DIR = Path(
    r"D:\solana\solarchive\txs\2025-11-01\chunks_20mb"
)

# Maximum actual file size
MAX_SIZE = 20 * 1024 * 1024       # 20 MiB

# Temporary directory
TEMP_DIR = OUTPUT_DIR / "_temp"


# ============================================================
# SETUP
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

TEMP_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# OPEN INPUT
# ============================================================

pf = pq.ParquetFile(INPUT_FILE)

print("=" * 80)
print("PARQUET SPLITTER - MAX 20 MiB")
print("=" * 80)

print()
print("Input :", INPUT_FILE)
print(
    "Input size :",
    round(INPUT_FILE.stat().st_size / 1024 / 1024, 2),
    "MiB"
)
print("Rows       :", f"{pf.metadata.num_rows:,}")
print("Row groups :", pf.num_row_groups)
print()
print("Maximum output size : 20 MiB")
print()


# ============================================================
# WRITE TABLE TO TEMP FILE AND RETURN ACTUAL SIZE
# ============================================================

def test_table_size(table, filename):

    if filename.exists():
        filename.unlink()

    pq.write_table(
        table,
        filename,
        compression="snappy"
    )

    return filename.stat().st_size


# ============================================================
# FIND LARGEST NUMBER OF ROWS THAT FIT
# ============================================================

def find_fitting_rows(table):

    total_rows = table.num_rows

    if total_rows == 0:
        return 0, 0

    # --------------------------------------------------------
    # First check the complete table
    # --------------------------------------------------------

    test_file = TEMP_DIR / "test.parquet"

    size = test_table_size(
        table,
        test_file
    )

    if size <= MAX_SIZE:
        test_file.unlink()
        return total_rows, size

    # --------------------------------------------------------
    # Binary search
    # --------------------------------------------------------

    low = 1
    high = total_rows

    best_rows = 0
    best_size = 0

    while low <= high:

        middle = (low + high) // 2

        candidate = table.slice(
            0,
            middle
        )

        size = test_table_size(
            candidate,
            test_file
        )

        if size <= MAX_SIZE:

            best_rows = middle
            best_size = size

            low = middle + 1

        else:

            high = middle - 1

    # --------------------------------------------------------
    # Safety check
    # --------------------------------------------------------

    if best_rows == 0:

        raise RuntimeError(
            "A single row is larger than 20 MiB. "
            "Cannot create a file <= 20 MiB."
        )

    test_file.unlink()

    return best_rows, best_size


# ============================================================
# CREATE OUTPUT FILE
# ============================================================

def create_output_file(table, part_number):

    filename = (
        OUTPUT_DIR /
        f"part_{part_number:04d}.parquet"
    )

    # Write directly
    pq.write_table(
        table,
        filename,
        compression="snappy"
    )

    actual_size = filename.stat().st_size

    # --------------------------------------------------------
    # HARD SAFETY CHECK
    # --------------------------------------------------------

    if actual_size > MAX_SIZE:

        filename.unlink()

        raise RuntimeError(
            f"ERROR: {filename.name} is "
            f"{actual_size / 1024 / 1024:.2f} MiB "
            f"which exceeds the 20 MiB limit."
        )

    return filename, actual_size


# ============================================================
# PROCESS ROW GROUPS
# ============================================================

part_number = 0
total_output_rows = 0
total_output_size = 0


for rg in range(pf.num_row_groups):

    print(
        f"Processing row group "
        f"{rg + 1}/{pf.num_row_groups}..."
    )

    table = pf.read_row_group(rg)

    remaining = table

    while remaining.num_rows > 0:

        # ----------------------------------------------------
        # Find largest portion that fits into 20 MiB
        # ----------------------------------------------------

        rows, estimated_size = find_fitting_rows(
            remaining
        )

        chunk = remaining.slice(
            0,
            rows
        )

        # ----------------------------------------------------
        # Write actual Parquet file
        # ----------------------------------------------------

        filename, actual_size = create_output_file(
            chunk,
            part_number
        )

        part_number += 1

        total_output_rows += chunk.num_rows
        total_output_size += actual_size

        print(
            f"  {filename.name:25s} "
            f"{actual_size / 1024 / 1024:8.2f} MiB "
            f"{chunk.num_rows:12,} rows"
        )

        # ----------------------------------------------------
        # Remove rows already processed
        # ----------------------------------------------------

        remaining = remaining.slice(
            rows
        )


# ============================================================
# CLEAN TEMP FILES
# ============================================================

try:
    shutil.rmtree(TEMP_DIR)
except Exception:
    pass


# ============================================================
# FINAL VERIFICATION
# ============================================================

print()
print("=" * 80)
print("FINAL VERIFICATION")
print("=" * 80)

output_files = sorted(
    OUTPUT_DIR.glob("part_*.parquet")
)

all_ok = True

for file in output_files:

    size = file.stat().st_size
    size_mb = size / 1024 / 1024

    if size > MAX_SIZE:
        all_ok = False

    print(
        f"{file.name:25s} "
        f"{size_mb:8.2f} MiB "
        f"{'OK' if size <= MAX_SIZE else 'TOO LARGE'}"
    )


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 80)
print("DONE")
print("=" * 80)

print("Number of files :", len(output_files))
print(
    "Total rows      :",
    f"{total_output_rows:,}"
)
print(
    "Total size      :",
    f"{total_output_size / 1024 / 1024:.2f} MiB"
)

print()

if all_ok:
    print("SUCCESS: Every file is <= 20 MiB.")
else:
    print("ERROR: At least one file exceeds 20 MiB.")

print()
print("Output directory:")
print(OUTPUT_DIR)