"""
Retrieve and aggregate voting results from nilDB.
"""

import argparse
import asyncio
import time
import aiohttp
from collections import defaultdict

import nilql

from nilrag.config import load_nil_db_config
from nilrag.util import decrypt_float_list

DEFAULT_CONFIG = "examples/nildb_config.json"

def run_get_results(config_path: str = DEFAULT_CONFIG):
    """
    Synchronous wrapper for retrieving and aggregating voting results.
    Can be called from a web backend.
    """
    return asyncio.run(_get_results_logic(config_path))

async def _get_results_logic(config_path: str):
    """
    Core async logic for retrieving and aggregating votes.
    Returns the final result vector (list of vote counts per slot).
    """
    nil_db, _ = load_nil_db_config(
        config_path,
        require_bearer_token=True,
        require_schema_id=True,
    )

    num_nodes = len(nil_db.nodes)
    additive_key = nilql.ClusterKey.generate({"nodes": [{}] * num_nodes}, {"sum": True})

    print("Step 1: Retrieving shares from nodes...")
    start_time = time.time()
    
    votes_by_id = defaultdict(list)
    async with aiohttp.ClientSession() as session:
        for node_idx, node in enumerate(nil_db.nodes):
            url = f"{node.url}/data/read"
            headers = {
                "Authorization": f"Bearer {node.bearer_token}",
                "Content-Type": "application/json",
            }
            payload = {
                "schema": node.schema_id,
                "filter": {}  # Get all votes
            }

            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    for vote in data.get("data", []):
                        vote_id = vote.get("_id")
                        if vote_id:
                            votes_by_id[vote_id].append((node_idx, vote.get("vote_vector", [])))

    print(f"Found {len(votes_by_id)} unique votes")

    reconstructed_votes = []
    for vote_id, node_shares in votes_by_id.items():
        node_shares.sort(key=lambda x: x[0])
        node_vectors = [share for _, share in node_shares]
        if not node_vectors:
            continue
        vote_shares = list(map(list, zip(*node_vectors)))
        decrypted_vote = decrypt_float_list(additive_key, vote_shares)
        decrypted_vote = [int(round(v)) for v in decrypted_vote]
        reconstructed_votes.append(decrypted_vote)
        print(f"Reconstructed vote {vote_id}: {decrypted_vote}")

    if reconstructed_votes:
        result = [0] * len(reconstructed_votes[0])
        for vote in reconstructed_votes:
            for i in range(len(vote)):
                result[i] += vote[i]
    else:
        result = []

    end_time = time.time()
    print(f"\nResults computed in {end_time - start_time:.2f} seconds")

    print("\nFinal Results:")
    for i, count in enumerate(result):
        print(f"Slot {i}: {count} votes")

    return result

# CLI Entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve voting results from nilDB")
    parser.add_argument("--config", type=str, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    asyncio.run(_get_results_logic(args.config))
