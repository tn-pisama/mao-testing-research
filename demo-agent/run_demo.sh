#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt
pip install -q -e ../sdk

if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY not set"
    exit 1
fi

MODE=${1:-normal}
echo ""
echo "Running LangGraph demo in '$MODE' mode..."
echo ""

python langgraph_demo.py --mode "$MODE" "${@:2}"
