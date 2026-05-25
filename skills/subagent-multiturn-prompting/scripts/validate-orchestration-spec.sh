#!/usr/bin/env bash
set -uo pipefail

INPUT=""
ERR_FILE=$(mktemp)
trap "rm -f '$ERR_FILE'" EXIT

if [[ $# -ge 1 ]]; then
  if [[ ! -f "$1" ]]; then
    echo "[]" >&2
    exit 2
  fi
  INPUT=$(<"$1")
else
  INPUT=$(cat)
fi

if [[ -z "${INPUT// }" ]]; then
  echo "[]" >&2
  exit 2
fi

python3 - "$INPUT" "$ERR_FILE" << 'PYEOF'
import sys, json

try:
  spec = json.loads(sys.argv[1])
except json.JSONDecodeError:
  errs = json.dumps([{"field": "", "error": "not valid JSON or YAML"}])
  with open(sys.argv[2], 'w') as f:
    f.write(errs)
  sys.exit(2)

errors = []

if not isinstance(spec, dict):
  errors.append({"field": "root", "error": "spec must be a JSON object"})

if "task_id" not in spec:
  errors.append({"field": "task_id", "error": "missing required field"})

if "profiles" not in spec or not isinstance(spec.get("profiles"), dict) or len(spec.get("profiles", {})) == 0:
  errors.append({"field": "profiles", "error": "missing or empty profiles"})
elif "profiles" in spec:
  missing_risk_profiles = []
  for name, prof in spec["profiles"].items():
    if not isinstance(prof, dict):
      errors.append({"field": f"profiles.{name}", "error": "profile must be an object"})
      continue
    required = ["name", "model", "agent", "temperature", "max_tokens_default", "memory_gb"]
    for key in required:
      if key not in prof:
        errors.append({"field": f"profiles.{name}.{key}", "error": f"missing required field '{key}'"})
    if "degenerate_risk" not in prof or not isinstance(prof.get("degenerate_risk"), dict):
      missing_risk_profiles.append(name)
    else:
      risk_fields = ["low_temp", "long_prompt", "thinking_leak"]
      for key in risk_fields:
        if key not in prof["degenerate_risk"]:
          errors.append({"field": f"profiles.{name}.degenerate_risk.{key}", "error": f"missing degenerate_risk field '{key}'"})
  if missing_risk_profiles:
    errs = json.dumps([{"field": f"profiles.{p}", "error": "missing degenerate_risk"} for p in missing_risk_profiles], indent=2)
    with open(sys.argv[2], 'w') as f:
      f.write(errs)
    sys.exit(10)

if "turns" not in spec or not isinstance(spec.get("turns"), list):
  errors.append({"field": "turns", "error": "missing turns array"})
elif "turns" in spec and "profiles" in spec and isinstance(spec.get("profiles"), dict):
  profile_names = set(spec["profiles"].keys())
  for t in spec.get("turns", []):
    if not isinstance(t, dict):
      errors.append({"field": "turns", "error": "turn must be an object"})
      continue
    turn_num = t.get("turn_number", "?")
    if "profile" in t and t["profile"] not in profile_names:
      errors.append({"field": f"turns[{turn_num}].profile", "error": f"profile '{t['profile']}' not found in profiles"})

err_json = json.dumps(errors, indent=2)
with open(sys.argv[2], 'w') as f:
  f.write(err_json)

if errors:
  sys.exit(1)

print("OK")
sys.exit(0)
PYEOF

STATUS=$?
cat "$ERR_FILE" >&2
exit $STATUS
