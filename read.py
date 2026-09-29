import pyarrow.parquet as pq


# ============================================================
# CONFIGURATION
# ============================================================

FILE = r"D:\solana\solarchive\txs\2025-11-01\000000000000.parquet"
#FILE = r"D:\solana\solarchive\txs\2025-11-01\chunks_20mb\part_0000.parquet"

MAX_TRANSACTIONS = 1000000


# ============================================================
# KNOWN SOLANA TOKENS
# ============================================================

KNOWN_TOKENS = {

    # Native SOL is not normally represented by a mint in
    # token balances, but useful to have here.
    "So11111111111111111111111111111111111111112": "SOL",

    # Wrapped SOL
    "So11111111111111111111111111111111111111112": "SOL",

    # USDC
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",

    # USDT
    "Es9vMFrzaCERmJfrF4H2FYD4Gf4W9h8JfYw7YQ7K4k7": "USDT",
}


def token_name(mint):
    """
    Convert a known mint address into a symbol.
    Unknown tokens are displayed as UNKNOWN.
    """

    return KNOWN_TOKENS.get(mint, "UNKNOWN")


# ============================================================
# SIGNERS
# ============================================================

def get_signers(accounts):

    if not accounts:
        return []

    return [
        account["pubkey"]
        for account in accounts
        if account["signer"]
    ]


# ============================================================
# TOKEN BALANCE CHANGES
# ============================================================

def get_token_changes(pre_balances, post_balances):

    pre = {}
    post = {}

    for item in pre_balances or []:

        key = (
            item["account_index"],
            item["mint"],
            item["owner"],
        )

        pre[key] = item

    for item in post_balances or []:

        key = (
            item["account_index"],
            item["mint"],
            item["owner"],
        )

        post[key] = item

    changes = []

    for key in set(pre) | set(post):

        before_item = pre.get(key)
        after_item = post.get(key)

        before_raw = (
            before_item["amount"]
            if before_item is not None
            else None
        )

        after_raw = (
            after_item["amount"]
            if after_item is not None
            else None
        )

        # Ignore entries where both are unavailable
        if before_raw is None and after_raw is None:
            continue

        before = 0 if before_raw is None else before_raw
        after = 0 if after_raw is None else after_raw

        delta = after - before

        if delta == 0:
            continue

        item = after_item or before_item

        changes.append({
            "account_index": key[0],
            "mint": key[1],
            "owner": key[2],
            "decimals": item["decimals"],
            "before": before,
            "after": after,
            "delta": delta,
        })

    return changes


# ============================================================
# SOL BALANCE CHANGES
# ============================================================

def get_sol_changes(balance_changes):

    changes = []

    for item in balance_changes or []:

        before = item["before"]
        after = item["after"]

        if before is None or after is None:
            continue

        delta = after - before

        if delta == 0:
            continue

        changes.append({
            "account": item["account"],
            "before": before,
            "after": after,
            "delta": delta,
        })

    return changes


# ============================================================
# PRINT TRANSACTION
# ============================================================

def print_transaction(row, number):

    print()
    print("=" * 100)
    print(f"TRANSACTION #{number}")
    print("=" * 100)

    print("Time      :", row["block_timestamp"])
    print("Slot      :", row["block_slot"])
    print("Index     :", row["index"])
    print("Signature :", row["signature"])
    print("Status    :", row["status"])
    print("Fee       :", row["fee"], "lamports")

    if row["err"]:
        print("Error     :", row["err"])

    # --------------------------------------------------------
    # SIGNER
    # --------------------------------------------------------

    signers = get_signers(row["accounts"])

    print()
    print("-" * 100)
    print("WALLET")
    print("-" * 100)

    if signers:

        for signer in signers:
            print(signer)

    else:
        print("No signer")

    # --------------------------------------------------------
    # TOKEN CHANGES
    # --------------------------------------------------------

    token_changes = get_token_changes(
        row["pre_token_balances"],
        row["post_token_balances"]
    )

    print()
    print("-" * 100)
    print("TOKEN CHANGES")
    print("-" * 100)

    if not token_changes:

        print("No token changes")

    else:

        for change in token_changes:

            mint = change["mint"]
            symbol = token_name(mint)

            decimals = change["decimals"]

            before = change["before"] / (10 ** decimals)
            after = change["after"] / (10 ** decimals)
            delta = change["delta"] / (10 ** decimals)

            if delta > 0:
                direction = "BUY / RECEIVE"
            else:
                direction = "SELL / SEND"

            print()
            print("Direction     :", direction)
            print("Token         :", symbol)
            print("Mint          :", mint)
            print("Amount change :", f"{delta:+,.9f}")
            print("Before        :", f"{before:,.9f}")
            print("After         :", f"{after:,.9f}")
            print("Owner         :", change["owner"])
            print(
                "Account index :",
                change["account_index"]
            )

    # --------------------------------------------------------
    # SOL CHANGES
    # --------------------------------------------------------

    sol_changes = get_sol_changes(
        row["balance_changes"]
    )

    print()
    print("-" * 100)
    print("SOL BALANCE CHANGES")
    print("-" * 100)

    if sol_changes:

        for change in sol_changes:

            delta_sol = change["delta"] / 1_000_000_000

            print()
            print("Account :", change["account"])
            print(
                "Change  :",
                f"{delta_sol:+.9f}",
                "SOL"
            )

    else:

        print("No SOL balance changes")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print("SOLARCHIVE TOKEN TRANSACTION ANALYZER")
    print("=" * 100)

    print()
    print("File:")
    print(FILE)

    pf = pq.ParquetFile(FILE)

    print()
    print("Rows       :", pf.metadata.num_rows)
    print("Row groups :", pf.num_row_groups)

    transaction_count = 0

    for batch in pf.iter_batches(batch_size=1000):

        rows = batch.to_pylist()

        for row in rows:

            # Only successful transactions
            if row["status"] != "Success":
                continue

            token_changes = get_token_changes(
                row["pre_token_balances"],
                row["post_token_balances"]
            )

            # Ignore transactions with no token movement
            if not token_changes:
                continue

            transaction_count += 1

            print_transaction(
                row,
                transaction_count
            )

            if transaction_count >= MAX_TRANSACTIONS:
                break

        if transaction_count >= MAX_TRANSACTIONS:
            break

    print()
    print("=" * 100)
    print("FINISHED")
    print("=" * 100)

    print(
        "Transactions displayed:",
        transaction_count
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()