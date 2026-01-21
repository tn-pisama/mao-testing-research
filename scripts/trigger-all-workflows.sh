#!/bin/bash
# Trigger all 84 MAST failure mode workflows once

N8N_BASE="https://pisama.app.n8n.cloud/webhook"

# Extract webhook paths from all workflow JSON files
echo "Triggering all MAST workflows..."
echo "================================"

count=0
success=0
failed=0

for category in loop state persona coordination resource; do
    echo ""
    echo "Category: $category"
    echo "-------------------"

    for file in n8n-workflows/$category/*.json; do
        # Extract the webhook path from JSON
        path=$(grep -o '"path": "[^"]*"' "$file" | head -1 | cut -d'"' -f4)

        if [ -n "$path" ]; then
            count=$((count + 1))
            echo -n "  [$count] $path... "

            # Trigger webhook with POST
            response=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$N8N_BASE/$path" 2>/dev/null)

            if [ "$response" = "200" ] || [ "$response" = "201" ] || [ "$response" = "202" ]; then
                echo "OK ($response)"
                success=$((success + 1))
            else
                echo "FAILED ($response)"
                failed=$((failed + 1))
            fi

            # Small delay to avoid rate limiting
            sleep 0.5
        fi
    done
done

echo ""
echo "================================"
echo "Total: $count workflows"
echo "Success: $success"
echo "Failed: $failed"
echo "================================"
