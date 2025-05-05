"""
Initialize a voting schema in NilDB and store configuration with JWTs.
"""

import asyncio
import json
import time
import argparse

from nilrag.config import load_nil_db_config

# Default configuration file for the voting system
DEFAULT_CONFIG = "examples/nildb_config_voting.json"
DEFAULT_NUMBER_SLOTS = 5

def run_init_schema(config_path=DEFAULT_CONFIG, slots=DEFAULT_NUMBER_SLOTS):
    """
    Synchronous wrapper to call from web API.
    """
    return asyncio.run(_init_schema_logic(config_path, slots))

async def _init_schema_logic(config_path, slots):
    """
    Core logic for initializing the schema.
    """
    # Load NilDB configuration (this time using the voting-specific config)
    nil_db, secret_key = load_nil_db_config(config_path, require_secret_key=True)
    
    # Generate JWT tokens for each node
    jwts = nil_db.generate_jwt(secret_key, ttl=3600)

    print(nil_db)
    print("Initializing schema...")
    start_time = time.time()
    schema_id = await nil_db.init_schema(n_slots=slots)
    end_time = time.time()
    print(f"Schema initialized successfully in {end_time - start_time:.2f} seconds")

    # Update config file with schema ID and bearer tokens for each node
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Update the nodes with the schema_id and bearer tokens (JWT)
    for node_data, jwt in zip(data["nodes"], jwts):
        node_data["schema_id"] = schema_id
        node_data["bearer_token"] = jwt

    # Save the updated config file
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print("Updated NilDB configuration file with schema ID and JWT tokens.")
   # return f"Schema initialized in {end_time - start_time:.2f}s with schema_id: {schema_id}"

# Optional CLI entry point (still works)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initialize NilDB voting schema"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=DEFAULT_CONFIG,
        help=f"Path to NilDB config file (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--slots",
        type=int,
        default=DEFAULT_NUMBER_SLOTS,
        help=f"Number of vote slots (default: {DEFAULT_NUMBER_SLOTS})",
    )
    args = parser.parse_args()
    asyncio.run(_init_schema_logic(args.config, args.slots))
