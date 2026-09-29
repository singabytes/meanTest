import pyarrow.parquet as pq
import requests


# ============================================================
# CONFIGURATION
# ============================================================

FILE = r"D:\solana\solarchive\txs\2025-11-01\000000000000.parquet"
#FILE = r"D:\solana\solarchive\txs\2025-11-01\chunks_20mb\part_0000.parquet"

MAX_TRANSACTIONS = 100000


# ============================================================
# KNOWN SOLANA TOKENS
# ============================================================

KNOWN_TOKENS = {
    # SOL (wrapped SOL mint; native SOL has no mint)
    "So11111111111111111111111111111111111111112": "SOL",

    # Stablecoins
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo": "PYUSD",

    # Liquid staking tokens
    "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn": "JitoSOL",
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "mSOL",
    "bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1": "bSOL",
    "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj": "stSOL",

    # DeFi / infra
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
    "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R": "RAY",
    "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE": "ORCA",
    "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL": "JTO",
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3": "PYTH",
    "MNDEFzGvMt87ueuHvVU9VcTqsAP5b3fTGPsHuuPA5ey": "MNDE",
    "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4": "JLP",
    "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux": "HNT",
    "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof": "RENDER",
    "85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ": "W",

    # Wrapped assets (Wormhole)
    "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh": "WBTC",
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs": "WETH",

    # Memecoins
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": "WIF",
    "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr": "POPCAT",
    "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5": "MEW",
    "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN": "TRUMP",
    "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump": "FARTCOIN",
    "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv": "PENGU",
    "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU": "SAMO",
}

JUP_SEARCH = "https://api.jup.ag/tokens/v2/search"
API_KEY = None  # optional; free key at https://portal.jup.ag

def load_jupiter_tokens(mints: list[str]) -> dict:
    headers = {"x-api-key": API_KEY} if API_KEY else {}
    out = {}
    for i in range(0, len(mints), 100):
        chunk = mints[i:i + 100]
        r = requests.get(JUP_SEARCH, params={"query": ",".join(chunk)},
                         headers=headers, timeout=15)
        r.raise_for_status()
        for t in r.json():
            out[t["id"]] = {"symbol": t["symbol"], "decimals": t["decimals"]}
    return out

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
            #out = load_jupiter_tokens([mint])
            #symbol = out.get(mint, {}).get('symbol', 'UNKNOWN')
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
    mint = "6GfZAzkpEFQkethdYSe5ca7izdFwBYhYAmsKY2ZT8KqA"
    out = load_jupiter_tokens([mint])
    
    symbol = out.get(mint, {}).get('symbol', 'UNKNOWN')
    print(symbol)