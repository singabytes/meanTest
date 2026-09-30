
import polars as pl
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

FILE = r"D:\New folder (2)\meanTest\wallet_ledger.parquet"
FILE2 = r"D:\New folder (2)\meanTest\swap_movements.parquet"



LEDGER_FILE = Path(FILE)
CANDIDATES_FILE = Path(FILE2)
OUTPUT_FILE = Path("classified_swaps.parquet")

# Native SOL
SOL = "SOL"

# Wrapped SOL
WSOL = "So11111111111111111111111111111111111111112"


# ============================================================
# LOAD
# ============================================================

print()
print("=" * 40)
print("STEP 3 - WALLET SWAP CLASSIFICATION")
print("=" * 40)
print()

if not LEDGER_FILE.exists():
    raise FileNotFoundError(
        f"Cannot find {LEDGER_FILE}"
    )

if not CANDIDATES_FILE.exists():
    raise FileNotFoundError(
        f"Cannot find {CANDIDATES_FILE}"
    )

ledger = pl.read_parquet(LEDGER_FILE)
candidates = pl.read_parquet(CANDIDATES_FILE)

print(f"Ledger rows:       {len(ledger):,}")
print(f"Candidate rows:    {len(candidates):,}")


# ============================================================
# CHECK LEDGER
# ============================================================

required = {
    "block_timestamp",
    "signature",
    "wallet",
    "mint",
    "delta",
    "decimals",
    "asset_type",
}

missing = required - set(ledger.columns)

if missing:
    raise ValueError(
        f"Ledger is missing columns: {sorted(missing)}"
    )


# ============================================================
# GET CANDIDATE WALLET / TRANSACTION PAIRS
# ============================================================

candidate_keys = (
    candidates
    .select([
        "signature",
        "wallet",
    ])
    .unique()
)

print(
    f"Candidate wallet/tx pairs: "
    f"{len(candidate_keys):,}"
)


# ============================================================
# FILTER LEDGER
# ============================================================

df = ledger.join(
    candidate_keys,
    on=["signature", "wallet"],
    how="inner",
)

print(
    f"Ledger rows after candidate filter: "
    f"{len(df):,}"
)


# ============================================================
# CLEAN
# ============================================================

df = df.filter(
    pl.col("mint").is_not_null()
    & pl.col("delta").is_not_null()
    & pl.col("decimals").is_not_null()
)


# ============================================================
# NORMALIZE TOKEN AMOUNTS
# ============================================================

df = df.with_columns(
    (
        pl.col("delta").cast(pl.Float64)
        /
        (
            pl.lit(10.0)
            ** pl.col("decimals").cast(pl.Float64)
        )
    ).alias("amount")
)


# ============================================================
# COMBINE SOL + WSOL
# ============================================================

df = df.with_columns(
    pl.when(
        (pl.col("mint") == SOL)
        | (pl.col("mint") == WSOL)
    )
    .then(pl.lit(SOL))
    .otherwise(pl.col("mint"))
    .alias("asset")
)


# ============================================================
# AGGREGATE SAME ASSET WITHIN WALLET / TRANSACTION
# ============================================================

flows = (
    df
    .group_by([
        "signature",
        "block_timestamp",
        "wallet",
        "asset",
    ])
    .agg([
        pl.col("amount").sum().alias("net_amount"),
        pl.col("decimals").max().alias("decimals"),
        pl.col("asset_type").first().alias("asset_type"),
    ])
    .sort([
        "block_timestamp",
        "signature",
        "wallet",
    ])
)


# ============================================================
# REMOVE ZERO FLOWS
# ============================================================

flows = flows.filter(
    pl.col("net_amount").abs() > 1e-12
)

print(
    f"Non-zero wallet asset flows: "
    f"{len(flows):,}"
)


# ============================================================
# CREATE SEPARATE SOL / TOKEN TABLES
#
# This avoids the Polars nested-filter problem.
# ============================================================

sol_flows = (
    flows
    .filter(pl.col("asset") == SOL)
    .select([
        "signature",
        "wallet",
        "net_amount",
    ])
    .rename({
        "net_amount": "sol_delta"
    })
)


token_flows = (
    flows
    .filter(pl.col("asset") != SOL)
)


# ============================================================
# SOL DELTA
# ============================================================

sol_summary = (
    sol_flows
    .group_by([
        "signature",
        "wallet",
    ])
    .agg(
        pl.col("sol_delta").sum()
    )
)


# ============================================================
# TOKEN RECEIVED
# ============================================================

tokens_received = (
    token_flows
    .filter(pl.col("net_amount") > 0)
    .group_by([
        "signature",
        "wallet",
    ])
    .agg(
        pl.col("net_amount")
        .sum()
        .alias("tokens_received")
    )
)


# ============================================================
# TOKEN SENT
# ============================================================

tokens_sent = (
    token_flows
    .filter(pl.col("net_amount") < 0)
    .group_by([
        "signature",
        "wallet",
    ])
    .agg(
        pl.col("net_amount")
        .sum()
        .alias("tokens_sent")
    )
)


# ============================================================
# NUMBER OF NON-SOL ASSETS
# ============================================================

asset_summary = (
    token_flows
    .group_by([
        "signature",
        "wallet",
    ])
    .agg([
        pl.col("asset")
        .n_unique()
        .alias("n_non_sol_assets"),

        pl.len()
        .alias("n_token_flows"),
    ])
)


# ============================================================
# TOTAL NUMBER OF ASSETS
# ============================================================

asset_count = (
    flows
    .group_by([
        "signature",
        "wallet",
    ])
    .agg(
        pl.col("asset")
        .n_unique()
        .alias("n_assets")
    )
)


# ============================================================
# BASE TRANSACTION TABLE
# ============================================================

base = (
    flows
    .select([
        "signature",
        "block_timestamp",
        "wallet",
    ])
    .unique()
)


# ============================================================
# BUILD SUMMARY
# ============================================================

summary = (
    base
    .join(
        asset_count,
        on=["signature", "wallet"],
        how="left",
    )
    .join(
        sol_summary,
        on=["signature", "wallet"],
        how="left",
    )
    .join(
        tokens_received,
        on=["signature", "wallet"],
        how="left",
    )
    .join(
        tokens_sent,
        on=["signature", "wallet"],
        how="left",
    )
    .join(
        asset_summary,
        on=["signature", "wallet"],
        how="left",
    )
)


# ============================================================
# REPLACE NULLS
# ============================================================

summary = summary.with_columns([
    pl.col("sol_delta")
    .fill_null(0.0),

    pl.col("tokens_received")
    .fill_null(0.0),

    pl.col("tokens_sent")
    .fill_null(0.0),

    pl.col("n_non_sol_assets")
    .fill_null(0),

    pl.col("n_token_flows")
    .fill_null(0),
])


# ============================================================
# CLASSIFICATION
# ============================================================

summary = summary.with_columns(
    pl.when(
        # BUY TOKEN WITH SOL
        (pl.col("sol_delta") < 0)
        & (pl.col("tokens_received") > 0)
    )
    .then(pl.lit("BUY"))

    .when(
        # SELL TOKEN FOR SOL
        (pl.col("sol_delta") > 0)
        & (pl.col("tokens_sent") < 0)
    )
    .then(pl.lit("SELL"))

    .when(
        # TOKEN -> TOKEN
        (pl.col("n_non_sol_assets") >= 2)
        & (pl.col("tokens_received") > 0)
        & (pl.col("tokens_sent") < 0)
    )
    .then(pl.lit("SWAP"))

    .otherwise(pl.lit("OTHER"))
    .alias("classification")
)


# ============================================================
# FIND PRIMARY BOUGHT ASSET
# ============================================================

bought_assets = (
    token_flows
    .filter(pl.col("net_amount") > 0)
    .sort([
        "signature",
        "wallet",
        "net_amount",
    ])
    .group_by([
        "signature",
        "wallet",
    ])
    .agg([
        pl.col("asset")
        .last()
        .alias("bought_asset"),

        pl.col("net_amount")
        .last()
        .alias("bought_amount"),
    ])
)


# ============================================================
# FIND PRIMARY SOLD ASSET
# ============================================================

sold_assets = (
    token_flows
    .filter(pl.col("net_amount") < 0)
    .sort([
        "signature",
        "wallet",
        "net_amount",
    ])
    .group_by([
        "signature",
        "wallet",
    ])
    .agg([
        pl.col("asset")
        .first()
        .alias("sold_asset"),

        pl.col("net_amount")
        .first()
        .alias("sold_amount"),
    ])
)


# ============================================================
# ADD ASSET INFORMATION
# ============================================================

result = (
    summary
    .join(
        bought_assets,
        on=["signature", "wallet"],
        how="left",
    )
    .join(
        sold_assets,
        on=["signature", "wallet"],
        how="left",
    )
)


# ============================================================
# TRADE TYPE
# ============================================================

result = result.with_columns(
    pl.when(
        (pl.col("classification") == "BUY")
        & (pl.col("sol_delta") < 0)
    )
    .then(pl.lit("BUY_TOKEN_WITH_SOL"))

    .when(
        (pl.col("classification") == "SELL")
        & (pl.col("sol_delta") > 0)
    )
    .then(pl.lit("SELL_TOKEN_FOR_SOL"))

    .when(
        pl.col("classification") == "SWAP"
    )
    .then(pl.lit("TOKEN_FOR_TOKEN"))

    .otherwise(pl.lit("OTHER"))
    .alias("trade_type")
)


# ============================================================
# FINAL COLUMN ORDER
# ============================================================

result = result.select([
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
])


# ============================================================
# SORT
# ============================================================

result = result.sort([
    "block_timestamp",
    "signature",
    "wallet",
])


# ============================================================
# SAVE
# ============================================================

result.write_parquet(
    OUTPUT_FILE,
    compression="zstd",
)


# ============================================================
# REPORT
# ============================================================

print()
print("=" * 40)
print("CLASSIFICATION RESULTS")
print("=" * 40)
print()

print(
    f"Classified wallet-transactions: "
    f"{len(result):,}"
)

print()
print("Trade types:")
print(
    result
    .group_by("trade_type")
    .len()
    .sort("len", descending=True)
)

print()
print("Classifications:")
print(
    result
    .group_by("classification")
    .len()
    .sort("len", descending=True)
)

print()
print("First 50 classified transactions:")
print(
    result.head(50)
)

print()
print(f"Saved to: {OUTPUT_FILE}")
print()
