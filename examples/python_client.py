#!/usr/bin/env python3
"""
SQLite Cache Python Client Example

This example demonstrates how to interact with the sqcache binary
from Python using JSON over stdin/stdout communication.
"""

import json
import subprocess
import sys
import time
from typing import Optional, Any, Dict


class SqliteCacheClient:
    """Python client for sqcache binary."""
    
    def __init__(self, binary_path: str = "./build/sqcache"):
        """Initialize the client with the path to the sqcache binary."""
        self.binary_path = binary_path
        self.process: Optional[subprocess.Popen] = None
    
    def start(self):
        """Start the sqcache process."""
        if self.process is not None:
            raise RuntimeError("Process already started")
        
        self.process = subprocess.Popen(
            [self.binary_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
    
    def stop(self):
        """Stop the sqcache process."""
        if self.process is not None:
            try:
                self.close()
            except:
                pass
            
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None
    
    def _send_command(self, command: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to the sqcache process and get the response."""
        if self.process is None:
            raise RuntimeError("Process not started")
        
        # Send command
        request_json = json.dumps(request)
        command_line = f"{command} {request_json}\n"
        
        self.process.stdin.write(command_line)
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline().strip()
        if not response_line:
            raise RuntimeError("No response from sqcache")
        
        try:
            return json.loads(response_line)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response: {response_line}") from e
    
    def init(self, base_dir: str, max_size: int, cap: float = 0.8) -> bool:
        """Initialize the cache system."""
        request = {
            "base_dir": base_dir,
            "max_size": max_size,
            "cap": cap
        }
        
        response = self._send_command("INIT", request)
        if not response.get("success", False):
            raise RuntimeError(f"Failed to initialize cache: {response.get('error', 'unknown error')}")
        
        return True
    
    def get(self, table: str, tenant_id: str, freshness: str, bind: str) -> Optional[bytes]:
        """Get data from cache."""
        request = {
            "table": table,
            "tenant_id": tenant_id,
            "freshness": freshness,
            "bind": bind
        }
        
        response = self._send_command("GET", request)
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
        import base64
        
        request = {
            "table": table,
            "tenant_id": tenant_id,
            "freshness": freshness,
            "bind": bind,
            "content": base64.b64encode(content).decode('ascii')
        }
        
        response = self._send_command("SET", request)
        if not response.get("success", False):
            raise RuntimeError(f"Failed to set cache: {response.get('error', 'unknown error')}")
        
        return True
    
    def delete(self, table: str) -> bool:
        """Delete all cache data for a table."""
        request = {"table": table}
        
        response = self._send_command("DELETE", request)
        if not response.get("success", False):
            raise RuntimeError(f"Failed to delete cache: {response.get('error', 'unknown error')}")
        
        return True
    
    def close(self) -> bool:
        """Close the cache system."""
        request = {}
        
        response = self._send_command("CLOSE", request)
        if not response.get("success", False):
            raise RuntimeError(f"Failed to close cache: {response.get('error', 'unknown error')}")
        
        return True
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


def main():
    """Example usage of the SqliteCacheClient."""
    
    # Example usage
    with SqliteCacheClient("./build/sqcache") as cache:
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
        
        print("Cache operations completed successfully!")


if __name__ == "__main__":
    main()