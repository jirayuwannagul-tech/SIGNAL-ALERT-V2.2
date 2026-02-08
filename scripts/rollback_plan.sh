#!/bin/bash
# Rollback plan for SIGNAL-ALERT v2.0 deployment
# Emergency rollback script for Cloud Run deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/rollback_$(date +%Y%m%d_%H%M%S).log"

# Default configuration
SERVICE_NAME="squeeze-bot"
REGION="asia-southeast1"
PROJECT_ID=""
DRY_RUN=false
FORCE=false

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Print usage
usage() {
    cat << EOF
SIGNAL-ALERT v2.0 Rollback Script

Usage: $0 [OPTIONS]

Options:
    -s, --service SERVICE_NAME    Service name (default: squeeze-bot)
    -r, --region REGION          Cloud Run region (default: asia-southeast1)
    -p, --project PROJECT_ID     Google Cloud project ID
    -d, --dry-run               Show what would be done without executing
    -f, --force                 Skip confirmation prompts
    -h, --help                  Show this help message

Examples:
    $0 --project my-project-123
    $0 --service squeeze-bot --region asia-southeast1 --project my-project
    $0 --dry-run --project my-project

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|--service)
                SERVICE_NAME="$2"
                shift 2
                ;;
            -r|--region)
                REGION="$2"
                shift 2
                ;;
            -p|--project)
                PROJECT_ID="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -f|--force)
                FORCE=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

# Validate requirements
validate_requirements() {
    log "Validating requirements..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_color "$RED" "❌ gcloud CLI is not installed"
        exit 1
    fi
    
    # Get project ID if not provided
    if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
        if [ -z "$PROJECT_ID" ]; then
            print_color "$RED" "❌ No project ID specified and no default project set"
            print_color "$YELLOW" "Use: gcloud config set project YOUR_PROJECT_ID"
            exit 1
        fi
    fi
    
    # Check if user is authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        print_color "$RED" "❌ Not authenticated with gcloud"
        print_color "$YELLOW" "Use: gcloud auth login"
        exit 1
    fi
    
    # Verify Cloud Run API is enabled
    if ! gcloud services list --enabled --filter="name:run.googleapis.com" --format="value(name)" | grep -q "run.googleapis.com"; then
        print_color "$RED" "❌ Cloud Run API is not enabled"
        print_color "$YELLOW" "Enable it with: gcloud services enable run.googleapis.com"
        exit 1
    fi
    
    log "✅ Requirements validation passed"
}

# Get current service info
get_current_service_info() {
    log "Getting current service information..."
    
    # Check if service exists
    if ! gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(metadata.name)" &>/dev/null; then
        print_color "$RED" "❌ Service '$SERVICE_NAME' not found in region '$REGION'"
        exit 1
    fi
    
    # Get current revision
    CURRENT_REVISION=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.latestReadyRevisionName)")
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)")
    
    log "Current revision: $CURRENT_REVISION"
    log "Service URL: $SERVICE_URL"
}

# List available revisions
list_revisions() {
    log "Listing available revisions..."
    
    print_color "$BLUE" "📋 Available revisions for $SERVICE_NAME:"
    
    gcloud run revisions list \
        --service="$SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="table(metadata.name:label=REVISION,metadata.creationTimestamp:label=CREATED,spec.containers[0].image:label=IMAGE,status.conditions[0].status:label=READY)" \
        | tee -a "$LOG_FILE"
}

# Find previous stable revision
find_previous_revision() {
    log "Finding previous stable revision..."
    
    # Get all revisions excluding current one
    REVISIONS=$(gcloud run revisions list \
        --service="$SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(metadata.name)" \
        --sort-by="~metadata.creationTimestamp")
    
    # Find previous revision (skip current one)
    PREVIOUS_REVISION=""
    FOUND_CURRENT=false
    
    for revision in $REVISIONS; do
        if [ "$revision" = "$CURRENT_REVISION" ]; then
            FOUND_CURRENT=true
            continue
        fi
        
        if [ "$FOUND_CURRENT" = true ]; then
            # Check if this revision is ready
            REVISION_STATUS=$(gcloud run revisions describe "$revision" \
                --region="$REGION" \
                --project="$PROJECT_ID" \
                --format="value(status.conditions[0].status)" 2>/dev/null || echo "False")
            
            if [ "$REVISION_STATUS" = "True" ]; then
                PREVIOUS_REVISION="$revision"
                break
            fi
        fi
    done
    
    if [ -z "$PREVIOUS_REVISION" ]; then
        print_color "$RED" "❌ No previous stable revision found!"
        print_color "$YELLOW" "Available revisions:"
        list_revisions
        exit 1
    fi
    
    log "Previous stable revision: $PREVIOUS_REVISION"
    
    # Get image for previous revision
    PREVIOUS_IMAGE=$(gcloud run revisions describe "$PREVIOUS_REVISION" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(spec.containers[0].image)")
    
    log "Previous image: $PREVIOUS_IMAGE"
}

# Confirm rollback
confirm_rollback() {
    if [ "$FORCE" = true ]; then
        log "Force mode enabled - skipping confirmation"
        return
    fi
    
    print_color "$YELLOW" "⚠️  ROLLBACK CONFIRMATION"
    echo "=================================="
    echo "Service: $SERVICE_NAME"
    echo "Region: $REGION"
    echo "Project: $PROJECT_ID"
    echo ""
    echo "Current revision: $CURRENT_REVISION"
    echo "Target revision:  $PREVIOUS_REVISION"
    echo "Target image:     $PREVIOUS_IMAGE"
    echo ""
    
    if [ "$DRY_RUN" = true ]; then
        print_color "$BLUE" "🔍 DRY RUN MODE - No changes will be made"
        return
    fi
    
    read -p "⚠️ Confirm rollback to $PREVIOUS_REVISION? (y/N): " -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_color "$YELLOW" "Rollback cancelled by user"
        exit 0
    fi
}

# Execute rollback
execute_rollback() {
    log "Executing rollback to $PREVIOUS_REVISION..."
    
    if [ "$DRY_RUN" = true ]; then
        print_color "$BLUE" "🔍 DRY RUN: Would execute:"
        print_color "$BLUE" "gcloud run services update-traffic $SERVICE_NAME \\"
        print_color "$BLUE" "    --to-revisions=$PREVIOUS_REVISION=100 \\"
        print_color "$BLUE" "    --region=$REGION \\"
        print_color "$BLUE" "    --project=$PROJECT_ID"
        return
    fi
    
    print_color "$YELLOW" "🔄 Rolling back to $PREVIOUS_REVISION..."
    
    if gcloud run services update-traffic "$SERVICE_NAME" \
        --to-revisions="$PREVIOUS_REVISION=100" \
        --region="$REGION" \
        --project="$PROJECT_ID"; then
        
        print_color "$GREEN" "✅ Rollback command executed successfully"
        log "Rollback command completed"
    else
        print_color "$RED" "❌ Rollback command failed"
        log "ERROR: Rollback command failed"
        exit 1
    fi
}

# Verify rollback
verify_rollback() {
    if [ "$DRY_RUN" = true ]; then
        print_color "$BLUE" "🔍 DRY RUN: Would verify rollback"
        return
    fi
    
    log "Verifying rollback..."
    
    print_color "$YELLOW" "⏳ Waiting for traffic to switch (30 seconds)..."
    sleep 30
    
    # Check current serving revision
    CURRENT_SERVING=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.traffic[0].revisionName)")
    
    if [ "$CURRENT_SERVING" = "$PREVIOUS_REVISION" ]; then
        print_color "$GREEN" "✅ Traffic successfully switched to $PREVIOUS_REVISION"
        log "Traffic switch verification passed"
    else
        print_color "$RED" "❌ Traffic switch verification failed"
        print_color "$RED" "Expected: $PREVIOUS_REVISION"
        print_color "$RED" "Actual: $CURRENT_SERVING"
        log "ERROR: Traffic switch verification failed"
    fi
    
    # Health check
    if [ -n "$SERVICE_URL" ]; then
        print_color "$YELLOW" "🏥 Running health check..."
        
        HEALTH_CHECK_URL="${SERVICE_URL}/health"
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_CHECK_URL" --max-time 10 || echo "000")
        
        if [ "$HTTP_STATUS" = "200" ]; then
            print_color "$GREEN" "✅ Health check passed (HTTP $HTTP_STATUS)"
            log "Health check passed"
        else
            print_color "$RED" "❌ Health check failed (HTTP $HTTP_STATUS)"
            log "WARNING: Health check failed with HTTP $HTTP_STATUS"
        fi
        
        # Try to get health response
        HEALTH_RESPONSE=$(curl -s "$HEALTH_CHECK_URL" --max-time 10 || echo "ERROR")
        if [[ $HEALTH_RESPONSE == *"healthy"* ]]; then
            print_color "$GREEN" "✅ Service reports healthy status"
            log "Service health status: healthy"
        else
            print_color "$RED" "⚠️ Service health status unclear"
            log "WARNING: Service health status unclear: $HEALTH_RESPONSE"
        fi
    fi
}

# Generate rollback report
generate_report() {
    REPORT_FILE="${SCRIPT_DIR}/rollback_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$REPORT_FILE" << EOF
SIGNAL-ALERT v2.0 Rollback Report
=================================

Rollback Date: $(date '+%Y-%m-%d %H:%M:%S')
Executed By: $(whoami)
Project: $PROJECT_ID
Service: $SERVICE_NAME
Region: $REGION

Rollback Details:
- From Revision: $CURRENT_REVISION
- To Revision: $PREVIOUS_REVISION
- Target Image: $PREVIOUS_IMAGE
- Service URL: $SERVICE_URL

Rollback Status: $([ "$DRY_RUN" = true ] && echo "DRY RUN" || echo "EXECUTED")

Post-Rollback Checklist:
□ Monitor application logs for errors
□ Check Google Sheets integration
□ Verify LINE Bot notifications
□ Test signal detection manually
□ Confirm position tracking works
□ Monitor for 2-4 hours minimum

Recovery Actions if Issues Persist:
1. Check service logs:
   gcloud run services logs read $SERVICE_NAME --region=$REGION

2. Roll forward to working version:
   gcloud run services update-traffic $SERVICE_NAME --to-latest --region=$REGION

3. Manual intervention points:
   - Check environment variables
   - Verify Google Sheets credentials
   - Test LINE Bot configuration
   - Validate Binance API connectivity

Log File: $LOG_FILE
Report Generated: $(date '+%Y-%m-%d %H:%M:%S')
EOF
    
    log "Rollback report saved to: $REPORT_FILE"
    print_color "$GREEN" "📊 Rollback report saved to: $REPORT_FILE"
}

# Main function
main() {
    print_color "$RED" "🚨 SIGNAL-ALERT v2.0 Rollback Plan"
    print_color "$RED" "=================================="
    
    log "Starting rollback process"
    
    # Parse arguments
    parse_args "$@"
    
    # Validate environment
    validate_requirements
    
    # Get service information
    get_current_service_info
    
    # List available revisions
    list_revisions
    
    # Find target revision
    find_previous_revision
    
    # Confirm rollback
    confirm_rollback
    
    # Execute rollback
    execute_rollback
    
    # Verify rollback
    verify_rollback
    
    # Generate report
    generate_report
    
    if [ "$DRY_RUN" = true ]; then
        print_color "$BLUE" "🔍 Dry run completed - no changes made"
    else
        print_color "$GREEN" "🎉 Rollback completed successfully!"
    fi
    
    print_color "$YELLOW" "📋 Next steps:"
    echo "1. Monitor application logs for 30 minutes"
    echo "2. Check Google Sheets integration"
    echo "3. Verify LINE Bot notifications"
    echo "4. Test signal detection manually"
    echo "5. Document rollback reason"
    echo ""
    print_color "$BLUE" "📊 Check rollback report for details and checklist"
    
    log "Rollback process completed"
}

# Handle script interruption
trap 'print_color "$YELLOW" "\n⚠️ Rollback interrupted by user"; log "Rollback interrupted"; exit 130' INT TERM

# Run main function
main "$@"