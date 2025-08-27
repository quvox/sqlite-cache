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

# Error codes matching library.go
SUCCESS = 1
ERROR_GENERAL = 0
ERROR_DISK_FULL = -1
ERROR_INVALID_ARG = -2
ERROR_NOT_FOUND = -3
ERROR_NOT_INIT = -4


class SqliteCacheLibrary:
    """Python client for sqcache library using ctypes."""
    
    def __init__(self, library_path: str = None):
        """Initialize the client with the path to the sqcache library."""
        if library_path is None:
            # Get version from environment variable, default to 0.3.0
            version = os.environ.get('VERSION', '0.3.0')
            # Try various paths: project root, examples directory, Linux build, Lambda build, and Lambda environment
            paths = [
                f"./build/sqcachelib.{version}.so", 
                f"../build/sqcachelib.{version}.so",
                f"./build/linux/sqcachelib.{version}.so",
                f"../build/linux/sqcachelib.{version}.so",
                f"./build/linux/sqcachelib.{version}.arm64.so",
                f"../build/linux/sqcachelib.{version}.arm64.so",
                f"./build/lambda/sqcachelib.{version}.so",
                f"../build/lambda/sqcachelib.{version}.so",
                f"./build/lambda/sqcachelib.{version}.arm64.so",
                f"../build/lambda/sqcachelib.{version}.arm64.so",
                f"/var/task/sqcachelib.{version}.so"
            ]
            library_path = None
            for p in paths:
                if os.path.exists(p):
                    library_path = p
                    break
            if library_path is None:
                library_path = f"./build/sqcachelib.{version}.so"  # fallback
        self.library_path = library_path
        self.lib = None
        self._load_library()
    
    def _load_library(self):
        """Load the shared library and configure function signatures."""
        if not os.path.exists(self.library_path):
            raise FileNotFoundError(f"Library not found: {self.library_path}")
        
        print(f"Trying to load library: {self.library_path}")
        try:
            self.lib = ctypes.CDLL(self.library_path)
            print(f"Successfully loaded: {self.library_path}")
        except Exception as e:
            print(f"Failed to load library: {e}")
            # Try different loading strategies for Amazon Linux 2 compatibility
            loading_strategies = [
                ("RTLD_LAZY", lambda: ctypes.CDLL(self.library_path, mode=ctypes.RTLD_LAZY)),
                ("RTLD_NOW", lambda: ctypes.CDLL(self.library_path, mode=ctypes.RTLD_NOW)),
                ("RTLD_GLOBAL", lambda: ctypes.CDLL(self.library_path, mode=ctypes.RTLD_GLOBAL)),
            ]
            
            for strategy_name, loader in loading_strategies:
                try:
                    print(f"Attempting to load with {strategy_name} mode...")
                    self.lib = loader()
                    print(f"Success with {strategy_name} mode!")
                    break
                except Exception as e2:
                    print(f"{strategy_name} also failed: {e2}")
            else:
                raise RuntimeError(f"Cannot load library {self.library_path}: {e}") from e
        
        # Configure function signatures for new API
        # Init(char* baseDir, int maxSize, double cap) -> int
        self.lib.Init.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_double]
        self.lib.Init.restype = ctypes.c_int
        
        # Get(char* table, char* tenantId, char* freshness, char* bind, int* resultLen) -> char*
        self.lib.Get.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
        self.lib.Get.restype = ctypes.c_void_p  # void*に変更して安全に
        
        # FreeMem(char* ptr)
        self.lib.FreeMem.argtypes = [ctypes.c_void_p]
        self.lib.FreeMem.restype = None
        
        # Set(char* table, char* tenantId, char* freshness, char* bind, char* content, int contentLen) -> int
        self.lib.Set.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        self.lib.Set.restype = ctypes.c_int
        
        # Delete(char* table) -> int
        self.lib.Delete.argtypes = [ctypes.c_char_p]
        self.lib.Delete.restype = ctypes.c_int
        
        # Close() -> int
        self.lib.Close.argtypes = []
        self.lib.Close.restype = ctypes.c_int
    
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
        result = self.lib.Init(base_dir_c, max_size, cap)
        
        if result == ERROR_DISK_FULL:
            raise RuntimeError("Disk full - cannot initialize cache")
        elif result == ERROR_INVALID_ARG:
            raise ValueError("Invalid argument provided to init")
        elif result != SUCCESS:
            raise RuntimeError(f"Failed to initialize cache (error code: {result})")
        
        return True
    
    def get(self, table: str, tenant_id: str, freshness: str, bind: str) -> Optional[bytes]:
        """Get data from cache."""
        if self.lib is None:
            raise RuntimeError("Library not loaded")
        
        table_c = table.encode('utf-8')
        tenant_id_c = tenant_id.encode('utf-8')
        freshness_c = freshness.encode('utf-8')
        bind_c = bind.encode('utf-8')
        
        result_len = ctypes.c_int(0)
        result_ptr = self.lib.Get(table_c, tenant_id_c, freshness_c, bind_c, ctypes.byref(result_len))
        
        # Check for error codes in result_len
        if result_len.value == ERROR_DISK_FULL:
            raise RuntimeError("Disk full error during cache get")
        elif result_len.value == ERROR_INVALID_ARG:
            raise ValueError("Invalid argument provided to get")
        elif result_len.value == ERROR_NOT_INIT:
            raise RuntimeError("Cache not initialized")
        elif result_len.value == ERROR_NOT_FOUND:
            return None  # Cache miss
        elif result_len.value < 0:
            raise RuntimeError(f"Cache get failed (error code: {result_len.value})")
        
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
                self.lib.FreeMem(result_ptr)
    
    def set(self, table: str, tenant_id: str, freshness: str, bind: str, content: bytes) -> bool:
        """Set data in cache."""
        if self.lib is None:
            raise RuntimeError("Library not loaded")
        
        table_c = table.encode('utf-8')
        tenant_id_c = tenant_id.encode('utf-8')
        freshness_c = freshness.encode('utf-8')
        bind_c = bind.encode('utf-8')
        
        # Content is passed as raw bytes with length
        content_ptr = ctypes.c_char_p(content)
        content_len = len(content)
        
        result = self.lib.Set(table_c, tenant_id_c, freshness_c, bind_c, content_ptr, content_len)
        
        if result == ERROR_DISK_FULL:
            raise RuntimeError("Disk full - cannot set cache")
        elif result == ERROR_INVALID_ARG:
            raise ValueError("Invalid argument provided to set")
        elif result == ERROR_NOT_INIT:
            raise RuntimeError("Cache not initialized")
        elif result != SUCCESS:
            raise RuntimeError(f"Failed to set cache (error code: {result})")
        
        return True
    
    def delete(self, table: str) -> bool:
        """Delete all cache data for a table."""
        if self.lib is None:
            raise RuntimeError("Library not loaded")
        
        table_c = table.encode('utf-8')
        result = self.lib.Delete(table_c)
        
        if result == ERROR_DISK_FULL:
            raise RuntimeError("Disk full error during cache delete")
        elif result == ERROR_INVALID_ARG:
            raise ValueError("Invalid argument provided to delete")
        elif result == ERROR_NOT_INIT:
            raise RuntimeError("Cache not initialized")
        elif result != SUCCESS:
            raise RuntimeError(f"Failed to delete cache (error code: {result})")
        
        return True
    
    def close(self) -> bool:
        """Close the cache system."""
        if self.lib is None:
            raise RuntimeError("Library not loaded")
        
        result = self.lib.Close()
        
        if result == ERROR_DISK_FULL:
            raise RuntimeError("Disk full error during cache close")
        elif result == ERROR_INVALID_ARG:
            raise ValueError("Invalid argument provided to close")
        elif result == ERROR_NOT_INIT:
            raise RuntimeError("Cache not initialized")
        elif result != SUCCESS:
            raise RuntimeError(f"Failed to close cache (error code: {result})")
        
        return True


def main():
    """Example usage of the SqliteCacheLibrary."""
    
    # Try shared library paths with version from environment
    version = os.environ.get('VERSION', '0.3.0')
    library_paths = [
        f"./build/sqcachelib.{version}.so", f"./build/mac/sqcachelib.{version}.so",
        f"../build/sqcachelib.{version}.so", f"../build/mac/sqcachelib.{version}.so"
    ]
    
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
        freshness = "fresh1"  # Use string as per DESIGN.md
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
        
    except RuntimeError as e:
        if "disk full" in str(e).lower():
            print(f"DISK FULL ERROR: {e}")
            print("Please free up disk space and try again.")
        elif "not initialized" in str(e).lower():
            print(f"INITIALIZATION ERROR: {e}")
            print("Make sure to call init() before other operations.")
        else:
            print(f"RUNTIME ERROR: {e}")
        try:
            cache.close()
        except:
            pass
        return 1
    except ValueError as e:
        print(f"INVALID ARGUMENT ERROR: {e}")
        print("Please check your function arguments.")
        try:
            cache.close()
        except:
            pass
        return 1
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        try:
            cache.close()
        except:
            pass
        return 1


if __name__ == "__main__":
    exit(main())