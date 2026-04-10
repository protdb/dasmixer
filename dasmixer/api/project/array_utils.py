"""Utilities for numpy array compression and decompression."""

import numpy as np
import io


def compress_array(arr: np.ndarray) -> bytes:
    """
    Compress numpy array using savez_compressed.
    
    Args:
        arr: Numpy array
        
    Returns:
        Compressed bytes
    """
    buffer = io.BytesIO()
    np.savez_compressed(buffer, data=arr)
    return buffer.getvalue()


def decompress_array(data: bytes) -> np.ndarray:
    """
    Decompress numpy array.
    
    Args:
        data: Compressed bytes
        
    Returns:
        Numpy array
    """
    buffer = io.BytesIO(data)
    loaded = np.load(buffer, allow_pickle=False)
    return loaded['data']
