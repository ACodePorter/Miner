#!/bin/bash

# SSH Key Management Script for Docker Build
# This script handles GitHub SSH key setup for the miner-maintainer

set -e

# Configuration
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
RUNTIME_ENV="${RUNTIME_ENV:-}"
SSH_KEY_NAME="miner-maintainer"
SSH_KEY_FILE="$HOME/.ssh/id_rsa"
GITHUB_API_URL="https://api.github.com"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required environment variables are set
check_environment() {
    if [[ -z "$GITHUB_TOKEN" ]]; then
        log_error "GITHUB_TOKEN environment variable is required"
        exit 1
    fi

    if [[ "$RUNTIME_ENV" != "PROD" ]]; then
        log_error "RUNTIME_ENV must be set to 'PROD' to setup SSH keys, got: '$RUNTIME_ENV'"
        exit 0
    fi
}

# Add GitHub to SSH known hosts
add_github_to_known_hosts() {
    log_info "Adding github.com to SSH known hosts..."
    
    if [[ ! -d "$HOME/.ssh" ]]; then
        mkdir -p "$HOME/.ssh"
        chmod 700 "$HOME/.ssh"
    fi
    
    # Add GitHub to known hosts
    ssh-keyscan -H github.com >> "$HOME/.ssh/known_hosts" 2>/dev/null || {
        log_error "Failed to add github.com to known hosts"
        return 1
    }
    
    log_info "Successfully added github.com to known hosts"
}

# Check and create SSH key if needed
create_ssh_key() {
    log_info "Checking for existing SSH key..."
    
    if [[ -f "$SSH_KEY_FILE" && -f "$SSH_KEY_FILE.pub" ]]; then
        log_info "Existing SSH key found, using it..."
        
        # Verify the key is valid
        if ssh-keygen -lf "$SSH_KEY_FILE" >/dev/null 2>&1; then
            log_info "Existing SSH key is valid"
            chmod 600 "$SSH_KEY_FILE"
            chmod 644 "$SSH_KEY_FILE.pub"
            return 0
        else
            log_warn "Existing SSH key appears to be invalid, creating new one..."
            rm -f "$SSH_KEY_FILE" "$SSH_KEY_FILE.pub"
        fi
    else
        log_info "No existing SSH key found, creating new one..."
    fi
    
    # Generate new SSH key
    ssh-keygen -t rsa -b 4096 -f "$SSH_KEY_FILE" -N "" -C "miner-maintainer@docker" || {
        log_error "Failed to create SSH key"
        return 1
    }
    
    chmod 600 "$SSH_KEY_FILE"
    chmod 644 "$SSH_KEY_FILE.pub"
    
    log_info "Successfully created new SSH key"
}

# Get SSH key fingerprint
get_key_fingerprint() {
    ssh-keygen -lf "$SSH_KEY_FILE" | awk '{print $2}'
}

# Remove existing SSH key from GitHub
remove_existing_key() {
    log_info "Checking for existing SSH key '$SSH_KEY_NAME' on GitHub..."
    
    # Get list of SSH keys
    local keys_response
    keys_response=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "$GITHUB_API_URL/user/keys")
    
    if [[ $? -ne 0 ]]; then
        log_error "Failed to fetch SSH keys from GitHub"
        return 1
    fi
    
    # Find and remove the key with matching name
    local key_id
    key_id=$(echo "$keys_response" | jq -r ".[] | select(.title == \"$SSH_KEY_NAME\") | .id")
    
    if [[ "$key_id" != "null" && -n "$key_id" ]]; then
        log_info "Removing existing SSH key (ID: $key_id)..."
        
        local remove_response
        remove_response=$(curl -s -X DELETE \
            -H "Authorization: Bearer $GITHUB_TOKEN" \
            -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "$GITHUB_API_URL/user/keys/$key_id")
        
        if [[ $? -eq 0 ]]; then
            log_info "Successfully removed existing SSH key"
        else
            log_warn "Failed to remove existing SSH key (may not exist)"
        fi
    else
        log_info "No existing SSH key found with name '$SSH_KEY_NAME'"
    fi
}

# Add new SSH key to GitHub
add_key_to_github() {
    log_info "Adding SSH key to GitHub..."
    
    # Read the public key
    local public_key
    public_key=$(cat "$SSH_KEY_FILE.pub")
    
    if [[ -z "$public_key" ]]; then
        log_error "Failed to read public key"
        return 1
    fi
    
    # Prepare the request payload
    local payload
    payload=$(cat <<EOF
{
    "title": "$SSH_KEY_NAME",
    "key": "$public_key"
}
EOF
)
    
    # Add the key to GitHub
    local response
    response=$(curl -s -X POST \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        -d "$payload" \
        "$GITHUB_API_URL/user/keys")
    
    if [[ $? -ne 0 ]]; then
        log_error "Failed to add SSH key to GitHub"
        return 1
    fi
    
    # Check if the request was successful
    local key_id
    key_id=$(echo "$response" | jq -r '.id')
    
    if [[ "$key_id" != "null" && -n "$key_id" ]]; then
        log_info "Successfully added SSH key to GitHub (ID: $key_id)"
        log_info "Key fingerprint: $(get_key_fingerprint)"
    else
        local error_message
        error_message=$(echo "$response" | jq -r '.message // .errors[0].message // "Unknown error"')
        log_error "Failed to add SSH key to GitHub: $error_message"
        return 1
    fi
}

# Test SSH connection to GitHub
test_ssh_connection() {
    log_info "Testing SSH connection to GitHub..."
    
    # Wait a moment for the key to propagate
    sleep 5
    
    if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
        log_info "SSH connection to GitHub successful"
        return 0
    else
        log_warn "SSH connection test failed (this is normal during build)"
        return 0
    fi
}

# Main execution
main() {
    log_info "Starting SSH key setup for miner-maintainer..."
    
    check_environment
    add_github_to_known_hosts
    create_ssh_key
    remove_existing_key
    add_key_to_github
    test_ssh_connection
    
    log_info "SSH key setup completed successfully"
}

# Run main function
main "$@" 