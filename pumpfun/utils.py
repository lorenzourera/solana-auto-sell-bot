import json
import time
from solana.rpc.commitment import Processed, Confirmed
from solana.rpc.types import TokenAccountOpts
from solana.transaction import Signature
from solders.pubkey import Pubkey  # type: ignore
from pumpfun.coin_data import get_coin_data
import time
from loguru import logger 
import requests
# from configparser import ConfigParser
# import os, sys

# config = ConfigParser()
# config.read(os.path.join(sys.path[0], 'data', 'config.ini'))
# PAYER_KEYPAIR = config.get("DEFAULT", "PRIVATE_KEY") 



def get_token_balance(client, payer_keypair, mint_str: str) -> float | None:
    try:
        mint = Pubkey.from_string(mint_str)
        # for debugging
        logger.info(f'mint {mint}')
        logger.info(f'payer pubkey {payer_keypair.pubkey()}')
        response = client.get_token_accounts_by_owner_json_parsed(
            payer_keypair.pubkey(),
            TokenAccountOpts(mint=mint),
            commitment=Processed
        )
        # logger.info(f'response {response}')
        accounts = response.value
        # logger.info(f'accounts {accounts}')
        if accounts:
            token_amount = accounts[0].account.data.parsed['info']['tokenAmount']['uiAmount']
            return float(token_amount)

        
    except Exception as e:
        logger.error(f"Error fetching token balance: {e}")
        return None

def confirm_txn(client, txn_sig: Signature, max_retries: int = 20, retry_interval: int = 3) -> bool:
    retries = 1
    
    while retries < max_retries:
        try:
            txn_res = client.get_transaction(txn_sig, encoding="json", commitment=Confirmed, max_supported_transaction_version=0)
            txn_json = json.loads(txn_res.value.transaction.meta.to_json())
            
            if txn_json['err'] is None:
                logger.info("Transaction confirmed... try count:", retries)
                return True
            
            logger.warning("Error: Transaction not confirmed. Retrying...")
            if txn_json['err']:
                logger.error("Transaction failed.")
                return False
        except Exception as e:
            logger.error("Awaiting confirmation... try count:", retries)
            retries += 1
            time.sleep(retry_interval)
    
    logger.info("Max retries reached. Transaction confirmation failed.")
    return None

def get_token_price(mint_str: str) -> float:
    try:
        coin_data = get_coin_data(mint_str)
        
        if not coin_data:
            logger.info("Failed to retrieve coin data...")
            return None
        
        virtual_sol_reserves = coin_data.virtual_sol_reserves / 10**9
        virtual_token_reserves = coin_data.virtual_token_reserves / 10**6

        token_price = virtual_sol_reserves / virtual_token_reserves
        logger.info(f"Token Price: {token_price:.20f} SOL")
        
        return token_price

    except Exception as e:
        logger.info(f"Error calculating token price: {e}")
        return None


def is_tradeable_on_pumpfun(token_address):
    try:
        # PumpFun uses a specific API endpoint to check token status
        response = requests.get(f"https://api.pump.fun/token/{token_address}")
        if response.status_code == 200:
            data = response.json()
            # Check if the token has active liquidity or is listed
            return data.get('is_active', False) and data.get('liquidity', 0) > 0
    except Exception as e:
        logger.error(f"Error checking PumpFun tradability: {e}")
    return False