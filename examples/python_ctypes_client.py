#!/usr/bin/env python3
"""
SQLite Cache Python Client using ctypes

This example demonstrates how to interact with the sqcache library
using ctypes to call the C interface directly.
"""

import ctypes
import json
import time
from typing import Optional, Any, Dict
import os


class SqliteCacheLibrary:
    """Python client for sqcache library using ctypes."""
    
    def __init__(self, library_path: str = "./build/sqcachelib.0.1.0.so"):
        """Initialize the client with the path to the sqcache library."""
        self.library_path = library_path
        self.lib = None
        self._load_library()
    
    def _load_library(self):
        """Load the shared library and configure function signatures."""
        if not os.path.exists(self.library_path):
            raise FileNotFoundError(f"Library not found: {self.library_path}")
        
        self.lib = ctypes.CDLL(self.library_path)
        
        # Configure function signatures for new API
        # Init(char* baseDir, int maxSize, double cap) -> char*
        self.lib.Init.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_double]
        self.lib.Init.restype = ctypes.c_char_p
        
        # Get(char* table, char* tenantId, long long freshness, char* bind) -> char*
        self.lib.Get.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_longlong, ctypes.c_char_p]
        self.lib.Get.restype = ctypes.c_char_p
        
        # Set(char* table, char* tenantId, long long freshness, char* bind, char* content, int contentLen) -> char*
        self.lib.Set.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_longlong, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        self.lib.Set.restype = ctypes.c_char_p
        
        # Delete(char* table) -> char*
        self.lib.Delete.argtypes = [ctypes.c_char_p]
        self.lib.Delete.restype = ctypes.c_char_p
        
        # Close() -> char*
        self.lib.Close.argtypes = []
        self.lib.Close.restype = ctypes.c_char_p
    
    def _handle_response(self, result_ptr) -> Dict[str, Any]:
        """Handle the response from a library function call."""
        if not result_ptr:
            raise RuntimeError("No response from library function")
        
        # Convert C string to Python string
        result_str = ctypes.string_at(result_ptr).decode('utf-8')
        
        # Note: Memory allocated by C.CString in Go should be managed by Go's GC
        
        try:
            return json.loads(result_str)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response: {result_str}") from e
    
    def init(self, base_dir: str, max_size: int, cap: float = 0.8) -> bool:
        """Initialize the cache system."""
        if self.lib is None:
            raise RuntimeError("Library not loaded")
        
        base_dir_c = base_dir.encode('utf-8')
        result_ptr = self.lib.Init(base_dir_c, max_size, cap)
        response = self._handle_response(result_ptr)
        
        if not response.get("success", False):
            raise RuntimeError(f"Failed to initialize cache: {response.get('error', 'unknown error')}")
        
        return True
    
    def get(self, table: str, tenant_id: str, freshness: int, bind: str) -> Optional[bytes]:
        """Get data from cache."""
        if self.lib is None:
            raise RuntimeError("Library not loaded")
        
        table_c = table.encode('utf-8')
        tenant_id_c = tenant_id.encode('utf-8')
        bind_c = bind.encode('utf-8')
        
        result_ptr = self.lib.Get(table_c, tenant_id_c, freshness, bind_c)
        response = self._handle_response(result_ptr)
        
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
    
    def set(self, table: str, tenant_id: str, freshness: int, bind: str, content: bytes) -> bool:
        """Set data in cache."""
        if self.lib is None:
            raise RuntimeError("Library not loaded")
        
        table_c = table.encode('utf-8')
        tenant_id_c = tenant_id.encode('utf-8')
        bind_c = bind.encode('utf-8')
        
        # Content is passed as raw bytes with length
        content_ptr = ctypes.c_char_p(content)
        content_len = len(content)
        
        result_ptr = self.lib.Set(table_c, tenant_id_c, freshness, bind_c, content_ptr, content_len)
        response = self._handle_response(result_ptr)
        
        if not response.get("success", False):
            raise RuntimeError(f"Failed to set cache: {response.get('error', 'unknown error')}")
        
        return True
    
    def delete(self, table: str) -> bool:
        """Delete all cache data for a table."""
        if self.lib is None:
            raise RuntimeError("Library not loaded")
        
        table_c = table.encode('utf-8')
        result_ptr = self.lib.Delete(table_c)
        response = self._handle_response(result_ptr)
        
        if not response.get("success", False):
            raise RuntimeError(f"Failed to delete cache: {response.get('error', 'unknown error')}")
        
        return True
    
    def close(self) -> bool:
        """Close the cache system."""
        if self.lib is None:
            raise RuntimeError("Library not loaded")
        
        result_ptr = self.lib.Close()
        response = self._handle_response(result_ptr)
        
        if not response.get("success", False):
            raise RuntimeError(f"Failed to close cache: {response.get('error', 'unknown error')}")
        
        return True


def main():
    """Example usage of the SqliteCacheLibrary."""
    
    # Try shared library paths
    library_paths = ["./build/sqcachelib.0.1.0.so", "./build/mac/sqcachelib.0.1.0.so"]
    
    cache = None
    for lib_path in library_paths:
        try:
            print(f"Trying to load library: {lib_path}")
            cache = SqliteCacheLibrary(lib_path)
            print(f"Successfully loaded: {lib_path}")
            break
        except FileNotFoundError:
            print(f"Library not found: {lib_path}")
            continue
        except Exception as e:
            print(f"Failed to load {lib_path}: {e}")
            continue
    
    if cache is None:
        print("No usable library found. Please build the library first:")
        print("  make build-lib        # for shared library (.so)")
        return 1
    
    try:
        print("Initializing cache...")
        cache.init("./cache", max_size=100, cap=0.8)
        
        # Test data
        table = "users"
        tenant_id = "tenant_001"
        freshness = int(time.time())
        bind_key = "user_123"
        test_data = b'{"name": "John Doe", "email": "john@example.com"}'
        
        print(f"Setting cache for {bind_key}...")
        cache.set(table, tenant_id, freshness, bind_key, test_data)
        
        print(f"Getting cache for {bind_key}...")
        retrieved_data = cache.get(table, tenant_id, freshness, bind_key)
        
        if retrieved_data:
            print(f"Cache hit! Data: {retrieved_data.decode('utf-8')}")
        else:
            print("Cache miss!")
        
        # Test cache miss
        print("Testing cache miss...")
        missing_data = cache.get(table, tenant_id, freshness, "nonexistent_key")
        if missing_data is None:
            print("Cache miss as expected")
        
        # Clean up
        print(f"Deleting cache for table {table}...")
        cache.delete(table)
        
        print("Closing cache...")
        cache.close()
        
        print("Cache operations completed successfully!")
        return 0
        
    except Exception as e:
        print(f"Error during cache operations: {e}")
        try:
            cache.close()
        except:
            pass
        return 1


if __name__ == "__main__":
    exit(main())