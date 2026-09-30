import polars as pl

FILE = r"D:\New folder (2)\meanTest\part_0000.parquet"
FILE2 = r"D:\New folder (2)\meanTest\wallet_ledger.parquet"

df = pl.read_parquet(FILE)

# Candidate signatures from Step 2
candidates = pl.read_parquet(FILE2)

# Take first 5 distinct transactions
signatures = (
    candidates
    .select("signature")
    .unique()
    .head(5)
    ["signature"]
    .to_list()
)

print("Inspecting:")
print(signatures)

print("\n" + "=" * 100)

for sig in signatures:

    row = (
        df
        .filter(pl.col("signature") == sig)
        .to_dicts()
    )

    if not row:
        continue

    tx = row[0]

    print("\n")
    print("=" * 100)
    print("SIGNATURE")
    print(sig)

    print("\nTIMESTAMP")
    print(tx["block_timestamp"])

    print("\nSTATUS")
    print(tx["status"])

    print("\nERROR")
    print(tx["err"])

    print("\nFEE")
    print(tx["fee"])

    print("\nACCOUNTS")
    for account in tx["accounts"]:
        print(account)

    print("\nLOG MESSAGES")
    for msg in tx["log_messages"]:
        print(msg)

    print("\nBALANCE CHANGES")
    for x in tx["balance_changes"]:
        print(x)

    print("\nPRE TOKEN BALANCES")
    for x in tx["pre_token_balances"]:
        print(x)

    print("\nPOST TOKEN BALANCES")
    for x in tx["post_token_balances"]:
        print(x)