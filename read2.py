"""
Solarchive swap analyzer.

For each successful transaction, look at the FEE PAYER (first signer) and work
out what that wallet actually gave up and received:

    SELL  token -> SOL
    BUY   SOL   -> token
    SWAP  token -> token
    TRANSFER  tokens moved with no SOL going the other way

Outputs:
  - swaps.csv         one row per wallet trade
  - console summary   most traded tokens
"""
import csv
import sys
from collections import defaultdict
from decimal import Decimal

FILE = r"D:\solana\solarchive\txs\2025-11-01\000000000000.parquet"
OUTPUT_CSV = "swaps.csv"
MAX_TRADES = 5000          # stop after this many trades
TOP_N = 25                 # rows in the summary
DUST_SOL = Decimal("0.00001")

WSOL = "So11111111111111111111111111111111111111112"

# Paste your full KNOWN_TOKENS dict from read.py here.
KNOWN_TOKENS = {
    WSOL: "SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
}

JUP_SEARCH = "https://api.jup.ag/tokens/v2/search"
JUP_API_KEY = None  # optional, https://portal.jup.ag

COLUMNS = [
    "block_timestamp", "signature", "status", "fee", "accounts",
    "pre_token_balances", "post_token_balances", "balance_changes",
]


# ------------------------------------------------------------
# Amount helpers (Decimal, so no floating-point noise)
# ------------------------------------------------------------

def to_ui(raw, decimals):
    return Decimal(int(raw)).scaleb(-decimals)


# ------------------------------------------------------------
# Per-wallet deltas
# ------------------------------------------------------------

def token_deltas(wallet, pre, post):
    """Net change per mint for token accounts owned by `wallet`."""
    before, after, decimals = {}, {}, {}

    for item in pre or []:
        if item["owner"] == wallet:
            key = (item["account_index"], item["mint"])
            before[key] = int(item["amount"] or 0)
            decimals[item["mint"]] = item["decimals"]

    for item in post or []:
        if item["owner"] == wallet:
            key = (item["account_index"], item["mint"])
            after[key] = int(item["amount"] or 0)
            decimals[item["mint"]] = item["decimals"]

    deltas = defaultdict(Decimal)
    for key in set(before) | set(after):
        raw = after.get(key, 0) - before.get(key, 0)
        if raw:
            mint = key[1]
            deltas[mint] += to_ui(raw, decimals[mint])
    return deltas


def native_sol_delta(wallet, balance_changes, fee):
    """Native SOL change for the wallet, with the network fee added back."""
    total = 0
    for item in balance_changes or []:
        if item["account"] == wallet and item["before"] is not None \
                and item["after"] is not None:
            total += item["after"] - item["before"]
    total += int(fee or 0)
    return Decimal(total).scaleb(-9)


# ------------------------------------------------------------
# Classify one transaction
# ------------------------------------------------------------

def analyze(row):
    if row["status"] != "Success":
        return None

    signers = [a["pubkey"] for a in (row["accounts"] or []) if a["signer"]]
    if not signers:
        return None
    wallet = signers[0]  # fee payer

    deltas = token_deltas(wallet, row["pre_token_balances"],
                          row["post_token_balances"])

    # wrapped SOL + native SOL together = the wallet's real SOL movement
    sol = native_sol_delta(wallet, row["balance_changes"], row["fee"])
    sol += deltas.pop(WSOL, Decimal(0))

    sold = {m: -d for m, d in deltas.items() if d < 0}
    bought = {m: d for m, d in deltas.items() if d > 0}

    if not sold and not bought:
        return None

    if bought and sold:
        side = "SWAP"
    elif sold and sol > DUST_SOL:
        side = "SELL"
    elif bought and sol < -DUST_SOL:
        side = "BUY"
    else:
        side = "TRANSFER"

    return {
        "time": row["block_timestamp"],
        "signature": row["signature"],
        "wallet": wallet,
        "side": side,
        "sold": sold,
        "bought": bought,
        "sol": sol,
    }


# ------------------------------------------------------------
# Symbols
# ------------------------------------------------------------

def resolve_symbols(mints):
    symbols = {m: KNOWN_TOKENS[m] for m in mints if m in KNOWN_TOKENS}
    todo = [m for m in mints if m not in symbols]
    if todo:
        import requests
        headers = {"x-api-key": JUP_API_KEY} if JUP_API_KEY else {}
        for i in range(0, len(todo), 100):
            chunk = todo[i:i + 100]
            try:
                r = requests.get(JUP_SEARCH, params={"query": ",".join(chunk)},
                                 headers=headers, timeout=15)
                r.raise_for_status()
                for t in r.json():
                    if t.get("id") in chunk:
                        symbols[t["id"]] = t["symbol"]
            except Exception as e:
                print(f"Jupiter lookup failed for a batch: {e}", file=sys.stderr)
    return symbols


def label(mint, symbols):
    short = f"{mint[:4]}…{mint[-4:]}"
    return f"{symbols.get(mint, 'UNKNOWN')} ({short})"


def fmt_side(items, symbols):
    return "; ".join(f"{amt:,f} {label(m, symbols)}" for m, amt in items.items())


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(FILE)
    print(f"Rows: {pf.metadata.num_rows:,}")

    trades = []
    scanned = 0
    for batch in pf.iter_batches(batch_size=1000, columns=COLUMNS):
        for row in batch.to_pylist():
            scanned += 1
            trade = analyze(row)
            if trade:
                trades.append(trade)
                if len(trades) >= MAX_TRADES:
                    break
        if len(trades) >= MAX_TRADES:
            break

    print(f"Scanned {scanned:,} transactions, found {len(trades):,} wallet trades")

    all_mints = {m for t in trades for m in list(t["sold"]) + list(t["bought"])}
    symbols = resolve_symbols(sorted(all_mints))

    # ---- CSV ----
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "wallet", "side", "sold", "bought",
                    "net_sol", "signature"])
        for t in trades:
            w.writerow([t["time"], t["wallet"], t["side"],
                        fmt_side(t["sold"], symbols),
                        fmt_side(t["bought"], symbols),
                        f"{t['sol']:f}", t["signature"]])
    print(f"Wrote {OUTPUT_CSV}")

    # ---- Summary per token ----
    stats = defaultdict(lambda: {"buys": 0, "sells": 0, "wallets": set(),
                                 "sol_in": Decimal(0), "sol_out": Decimal(0)})
    for t in trades:
        for m in t["bought"]:
            s = stats[m]
            s["buys"] += 1
            s["wallets"].add(t["wallet"])
            if t["side"] == "BUY":
                s["sol_out"] += -t["sol"]      # SOL wallets spent buying
        for m in t["sold"]:
            s = stats[m]
            s["sells"] += 1
            s["wallets"].add(t["wallet"])
            if t["side"] == "SELL":
                s["sol_in"] += t["sol"]        # SOL wallets received selling

    ranked = sorted(stats.items(),
                    key=lambda kv: kv[1]["buys"] + kv[1]["sells"],
                    reverse=True)[:TOP_N]

    print()
    print(f"{'TOKEN':<26}{'BUYS':>7}{'SELLS':>7}{'WALLETS':>9}"
          f"{'SOL SPENT':>12}{'SOL RECV':>12}")
    for mint, s in ranked:
        print(f"{label(mint, symbols):<26}{s['buys']:>7}{s['sells']:>7}"
              f"{len(s['wallets']):>9}{s['sol_out']:>12.3f}{s['sol_in']:>12.3f}")


if __name__ == "__main__":
    main()