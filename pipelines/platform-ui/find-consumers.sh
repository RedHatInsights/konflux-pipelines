#!/bin/bash
# Script to help identify consumer repositories that may need migration
# after the chrome sidecar removal

set -e

echo "========================================"
echo "Chrome Sidecar Removal - Consumer Finder"
echo "========================================"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "ERROR: GitHub CLI (gh) is not installed."
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

echo "Searching for repositories using platform-ui pipeline..."
echo ""

# Create output directory
mkdir -p migration-reports
REPORT_FILE="migration-reports/affected-repos-$(date +%Y%m%d-%H%M%S).txt"

echo "Report will be saved to: $REPORT_FILE"
echo ""

# Function to search and log results
search_and_log() {
    local query=$1
    local description=$2

    echo "----------------------------------------"
    echo "Searching: $description"
    echo "Query: $query"
    echo "----------------------------------------"

    # Save to report
    echo "" >> "$REPORT_FILE"
    echo "========================================" >> "$REPORT_FILE"
    echo "Search: $description" >> "$REPORT_FILE"
    echo "Query: $query" >> "$REPORT_FILE"
    echo "========================================" >> "$REPORT_FILE"

    # Run search and save results
    gh search code "$query" --json repository,path,url 2>/dev/null | tee -a "$REPORT_FILE" || echo "No results found"

    echo ""
}

# Search 1: Repositories using the platform-ui pipeline
search_and_log \
    "org:RedHatInsights docker-build-run-all-tests path:.tekton/" \
    "Repositories using platform-ui docker-build-run-all-tests pipeline"

# Search 2: References to port 9912
search_and_log \
    "org:RedHatInsights 9912 path:.tekton/" \
    "Repositories with port 9912 references in .tekton/"

# Search 3: References to chrome-dev-image parameter
search_and_log \
    "org:RedHatInsights e2e-chrome-dev-image" \
    "Repositories setting e2e-chrome-dev-image parameter"

# Search 4: ConfigMaps with chrome routes
search_and_log \
    "org:RedHatInsights /apps/chrome reverse_proxy" \
    "ConfigMaps routing /apps/chrome paths"

# Search 5: Learning resources (known consumer)
search_and_log \
    "repo:RedHatInsights/learning-resources 9912" \
    "Learning Resources repository (known consumer)"

echo "========================================="
echo "Search complete!"
echo "========================================="
echo ""
echo "Report saved to: $REPORT_FILE"
echo ""
echo "Next steps:"
echo "1. Review the report file"
echo "2. For each affected repository:"
echo "   - Clone the repository"
echo "   - Review ConfigMaps and pipeline files"
echo "   - Remove references to port 9912"
echo "   - Test the changes"
echo "3. See MIGRATION.md for detailed migration steps"
echo ""

# Print summary
echo "Summary:"
echo "--------"
if [ -f "$REPORT_FILE" ]; then
    echo "Total searches performed: 5"
    echo "Check $REPORT_FILE for detailed results"
fi
