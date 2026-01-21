#!/bin/bash
# Import all 84 MAST workflows to n8n Cloud

N8N_BASE="https://pisama.app.n8n.cloud/api/v1/workflows"

if [ -z "$N8N_API_KEY" ]; then
    echo "Error: N8N_API_KEY environment variable is required"
    echo ""
    echo "Usage:"
    echo "  export N8N_API_KEY='your-api-key'"
    echo "  ./scripts/import-workflows-to-n8n.sh"
    echo ""
    echo "Get your API key from: n8n Cloud → Settings → API"
    exit 1
fi

echo "Importing MAST workflows to n8n Cloud..."
echo "========================================="

count=0
success=0
failed=0

for category in loop state persona coordination resource; do
    echo ""
    echo "Category: $category"
    echo "-------------------"

    for file in n8n-workflows/$category/*.json; do
        name=$(basename "$file" .json)
        count=$((count + 1))
        echo -n "  [$count] $name... "

        # Import workflow via API
        response=$(curl -s -o /tmp/n8n_response.json -w "%{http_code}" \
            -X POST "$N8N_BASE" \
            -H "X-N8N-API-KEY: $N8N_API_KEY" \
            -H "Content-Type: application/json" \
            -d @"$file" 2>/dev/null)

        if [ "$response" = "200" ] || [ "$response" = "201" ]; then
            echo "OK"
            success=$((success + 1))
        else
            error=$(cat /tmp/n8n_response.json 2>/dev/null | grep -o '"message":"[^"]*"' | head -1)
            echo "FAILED ($response) $error"
            failed=$((failed + 1))
        fi

        # Small delay to avoid rate limiting
        sleep 0.3
    done
done

echo ""
echo "========================================="
echo "Total: $count workflows"
echo "Success: $success"
echo "Failed: $failed"
echo "========================================="

if [ $success -gt 0 ]; then
    echo ""
    echo "Next: Activate workflows in n8n Cloud dashboard"
    echo "Or run: ./scripts/trigger-all-workflows.sh"
fi
