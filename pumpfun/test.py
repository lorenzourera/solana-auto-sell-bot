from configparser import ConfigParser
import os, sys

config = ConfigParser()
config_path = os.path.join(sys.path[0], 'data', 'config.ini')

print(f"Config path: {config_path}")  # Debugging line to check the path

config.read(config_path)

try:
    UNIT_BUDGET = config.get("PUMPFUN", "UNIT_BUDGET") 
    print(f"Unit Budget: {UNIT_BUDGET}")  # Debugging line to check value
except Exception as e:
    print(f"Error reading configuration: {e}")
    sys.exit(1)  # Exit if configuration fails