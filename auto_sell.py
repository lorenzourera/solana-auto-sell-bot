
    

import requests
from loguru import logger
import json
from solana.rpc.api import Client
from solana.rpc.commitment import Commitment
from solders.keypair import Keypair
import sys
from configparser import ConfigParser
import base58, logging,time, re, os,sys, json
from raydium.Raydium import *


def get_assets_by_owner(RPC_URL, wallet_address):
    logger.info("Checking Wallet for New Tokens")
    payload = {
        "jsonrpc": "2.0",
        "id": "my-id",
        "method": "getAssetsByOwner",
        "params": {
            "ownerAddress": wallet_address,
            "page": 1,  # Starts at 1
            "limit": 1000,
            "displayOptions": {
                "showFungible": True
            }
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(RPC_URL, headers=headers, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        if "result" in data:
            assets = data["result"]["items"]
            spl_tokens = []
            for asset in assets:
                interface_type = asset.get("interface", "")
                if interface_type == "V1_NFT":
                    continue  # Skip NFT assets
                token_info = asset.get("token_info", {})
                balance = token_info.get("balance", None)
                if balance and float(balance) > 0:
                    spl_tokens.append({
                        "id": asset["id"],
                        "symbol": token_info.get("symbol", ""),
                        "balance": balance,
                        "token_info": token_info
                    })
            for token in spl_tokens:
                logger.info("Token ID: {}", token["id"])
                logger.info("Symbol: {}", token["symbol"])
                logger.info("Balance: {}", token["balance"])
                logger.info("Metadata: {}", token["token_info"])
        else:
            logger.error("No result found in response")
    else:
        logger.error("Error: {}, {}", response.status_code, response.text)
        
        
    logger.info(f"Current SPL Tokens {spl_tokens}")
    return spl_tokens


def write_wallet_tokens(tokens):
    if not tokens:
        return
    
    current_time = int(time.time())
    
    # Load existing data from the JSON file
    try:
        with open("data/wallet_tokens.json", "r") as file:
            existing_tokens = json.load(file)
    except FileNotFoundError:
        existing_tokens = []

    # Filter out existing tokens and add new tokens using list comprehensions
    new_tokens = [
        {
            "symbol": token.get("token_info", {}).get("symbol", ""),
            "token_id": token.get("id"),
            "balance": token.get("token_info", {}).get("balance", ""),
            "detection_time": current_time
        }
        for token in tokens
        if not any(existing_token.get("token_id") == token.get("id") for existing_token in existing_tokens)
    ]

    # Append new tokens to the existing data
    existing_tokens.extend(new_tokens)

    # Write the updated data back to the JSON file
    with open("data/wallet_tokens.json", "w") as file:
        json.dump(existing_tokens, file, indent=4)

def detect_old_tokens(json_file, threshold_seconds):
    current_time = int(time.time())

    try:
        with open(json_file, "r") as file:
            existing_tokens = json.load(file)
    except FileNotFoundError:
        existing_tokens = []

    # Use a list comprehension to filter old tokens
    old_tokens = [
        token for token in existing_tokens
        if current_time - token.get("detection_time", 0) > threshold_seconds
    ]

    return old_tokens


def remove_token_from_json(token_id):
    json_file = "data/wallet_tokens.json"
    
    try:
        # Load existing data from the JSON file
        with open(json_file, "r") as file:
            existing_tokens = json.load(file)
    except FileNotFoundError:
        # If the file doesn't exist, there's nothing to remove
        return

    # Filter out the token to be removed
    updated_tokens = [token for token in existing_tokens if token.get("token_id") != token_id]

    # Write the updated data back to the JSON file
    with open(json_file, "w") as file:
        json.dump(updated_tokens, file, indent=4)


def main():
    
    # Load Configs
    config = ConfigParser()
    config.read(os.path.join(sys.path[0], 'data', 'config.ini'))
    
    # Infura settings - register at infura and get your mainnet url.
    RPC_HTTPS_URL = config.get("DEFAULT", "SOLANA_RPC_URL")
    # Wallet Address
    wallet_address = config.get("DEFAULT", "WALLET_ADDRESS")
    # Wallets private key
    private_key = config.get("DEFAULT", "PRIVATE_KEY")
    # Time to Hold
    threshold_seconds = int(config.get("DEFAULT", "X_SECONDS"))
    
    ctx = Client(RPC_HTTPS_URL, commitment=Commitment("confirmed"), timeout=30,blockhash_cache=True)
    payer = Keypair.from_bytes(base58.b58decode(private_key))
    
    while True:
        spl_tokens = get_assets_by_owner(RPC_URL=RPC_HTTPS_URL, wallet_address=wallet_address)
        write_wallet_tokens(spl_tokens)

        # Detect and process old tokens
        
        old_tokens = detect_old_tokens("data/wallet_tokens.json", threshold_seconds)
        for token in old_tokens:
            logger.info(f"Detected old token: {token}. Selling now.")
            raydium_swap(ctx=ctx, payer=payer, desired_token_address=token['token_id'])
            remove_token_from_json(token_id=token['token_id'])
            

        # Pause for some time before the next iteration
        time.sleep(1)  # 1 minute

if __name__ == "__main__":
    main()
