import argparse
import asyncio
import time
import nilql
from nilrag.config import load_nil_db_config
from nilrag.util import decrypt_float_list, encrypt_float_list

DEFAULT_CONFIG = "examples/nildb_config_voting.json"

def run_upload_vote(voter_id: str, vote: str, config_path: str = DEFAULT_CONFIG):
    """
    Synchronous entry point to upload a vote.
    """
    return asyncio.run(_upload_vote_logic(voter_id, vote, config_path))

async def _upload_vote_logic(voter_id: str, vote_str: str, config_path: str):
    """
    Async function to upload a vote.
    """
    # Load NilDB configuration
    nil_db, _ = load_nil_db_config(
        config_path,
        require_bearer_token=True,
        require_schema_id=True,
    )
    print(nil_db)
    print()

    # Initialize secret keys for different modes of operation
    num_nodes = len(nil_db.nodes)
    additive_key = nilql.ClusterKey.generate({"nodes": [{}] * num_nodes}, {"sum": True})

    # Process the vote string into a list of floats
    vote = [float(x) for x in vote_str.split(',')]
    if not all(x in (0.0, 1.0) for x in vote):
        raise ValueError("Vote must only contain 0s and a single 1.")
    if vote.count(1.0) != 1:
        raise ValueError("Vote must contain exactly one '1' and the rest '0's.")

    print(f"Original vote: {vote}")

    # Encrypt vote
    print("Encrypting vote...")
    start_time = time.time()
    vote_shares = encrypt_float_list(additive_key, vote)
    end_time = time.time()
    print(f"Vote encrypted in {end_time - start_time:.2f} seconds")

    actual_vote = decrypt_float_list(additive_key, vote_shares)
    print(f"Actual vote: {actual_vote}")

    # Debug: Upload preview
    print("\nDebug: Uploading to nodes:")
    for node_idx, node in enumerate(nil_db.nodes):
        node_share = [share[node_idx] for share in vote_shares]
        print(f"Node {node_idx} ({node.url}): {node_share}")

    print("\nUploading vote...")
    start_time = time.time()
    await nil_db.upload_vote(vote_shares, voter_id)
    end_time = time.time()
    print(f"Vote uploaded in {end_time - start_time:.2f} seconds")

    return f"Vote for voter '{voter_id}' uploaded successfully."

# CLI entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload a vote to nilDB")
    parser.add_argument("--config", type=str, default=DEFAULT_CONFIG)
    parser.add_argument("--voter_id", type=str, required=True)
    parser.add_argument("--vote", type=str, default="1,0,0")
    args = parser.parse_args()

    asyncio.run(_upload_vote_logic(args.voter_id, args.vote, args.config))
