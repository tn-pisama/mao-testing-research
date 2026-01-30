#!/bin/bash
# Helper script to generate real LLM samples with proper environment setup

set -e

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY not set"
    echo ""
    echo "Set your API key first:"
    echo "  export ANTHROPIC_API_KEY='your-key-here'"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Activate venv if it exists
if [ -d "$PROJECT_ROOT/.venv" ]; then
    echo "🐍 Activating virtual environment..."
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Run the CLI with all arguments passed through
echo "🚀 Running real LLM generator..."
python "$PROJECT_ROOT/benchmarks/generators/moltbot/cli_real.py" "$@"
