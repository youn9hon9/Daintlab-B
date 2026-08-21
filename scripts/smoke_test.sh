#!/usr/bin/env bash
set -euo pipefail

DRIVER_URL="${DRIVER_URL:-http://localhost:8000}"

curl --fail --silent --show-error "${DRIVER_URL}/v1/models" \
  | python3 -m json.tool

if [[ -n "${LUNIT_FM_API_KEY:-}" ]]; then
  curl --fail --silent --show-error \
    "${DRIVER_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "lunit-hackathon-driver",
      "messages": [
        {
          "role": "user",
          "content": "만성 신장질환 환자의 혈압 목표를 알려주세요."
        }
      ]
    }' \
    | python3 -m json.tool
else
  echo "LUNIT_FM_API_KEY is not set; skipped the live chat smoke test."
fi

