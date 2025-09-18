from dataclasses import dataclass
from typing import Optional
from construct import Flag, Int64ul, Padding, Struct, Bytes
from solders.pubkey import Pubkey  # type: ignore
from spl.token.instructions import get_associated_token_address
from pumpfun.constants import PUMP_FUN_PROGRAM
from loguru import logger

@dataclass
class CoinData:
    mint: Pubkey
    bonding_curve: Pubkey
    associated_bonding_curve: Pubkey
    virtual_token_reserves: int
    virtual_sol_reserves: int
    token_total_supply: int
    complete: bool
    creator: Pubkey

def get_virtual_reserves(client, bonding_curve: Pubkey):
    bonding_curve_struct = Struct(
        Padding(8),
        "virtualTokenReserves" / Int64ul,
        "virtualSolReserves" / Int64ul,
        "realTokenReserves" / Int64ul,
        "realSolReserves" / Int64ul,
        "tokenTotalSupply" / Int64ul,
        "complete" / Flag,
        "creator" / Bytes(32),
    )
    
    try:
        account_info = client.get_account_info(bonding_curve)
        data = account_info.value.data
        parsed_data = bonding_curve_struct.parse(data)
        return parsed_data
    except Exception:
        return None

def derive_bonding_curve_accounts(mint_str: str):
    try:
        logger.info(f"Deriving bonding curve for {mint_str}")
        mint = Pubkey.from_string(mint_str)
        logger.info(f'mint {mint}')
        bonding_curve, _ = Pubkey.find_program_address(
            ["bonding-curve".encode(), bytes(mint)],
            PUMP_FUN_PROGRAM
        )
        associated_bonding_curve = get_associated_token_address(bonding_curve, mint)
        logger.info(f"associated bonding curve {associated_bonding_curve}")
        return bonding_curve, associated_bonding_curve
    except Exception as e:
        logger.error(f'PF - error occured in deriving bonding curve account - {e}')
        return None, None

def get_coin_data(client, mint_str: str) -> Optional[CoinData]:
    logger.info("PF - retrieving coin data")
    bonding_curve, associated_bonding_curve = derive_bonding_curve_accounts(mint_str)
    if bonding_curve is None or associated_bonding_curve is None:
        return None

    virtual_reserves = get_virtual_reserves(client, bonding_curve)
    if virtual_reserves is None:
        return None
    
    try:
        return CoinData(
            mint=Pubkey.from_string(mint_str),
            bonding_curve=bonding_curve,
            associated_bonding_curve=associated_bonding_curve,
            virtual_token_reserves=int(virtual_reserves.virtualTokenReserves),
            virtual_sol_reserves=int(virtual_reserves.virtualSolReserves),
            token_total_supply=int(virtual_reserves.tokenTotalSupply),
            complete=bool(virtual_reserves.complete),
            creator=Pubkey.from_bytes(virtual_reserves.creator)
        )
    except Exception as e:
        logger.error(e)
        return None
