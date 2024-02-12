from raydium.sell_swap import sell
from dexscreener import get_price, getSymbol
import time
from loguru import logger

def raydium_swap(ctx, payer, desired_token_address):
      
    token_symbol, SOl_Symbol = getSymbol(desired_token_address)
    logger.info(f"Raydium - Selling token {token_symbol} CA {desired_token_address}")
    bought_token_curr_price = get_price(desired_token_address)
    
    start_time = time.time()
    txS = sell(solana_client=ctx, TOKEN_TO_SWAP_SELL=desired_token_address, payer=payer, token_symbol=token_symbol, S0l_Symbol=SOl_Symbol)
    end_time = time.time()
    execution_time = end_time - start_time
    logger.info(f"Total Sell Execution time: {execution_time} seconds")

    if str(txS) != 'failed':
        txS =  str(txS)   
        logger.info("-" * 79)
        logger.info(f"| {'Sold Price':<15} | {'Tx Sell':<40} |")
        logger.info("-" * 79)
