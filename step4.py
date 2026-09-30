import polars as pl
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "classified_swaps.parquet"

OUTPUT_FILE = BASE_DIR / "swaps.parquet"
COMPLEX_FILE = BASE_DIR / "complex_swaps.parquet"


# ============================================================
# CONSTANTS
# ============================================================

WSOL = "So11111111111111111111111111111111111111112"
SOL = "SOL"


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 70)
print("STEP 4 - NORMALIZE WALLET SWAPS")
print("=" * 70)
print()


# ============================================================
# LOAD
# ============================================================

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input file not found:\n{INPUT_FILE}\n\n"
        "Check that step3.py created classified_swaps.parquet."
    )

df = pl.read_parquet(INPUT_FILE)

print(f"Input rows: {len(df):,}")
print(f"Columns: {df.columns}")
print()


# ============================================================
# REQUIRED COLUMNS
# ============================================================

required = [
    "block_timestamp",
    "signature",
    "wallet",
    "classification",
    "trade_type",
    "sold_asset",
    "sold_amount",
    "bought_asset",
    "bought_amount",
    "sol_delta",
    "tokens_sent",
    "tokens_received",
    "n_assets",
    "n_non_sol_assets",
    "n_token_flows",
]

missing = [c for c in required if c not in df.columns]

if missing:
    raise ValueError(
        f"STEP 3 output is missing columns: {missing}\n\n"
        f"Available columns:\n{df.columns}"
    )


# ============================================================
# NORMALIZE TYPES
# ============================================================

df = df.with_columns(
    [
        pl.col("classification")
        .cast(pl.String)
        .str.to_uppercase()
        .str.strip_chars(),

        pl.col("trade_type")
        .cast(pl.String)
        .str.to_uppercase()
        .str.strip_chars(),

        pl.col("sold_asset")
        .cast(pl.String),

        pl.col("bought_asset")
        .cast(pl.String),

        pl.col("sold_amount")
        .cast(pl.Float64)
        .fill_null(0.0),

        pl.col("bought_amount")
        .cast(pl.Float64)
        .fill_null(0.0),

        pl.col("sol_delta")
        .cast(pl.Float64)
        .fill_null(0.0),

        pl.col("tokens_sent")
        .cast(pl.Float64)
        .fill_null(0.0),

        pl.col("tokens_received")
        .cast(pl.Float64)
        .fill_null(0.0),
    ]
)


# ============================================================
# BASIC REPORT
# ============================================================

print("Classification:")
print(
    df
    .group_by("classification")
    .len()
    .sort("classification")
)

print()

print("Trade type:")
print(
    df
    .group_by("trade_type")
    .len()
    .sort("trade_type")
)

print()


# ============================================================
# NORMALIZE ASSET NAMES
# ============================================================

df = df.with_columns(
    [
        pl.when(pl.col("sold_asset") == WSOL)
        .then(pl.lit(SOL))
        .otherwise(pl.col("sold_asset"))
        .alias("sold_asset_normalized"),

        pl.when(pl.col("bought_asset") == WSOL)
        .then(pl.lit(SOL))
        .otherwise(pl.col("bought_asset"))
        .alias("bought_asset_normalized"),
    ]
)


# ============================================================
# DETERMINE TOKEN MINT
# ============================================================

# BUY:
#     sold_asset   = SOL
#     bought_asset = TOKEN
#
# SELL:
#     sold_asset   = TOKEN
#     bought_asset = SOL
#
# Therefore:
#
# BUY  -> bought_asset
# SELL -> sold_asset

df = df.with_columns(
    pl.when(pl.col("classification") == "BUY")
    .then(pl.col("bought_asset_normalized"))
    .when(pl.col("classification") == "SELL")
    .then(pl.col("sold_asset_normalized"))
    .otherwise(pl.lit(None))
    .alias("token_mint")
)


# ============================================================
# DETERMINE TOKEN AMOUNT
# ============================================================

df = df.with_columns(
    pl.when(pl.col("classification") == "BUY")
    .then(pl.col("bought_amount"))
    .when(pl.col("classification") == "SELL")
    .then(-pl.col("sold_amount"))
    .otherwise(pl.lit(0.0))
    .alias("token_amount")
)


# ============================================================
# SOL AMOUNT
# ============================================================

# sol_delta is the wallet's net SOL balance change.
#
# BUY:
#     normally negative
#
# SELL:
#     normally positive
#
# Keep the original value rather than reconstructing it.

df = df.with_columns(
    pl.col("sol_delta")
    .alias("sol_amount")
)


# ============================================================
# REMOVE INVALID TOKEN ASSETS
# ============================================================

df = df.filter(
    pl.col("token_mint").is_not_null()
)

df = df.filter(
    pl.col("token_mint") != SOL
)


# ============================================================
# SIMPLE SWAPS
# ============================================================

# A simple swap is:
#
#   2 assets
#   1 non-SOL asset
#   1 token flow
#
# This corresponds to the cleanest observations.

simple_condition = (
    (pl.col("n_assets") == 2)
    & (pl.col("n_non_sol_assets") == 1)
    & (pl.col("n_token_flows") == 1)
)

simple = df.filter(simple_condition)

complex_swaps = df.filter(~simple_condition)


# ============================================================
# REMOVE ZERO TOKEN AMOUNTS
# ============================================================

simple = simple.filter(
    pl.col("token_amount").abs() > 0
)


# ============================================================
# DIRECTION CHECK
# ============================================================

simple = simple.with_columns(
    (
        (
            (pl.col("classification") == "BUY")
            & (pl.col("token_amount") > 0)
            & (pl.col("sol_amount") < 0)
        )
        |
        (
            (pl.col("classification") == "SELL")
            & (pl.col("token_amount") < 0)
            & (pl.col("sol_amount") > 0)
        )
    ).alias("direction_consistent")
)


# ============================================================
# SIDE
# ============================================================

simple = simple.with_columns(
    pl.when(pl.col("token_amount") > 0)
    .then(pl.lit("BUY"))
    .when(pl.col("token_amount") < 0)
    .then(pl.lit("SELL"))
    .otherwise(pl.lit("UNKNOWN"))
    .alias("side")
)


# ============================================================
# PRICE IN SOL
# ============================================================

# Approximate execution price:
#
#     SOL spent / token received       BUY
#
#     SOL received / token sold        SELL
#
# This gives SOL per token.

simple = simple.with_columns(
    pl.when(
        (pl.col("side") == "BUY")
        & (pl.col("token_amount") > 0)
    )
    .then(
        (-pl.col("sol_amount"))
        / pl.col("token_amount")
    )
    .when(
        (pl.col("side") == "SELL")
        & (pl.col("token_amount") < 0)
    )
    .then(
        pl.col("sol_amount")
        / (-pl.col("token_amount"))
    )
    .otherwise(None)
    .alias("price_sol")
)


# ============================================================
# CLEAN NUMERIC VALUES
# ============================================================

simple = simple.with_columns(
    [
        pl.col("token_amount")
        .cast(pl.Float64),

        pl.col("sol_amount")
        .cast(pl.Float64),

        pl.col("price_sol")
        .cast(pl.Float64),
    ]
)


# ============================================================
# REMOVE INVALID PRICES
# ============================================================

simple = simple.filter(
    (
        pl.col("price_sol").is_not_null()
    )
    &
    (
        pl.col("price_sol") > 0
    )
    &
    (
        pl.col("price_sol").is_finite()
    )
)


# ============================================================
# SELECT FINAL COLUMNS
# ============================================================

simple = simple.select(
    [
        "block_timestamp",
        "signature",
        "wallet",

        "side",
        "classification",
        "trade_type",

        "token_mint",
        "token_amount",

        "sold_asset_normalized",
        "sold_amount",

        "bought_asset_normalized",
        "bought_amount",

        "sol_amount",
        "price_sol",

        "tokens_sent",
        "tokens_received",

        "n_assets",
        "n_non_sol_assets",
        "n_token_flows",

        "direction_consistent",
    ]
)


# ============================================================
# DEDUPLICATE
# ============================================================

simple = simple.unique(
    subset=[
        "signature",
        "wallet",
        "token_mint",
    ],
    keep="first",
)


# ============================================================
# SORT
# ============================================================

simple = simple.sort(
    [
        "block_timestamp",
        "signature",
        "wallet",
    ]
)


# ============================================================
# WRITE SIMPLE SWAPS
# ============================================================

simple.write_parquet(
    OUTPUT_FILE,
    compression="zstd",
)


# ============================================================
# WRITE COMPLEX SWAPS
# ============================================================

complex_swaps.write_parquet(
    COMPLEX_FILE,
    compression="zstd",
)


# ============================================================
# FINAL REPORT
# ============================================================

print()
print("=" * 70)
print("STEP 4 COMPLETE")
print("=" * 70)
print()

print(f"Input rows:          {len(df):,}")
print(f"Simple swaps:        {len(simple):,}")
print(f"Complex swaps:       {len(complex_swaps):,}")
print()

print("SIDE DISTRIBUTION")
print(
    simple
    .group_by("side")
    .len()
    .sort("side")
)

print()

print("DIRECTION CONSISTENCY")
print(
    simple
    .group_by("direction_consistent")
    .len()
    .sort("direction_consistent")
)

print()

print(
    f"Unique wallets:      "
    f"{simple.select(pl.col('wallet').n_unique()).item():,}"
)

print(
    f"Unique tokens:       "
    f"{simple.select(pl.col('token_mint').n_unique()).item():,}"
)

print(
    f"Unique transactions: "
    f"{simple.select(pl.col('signature').n_unique()).item():,}"
)

print()

print("FIRST 30 NORMALIZED SWAPS")
print(
    simple
    .select(
        [
            "block_timestamp",
            "signature",
            "wallet",
            "side",
            "token_mint",
            "token_amount",
            "sol_amount",
            "price_sol",
            "direction_consistent",
        ]
    )
    .head(30)
)

print()

print("LARGEST TOKEN FLOWS")
print(
    simple
    .with_columns(
        pl.col("token_amount")
        .abs()
        .alias("abs_token_amount")
    )
    .sort(
        "abs_token_amount",
        descending=True
    )
    .select(
        [
            "block_timestamp",
            "signature",
            "wallet",
            "side",
            "token_mint",
            "token_amount",
            "sol_amount",
            "price_sol",
        ]
    )
    .head(20)
)

print()
print("OUTPUT FILES")
print(f"  Simple swaps : {OUTPUT_FILE}")
print(f"  Complex swaps: {COMPLEX_FILE}")
print()