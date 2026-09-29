"""
Read mint addresses from mints.txt (one per line) and write tokens.csv
with columns: mint, token, decimals

Lookup order per mint:
  1. Hardcoded overrides (SOL, USDC, USDT)
  2. Jupiter Tokens API v2
  3. On-chain: getTokenSupply for decimals, Metaplex metadata for symbol
"""
import base64
import csv
import struct
import sys

import requests
from solders.pubkey import Pubkey  # pip install solders

INPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "mints.txt"
OUTPUT_FILE = sys.argv[2] if len(sys.argv) > 2 else "tokens.csv"

RPC_URL = "https://api.mainnet-beta.solana.com"  # use your own RPC for heavy use
JUP_SEARCH = "https://api.jup.ag/tokens/v2/search"
JUP_API_KEY = None  # optional, from https://portal.jup.ag

META_PROGRAM = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")

OVERRIDES = {
    "So11111111111111111111111111111111111111112": ("SOL", 9),
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": ("USDC", 6),
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": ("USDT", 6),
}


def read_mints(path):
    seen, mints = set(), []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = line.strip()
            if m and m not in seen:
                seen.add(m)
                mints.append(m)
    return mints


def jupiter_lookup(mints):
    headers = {"x-api-key": JUP_API_KEY} if JUP_API_KEY else {}
    out = {}
    for i in range(0, len(mints), 100):
        chunk = mints[i:i + 100]
        try:
            r = requests.get(JUP_SEARCH, params={"query": ",".join(chunk)},
                             headers=headers, timeout=15)
            r.raise_for_status()
            for t in r.json():
                mint = t.get("id") or t.get("address")
                if mint in chunk:
                    out[mint] = (t.get("symbol"), t.get("decimals"))
        except (requests.RequestException, ValueError) as e:
            print(f"Jupiter lookup failed: {e}", file=sys.stderr)
    return out


def rpc(method, params):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return requests.post(RPC_URL, json=payload, timeout=15).json()


def onchain_decimals(mint):
    r = rpc("getTokenSupply", [mint])
    if "error" in r:
        return None
    return r["result"]["value"]["decimals"]


def read_string(data, offset):
    (length,) = struct.unpack_from("<I", data, offset)
    offset += 4
    s = data[offset:offset + length].rstrip(b"\x00").decode("utf-8", "replace")
    return s, offset + length


def onchain_symbol(mint):
    mint_pk = Pubkey.from_string(mint)
    pda, _ = Pubkey.find_program_address(
        [b"metadata", bytes(META_PROGRAM), bytes(mint_pk)], META_PROGRAM
    )
    r = rpc("getAccountInfo", [str(pda), {"encoding": "base64"}])
    value = (r.get("result") or {}).get("value")
    if value is None:
        return None
    data = base64.b64decode(value["data"][0])
    offset = 1 + 32 + 32
    _name, offset = read_string(data, offset)
    symbol, _ = read_string(data, offset)
    return symbol or None


def main():
    mints = read_mints(INPUT_FILE)
    results = {m: OVERRIDES[m] for m in mints if m in OVERRIDES}

    todo = [m for m in mints if m not in results]
    jup = jupiter_lookup(todo)

    for m in todo:
        symbol, decimals = jup.get(m, (None, None))
        if decimals is None:
            try:
                decimals = onchain_decimals(m)
            except requests.RequestException:
                pass
        if not symbol:
            try:
                symbol = onchain_symbol(m)
            except Exception:
                pass
        results[m] = (symbol or "UNKNOWN", decimals)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mint", "token", "decimals"])
        for m in mints:
            symbol, decimals = results[m]
            w.writerow([m, symbol, "" if decimals is None else decimals])

    print(f"Wrote {len(mints)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()