import polars as pl

df = pl.read_parquet(r"D:\New folder (2)\meanTest\part_0000.parquet")

print(df.schema)
print(df.head())
print(df.shape)

'''
You have:

block_timestamp → transaction time
signature → transaction ID
accounts → accounts involved
balance_changes → SOL changes
pre_token_balances → token balances before
post_token_balances → token balances after
fee → transaction fee
mint → token contract
owner → wallet owning the token account
decimals → token precision
'''