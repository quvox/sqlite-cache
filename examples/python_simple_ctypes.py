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


def load_library(library_path: str = None):
    """Load the shared library and configure function signatures."""
    global _lib
    
    if library_path is None:
        # Get version from environment variable, default to 0.3.0
        version = os.environ.get('VERSION', '0.3.0')
        # Try both project root and examples directory
        paths = [f"./build/sqcachelib.{version}.so", f"../build/sqcachelib.{version}.so"]
        library_path = None
        for p in paths:
            if os.path.exists(p):
                library_path = p
                break
        if library_path is None:
            library_path = f"./build/sqcachelib.{version}.so"  # fallback
    
    if not os.path.exists(library_path):
        raise FileNotFoundError(f"Library not found: {library_path}")
    
    _lib = ctypes.CDLL(library_path)
    
    # Configure function signatures
    # Init(char* baseDir, int maxSize, double cap) -> int
    _lib.Init.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_double]
    _lib.Init.restype = ctypes.c_int
    
    # Get(char* table, char* tenantId, char* freshness, char* bind, int* resultLen) -> char*
    _lib.Get.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
    _lib.Get.restype = ctypes.c_void_p
    
    # FreeMem(char* ptr)
    _lib.FreeMem.argtypes = [ctypes.c_void_p]
    _lib.FreeMem.restype = None
    
    # Set(char* table, char* tenantId, char* freshness, char* bind, char* content, int contentLen) -> int
    _lib.Set.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    _lib.Set.restype = ctypes.c_int


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
    result = _lib.Init(base_dir_c, max_size, cap)
    
    if result == 0:
        raise RuntimeError("Failed to initialize cache")
    
    return True


def get(table: str, tenant_id: str, freshness: str, bind: str) -> Optional[bytes]:
    """Get data from cache."""
    if _lib is None:
        raise RuntimeError("Library not loaded. Call load_library() first.")
    
    table_c = table.encode('utf-8')
    tenant_id_c = tenant_id.encode('utf-8')
    freshness_c = freshness.encode('utf-8')
    bind_c = bind.encode('utf-8')
    
    result_len = ctypes.c_int(0)
    result_ptr = _lib.Get(table_c, tenant_id_c, freshness_c, bind_c, ctypes.byref(result_len))
    
    if not result_ptr or result_len.value == 0:
        return None
    
    try:
        # メモリからデータをコピーして取得
        buffer = ctypes.create_string_buffer(result_len.value)
        ctypes.memmove(buffer, result_ptr, result_len.value)
        return buffer.raw
    finally:
        # Goで確保されたメモリを解放
        if result_ptr:
            _lib.FreeMem(result_ptr)


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
    
    result = _lib.Set(table_c, tenant_id_c, freshness_c, bind_c, content_ptr, content_len)
    
    if result == 0:
        raise RuntimeError("Failed to set cache")
    
    return True


def main():
    """Example usage of the simple cache functions."""
    
    # Try different library paths with version from environment
    version = os.environ.get('VERSION', '0.3.0')
    library_paths = [
        f"./build/sqcachelib.{version}.so", f"./build/mac/sqcachelib.{version}.so",
        f"../build/sqcachelib.{version}.so", f"../build/mac/sqcachelib.{version}.so"
    ]
    
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