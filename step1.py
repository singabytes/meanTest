import polars as pl

FILE = r"D:\New folder (2)\meanTest\part_0000.parquet"

df = pl.read_parquet(FILE)
df = df.filter(pl.col("status") == "Success")

# ============================================================
# COMMON SCHEMA
# ============================================================

COLUMNS = [
    "block_timestamp",
    "signature",
    "wallet",
    "mint",
    "delta",
    "decimals",
    "asset_type",
]


# ============================================================
# 1. SOL
# ============================================================

sol = (
    df
    .select([
        "block_timestamp",
        "signature",
        "balance_changes",
    ])
    .explode("balance_changes", empty_as_null=True)
    .unnest("balance_changes")
    .rename({
        "account": "wallet",
        "before": "before_lamports",
        "after": "after_lamports",
    })
    .with_columns([
        (
            (
                pl.col("after_lamports").cast(pl.Float64)
                -
                pl.col("before_lamports").cast(pl.Float64)
            )
            / 1_000_000_000.0
        ).cast(pl.Float64).alias("delta"),

        pl.lit("SOL").cast(pl.String).alias("mint"),

        pl.lit(9).cast(pl.Int64).alias("decimals"),

        pl.lit("SOL").cast(pl.String).alias("asset_type"),
    ])
    .select(COLUMNS)
)


# ============================================================
# 2. SPL PRE
# ============================================================

pre = (
    df
    .select([
        "block_timestamp",
        "signature",
        "pre_token_balances",
    ])
    .explode("pre_token_balances", empty_as_null=True)
    .unnest("pre_token_balances")
    .rename({
        "owner": "wallet",
        "amount": "amount",
    })
    .with_columns([
        (
            -pl.col("amount").cast(pl.Float64)
            /
            (
                10.0
                **
                pl.col("decimals").cast(pl.Int64)
            )
        ).cast(pl.Float64).alias("delta"),

        pl.col("decimals")
          .cast(pl.Int64),

        pl.lit("SPL").cast(pl.String)
          .alias("asset_type"),
    ])
    .select(COLUMNS)
)


# ============================================================
# 3. SPL POST
# ============================================================

post = (
    df
    .select([
        "block_timestamp",
        "signature",
        "post_token_balances",
    ])
    .explode("post_token_balances", empty_as_null=True)
    .unnest("post_token_balances")
    .rename({
        "owner": "wallet",
        "amount": "amount",
    })
    .with_columns([
        (
            pl.col("amount").cast(pl.Float64)
            /
            (
                10.0
                **
                pl.col("decimals").cast(pl.Int64)
            )
        ).cast(pl.Float64).alias("delta"),

        pl.col("decimals")
          .cast(pl.Int64),

        pl.lit("SPL").cast(pl.String)
          .alias("asset_type"),
    ])
    .select(COLUMNS)
)


# ============================================================
# 4. COMBINE PRE + POST
# ============================================================

tokens = pl.concat(
    [pre, post],
    how="vertical",
)


# ============================================================
# 5. NET TOKEN MOVEMENTS
# ============================================================

tokens = (
    tokens
    .group_by([
        "block_timestamp",
        "signature",
        "wallet",
        "mint",
        "decimals",
        "asset_type",
    ])
    .agg(
        pl.col("delta").sum().cast(pl.Float64).alias("delta")
    )
    .select(COLUMNS)
)


# ============================================================
# 6. FINAL TYPE NORMALIZATION
# ============================================================

sol = sol.with_columns([
    pl.col("delta").cast(pl.Float64),
    pl.col("decimals").cast(pl.Int64),
])

tokens = tokens.with_columns([
    pl.col("delta").cast(pl.Float64),
    pl.col("decimals").cast(pl.Int64),
])


# ============================================================
# 7. COMBINE SOL + SPL
# ============================================================

ledger = pl.concat(
    [sol, tokens],
    how="vertical",
)


# ============================================================
# 8. REMOVE INVALID / ZERO MOVEMENTS
# ============================================================

ledger = (
    ledger
    .filter(
        pl.col("wallet").is_not_null()
        &
        pl.col("signature").is_not_null()
        &
        pl.col("mint").is_not_null()
        &
        (pl.col("delta") != 0)
    )
    .sort([
        "wallet",
        "block_timestamp",
    ])
)


# ============================================================
# 9. SAVE
# ============================================================

ledger.write_parquet(
    "wallet_ledger.parquet"
)


# ============================================================
# 10. DIAGNOSTICS
# ============================================================

print()
print("========================================")
print("WALLET LEDGER")
print("========================================")

print()
print("Rows:", ledger.height)
print("Wallets:", ledger["wallet"].n_unique())
print("Assets:", ledger["mint"].n_unique())

print()
print("Schema:")
print(ledger.schema)

print()
print("Null counts:")
print(
    ledger.select([
        pl.col("block_timestamp").is_null().sum().alias("timestamp"),
        pl.col("signature").is_null().sum().alias("signature"),
        pl.col("wallet").is_null().sum().alias("wallet"),
        pl.col("mint").is_null().sum().alias("mint"),
        pl.col("delta").is_null().sum().alias("delta"),
    ])
)

print()
print("Asset types:")
print(
    ledger
    .group_by("asset_type")
    .len()
)

print()
print("Largest assets:")
print(
    ledger
    .group_by("mint")
    .len()
    .sort("len", descending=True)
    .head(20)
)

print()
print("First 30 rows:")
print(
    ledger.head(30)
)