from pumpfun.pump_fun import pf_sell
from configparser import ConfigParser
import os, sys
from solana.rpc.api import Client
from solana.rpc.commitment import Commitment
from solders.keypair import Keypair

config = ConfigParser()
config.read(os.path.join(sys.path[0], 'data', 'config.ini'))
RPC_HTTPS_URL = config.get("DEFAULT", "SOLANA_RPC_URL")
payer_keypair = config.get("DEFAULT", "PRIVATE_KEY")
payer_keypair = Keypair.from_base58_string(payer_keypair)

client = Client(RPC_HTTPS_URL, commitment=Commitment("confirmed"), timeout=30,blockhash_cache=True)

# Sell Example
mint_str = "5syFBzELxeG4TvjBAt5Koq9BKTJeF1jJ679RYy2wpump"
percentage = 100
slippage = 25

pf_sell(client=client, payer_keypair=payer_keypair, mint_str=mint_str, percentage=percentage, slippage=slippage)