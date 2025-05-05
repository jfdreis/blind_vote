"""
nilDB class for managing secure voting and storage with distributed nodes.
"""

import asyncio
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiohttp
import jwt
import nilql
import numpy as np
import requests
from ecdsa import SECP256k1, SigningKey

# Constants
TIMEOUT = 3600
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

@dataclass
class Node:  # pylint: disable=too-few-public-methods
    """
    Represents a node in the NilDB network.

    A Node contains connection information and identifiers for a specific NilDB instance,
    including the URL endpoint, org identifier, authentication token, and IDs for
    associated schema.

    Attributes:
        url (str): The base URL endpoint for the node, with trailing slash removed
        org (str): The org identifier for this node
        bearer_token (str): Authentication token for API requests
        schema_id (str, optional): ID of the schema associated with this node
    """

    def __init__(
        self,
        url: str,
        node_id: Optional[str] = None,
        org: Optional[str] = None,
        bearer_token: Optional[str] = None,
        schema_id: Optional[str] = None,
    ):
        """
        Initialize a new Node instance.
        Args:
            url (str): Base URL endpoint for the node
            org (str): org identifier
            bearer_token (str): Authentication token
            schema_id (str, optional): Associated schema ID

        """
        self.url = url[:-1] if url.endswith("/") else url
        self.node_id = node_id
        self.org = org
        self.bearer_token = bearer_token
        self.schema_id = schema_id

    def __repr__(self):
        """
        Returns:
            str: Multi-line string containing all Node attributes
        """
        return f"  URL: {self.url}\
            \n  node_id: {self.node_id}\
            \n  org: {self.org}\
            \n  Bearer Token: {self.bearer_token}\
            \n  Schema ID: {self.schema_id}\
"


class NilDB:
    """
    A class to manage distributed nilDB nodes for managing secure voting and storage with distributed nodes.

    This class handles initialization and vote upload across multiple nilDB nodes
    while maintaining data security through secret sharing.

    Attributes:
        nodes (list): List of Node instances representing the distributed nilDB nodes
    """

    def __init__(self, nodes: list[Node]):
        """
        Initialize NilDB with a list of nilDB nodes.

        Args:
            nodes (list): List of Node instances representing nilDB nodes
        """
        self.nodes = nodes

    def __repr__(self):
        """Return string representation of NilDB showing all nodes."""
        return "\n".join(
            f"\nNode({i}):\n{repr(node)}" for i, node in enumerate(self.nodes)
        )

    async def init_schema(self, n_slots: int):
        """
        Initialize the nilDB schema across all nodes asynchronously.

        Creates a schema for storing vote vectors where each vector has length equal to
        the number of slots, and each entry corresponds to a slot (1 for selected, 0 otherwise).

        Raises:
            ValueError: If schema creation fails on any nilDB node
        """
        schema_id = str(uuid4())

        async def create_schema_for_node(node: Node) -> None:
            url = node.url + "/schemas"
            headers = {
                "Authorization": "Bearer " + str(node.bearer_token),
                "Content-Type": "application/json",
            }
            payload = {
                "_id": schema_id,
                "name": "voting_schema",
                "keys": ["_id"],
                "schema": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "title": "VOTING SCHEMA",
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "_id": {"type": "string", "format": "uuid", "coerce": True},
                            "vote_vector": {
                                "description": "Vector representing the vote, where each entry corresponds to a slot",
                                "type": "array",
                                "items": {"type": "integer"},
                                "minItems": n_slots,
                                "maxItems": n_slots,
                            },
                            "voter_id": {
                                "type": "string",
                                "description": "Unique identifier of the voter",
                            }
                        },
                        "required": ["_id", "vote_vector", "voter_id"],
                        "additionalProperties": False,
                    },
                },
            }
            for attempt in range(MAX_RETRIES):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            url, headers=headers, json=payload, timeout=TIMEOUT
                        ) as response:
                            if response.status not in [
                                HTTPStatus.CREATED,
                                HTTPStatus.OK,
                            ]:
                                error_text = await response.text()
                                raise ValueError(
                                    f"Error in POST request: {response.status}, {error_text}"
                                )
                            node.schema_id = schema_id
                            return
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt == MAX_RETRIES - 1:
                        raise ValueError(
                            f"Failed to create schema after {MAX_RETRIES} attempts: {str(e)}"
                        ) from e
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        # Create schema on all nodes in parallel
        tasks = [create_schema_for_node(node) for node in self.nodes]
        await asyncio.gather(*tasks)
        print(f"Schema {schema_id} created successfully.")
        return schema_id

    def generate_jwt(self, secret_key: str, ttl: int = 3600):
        """
        Create JWTs signed with ES256K for multiple node_ids.

        Args:
            secret_key: Secret key in hex format
            org_did: Issuer's DID
            node_ids: List of node IDs (audience)
            ttl: Time-to-live for the JWT in seconds
        """
        # Convert the secret key from hex to bytes
        private_key = bytes.fromhex(secret_key)
        signer = SigningKey.from_string(private_key, curve=SECP256k1)
        jwts = []
        for node in self.nodes:
            # Create payload for each node_id
            payload = {
                "iss": node.org,
                "aud": node.node_id,
                "exp": int(time.time()) + ttl,
            }

            # Create and sign the JWT
            node.bearer_token = jwt.encode(payload, signer.to_pem(), algorithm="ES256K")
            jwts.append(node.bearer_token)
        return jwts

    async def upload_vote(
        self,
        lst_vote_shares: list[list[int]],
        voter_id: str,
    ) -> None:
        """
        Upload vote shares (one-hot vector) to all nodes.

        Args:
            lst_vote_shares (list): List of vote shares for each vote,
            voter_id (str): Unique identifier of the voter
        Raises:
            AssertionError: If number of embeddings and chunks don't match
            ValueError: If upload fails on any nilDB node
        """

        if await self.has_voted(voter_id):
            raise ValueError(f"Voter {voter_id} has already voted.")

        vote_id = str(uuid4())
        tasks = []
        for node_idx, node in enumerate(self.nodes):
            data = []
            # Join the shares of one vote in one vector for this node
            entry = {
                "_id": vote_id,
                "vote_vector": [
                    e[node_idx] for e in lst_vote_shares
                ],
                "voter_id": voter_id
            }
            # Add this entry to the batch data
            data.append(entry)
            tasks.append(upload_to_node(node, data))
        try:
            results = await asyncio.gather(*tasks)
            print(f"Successfully uploaded vote")
            for result in results:
                print(
                    {
                        "status_code": 200,
                        "message": "Success",
                        "response_json": result,
                    }
                )
        except Exception as e:
            print(f"Error uploading vote: {str(e)}")
            raise

    async def has_voted(self, voter_id: str) -> bool:
        """
        Check if a voter has already submitted a vote by querying any one node.

        Args:
            voter_id (str): Unique identifier of the voter

        Returns:
            bool: True if voter has already voted, False otherwise
        """
        node = self.nodes[0]  # Use any node
        url = node.url + "/data/read"
        headers = {
            "Authorization": "Bearer " + str(node.bearer_token),
            "Content-Type": "application/json",
        }
        payload = {
            "schema": node.schema_id,
            "filter": {"voter_id": voter_id},
            "options": {"limit": 1}
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Error checking voter: {response.status}, {error_text}")
                data = await response.json()
                return len(data.get("data", [])) > 0


async def upload_to_node(node: Node, data: list[dict]):
    """Upload a vote data to a specific node."""
    url = node.url + "/data/create"
    headers = {
        "Authorization": "Bearer " + str(node.bearer_token),
        "Content-Type": "application/json",
    }

    payload = {
        "schema": node.schema_id,
        "data": data,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise ValueError(
                    f"Error in POST request: {response.status}, {error_text}"
                )
            return await response.json()
