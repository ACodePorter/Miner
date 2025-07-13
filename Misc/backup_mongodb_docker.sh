#!/bin/bash

# MongoDB Docker Backup Script
# Specifically designed for the Miner project Docker setup

set -e  # Exit on any error

# Configuration for Docker setup
CONTAINER_NAME="miner-mongodb"
DB_NAME="mongogo"
BACKUP_PATH="./backups/mongodb"
RETENTION_DAYS=30

# Create timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_PATH}/${DB_NAME}_${TIMESTAMP}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        error "Docker is not running or not accessible"
        exit 1
    fi
}

# Check if MongoDB container is running
check_container() {
    if ! docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        error "MongoDB container '${CONTAINER_NAME}' is not running"
        error "Please start the Docker containers first: docker-compose up -d"
        exit 1
    fi
    log "MongoDB container is running"
}

# Create backup directory
create_backup_dir() {
    log "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
}

# Perform backup using Docker
perform_backup() {
    log "Starting backup of database: $DB_NAME from container: $CONTAINER_NAME"
    log "Backup location: $BACKUP_DIR"
    
    # Create backup inside container
    docker exec "$CONTAINER_NAME" mongodump \
        --db "$DB_NAME" \
        --gzip \
        --out "/dump/${DB_NAME}_${TIMESTAMP}"
    
    if [ $? -eq 0 ]; then
        log "Backup created inside container successfully"
    else
        error "Backup failed inside container"
        exit 1
    fi
    
    # Copy backup from container to host
    docker cp "${CONTAINER_NAME}:/dump/${DB_NAME}_${TIMESTAMP}" "$BACKUP_DIR"
    
    if [ $? -eq 0 ]; then
        log "Backup copied to host successfully"
    else
        error "Failed to copy backup from container"
        exit 1
    fi
    
    # Clean up backup inside container
    docker exec "$CONTAINER_NAME" rm -rf "/dump/${DB_NAME}_${TIMESTAMP}"
    log "Cleaned up backup inside container"
}

# Clean old backups
cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days"
    
    if [ -d "$BACKUP_PATH" ]; then
        find "$BACKUP_PATH" -name "${DB_NAME}_*" -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \;
        log "Cleanup completed"
    else
        warn "Backup path does not exist: $BACKUP_PATH"
    fi
}

# Calculate backup size
calculate_backup_size() {
    if [ -d "$BACKUP_DIR" ]; then
        SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
        log "Backup size: $SIZE"
    fi
}

# Show backup info
show_backup_info() {
    log "=== Backup Information ==="
    log "Database: $DB_NAME"
    log "Container: $CONTAINER_NAME"
    log "Backup location: $BACKUP_DIR"
    log "Timestamp: $TIMESTAMP"
    
    if [ -d "$BACKUP_DIR" ]; then
        log "Backup contents:"
        ls -la "$BACKUP_DIR"
    fi
}

# Main execution
main() {
    log "Starting MongoDB Docker backup process"
    
    check_docker
    check_container
    create_backup_dir
    perform_backup
    calculate_backup_size
    cleanup_old_backups
    show_backup_info
    
    log "Backup process completed successfully"
    log "Backup location: $BACKUP_DIR"
}

# Run main function
main "$@" 