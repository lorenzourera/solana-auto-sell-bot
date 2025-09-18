import struct
from solana.rpc.types import TokenAccountOpts, TxOpts
from solana.transaction import AccountMeta
from spl.token.instructions import (
    CloseAccountParams,
    close_account,
    create_associated_token_account,
    get_associated_token_address,
)
from solana.rpc.api import RPCException
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price  # type: ignore
from solders.instruction import Instruction  # type: ignore
from solders.message import MessageV0  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore
from solders.pubkey import Pubkey
from pumpfun.utils import confirm_txn, get_token_balance
from pumpfun.coin_data import get_coin_data
from loguru import logger
import time
from raydium.Raydium import raydium_swap

GLOBAL = Pubkey.from_string("4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf")
FEE_RECIPIENT = Pubkey.from_string("CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM")
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOC_TOKEN_ACC_PROG = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
RENT = Pubkey.from_string("SysvarRent111111111111111111111111111111111")
EVENT_AUTHORITY = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")
PUMP_FUN_PROGRAM = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
PUMP_FUN_FEE_PROGRAM = Pubkey.from_string("pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ")
PUMP_FUN_FEE_CONFIG = Pubkey.from_string("8Wf5TiAheLUqBrKXeYg2JtAFFMWtKdG2BSFgqUcPVwTt")
SOL_DECIMAL = 10**9
UNIT_BUDGET = 100_000
UNIT_PRICE = 1_000_000

def derive_creator_vault(creator: Pubkey) -> Pubkey:
    creator_vault, _ = Pubkey.find_program_address(
        [b"creator-vault", bytes(creator)], PUMP_FUN_PROGRAM
    )
    return creator_vault




def pf_buy(client, payer_keypair, mint_str: str, sol_in: float = 0.01, slippage: int = 15) -> bool:
    try:
        logger.info(f"PF - Starting buy transaction for mint: {mint_str}")

        coin_data = get_coin_data(client=client, mint_str=mint_str)
        
        if not coin_data:
            logger.warning("Failed to retrieve coin data.")
            return False

        if coin_data.complete:
            logger.warning("Warning: This token has bonded and is only tradable on Raydium.")
            logger.info('Initiating swap on raydium')
            raydium_swap(ctx=client, payer=payer_keypair, desired_token_address=mint_str)

            return False

        MINT = coin_data.mint
        BONDING_CURVE = coin_data.bonding_curve
        ASSOCIATED_BONDING_CURVE = coin_data.associated_bonding_curve
        USER = payer_keypair.pubkey()

        logger.info("Fetching or creating associated token account...")
        try:
            ASSOCIATED_USER = client.get_token_accounts_by_owner(USER, TokenAccountOpts(MINT)).value[0].pubkey
            token_account_instruction = None
            logger.info(f"Token account found: {ASSOCIATED_USER}")
        except:
            ASSOCIATED_USER = get_associated_token_address(USER, MINT)
            token_account_instruction = create_associated_token_account(USER, USER, MINT)
            logger.info(f"Creating token account : {ASSOCIATED_USER}")

        logger.info("Calculating transaction amounts...")
        virtual_sol_reserves = coin_data.virtual_sol_reserves
        virtual_token_reserves = coin_data.virtual_token_reserves
        sol_in_lamports = sol_in * SOL_DECIMAL
        amount = int(sol_in_lamports * virtual_token_reserves / virtual_sol_reserves)
        slippage_adjustment = 1 + (slippage / 100)
        max_sol_cost = int(sol_in * slippage_adjustment * SOL_DECIMAL)
        logger.info(f"Amount: {amount}, Max Sol Cost: {max_sol_cost}")

        logger.info("Creating swap instructions...")
        keys = [
            AccountMeta(pubkey=GLOBAL, is_signer=False, is_writable=False),
            AccountMeta(pubkey=FEE_RECIPIENT, is_signer=False, is_writable=True),
            AccountMeta(pubkey=MINT, is_signer=False, is_writable=False),
            AccountMeta(pubkey=BONDING_CURVE, is_signer=False, is_writable=True),
            AccountMeta(pubkey=ASSOCIATED_BONDING_CURVE, is_signer=False, is_writable=True),
            AccountMeta(pubkey=ASSOCIATED_USER, is_signer=False, is_writable=True),
            AccountMeta(pubkey=USER, is_signer=True, is_writable=True),
            AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=TOKEN_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=RENT, is_signer=False, is_writable=False),
            AccountMeta(pubkey=EVENT_AUTHORITY, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_FUN_PROGRAM, is_signer=False, is_writable=False)
        ]

        data = bytearray()
        data.extend(bytes.fromhex("66063d1201daebea"))
        data.extend(struct.pack('<Q', amount))
        data.extend(struct.pack('<Q', max_sol_cost))
        swap_instruction = Instruction(PUMP_FUN_PROGRAM, bytes(data), keys)

        instructions = [
            set_compute_unit_limit(UNIT_BUDGET),
            set_compute_unit_price(UNIT_PRICE),
        ]
        if token_account_instruction:
            instructions.append(token_account_instruction)
        instructions.append(swap_instruction)

        logger.info("Compiling transaction message...")
        compiled_message = MessageV0.try_compile(
            payer_keypair.pubkey(),
            instructions,
            [],
            client.get_latest_blockhash().value.blockhash,
        )

        logger.info("Sending transaction...")
        txn_sig = client.send_transaction(
            txn=VersionedTransaction(compiled_message, [payer_keypair]),
            opts=TxOpts(skip_preflight=True)
        ).value
        logger.info(f"Transaction Signature: {txn_sig}")

        logger.info("Confirming transaction...")
        confirmed = confirm_txn(client=client, txn_sig=txn_sig)
        
        logger.info(f"Transaction confirmed: {confirmed}")
        return confirmed

    except Exception as e:
        logger.info(f"Error occurred during transaction: {e}")
        return False

def pf_sell(client, payer_keypair, mint_str: str, percentage: int = 100, slippage: int = 15) -> bool:
    try:
        logger.info(f"PF - Starting sell transaction for mint: {mint_str}")

        if not (1 <= percentage <= 100):
            logger.info("Percentage must be between 1 and 100.")
            return False

        coin_data = get_coin_data(client=client, mint_str=mint_str)
        
        if not coin_data:
            logger.info("Failed to retrieve coin data.")
            return False

        if coin_data.complete:
            logger.info("Warning: This token has bonded and is only tradable on Raydium.")            
            logger.info('Initiating swap on raydium')
            raydium_swap(ctx=client, payer=payer_keypair, desired_token_address=mint_str)
            return

        MINT = coin_data.mint
        BONDING_CURVE = coin_data.bonding_curve
        ASSOCIATED_BONDING_CURVE = coin_data.associated_bonding_curve
        USER = payer_keypair.pubkey()
        ASSOCIATED_USER = get_associated_token_address(USER, MINT)
        CREATOR = coin_data.creator
        CREATOR_VAULT = derive_creator_vault(CREATOR)
        logger.info("Calculating token price...")
        sol_decimal = 10**9
        token_decimal = 10**6
        token_price = (
            coin_data.virtual_sol_reserves / sol_decimal
        ) / (coin_data.virtual_token_reserves / token_decimal)
        logger.info(f"Token Price: {token_price:.8f} SOL")

        logger.info("Retrieving token balance...")
        token_balance = get_token_balance(client, payer_keypair, mint_str)
        
        ## Edgecase: token balance is mixed number (i.e. 1.5), then sell the whole number part (1)
        if token_balance % 1 != 0 and token_balance > 1: # is a mixed number
            token_balance = int(token_balance)

    
        logger.info(f"token_balance {token_balance}")
        if token_balance == 0:
            logger.info("Token balance is zero. Nothing to sell.")
            return False

        logger.info("Calculating transaction amounts...")
        token_balance *= percentage / 100
        # for debugging
        logger.info(f"token_balance {token_balance}")
        logger.info(f"token_decimal {token_decimal}")
        amount = int(token_balance * token_decimal)
        sol_out = token_balance * token_price
        slippage_adjustment = 1 - (slippage / 100)
        min_sol_output = int(sol_out * slippage_adjustment * SOL_DECIMAL)
        logger.info(f"Amount: {amount}, Minimum Sol Out: {min_sol_output}")

        logger.info("Creating swap instructions...")
        keys = [
            AccountMeta(pubkey=GLOBAL, is_signer=False, is_writable=False),
            AccountMeta(pubkey=FEE_RECIPIENT, is_signer=False, is_writable=True),
            AccountMeta(pubkey=MINT, is_signer=False, is_writable=False),
            AccountMeta(pubkey=BONDING_CURVE, is_signer=False, is_writable=True),
            AccountMeta(pubkey=ASSOCIATED_BONDING_CURVE, is_signer=False, is_writable=True),
            AccountMeta(pubkey=ASSOCIATED_USER, is_signer=False, is_writable=True),
            AccountMeta(pubkey=USER, is_signer=True, is_writable=True),
            AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
            # CREATOR VAULT
            AccountMeta(pubkey=CREATOR_VAULT, is_signer=False, is_writable=True),
            # AccountMeta(pubkey=ASSOC_TOKEN_ACC_PROG, is_signer=False, is_writable=False),
            AccountMeta(pubkey=TOKEN_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=EVENT_AUTHORITY, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_FUN_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_FUN_FEE_CONFIG, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_FUN_FEE_PROGRAM, is_signer=False, is_writable=False),
        ]

        data = bytearray()
        data.extend(bytes.fromhex("33e685a4017f83ad"))
        data.extend(struct.pack('<Q', amount))
        data.extend(struct.pack('<Q', min_sol_output))
        swap_instruction = Instruction(PUMP_FUN_PROGRAM, bytes(data), keys)

        instructions = [
            set_compute_unit_limit(UNIT_BUDGET),
            set_compute_unit_price(UNIT_PRICE),
            swap_instruction,
        ]

        # if percentage == 100:
        #     logger.info("Preparing to close token account after swap...")
        #     close_account_instruction = close_account(CloseAccountParams(TOKEN_PROGRAM, ASSOCIATED_USER, USER, USER))
        #     instructions.append(close_account_instruction)

        logger.info("Compiling transaction message...")
        compiled_message = MessageV0.try_compile(
            payer_keypair.pubkey(),
            instructions,
            [],
            client.get_latest_blockhash().value.blockhash,
        )

        logger.info("Sending transaction...")

        try: 
            start_time = time.time()
            txn_sig = client.send_transaction(
                txn=VersionedTransaction(compiled_message, [payer_keypair]),
                opts=TxOpts(skip_preflight=False)
            ).value
        except RPCException as e:
            logger.info(f"Error: [{e.args[0].message}]...\nRetrying...")
            logger.info(f"sell error {mint_str} ",f" {e.args[0].message}")

        except Exception as e:
            logger.info(f"Error: [{e}]...\nEnd...")
            logger.info(f"sell error  {mint_str}",f": {e.args[0].message}")
            txnBool = False
            return "failed"



        logger.info(f"Transaction Signature: {txn_sig}")

        logger.info("Confirming transaction...")
        confirmed = confirm_txn(client=client,txn_sig=txn_sig)
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"Transaction confirmed: {confirmed}")
        logger.info(f"Execution time {execution_time}")
        return confirmed

    except Exception as e:
        logger.error(f"Error occurred during transaction: {e}")
        return False
