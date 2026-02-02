#!/bin/bash

echo "TextGrid to JSON Converter API - CURL Tests"
echo "=========================================="
echo ""

# Base URL
BASE_URL="http://localhost:5000"

echo "1. Health Check:"
echo "----------------"
curl -X GET "$BASE_URL/health"
echo ""
echo ""

echo "2. API Information:"
echo "------------------"
curl -X GET "$BASE_URL/"
echo ""
echo ""

echo "3. Convert TextGrid File (Upload):"
echo "---------------------------------"
echo "Note: Replace 'chunk_0.TextGrid' with your actual file path"
curl -X POST \
  -F "file=@/Volumes/akshar_data/demo/data/chunk_0/chunk_0.TextGrid" \
  -F "audio_id=test_audio_001" \
  "$BASE_URL/convert"
echo ""
echo ""

echo "4. Convert Local TextGrid File (Debug):"
echo "--------------------------------------"
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "filepath": "/Volumes/akshar_data/demo/data/chunk_0/chunk_0.TextGrid",
    "audio_id": "debug_audio_001"
  }' \
  "$BASE_URL/convert/local"
echo ""
echo ""

echo "5. Test with invalid file (should fail):"
echo "----------------------------------------"
curl -X POST \
  -F "file=@/nonexistent.txt" \
  "$BASE_URL/convert"
echo ""
echo ""

echo "Testing complete!"
