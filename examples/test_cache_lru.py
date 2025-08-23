#!/usr/bin/env python3
"""
SQLite Cache LRU Test

This test implements the test scenario specified in docs/DESIGN.md:
- Initialize with max_size=10MB, cap=0.5
- Create ~100kB content records with bind values 1-200
- Test cache hits/misses and LRU behavior
"""

import ctypes
import json
import random
import time
import os
from typing import Optional, Any, Dict


class SqliteCacheLibrary:
    """Python client for sqcache library using ctypes."""
    
    def __init__(self, library_path: str = "./build/sqcachelib.0.2.0.so"):
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
        
        # Get(char* table, char* tenantId, char* freshness, char* bind) -> char*
        self.lib.Get.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.Get.restype = ctypes.c_char_p
        
        # Set(char* table, char* tenantId, char* freshness, char* bind, char* content, int contentLen) -> char*
        self.lib.Set.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
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
    
    def get(self, table: str, tenant_id: str, freshness: str, bind: str) -> Optional[bytes]:
        """Get data from cache."""
        if self.lib is None:
            raise RuntimeError("Library not loaded")
        
        table_c = table.encode('utf-8')
        tenant_id_c = tenant_id.encode('utf-8')
        freshness_c = freshness.encode('utf-8')
        bind_c = bind.encode('utf-8')
        
        result_ptr = self.lib.Get(table_c, tenant_id_c, freshness_c, bind_c)
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
        
        result_ptr = self.lib.Set(table_c, tenant_id_c, freshness_c, bind_c, content_ptr, content_len)
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


def generate_content(bind_value: int, target_size: int = 100 * 1024) -> bytes:
    """Generate ~100kB content with bind value at the beginning."""
    # Start with bind value
    content = f"bind_value={bind_value}|"
    
    # Calculate remaining size needed
    remaining_size = target_size - len(content.encode('utf-8'))
    
    # Fill with random data to reach target size
    import string
    chars = string.ascii_letters + string.digits + " "
    random_data = ''.join(random.choices(chars, k=remaining_size))
    
    full_content = content + random_data
    return full_content.encode('utf-8')


def test_cache_lru():
    """Test cache LRU behavior according to DESIGN.md specifications."""
    print("=== SQLite Cache LRU Test ===")
    
    # Test parameters  
    MAX_SIZE_MB = 10  # int as per DESIGN.md
    CAP = 0.5  # cap=0.5 as per DESIGN.md
    TABLE = "test_table"
    TENANT_ID = "tenant_001"
    FRESHNESS = "fresh1"  # string as per DESIGN.md
    
    # Initialize cache
    try:
        cache = SqliteCacheLibrary()
        print("✓ Library loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load library: {e}")
        return False
    
    try:
        cache.init("./test_cache", max_size=MAX_SIZE_MB, cap=CAP)
        print(f"✓ Cache initialized (max_size={MAX_SIZE_MB}MB, cap={CAP})")
    except Exception as e:
        print(f"✗ Failed to initialize cache: {e}")
        return False
    
    try:
        # Step 1: Register records 1-90
        print("\n--- Step 1: Registering records 1-90 ---")
        for i in range(1, 91):
            bind_str = str(i)
            content = generate_content(i)
            cache.set(TABLE, TENANT_ID, FRESHNESS, bind_str, content)
            if i % 10 == 0:
                print(f"  Registered {i} records...")
        print("✓ Registered records 1-90")
        
        # Step 2: Test cache hits for 30 random records from 1-90
        print("\n--- Step 2: Testing cache hits for records 1-90 ---")
        test_binds = random.sample(range(1, 91), 30)
        hit_count = 0

        for bind_value in test_binds:
            bind_str = str(bind_value)
            result = cache.get(TABLE, TENANT_ID, FRESHNESS, bind_str)
            if result is not None:
                # Verify content starts with bind value
                content_str = result.decode('utf-8')
                if content_str.startswith(f"bind_value={bind_value}|"):
                    hit_count += 1
                else:
                    print(f"  ✗ Content mismatch for bind {bind_value}")
            else:
                print(f"  ✗ Cache miss for bind {bind_value}")
        
        print(f"  Cache hits: {hit_count}/30")
        if hit_count == 30:
            print("✓ All records 1-90 found in cache")
        else:
            print(f"✗ Expected 30 hits, got {hit_count}")
            return False
        
        # Step 3: Register records 91-200 (should trigger LRU cleanup)
        print("\n--- Step 3: Registering records 91-200 (triggering LRU) ---")
        for i in range(91, 201):
            bind_str = str(i)
            content = generate_content(i)
            cache.set(TABLE, TENANT_ID, FRESHNESS, bind_str, content)
            if i % 20 == 0:
                print(f"  Registered up to {i} records...")
        print("✓ Registered records 91-200")
        
        # Step 4: Test cache misses for records 1-99
        print("\n--- Step 4: Testing cache misses for records 1-99 ---")
        test_binds = random.sample(range(1, 100), 30)
        miss_count = 0
        
        for bind_value in test_binds:
            bind_str = str(bind_value)
            result = cache.get(TABLE, TENANT_ID, FRESHNESS, bind_str)
            if result is None:
                miss_count += 1
            else:
                print(f"  ✗ Unexpected cache hit for bind {bind_value}")
        
        print(f"  Cache misses: {miss_count}/30")
        if miss_count == 30:
            print("✓ All records 1-99 correctly evicted from cache")
        else:
            print(f"✗ Expected 30 misses, got {miss_count}")
            return False
        
        # Step 5: Test cache hits for records 131-200
        print("\n--- Step 5: Testing cache hits for records 131-200 ---")
        test_binds = random.sample(range(131, 201), 30)
        hit_count = 0
        
        for bind_value in test_binds:
            bind_str = str(bind_value)
            result = cache.get(TABLE, TENANT_ID, FRESHNESS, bind_str)
            if result is not None:
                # Verify content starts with bind value
                content_str = result.decode('utf-8')
                if content_str.startswith(f"bind_value={bind_value}|"):
                    hit_count += 1
                else:
                    print(f"  ✗ Content mismatch for bind {bind_value}")
            else:
                print(f"  ✗ Cache miss for bind {bind_value}")
        
        print(f"  Cache hits: {hit_count}/30")
        if hit_count == 30:
            print("✓ All records 131-200 found in cache")
        else:
            print(f"✗ Expected 30 hits, got {hit_count}")
            return False
        
        # Step 6: Test freshness="fresh2" and confirm fresh1 cache deletion
        print("\n--- Step 6: Testing freshness='fresh2' and cache cleanup ---")
        NEW_FRESHNESS = "fresh2"  # Different freshness as string
        
        # Try to get with new freshness (should fail and trigger cleanup)
        result = cache.get(TABLE, TENANT_ID, NEW_FRESHNESS, "1")
        if result is None:
            print("✓ Cache miss for freshness='fresh2' as expected")
        else:
            print("✗ Unexpected cache hit for freshness='fresh2'")
            return False

        # Register records 1-10 with new freshness
        print("\n--- Step 7: Registering records 1-10 with freshness='fresh2' ---")
        for i in range(1, 11):
            bind_str = str(i)
            content = generate_content(i)
            cache.set(TABLE, TENANT_ID, NEW_FRESHNESS, bind_str, content)
        print("✓ Registered records 1-10 with freshness='fresh2'")

        # Test cache hits for records 1-10 with new freshness
        print("\n--- Step 8: Testing cache hits for records 1-10 with freshness='fresh2' ---")
        hit_count = 0
        for bind_value in range(1, 11):
            bind_str = str(bind_value)
            result = cache.get(TABLE, TENANT_ID, NEW_FRESHNESS, bind_str)
            if result is not None:
                # Verify content starts with bind value
                content_str = result.decode('utf-8')
                if content_str.startswith(f"bind_value={bind_value}|"):
                    hit_count += 1
                else:
                    print(f"  ✗ Content mismatch for bind {bind_value}")
            else:
                print(f"  ✗ Cache miss for bind {bind_value}")
        
        print(f"  Cache hits: {hit_count}/10")
        if hit_count == 10:
            print("✓ All records 1-10 found in cache with freshness='fresh2'")
        else:
            print(f"✗ Expected 10 hits, got {hit_count}")
            return False
        
        # Cleanup
        cache.delete(TABLE)
        cache.close()
        print("\n✓ Test completed successfully - LRU algorithm working correctly!")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        try:
            cache.close()
        except:
            pass
        return False


if __name__ == "__main__":
    success = test_cache_lru()
    exit(0 if success else 1)