#!/bin/bash
#
# MAO Testing Platform - Demo Setup Script
#
# This script sets up everything needed for a demo:
# 1. Starts PostgreSQL (if using Docker)
# 2. Runs database migrations
# 3. Seeds demo data
# 4. Starts backend
# 5. Starts frontend
#
# Usage:
#   ./scripts/demo-setup.sh         # Full setup
#   ./scripts/demo-setup.sh --seed  # Just seed data
#   ./scripts/demo-setup.sh --start # Just start services
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_banner() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║           MAO TESTING PLATFORM - DEMO SETUP                   ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    
    if ! command -v node &> /dev/null; then
        log_error "Node.js is required but not installed"
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        log_error "npm is required but not installed"
        exit 1
    fi
    
    log_success "All dependencies found"
}

setup_backend() {
    log_info "Setting up backend..."
    cd "$PROJECT_ROOT/backend"
    
    if [ ! -d "venv" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    log_info "Installing Python dependencies..."
    pip install -q -r requirements.txt 2>/dev/null || pip install -q -e .
    
    log_success "Backend setup complete"
}

setup_frontend() {
    log_info "Setting up frontend..."
    cd "$PROJECT_ROOT/frontend"
    
    if [ ! -d "node_modules" ]; then
        log_info "Installing npm dependencies..."
        npm install --silent
    fi
    
    log_success "Frontend setup complete"
}

seed_database() {
    log_info "Seeding demo data..."
    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate
    
    python scripts/seed_demo.py
    
    log_success "Demo data seeded"
}

start_backend() {
    log_info "Starting backend on port 8000..."
    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate
    
    uvicorn app.main:app --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$PROJECT_ROOT/.backend.pid"
    
    sleep 2
    if kill -0 $BACKEND_PID 2>/dev/null; then
        log_success "Backend started (PID: $BACKEND_PID)"
    else
        log_error "Backend failed to start"
        exit 1
    fi
}

start_frontend() {
    log_info "Starting frontend on port 3000..."
    cd "$PROJECT_ROOT/frontend"
    
    npm run dev &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$PROJECT_ROOT/.frontend.pid"
    
    sleep 3
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        log_success "Frontend started (PID: $FRONTEND_PID)"
    else
        log_error "Frontend failed to start"
        exit 1
    fi
}

stop_services() {
    log_info "Stopping services..."
    
    if [ -f "$PROJECT_ROOT/.backend.pid" ]; then
        kill $(cat "$PROJECT_ROOT/.backend.pid") 2>/dev/null || true
        rm "$PROJECT_ROOT/.backend.pid"
    fi
    
    if [ -f "$PROJECT_ROOT/.frontend.pid" ]; then
        kill $(cat "$PROJECT_ROOT/.frontend.pid") 2>/dev/null || true
        rm "$PROJECT_ROOT/.frontend.pid"
    fi
    
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    pkill -f "next dev" 2>/dev/null || true
    
    log_success "Services stopped"
}

print_demo_info() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                    DEMO READY                                  ║"
    echo "╠═══════════════════════════════════════════════════════════════╣"
    echo "║                                                               ║"
    echo "║  Frontend:  http://localhost:3000                             ║"
    echo "║  Backend:   http://localhost:8000                             ║"
    echo "║  API Docs:  http://localhost:8000/docs                        ║"
    echo "║                                                               ║"
    echo "║  Demo API Key: mao_demo_key_12345                             ║"
    echo "║                                                               ║"
    echo "║  Quick Links:                                                 ║"
    echo "║    - Dashboard: http://localhost:3000/dashboard               ║"
    echo "║    - Demo:      http://localhost:3000/demo                    ║"
    echo "║    - Traces:    http://localhost:3000/traces                  ║"
    echo "║                                                               ║"
    echo "║  CLI Usage:                                                   ║"
    echo "║    mao config init                                            ║"
    echo "║    mao debug --last 5                                         ║"
    echo "║                                                               ║"
    echo "║  Press Ctrl+C to stop all services                            ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""
}

cleanup() {
    echo ""
    log_info "Shutting down..."
    stop_services
    log_success "Cleanup complete"
    exit 0
}

main() {
    print_banner
    
    case "${1:-full}" in
        --seed)
            setup_backend
            seed_database
            ;;
        --start)
            start_backend
            start_frontend
            print_demo_info
            trap cleanup SIGINT SIGTERM
            wait
            ;;
        --stop)
            stop_services
            ;;
        full|*)
            check_dependencies
            setup_backend
            setup_frontend
            seed_database
            start_backend
            start_frontend
            print_demo_info
            trap cleanup SIGINT SIGTERM
            wait
            ;;
    esac
}

main "$@"
