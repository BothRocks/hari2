#!/bin/bash
# Upload a PDF or URL to HARI

API_URL="${HARI_API_URL:-http://localhost:8000}"
API_KEY="${HARI_API_KEY:-gorgonzola}"

if [ -z "$1" ]; then
  echo "Usage: ./upload.sh <file.pdf | url>"
  echo ""
  echo "Examples:"
  echo "  ./upload.sh document.pdf"
  echo "  ./upload.sh https://example.com/article"
  exit 1
fi

INPUT="$1"

if [[ "$INPUT" == http* ]]; then
  # URL upload
  echo "Uploading URL: $INPUT"
  curl -s -X POST "$API_URL/api/documents/" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{\"url\": \"$INPUT\"}" | python3 -m json.tool
else
  # File upload
  if [ ! -f "$INPUT" ]; then
    echo "Error: File not found: $INPUT"
    exit 1
  fi
  echo "Uploading file: $INPUT"
  curl -s -X POST "$API_URL/api/documents/upload" \
    -H "X-API-Key: $API_KEY" \
    -F "file=@$INPUT" | python3 -m json.tool
fi
