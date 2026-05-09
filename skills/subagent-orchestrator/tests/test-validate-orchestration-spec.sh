#!/usr/bin/env bash
# test-validate-orchestration-spec.sh — Acceptance tests for validate-orchestration-spec.sh

set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$(cd "$SCRIPT_DIR/.." && pwd)/scripts/validate-orchestration-spec.sh"

PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1 — $2"; FAIL=$((FAIL + 1)); }

echo "=== validate-orchestration-spec Acceptance Tests ==="
echo "Script: $TARGET"
echo ""

VALID_SPEC='{
  "task_id": "test-001",
  "profiles": {
    "explorer": {
      "name": "explorer",
      "model": "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
      "agent": "explore",
      "temperature": 0.3,
      "max_tokens_default": 400,
      "memory_gb": 8.85,
      "degenerate_risk": {
        "low_temp": false,
        "long_prompt": false,
        "thinking_leak": false
      }
    }
  },
  "turns": [
    {
      "turn_number": 1,
      "profile": "explorer",
      "max_tokens": 400,
      "prompt_template": "Research: {{ topic }}",
      "requires_prior_context": false
    }
  ],
  "phase_handlers": {},
  "escalation_policy": {
    "max_retries": 2,
    "retry_temp_delta": 0.1,
    "escalate_after": 3
  }
}'

SPEC_MISSING_PROFILES='{
  "task_id": "test-002",
  "turns": []
}'

SPEC_MISSING_TURNS='{
  "task_id": "test-003",
  "profiles": {}
}'

SPEC_TURN_REF_MISSING_PROFILE='{
  "task_id": "test-004",
  "profiles": {
    "explorer": {
      "name": "explorer",
      "model": "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
      "agent": "explore",
      "temperature": 0.3,
      "max_tokens_default": 400,
      "memory_gb": 8.85,
      "degenerate_risk": {
        "low_temp": false,
        "long_prompt": false,
        "thinking_leak": false
      }
    }
  },
  "turns": [
    {
      "turn_number": 1,
      "profile": "nonexistent",
      "max_tokens": 400,
      "prompt_template": "test",
      "requires_prior_context": false
    }
  ]
}'

SPEC_NO_DEGENERATE_RISK='{
  "task_id": "test-005",
  "profiles": {
    "explorer": {
      "name": "explorer",
      "model": "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
      "agent": "explore",
      "temperature": 0.3,
      "max_tokens_default": 400,
      "memory_gb": 8.85
    }
  },
  "turns": [
    {
      "turn_number": 1,
      "profile": "explorer",
      "max_tokens": 400,
      "prompt_template": "test",
      "requires_prior_context": false
    }
  ]
}'

MALFORMED_JSON='{ task_id: "bad"'

PLAIN_TEXT="this is not json or yaml"

EMPTY=""

# --- AC1: Valid spec file → exit 0, output OK ---
VALID_FILE=$(mktemp)
echo "$VALID_SPEC" > "$VALID_FILE"
output=$(bash "$TARGET" "$VALID_FILE" 2>&1)
status=$?
if [[ $status -eq 0 ]]; then
  pass "AC1: exits 0 for valid spec file"
else
  fail "AC1: exit code" "expected 0, got $status"
fi
rm -f "$VALID_FILE"

# --- AC2: Valid spec via stdin → exit 0, output OK ---
output=$(echo "$VALID_SPEC" | bash "$TARGET" 2>&1)
status=$?
if [[ $status -eq 0 ]]; then
  pass "AC2: exits 0 for valid spec via stdin"
else
  fail "AC2: exit code" "expected 0, got $status"
fi

# --- AC3: Missing profiles → exit 1, error list ---
output=$(echo "$SPEC_MISSING_PROFILES" | bash "$TARGET" 2>&1)
status=$?
if [[ $status -eq 1 ]]; then
  pass "AC3: exits 1 for missing profiles"
else
  fail "AC3: exit code" "expected 1, got $status"
fi
if echo "$output" | grep -qi "profile" 2>/dev/null; then
  pass "AC3: error output mentions profiles"
else
  fail "AC3: error output" "expected mention of profiles in: $output"
fi

# --- AC4: Missing turns → exit 1, error list ---
output=$(echo "$SPEC_MISSING_TURNS" | bash "$TARGET" 2>&1)
status=$?
if [[ $status -eq 1 ]]; then
  pass "AC4: exits 1 for missing turns"
else
  fail "AC4: exit code" "expected 1, got $status"
fi
if echo "$output" | grep -qi "turn" 2>/dev/null; then
  pass "AC4: error output mentions turns"
else
  fail "AC4: error output" "expected mention of turns in: $output"
fi

# --- AC5: Non-JSON/YAML input → exit 2 ---
output=$(echo "$PLAIN_TEXT" | bash "$TARGET" 2>&1)
status=$?
if [[ $status -eq 2 ]]; then
  pass "AC5: exits 2 for non-JSON/YAML input"
else
  fail "AC5: exit code" "expected 2, got $status"
fi

# --- AC6: Empty input → exit 2 or 1 ---
output=$(echo "$EMPTY" | bash "$TARGET" 2>&1)
status=$?
if [[ $status -eq 2 || $status -eq 1 ]]; then
  pass "AC6: exits non-zero (2 or 1) for empty input, got $status"
else
  fail "AC6: exit code" "expected 2 or 1, got $status"
fi

# --- AC7: Malformed JSON → exit 2 ---
output=$(echo "$MALFORMED_JSON" | bash "$TARGET" 2>&1)
status=$?
if [[ $status -eq 2 ]]; then
  pass "AC7: exits 2 for malformed JSON"
else
  fail "AC7: exit code" "expected 2, got $status"
fi

# --- AC8: Turn references non-existent profile → exit 1 ---
output=$(echo "$SPEC_TURN_REF_MISSING_PROFILE" | bash "$TARGET" 2>&1)
status=$?
if [[ $status -eq 1 ]]; then
  pass "AC8: exits 1 for turn referencing non-existent profile"
else
  fail "AC8: exit code" "expected 1, got $status"
fi

# --- AC9: Profile missing degenerate_risk → exit 10 ---
output=$(echo "$SPEC_NO_DEGENERATE_RISK" | bash "$TARGET" 2>&1)
status=$?
if [[ $status -eq 10 ]]; then
  pass "AC9: exits 10 for profile missing degenerate_risk"
else
  fail "AC9: exit code" "expected 10, got $status -- NOTE: script may not exist yet (red state)"
fi

# --- AC10: Nonexistent file argument → exit 2 ---
output=$(bash "$TARGET" /tmp/nonexistent-file-12345.yaml 2>&1)
status=$?
if [[ $status -ne 0 ]]; then
  pass "AC10: exits non-zero for nonexistent file (got $status)"
else
  fail "AC10: exit code" "expected non-zero, got $status"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
