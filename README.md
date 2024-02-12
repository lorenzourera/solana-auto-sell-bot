# Description

This script `auto_sell.py` continously scans a solana wallet for new tokens. Upon detection, it will cache this token along with a few details (`token_address`, `balance`, `detection_time`) in `data\wallet_tokens.json`. When the token is older than a certain time duration it will sell the token.

# Configs/Parameters

1. WALLET_ADDRESS - Wallet Address to be tracked (only one at a time)
2. PRIVATE_KEY - Private Key for the wallet (to allow selling)
3. SOLANA_RPC_URL - RPC URL / I used helius for development
4. X_SECONDS - Amount in seconds between token detection and initiating the sell swap.


# How to use
1. Clone the repo by running: `git clone git@github.com:lorenzourera/solana-auto-sell-bot.git`
2. Create a virtual environment (`python -m venv venv`), activate it (`source venv/bin/activate`) and install all dependencies found in `requirements.txt` (`pip install -r requirements.txt`)
3. Create a new file in `data/` called `config.ini`. The contents of this file should be identical to `config_template.ini` but with the values.
4. Run the script: `python auto_sell.py`
