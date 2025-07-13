#!/bin/bash

# MongoDB Backup Script
# Usage: ./backup_mongodb.sh [database_name] [backup_path]

set -e  # Exit on any error

# Configuration
DEFAULT_DB="mongogo"
DEFAULT_BACKUP_PATH="/backups/mongodb"
DEFAULT_HOST="localhost"
DEFAULT_PORT="27017"
COMPRESS=true
RETENTION_DAYS=30

# Parse arguments
DB_NAME=${1:-$DEFAULT_DB}
BACKUP_PATH=${2:-$DEFAULT_BACKUP_PATH}
HOST=${3:-$DEFAULT_HOST}
PORT=${4:-$DEFAULT_PORT}

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

# Check if mongodump is available
check_mongodump() {
    if ! command -v mongodump &> /dev/null; then
        error "mongodump is not installed or not in PATH"
        exit 1
    fi
}

# Create backup directory
create_backup_dir() {
    log "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
}

# Perform backup
perform_backup() {
    log "Starting backup of database: $DB_NAME"
    log "Backup location: $BACKUP_DIR"
    
    # Build mongodump command
    CMD="mongodump --host $HOST --port $PORT --db $DB_NAME --out $BACKUP_DIR"
    
    if [ "$COMPRESS" = true ]; then
        CMD="$CMD --gzip"
        log "Compression enabled"
    fi
    
    log "Executing: $CMD"
    
    if eval $CMD; then
        log "Backup completed successfully"
    else
        error "Backup failed"
        exit 1
    fi
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

# Main execution
main() {
    log "Starting MongoDB backup process"
    
    check_mongodump
    create_backup_dir
    perform_backup
    calculate_backup_size
    cleanup_old_backups
    
    log "Backup process completed successfully"
    log "Backup location: $BACKUP_DIR"
}

# Run main function
main "$@" 