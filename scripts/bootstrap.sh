#!/bin/bash
# PISAMA Bootstrap — single command to set up and verify the dev environment.
#
# Usage:
#   ./scripts/bootstrap.sh          # Full bootstrap (deps + smoke test + registry)
#   ./scripts/bootstrap.sh --check  # Smoke test only (no install)
#   ./scripts/bootstrap.sh --quick  # Install deps only (no tests)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND="$PROJECT_ROOT/backend"

log_info()    { echo "  [INFO]  $1"; }
log_success() { echo "  [OK]    $1"; }
log_warn()    { echo "  [WARN]  $1"; }
log_error()   { echo "  [ERROR] $1"; }

install_deps() {
    cd "$BACKEND"
    if [ ! -d ".venv" ]; then
        log_info "Creating virtual environment..."
        python3 -m venv .venv
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
    if [ -f requirements-ci.txt ]; then
        pip install -q -r requirements-ci.txt 2>/dev/null
    elif [ -f requirements.txt ]; then
        pip install -q -r requirements.txt 2>/dev/null
    fi
    log_success "Backend dependencies installed"
}

check_services() {
    if command -v docker &> /dev/null && docker ps &> /dev/null 2>&1; then
        if docker ps --format '{{.Names}}' | grep -qi postgres; then
            log_success "PostgreSQL running"
        else
            log_warn "PostgreSQL not running — tests will use SQLite fallback"
        fi
    else
        log_warn "Docker not available — tests will use SQLite fallback"
    fi
}

run_smoke_test() {
    cd "$BACKEND"
    if [ -d ".venv" ]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
    fi
    log_info "Running smoke tests..."
    python3 -m pytest tests/test_smoke.py -v --tb=short
    log_success "Smoke tests passed"
}

update_registry() {
    cd "$BACKEND"
    if [ -d ".venv" ]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
    fi
    if [ -f "data/calibration_report.json" ]; then
        log_info "Updating capability registry..."
        python3 -m app.detection_enterprise.calibrate --registry
        log_success "Capability registry updated"
    else
        log_warn "No calibration report — skipping registry generation"
    fi
}

main() {
    echo ""
    echo "  PISAMA Bootstrap"
    echo "  ================"
    echo ""

    case "${1:-full}" in
        --check)
            run_smoke_test
            ;;
        --quick)
            install_deps
            check_services
            ;;
        full|*)
            install_deps
            check_services
            run_smoke_test
            update_registry
            ;;
    esac

    echo ""
    log_success "Bootstrap complete"
}

main "$@"
