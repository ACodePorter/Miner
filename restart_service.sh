#!/bin/bash

# Script to restart the MinerService by killing existing process and starting a new one
# Usage: ./restart_service.sh
# Only run inside Docker

set -e  # Exit on any error

echo "=== MinerService Restart Script ==="
echo "Timestamp: $(date)"

# Function to find and kill the process
kill_service() {
    echo "Looking for existing MinerService processes..."
    
    # Find processes running uvicorn with the specific socket
    PIDS=$(pgrep -f "uvicorn.*unicorn\.sock" || true)
    
    if [ -n "$PIDS" ]; then
        echo "Found running processes: $PIDS"
        echo "Killing processes..."
        
        for PID in $PIDS; do
            echo "Killing process $PID"
            kill -TERM $PID 2>/dev/null || true
            
            # Wait a bit for graceful shutdown
            sleep 2
            
            # Force kill if still running
            if kill -0 $PID 2>/dev/null; then
                echo "Force killing process $PID"
                kill -KILL $PID 2>/dev/null || true
            fi
        done
        
        echo "All processes killed"
    else
        echo "No running MinerService processes found"
    fi
    
    # Also kill any processes running the script itself
    SCRIPT_PIDS=$(pgrep -f "run_service_as_prod_uds\.sh" || true)
    if [ -n "$SCRIPT_PIDS" ]; then
        echo "Found script processes: $SCRIPT_PIDS"
        for PID in $SCRIPT_PIDS; do
            echo "Killing script process $PID"
            kill -TERM $PID 2>/dev/null || true
            sleep 1
            if kill -0 $PID 2>/dev/null; then
                kill -KILL $PID 2>/dev/null || true
            fi
        done
    fi
}

# Function to start the service
start_service() {
    echo "Starting MinerService..."
    
    # Check if the script exists
    if [ ! -f "/miner_release/run_service_as_prod_uds.sh" ]; then
        echo "Error: run_service_as_prod_uds.sh not found in current directory"
        exit 1
    fi
    
    # Make sure the script is executable
    chmod +x /miner_release/run_service_as_prod_uds.sh
    
    # Start the service in background
    echo "Running: run_service_as_prod_uds.sh"
    nohup /miner_release/run_service_as_prod_uds.sh &
    
    # Get the PID of the new process
    NEW_PID=$!
    echo "Service started with PID: $NEW_PID"
    
    # Wait a moment and check if it's still running
    sleep 3
    if kill -0 $NEW_PID 2>/dev/null; then
        echo "Service is running successfully"
        echo "Logs are being written to: service.log"
        echo "To monitor logs: tail -f service.log"
    else
        echo "Error: Service failed to start"
        echo "Check service.log for details"
        exit 1
    fi
}

# Function to check service status
check_status() {
    echo "Checking service status..."
    
    # Check for uvicorn processes
    UVICORN_PIDS=$(pgrep -f "uvicorn.*unicorn\.sock" || true)
    if [ -n "$UVICORN_PIDS" ]; then
        echo "✓ MinerService is running (PIDs: $UVICORN_PIDS)"
        
        # Check if socket file exists
        if [ -S "/tmp/unicorn.sock" ]; then
            echo "✓ Socket file exists: /tmp/unicorn.sock"
        else
            echo "⚠ Socket file not found: /tmp/unicorn.sock"
        fi
    else
        echo "✗ MinerService is not running"
    fi
}

# Main execution
main() {
    echo "Current directory: $(pwd)"
    
    # Kill existing service
    kill_service
    
    # Wait a moment for cleanup
    sleep 2
    
    # Start new service
    start_service
    
    # Check status
    check_status
    
    echo "=== Restart completed ==="
}

# Run main function
main "$@" 