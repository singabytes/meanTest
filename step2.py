import polars as pl

FILE = r"D:\New folder (2)\meanTest\wallet_ledger.parquet"

df = pl.read_parquet(FILE)

# ============================================================
# 1. Remove obvious system/program addresses
# ============================================================

SYSTEM_ADDRESSES = {
    "11111111111111111111111111111111",
    "Sysvar1111111111111111111111111111111111111",
    "Stake11111111111111111111111111111111111111",
    "Vote111111111111111111111111111111111111111",
}

df = df.filter(
    ~pl.col("wallet").is_in(list(SYSTEM_ADDRESSES))
)


# ============================================================
# 2. Aggregate movements by transaction + wallet + asset
# ============================================================

movements = (
    df
    .group_by([
        "signature",
        "block_timestamp",
        "wallet",
        "mint",
        "decimals",
        "asset_type",
    ])
    .agg(
        pl.col("delta").sum().alias("delta")
    )
    .filter(
        pl.col("delta").abs() > 1e-12
    )
)


# ============================================================
# 3. Number of different assets involved
# ============================================================

tx_summary = (
    movements
    .group_by([
        "signature",
        "block_timestamp",
        "wallet",
    ])
    .agg([
        pl.len().alias("n_assets"),

        (
            (pl.col("delta") > 0)
            .sum()
        ).alias("n_in"),

        (
            (pl.col("delta") < 0)
            .sum()
        ).alias("n_out"),
    ])
)


# ============================================================
# 4. Candidate swaps
#
# A basic swap normally has:
#
#       >= 1 asset leaving
#       >= 1 asset entering
#
# ============================================================

candidate_swaps = (
    tx_summary
    .filter(
        (pl.col("n_in") >= 1)
        &
        (pl.col("n_out") >= 1)
    )
)


# ============================================================
# 5. Join movements back to candidates
# ============================================================

swap_movements = (
    movements
    .join(
        candidate_swaps.select([
            "signature",
            "wallet",
        ]),
        on=[
            "signature",
            "wallet",
        ],
        how="inner",
    )
    .sort([
        "block_timestamp",
        "signature",
        "wallet",
    ])
)


# ============================================================
# 6. Save
# ============================================================

candidate_swaps.write_parquet(
    "candidate_swaps.parquet"
)

swap_movements.write_parquet(
    "swap_movements.parquet"
)


# ============================================================
# 7. Diagnostics
# ============================================================

print()
print("========================================")
print("STEP 2 - CANDIDATE SWAPS")
print("========================================")

print()

print(
    "Candidate swap wallet-transactions:",
    candidate_swaps.height
)

print(
    "Wallets involved:",
    candidate_swaps["wallet"].n_unique()
)

print(
    "Transactions involved:",
    candidate_swaps["signature"].n_unique()
)

print()

print("Asset-count distribution:")
print(
    candidate_swaps
    .group_by("n_assets")
    .len()
    .sort("n_assets")
)

print()

print("First candidate swaps:")
print(
    swap_movements.head(50)
)