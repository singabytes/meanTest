from huggingface_hub import snapshot_download

local_dir = snapshot_download(
    repo_id="solarchive/solarchive",
    repo_type="dataset",
    allow_patterns="txs/2025-11-01/*.parquet",
    local_dir=r"D:\solana\solarchive"
)

print(f"Downloaded to: {local_dir}")