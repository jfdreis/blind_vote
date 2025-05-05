"""
Utility functions for nilRAG.
"""

from typing import Union

import nilql

PRECISION = 7
SCALING_FACTOR = 10**PRECISION


def to_fixed_point(value: float) -> int:
    """
    Convert a floating-point value to fixed-point representation.

    Args:
        value (float): Value to convert

    Returns:
        int: Fixed-point representation with PRECISION decimal places
    """
    return int(round(value * SCALING_FACTOR))


def from_fixed_point(value: int) -> float:
    """s
    Convert a fixed-point value back to floating-point.

    Args:
        value (int): Fixed-point value to convert

    Returns:
        float: Floating-point representation
    """
    return value / SCALING_FACTOR


def encrypt_float_list(sk, lst: list[float]) -> list[list]:
    """
    Encrypt a list of floats using a secret key.

    Args:
        sk: Secret key for encryption
        lst (list): List of float values to encrypt

    Returns:
        list: List of encrypted fixed-point values
    """
    return [nilql.encrypt(sk, to_fixed_point(l)) for l in lst]


def decrypt_float_list(sk, lst: list[list]) -> list[float]:
    """
    Decrypt a list of encrypted fixed-point values to floats.

    Args:
        sk: Secret key for decryption
        lst (list): List of encrypted fixed-point values

    Returns:
        list: List of decrypted float values
    """
    return [from_fixed_point(nilql.decrypt(sk, l)) for l in lst]
