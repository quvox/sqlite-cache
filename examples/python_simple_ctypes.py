#!/usr/bin/env python3
"""
Simple SQLite Cache Python Client using ctypes (no classes)

This example demonstrates a minimal approach to interact with the sqcache library
using ctypes without class overhead. Only provides init, set, and get functions.
"""

import ctypes
import json
import os
from typing import Optional


# Global library handle
_lib = None


def load_library(library_path: str = "./build/sqcachelib.0.2.0.so"):
    """Load the shared library and configure function signatures."""
    global _lib
    
    if not os.path.exists(library_path):
        raise FileNotFoundError(f"Library not found: {library_path}")
    
    _lib = ctypes.CDLL(library_path)
    
    # Configure function signatures
    # Init(char* baseDir, int maxSize, double cap) -> char*
    _lib.Init.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_double]
    _lib.Init.restype = ctypes.c_char_p
    
    # Get(char* table, char* tenantId, char* freshness, char* bind) -> char*
    _lib.Get.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    _lib.Get.restype = ctypes.c_char_p
    
    # Set(char* table, char* tenantId, char* freshness, char* bind, char* content, int contentLen) -> char*
    _lib.Set.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    _lib.Set.restype = ctypes.c_char_p


def _handle_response(result_ptr):
    """Handle the response from a library function call."""
    if not result_ptr:
        raise RuntimeError("No response from library function")
    
    # Convert C string to Python string
    result_str = ctypes.string_at(result_ptr).decode('utf-8')
    
    try:
        return json.loads(result_str)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response: {result_str}") from e


def init(base_dir: str, max_size: int, cap: float = 0.8) -> bool:
    """Initialize the cache system."""
    if _lib is None:
        raise RuntimeError("Library not loaded. Call load_library() first.")
    
    base_dir_c = base_dir.encode('utf-8')
    result_ptr = _lib.Init(base_dir_c, max_size, cap)
    response = _handle_response(result_ptr)
    
    if not response.get("success", False):
        raise RuntimeError(f"Failed to initialize cache: {response.get('error', 'unknown error')}")
    
    return True


def get(table: str, tenant_id: str, freshness: str, bind: str) -> Optional[bytes]:
    """Get data from cache."""
    if _lib is None:
        raise RuntimeError("Library not loaded. Call load_library() first.")
    
    table_c = table.encode('utf-8')
    tenant_id_c = tenant_id.encode('utf-8')
    freshness_c = freshness.encode('utf-8')
    bind_c = bind.encode('utf-8')
    
    result_ptr = _lib.Get(table_c, tenant_id_c, freshness_c, bind_c)
    response = _handle_response(result_ptr)
    
    if response.get("success", False):
        # Data is base64 encoded in JSON
        import base64
        data = response.get("data")
        if data:
            return base64.b64decode(data)
        return None
    
    if "not found" in response.get("error", "").lower():
        return None
    
    raise RuntimeError(f"Failed to get cache: {response.get('error', 'unknown error')}")


def set(table: str, tenant_id: str, freshness: str, bind: str, content: bytes) -> bool:
    """Set data in cache."""
    if _lib is None:
        raise RuntimeError("Library not loaded. Call load_library() first.")
    
    table_c = table.encode('utf-8')
    tenant_id_c = tenant_id.encode('utf-8')
    freshness_c = freshness.encode('utf-8')
    bind_c = bind.encode('utf-8')
    
    # Content is passed as raw bytes with length
    content_ptr = ctypes.c_char_p(content)
    content_len = len(content)
    
    result_ptr = _lib.Set(table_c, tenant_id_c, freshness_c, bind_c, content_ptr, content_len)
    response = _handle_response(result_ptr)
    
    if not response.get("success", False):
        raise RuntimeError(f"Failed to set cache: {response.get('error', 'unknown error')}")
    
    return True


def main():
    """Example usage of the simple cache functions."""
    
    # Try different library paths
    library_paths = ["./build/sqcachelib.0.2.0.so", "./build/mac/sqcachelib.0.2.0.so"]
    
    library_loaded = False
    for lib_path in library_paths:
        try:
            print(f"Trying to load library: {lib_path}")
            load_library(lib_path)
            print(f"Successfully loaded: {lib_path}")
            library_loaded = True
            break
        except FileNotFoundError:
            print(f"Library not found: {lib_path}")
            continue
        except Exception as e:
            print(f"Failed to load {lib_path}: {e}")
            continue
    
    if not library_loaded:
        print("No usable library found. Please build the library first:")
        print("  make build-lib        # for shared library (.so)")
        return 1
    
    try:
        print("Initializing cache...")
        init("./cache", max_size=100, cap=0.8)
        
        # Test data
        table = "users"
        tenant_id = "tenant_001"
        freshness = "fresh1"  # Use string as per DESIGN.md
        bind_key = "user_123"
        test_data = b'{"name": "John Doe", "email": "john@example.com"}'
        
        print(f"Setting cache for {bind_key}...")
        set(table, tenant_id, freshness, bind_key, test_data)
        
        print(f"Getting cache for {bind_key}...")
        retrieved_data = get(table, tenant_id, freshness, bind_key)
        
        if retrieved_data:
            print(f"Cache hit! Data: {retrieved_data.decode('utf-8')}")
        else:
            print("Cache miss!")
        
        # Test cache miss
        print("Testing cache miss...")
        missing_data = get(table, tenant_id, freshness, "nonexistent_key")
        if missing_data is None:
            print("Cache miss as expected")
        
        print("Cache operations completed successfully!")
        return 0
        
    except Exception as e:
        print(f"Error during cache operations: {e}")
        return 1


if __name__ == "__main__":
    exit(main())