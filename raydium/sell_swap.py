from spl.token.instructions import close_account, CloseAccountParams
from solana.rpc.types import TokenAccountOpts
from solana.rpc.api import RPCException
from solana.transaction import Transaction
from solders.pubkey import Pubkey
from raydium.create_close_account import  fetch_pool_keys, sell_get_token_account,get_token_account, make_swap_instruction
from loguru import logger
import time


LAMPORTS_PER_SOL = 1000000000


def sell(solana_client, TOKEN_TO_SWAP_SELL, payer, token_symbol, S0l_Symbol):

    mint = Pubkey.from_string(TOKEN_TO_SWAP_SELL)
    sol = Pubkey.from_string("So11111111111111111111111111111111111111112")

    """Get swap token program id"""
    logger.info("1. Get TOKEN_PROGRAM_ID...")
    TOKEN_PROGRAM_ID = solana_client.get_account_info_json_parsed(mint).value.owner

    """Get Pool Keys"""
    logger.info("2. Get Pool Keys...")
    pool_keys = fetch_pool_keys(str(mint))
    if pool_keys == "failed":
        logger.info(f"a|Sell Pool ERROR {token_symbol}",f"[Raydium]: Pool Key Not Found")
        return "failed"
    
    txnBool = True
    while txnBool:
        """Get Token Balance from wallet"""
        logger.info("3. Get oken Balance from wallet...")

        balanceBool = True
        while balanceBool:
            tokenPk = mint

            accountProgramId = solana_client.get_account_info_json_parsed(tokenPk)
            programid_of_token = accountProgramId.value.owner

            accounts = solana_client.get_token_accounts_by_owner_json_parsed(payer.pubkey(),TokenAccountOpts(program_id=programid_of_token)).value
            for account in accounts:
                mint_in_acc = account.account.data.parsed['info']['mint']
                if mint_in_acc == str(mint):
                    amount_in = int(account.account.data.parsed['info']['tokenAmount']['amount'])
                    logger.info("3.1 Token Balance [Lamports]: ",amount_in)
                    break
            if int(amount_in) > 0:
                balanceBool = False
            else:
                logger.info("No Balance, Retrying...")
                time.sleep(2)

        """Get token accounts"""
        logger.info("4. Get token accounts for swap...")
        swap_token_account = sell_get_token_account(solana_client, payer.pubkey(), mint)
        WSOL_token_account, WSOL_token_account_Instructions = get_token_account(solana_client,payer.pubkey(), sol)
        
        if swap_token_account == None:
            logger.info("swap_token_account not found...")
            return "failed"

        else:
            """Make swap instructions"""
            logger.info("5. Create Swap Instructions...")
            instructions_swap = make_swap_instruction(  amount_in, 
                                                        swap_token_account,
                                                        WSOL_token_account,
                                                        pool_keys, 
                                                        mint, 
                                                        solana_client,
                                                        payer
                                                    )

            """Close wsol account"""
            logger.info("6.  Create Instructions to Close WSOL account...")
            params = CloseAccountParams(account=WSOL_token_account, dest=payer.pubkey(), owner=payer.pubkey(), program_id=TOKEN_PROGRAM_ID)
            closeAcc =(close_account(params))

            """Create transaction and add instructions"""
            logger.info("7. Create transaction and add instructions to Close WSOL account...")
            swap_tx = Transaction()
            signers = [payer]
            if WSOL_token_account_Instructions != None:
                swap_tx.add(WSOL_token_account_Instructions)
            swap_tx.add(instructions_swap)
            swap_tx.add(closeAcc)

            """Send transaction"""
            try:
                logger.info("8. Execute Transaction...")
                start_time = time.time()
                txn = solana_client.send_transaction(swap_tx, *signers)

                """Confirm it has been sent"""
                txid_string_sig = txn.value
                logger.info("9. Confirm it has been sent...")
                checkTxn = True
                while checkTxn:
                    try:
                        status = solana_client.get_transaction(txid_string_sig,"json")
                        FeesUsed = (status.value.transaction.meta.fee) / 1000000000
                        if status.value.transaction.meta.err == None:
                            logger.info("[create_account] Transaction Success",txn.value)
                            logger.info(f"[create_account] Transaction Fees: {FeesUsed:.10f} SOL")

                            end_time = time.time()
                            execution_time = end_time - start_time
                            logger.info(f"Execution time: {execution_time} seconds")

                            txnBool = False
                            checkTxn = False
                            return txid_string_sig
                        else:

                            logger.info("Transaction Failed")

                            end_time = time.time()
                            execution_time = end_time - start_time
                            logger.info(f"Execution time: {execution_time} seconds")

                            checkTxn = False

                    except Exception as e:
                        logger.info(f"e|Sell ERROR {token_symbol}",f"[Raydium]: {e}")

                        logger.info("Sleeping...",e)
                        time.sleep(0.500)
                        logger.info("Retrying...")

            except RPCException as e:
                logger.info(f"Error: [{e.args[0].message}]...\nRetrying...")
                logger.info(f"e|SELL ERROR {token_symbol}",f"[Raydium]: {e.args[0].message}")

            except Exception as e:
                logger.info(f"Error: [{e}]...\nEnd...")
                logger.info(f"e|SELL Exception ERROR {token_symbol}",f"[Raydium]: {e.args[0].message}")
                txnBool = False
                return "failed"
