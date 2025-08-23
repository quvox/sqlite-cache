#!/bin/bash
#
# SQLite Cache Bash Client
#
# This example demonstrates how to interact with the sqcache binary
# from bash using JSON over stdin/stdout communication.
#

set -euo pipefail

# Default binary path
BINARY_PATH="${1:-./build/sqcache}"
SQCACHE_PID=""

# Cleanup function
cleanup() {
    # Close file descriptors
    exec 3>&- 2>/dev/null || true
    exec 4<&- 2>/dev/null || true
    
    # Kill process if running
    if [[ -n "${SQCACHE_PID:-}" ]]; then
        kill "$SQCACHE_PID" 2>/dev/null || true
        wait "$SQCACHE_PID" 2>/dev/null || true
    fi
    
    # Remove pipes
    rm -f "$SQCACHE_IN" "$SQCACHE_OUT"
}

# Set trap for cleanup
trap cleanup EXIT

# Temporary files for communication
SQCACHE_IN="/tmp/sqcache_in_$$"
SQCACHE_OUT="/tmp/sqcache_out_$$"

# Start sqcache process
start_sqcache() {
    # Create named pipes
    mkfifo "$SQCACHE_IN" "$SQCACHE_OUT"
    
    # Start sqcache in background
    "$BINARY_PATH" < "$SQCACHE_IN" > "$SQCACHE_OUT" &
    SQCACHE_PID=$!
    
    # Open file descriptors
    exec 3> "$SQCACHE_IN"   # Write to sqcache
    exec 4< "$SQCACHE_OUT"  # Read from sqcache
    
    sleep 0.2  # Give process time to start
}

# Function to send command to sqcache and get response
send_command() {
    local command="$1"
    local request="$2"
    local cmd_line="$command $request"
    local response
    
    # Send command
    echo "$cmd_line" >&3
    
    # Read response with timeout
    if read -t 5 -r response <&4; then
        # Parse success field from JSON response
        local success=$(echo "$response" | jq -r '.success // false')
        
        if [[ "$success" != "true" ]]; then
            local error_msg=$(echo "$response" | jq -r '.error // "unknown error"')
            echo "Error: $error_msg" >&2
            return 1
        fi
        
        echo "$response"
    else
        echo "Error: timeout waiting for response" >&2
        return 1
    fi
}

# Function to initialize cache
cache_init() {
    local base_dir="$1"
    local max_size="$2"
    local cap="$3"
    
    local request=$(jq -nc \
        --arg base_dir "$base_dir" \
        --argjson max_size "$max_size" \
        --argjson cap "$cap" \
        '{base_dir: $base_dir, max_size: $max_size, cap: $cap}')
    
    send_command "INIT" "$request" > /dev/null
}

# Function to set cache data
cache_set() {
    local table="$1"
    local tenant_id="$2"
    local freshness="$3"
    local bind="$4"
    local content="$5"
    
    # Base64 encode the content
    local encoded_content=$(echo -n "$content" | base64 -w 0)
    
    local request=$(jq -nc \
        --arg table "$table" \
        --arg tenant_id "$tenant_id" \
        --arg freshness "$freshness" \
        --arg bind "$bind" \
        --arg content "$encoded_content" \
        '{table: $table, tenant_id: $tenant_id, freshness: $freshness, bind: $bind, content: $content}')
    
    send_command "SET" "$request" > /dev/null
}

# Function to get cache data
cache_get() {
    local table="$1"
    local tenant_id="$2"
    local freshness="$3"
    local bind="$4"
    
    local request=$(jq -nc \
        --arg table "$table" \
        --arg tenant_id "$tenant_id" \
        --arg freshness "$freshness" \
        --arg bind "$bind" \
        '{table: $table, tenant_id: $tenant_id, freshness: $freshness, bind: $bind}')
    
    local response
    if response=$(send_command "GET" "$request" 2>/dev/null); then
        # Extract and decode data
        local encoded_data=$(echo "$response" | jq -r '.data // empty')
        if [[ -n "$encoded_data" ]]; then
            echo "$encoded_data" | base64 -d
            return 0
        fi
    fi
    
    # Return empty/failure
    return 1
}

# Function to delete cache table
cache_delete() {
    local table="$1"
    
    local request=$(jq -nc --arg table "$table" '{table: $table}')
    send_command "DELETE" "$request" > /dev/null
}

# Function to close cache
cache_close() {
    local request='{}'
    send_command "CLOSE" "$request" > /dev/null
}

# Main function
main() {
    echo "SQLite Cache Bash Client Example"
    echo "================================="
    
    # Check if binary exists
    if [[ ! -f "$BINARY_PATH" ]]; then
        echo "Error: sqcache binary not found at $BINARY_PATH"
        echo "Please build it first: make build"
        exit 1
    fi
    
    # Check if jq is available
    if ! command -v jq >/dev/null 2>&1; then
        echo "Error: jq is required but not installed."
        echo "Please install jq: sudo apt-get install jq (Ubuntu) or brew install jq (macOS)"
        exit 1
    fi
    
    echo "Starting sqcache process..."
    start_sqcache
    echo "✓ sqcache process started (PID: $SQCACHE_PID)"
    
    # Test data
    local table="users"
    local tenant_id="tenant_001" 
    local freshness="fresh1"
    local bind_key="user_123"
    local test_data='{"name": "John Doe", "email": "john@example.com"}'
    
    echo "Initializing cache..."
    if cache_init "./cache" 100 0.8; then
        echo "✓ Cache initialized successfully"
    else
        echo "✗ Failed to initialize cache"
        exit 1
    fi
    
    echo "Setting cache for $bind_key..."
    if cache_set "$table" "$tenant_id" "$freshness" "$bind_key" "$test_data"; then
        echo "✓ Cache set successfully"
    else
        echo "✗ Failed to set cache"
        exit 1
    fi
    
    echo "Getting cache for $bind_key..."
    if retrieved_data=$(cache_get "$table" "$tenant_id" "$freshness" "$bind_key"); then
        echo "✓ Cache hit! Data: $retrieved_data"
    else
        echo "✗ Cache miss!"
        exit 1
    fi
    
    echo "Testing cache miss..."
    if cache_get "$table" "$tenant_id" "$freshness" "nonexistent_key" >/dev/null 2>&1; then
        echo "✗ Unexpected cache hit"
        exit 1
    else
        echo "✓ Cache miss as expected"
    fi
    
    echo "Deleting cache for table $table..."
    if cache_delete "$table"; then
        echo "✓ Cache deleted successfully"
    else
        echo "✗ Failed to delete cache"
        exit 1
    fi
    
    echo "Closing cache..."
    if cache_close; then
        echo "✓ Cache closed successfully"
    else
        echo "✗ Failed to close cache"
        exit 1
    fi
    
    echo ""
    echo "✓ All cache operations completed successfully!"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi