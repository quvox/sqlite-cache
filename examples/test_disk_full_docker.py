#!/usr/bin/env python3
"""
Docker-based test for ERROR_DISK_FULL using limited tmpfs
"""

import subprocess
import sys
import os
import tempfile
import shutil
from pathlib import Path

def create_docker_test():
    """Create a Docker-based test environment with limited disk space"""
    
    # Check if Docker is available
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        print("✓ Docker is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Docker is not available or not installed")
        return False
    
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    
    # Create Dockerfile for testing
    dockerfile_content = '''FROM ubuntu:20.04

# Install Python and build tools
RUN apt-get update && apt-get install -y \\
    python3 \\
    python3-pip \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the library and test files (try both x86_64 and arm64)
COPY build/linux/ /app/linux_libs/
COPY examples/python_simple_ctypes.py /app/
COPY examples/test_disk_full_docker_runner.py /app/

# Create a very small tmpfs mount point
RUN mkdir -p /small_disk

# Run the test
CMD ["python3", "test_disk_full_docker_runner.py"]
'''
    
    # Create the test runner script that will run inside Docker
    runner_content = '''#!/usr/bin/env python3
"""
Test runner that executes inside Docker container with limited disk space
"""

import os
import sys
import shutil

# Import our cache functions
from python_simple_ctypes import load_library, init, set, get, ERROR_DISK_FULL

def test_in_limited_space():
    """Test ERROR_DISK_FULL in a container with limited tmpfs"""
    print("=== Docker ERROR_DISK_FULL Test ===")
    
    # The container should be started with --tmpfs /small_disk:rw,size=1m
    test_dir = "/small_disk"
    
    if not os.path.exists(test_dir):
        print(f"❌ Test directory {test_dir} not found")
        print("Make sure Docker container was started with tmpfs mount")
        return False
    
    # Check available space
    stat = shutil.disk_usage(test_dir)
    available_kb = stat.free / 1024
    print(f"Available space in {test_dir}: {available_kb:.1f} KB")
    
    if available_kb > 2048:  # More than 2MB
        print("⚠️  Warning: More space available than expected")
    
    try:
        # Find the correct library file based on architecture
        import platform
        arch = platform.machine()
        print(f"Detected architecture: {arch}")
        
        # Try different library paths
        lib_paths = [
            "./linux_libs/sqcachelib.0.3.0.so",           # x86_64
            "./linux_libs/sqcachelib.0.3.0.arm64.so",     # arm64
            "./sqcachelib.0.3.0.so",                      # fallback
        ]
        
        library_loaded = False
        for lib_path in lib_paths:
            if os.path.exists(lib_path):
                try:
                    print(f"Trying library: {lib_path}")
                    load_library(lib_path)
                    print("✓ Library loaded")
                    library_loaded = True
                    break
                except Exception as e:
                    print(f"  Failed to load {lib_path}: {e}")
                    continue
        
        if not library_loaded:
            print("❌ Could not load any library")
            print("Available files:")
            for path in ["/app", "/app/linux_libs"]:
                if os.path.exists(path):
                    files = os.listdir(path)
                    print(f"  {path}: {files}")
            return False
        
        # Initialize cache in the limited space
        cache_dir = os.path.join(test_dir, "cache")
        print(f"Initializing cache in: {cache_dir}")
        
        try:
            init(cache_dir, max_size=2, cap=0.8)  # 2MB max
            print("✓ Cache initialized")
        except RuntimeError as e:
            if "disk full" in str(e).lower():
                print("✅ ERROR_DISK_FULL caught during initialization!:", e)
                return True
            else:
                raise
        
        # Try to fill the limited space by setting large data
        print("Attempting to trigger disk full with large data...")
        
        # Start with reasonable size and increase
        for i in range(10):
            size = 1024 * (i + 1) * 50  # 50KB, 100KB, 150KB, etc.
            data = b"A" * size
            key = f"large_data_{i}"
            
            print(f"  Setting {size/1024:.1f}KB data (key: {key})...")
            
            try:
                set("test", "tenant1", "fresh1", key, data)
                print(f"    ✓ Successfully set {size/1024:.1f}KB")
                
                # Check remaining space
                stat = shutil.disk_usage(test_dir)
                remaining_kb = stat.free / 1024
                print(f"    Remaining space: {remaining_kb:.1f}KB")
                
                if remaining_kb < 10:  # Very little space left
                    print("    Space is very low, next operation should fail...")
                
            except RuntimeError as e:
                if "disk full" in str(e).lower():
                    print(f"    ✅ ERROR_DISK_FULL caught when setting {size/1024:.1f}KB!")
                    print(f"    Error message: {e}")
                    return True
                else:
                    print(f"    ❌ Unexpected error: {e}")
                    return False
        
        print("❌ Did not trigger ERROR_DISK_FULL")
        return False
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

if __name__ == "__main__":
    success = test_in_limited_space()
    sys.exit(0 if success else 1)
'''
    
    # Write the runner script
    runner_path = project_root / "examples" / "test_disk_full_docker_runner.py"
    with open(runner_path, 'w') as f:
        f.write(runner_content)
    
    # Write Dockerfile
    dockerfile_path = project_root / "Dockerfile.diskfull_test"
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile_content)
    
    print("✓ Created Docker test files")
    return dockerfile_path, runner_path

def run_docker_test():
    """Build and run the Docker test"""
    project_root = Path(__file__).parent.parent
    
    # Ensure the library is built for Linux (both x86_64 and arm64)
    print("Building Linux libraries...")
    try:
        # Build both architectures
        subprocess.run(["make", "build-lib-linux-musl"], 
                      cwd=project_root, check=True, capture_output=True)
        subprocess.run(["make", "build-lib-linux-arm64-musl"], 
                      cwd=project_root, check=True, capture_output=True)
        print("✓ Linux libraries built")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to build Linux library: {e}")
        return False
    
    # Create test files
    dockerfile_path, runner_path = create_docker_test()
    
    try:
        # Build Docker image
        print("Building Docker image...")
        subprocess.run([
            "docker", "build", 
            "-f", str(dockerfile_path),
            "-t", "sqcache-diskfull-test",
            str(project_root)
        ], check=True, capture_output=True)
        print("✓ Docker image built")
        
        # Run the test with limited tmpfs
        print("Running Docker test with 1MB tmpfs...")
        print("This will create a 1MB filesystem at /small_disk in the container")
        
        result = subprocess.run([
            "docker", "run", "--rm",
            "--tmpfs", "/small_disk:rw,size=1m",  # 1MB tmpfs
            "sqcache-diskfull-test"
        ], capture_output=True, text=True)
        
        print("Docker test output:")
        print("-" * 40)
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        print("-" * 40)
        
        success = result.returncode == 0
        if success:
            print("✅ Docker ERROR_DISK_FULL test passed!")
        else:
            print("❌ Docker ERROR_DISK_FULL test failed!")
        
        return success
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker test failed: {e}")
        return False
    finally:
        # Cleanup
        try:
            os.unlink(dockerfile_path)
            os.unlink(runner_path)
            print("✓ Cleaned up test files")
        except:
            pass


if __name__ == "__main__":
    run_docker_test()
    sys.exit(0)