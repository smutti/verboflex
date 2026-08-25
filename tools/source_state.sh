#!/usr/bin/env bash
set -euo pipefail

readonly SOURCE_STATE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
readonly DEFAULT_ROOT=$(CDPATH= cd -- "$SOURCE_STATE_DIR/.." && pwd)
readonly DEFAULT_MANIFEST="tools/source_manifest.txt"
readonly REVIEW_PATH="docs/reviews/phase-01-code-security.md"
readonly DIGEST_RECORD="${VERBOFLEX_GAUNTLET_DIGEST_FILE:-/tmp/verboflex-phase01-gauntlet.digest}"

die() {
  printf 'source-state error: %s\n' "$1" >&2
  exit 1
}

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

parse_manifest() {
  local root=$1
  local manifest_path=$2
  local include_rules=$3
  local exclude_rules=$4
  local line_number=0
  local directive category pathspec reason extra

  : >"$include_rules"
  : >"$exclude_rules"
  [ -f "$root/$manifest_path" ] || die "manifest target is missing: $manifest_path"

  while IFS='|' read -r directive category pathspec reason extra || [ -n "${directive:-}" ]; do
    line_number=$((line_number + 1))
    case "${directive:-}" in
      ''|'#'*) continue ;;
    esac
    [ -z "${extra:-}" ] || die "manifest parser error at line $line_number: too many fields"
    case "$directive" in
      include)
        [ -n "${category:-}" ] || die "manifest parser error at line $line_number: empty category"
        [ -n "${pathspec:-}" ] || die "manifest parser error at line $line_number: empty pathspec"
        [ -z "${reason:-}" ] || die "manifest parser error at line $line_number: include reason is not allowed"
        printf '%s|%s\n' "$category" "$pathspec" >>"$include_rules"
        ;;
      exclude)
        [ "$category" = "artifact" ] || die "manifest parser error at line $line_number: exclusions use artifact category"
        [ -n "${pathspec:-}" ] || die "manifest parser error at line $line_number: empty pathspec"
        [ -n "${reason:-}" ] || die "manifest parser error at line $line_number: exclusion reason is required"
        printf '%s\n' "$pathspec" >>"$exclude_rules"
        ;;
      *) die "manifest parser error at line $line_number: unknown directive $directive" ;;
    esac
  done <"$root/$manifest_path"

  [ -s "$include_rules" ] || die "manifest parser error: no include rules"
}

resolve_manifest() {
  local root=$1
  local manifest_path=$2
  local mode=$3
  local destination=$4
  local scratch include_rules exclude_rules included_candidates excluded_paths rule_matches
  local category pathspec path required

  scratch=$(mktemp -d)
  include_rules="$scratch/include-rules"
  exclude_rules="$scratch/exclude-rules"
  included_candidates="$scratch/included-candidates"
  excluded_paths="$scratch/excluded-paths"
  rule_matches="$scratch/rule-matches"
  parse_manifest "$root" "$manifest_path" "$include_rules" "$exclude_rules"
  git -C "$root" rev-parse --is-inside-work-tree >/dev/null || die "root is not a Git work tree: $root"
  : >"$included_candidates"
  : >"$excluded_paths"

  while IFS='|' read -r category pathspec; do
    git -C "$root" ls-files --cached --others --exclude-standard -- "$pathspec" >"$rule_matches"
    [ -s "$rule_matches" ] || die "include rule is empty: $category ($pathspec)"
    while IFS= read -r path; do
      [ -n "$path" ] && printf '%s|%s\n' "$category" "$path" >>"$included_candidates"
    done <"$rule_matches"
  done <"$include_rules"

  while IFS= read -r pathspec; do
    while IFS= read -r path; do
      [ -n "$path" ] && printf '%s\n' "$path" >>"$excluded_paths"
    done < <(git -C "$root" ls-files --cached --others --exclude-standard -- "$pathspec")
  done <"$exclude_rules"
  sort -u "$excluded_paths" -o "$excluded_paths"

  if [ -s "$excluded_paths" ]; then
    awk -F '|' 'NR==FNR { excluded[$0]=1; next } !excluded[$2] { print }' \
      "$excluded_paths" "$included_candidates" | sort -u >"$destination"
  else
    sort -u "$included_candidates" >"$destination"
  fi

  for required in implementation tests config lockfiles migrations verifier-scripts review; do
    if [ "$mode" = "review" ] && [ "$required" = "review" ]; then
      continue
    fi
    awk -F '|' -v required="$required" '$1 == required { found=1 } END { exit found ? 0 : 1 }' \
      "$destination" || die "required category is empty: $required"
  done

  if [ "$mode" = "review" ]; then
    awk -F '|' -v review="$REVIEW_PATH" '$2 != review { print }' "$destination" >"$scratch/no-review"
    cp "$scratch/no-review" "$destination"
  fi
  rm -rf "$scratch"
}

assert_clean_paths() {
  local root=$1
  local resolved=$2
  local path tracked_rc diff_rc paths_file
  paths_file=$(mktemp)
  cut -d '|' -f2 "$resolved" | sort -u >"$paths_file"

  while IFS= read -r path; do
    [ -f "$root/$path" ] || die "included source is missing: $path"
    set +e
    git -C "$root" ls-files --error-unmatch -- "$path" >/dev/null 2>&1
    tracked_rc=$?
    set -e
    case "$tracked_rc" in
      0) ;;
      1) die "included source is untracked: $path" ;;
      *) die "Git tracking check failed for: $path" ;;
    esac

    set +e
    git -C "$root" diff --quiet -- "$path"
    diff_rc=$?
    set -e
    case "$diff_rc" in
      0) ;;
      1) die "included source has unstaged changes: $path" ;;
      *) die "Git unstaged-diff check failed for: $path" ;;
    esac

    set +e
    git -C "$root" diff --cached --quiet -- "$path"
    diff_rc=$?
    set -e
    case "$diff_rc" in
      0) ;;
      1) die "included source has staged changes: $path" ;;
      *) die "Git staged-diff check failed for: $path" ;;
    esac
  done <"$paths_file"
  rm -f "$paths_file"
}

compute_digest() {
  local root=$1
  local manifest_path=$2
  local mode=$3
  local resolved paths_file path file_digest
  resolved=$(mktemp)
  paths_file=$(mktemp)
  resolve_manifest "$root" "$manifest_path" "$mode" "$resolved"
  assert_clean_paths "$root" "$resolved"
  cut -d '|' -f2 "$resolved" | sort -u >"$paths_file"
  while IFS= read -r path; do
    file_digest=$(sha256_file "$root/$path")
    printf '%s\0%s\0' "$path" "$file_digest"
  done <"$paths_file" | shasum -a 256 | awk '{print $1}'
  rm -f "$resolved" "$paths_file"
}

verify_digest_value() {
  local expected=$1
  local actual=$2
  [ "$expected" = "$actual" ] || die "source digest changed: expected $expected, got $actual"
}

extract_markdown_value() {
  local file=$1
  local label=$2
  local value
  value=$(sed -n "s/^- ${label}: \\`\\([0-9a-f][0-9a-f]*\\)\\`$/\\1/p" "$file")
  [ "$(printf '%s\n' "$value" | sed '/^$/d' | wc -l | tr -d ' ')" = "1" ] \
    || die "expected exactly one $label value in ${file#$DEFAULT_ROOT/}"
  printf '%s\n' "$value"
}

expect_failure() {
  local expected_text=$1
  shift
  local output_file rc
  output_file=$(mktemp)
  set +e
  ("$@") >"$output_file" 2>&1
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    rm -f "$output_file"
    die "negative control unexpectedly passed: $expected_text"
  fi
  if ! grep -Fq "$expected_text" "$output_file"; then
    sed -n '1,80p' "$output_file" >&2
    rm -f "$output_file"
    die "negative control failed for the wrong reason: $expected_text"
  fi
  rm -f "$output_file"
}

self_test_manifest() {
  local fixture manifest baseline digest path
  fixture=$(mktemp -d)
  trap "rm -rf '$fixture'" EXIT
  git -C "$fixture" init -q
  git -C "$fixture" config user.email source-state@example.invalid
  git -C "$fixture" config user.name source-state-self-test
  mkdir -p "$fixture/app" "$fixture/tests" "$fixture/config" "$fixture/locks" \
    "$fixture/migrations" "$fixture/tools" "$fixture/docs/reviews" "$fixture/reports"
  manifest="$fixture/tools/source_manifest.txt"
  printf '%s\n' \
    'include|implementation|:(glob)app/**' \
    'include|tests|:(glob)tests/**' \
    'include|config|:(glob)config/**' \
    'include|lockfiles|:(glob)locks/**' \
    'include|migrations|:(glob)migrations/**' \
    'include|verifier-scripts|:(glob)tools/**' \
    'include|review|docs/reviews/phase-01-code-security.md' \
    'exclude|artifact|:(glob)reports/**|raw reports are outside the source set' >"$manifest"
  printf 'implementation\n' >"$fixture/app/main.txt"
  printf 'test\n' >"$fixture/tests/test.txt"
  printf 'config\n' >"$fixture/config/app.conf"
  printf 'lock\n' >"$fixture/locks/deps.lock"
  printf 'migration\n' >"$fixture/migrations/001.sql"
  printf 'review\n' >"$fixture/docs/reviews/phase-01-code-security.md"
  printf 'raw report\n' >"$fixture/reports/run.log"
  git -C "$fixture" add app/main.txt tests/test.txt config/app.conf locks/deps.lock \
    migrations/001.sql tools/source_manifest.txt docs/reviews/phase-01-code-security.md reports/run.log
  git -C "$fixture" commit -qm fixture

  baseline=$(compute_digest "$fixture" tools/source_manifest.txt final)
  [ "${#baseline}" -eq 64 ] || die "positive control did not produce a SHA-256 digest"

  digest=$(compute_digest "$fixture" tools/source_manifest.txt review)
  printf '%s\n' \
    '- Review-status: CLOSED' \
    '- Open-critical-high: 0' \
    "- Reviewed-source-digest: \`$digest\`" >"$fixture/docs/reviews/phase-01-code-security.md"
  verify_review_contract "$fixture/docs/reviews/phase-01-code-security.md" "$digest"
  sed 's/Review-status: CLOSED/Review-status: OPEN/' \
    "$fixture/docs/reviews/phase-01-code-security.md" >"$fixture/open-review.md"
  expect_failure 'review status is not CLOSED' \
    verify_review_contract "$fixture/open-review.md" "$digest"
  sed 's/Open-critical-high: 0/Open-critical-high: 1/' \
    "$fixture/docs/reviews/phase-01-code-security.md" >"$fixture/nonzero-review.md"
  expect_failure 'review has unresolved critical/high findings' \
    verify_review_contract "$fixture/nonzero-review.md" "$digest"
  printf '%s\n' '- Review-status: OPEN' >>"$fixture/docs/reviews/phase-01-code-security.md"
  expect_failure 'expected exactly one Review-status value' \
    verify_review_contract "$fixture/docs/reviews/phase-01-code-security.md" "$digest"
  expect_failure 'review artifact is missing' \
    verify_review_contract "$fixture/missing-review.md" "$digest"

  {
    cat "$manifest"
    printf 'include|implementation|:(glob)missing-implementation/**\n'
  } >"$fixture/empty-include-rule-manifest.txt"
  expect_failure 'include rule is empty: implementation' \
    compute_digest "$fixture" empty-include-rule-manifest.txt final

  sed 's#:(glob)reports/\*\*#:(glob)absent-artifacts/**#' \
    "$manifest" >"$fixture/empty-exclusion-manifest.txt"
  digest=$(compute_digest "$fixture" empty-exclusion-manifest.txt final)
  [ "${#digest}" -eq 64 ] || die "empty exclusion set removed included source"

  for path in app/main.txt tests/test.txt config/app.conf locks/deps.lock migrations/001.sql \
    tools/source_manifest.txt docs/reviews/phase-01-code-security.md; do
    if [ "$path" = "tools/source_manifest.txt" ]; then
      printf '# changed manifest comment\n' >>"$fixture/$path"
    else
      printf 'changed\n' >>"$fixture/$path"
    fi
    expect_failure "included source has unstaged changes: $path" \
      compute_digest "$fixture" tools/source_manifest.txt final
    git -C "$fixture" restore -- "$path"
  done

  printf 'excluded change\n' >>"$fixture/reports/run.log"
  digest=$(compute_digest "$fixture" tools/source_manifest.txt final)
  verify_digest_value "$baseline" "$digest"
  git -C "$fixture" restore -- reports/run.log

  rm "$fixture/app/main.txt"
  expect_failure 'included source is missing: app/main.txt' \
    compute_digest "$fixture" tools/source_manifest.txt final
  git -C "$fixture" restore -- app/main.txt

  sed 's#:(glob)tests/\*\*#:(glob)missing-tests/**#' "$manifest" >"$fixture/config/empty-manifest.txt"
  git -C "$fixture" add config/empty-manifest.txt
  git -C "$fixture" commit -qm empty-category-fixture
  expect_failure 'include rule is empty: tests' \
    compute_digest "$fixture" config/empty-manifest.txt final

  printf 'unknown|implementation|app/main.txt\n' >"$fixture/config/bad-manifest.txt"
  git -C "$fixture" add config/bad-manifest.txt
  git -C "$fixture" commit -qm parser-fixture
  expect_failure 'manifest parser error' \
    compute_digest "$fixture" config/bad-manifest.txt final

  printf 'source manifest self-test: PASS\n'
}

usage() {
  printf '%s\n' \
    'usage: tools/source_state.sh --digest | --review-digest | --self-test-manifest' \
    '       tools/source_state.sh --verify-review-closed | --verify-review-source' \
    '       tools/source_state.sh --verify-final-before-report | --verify-report-digest'
}

command=${1:-}
case "$command" in
  --digest)
    compute_digest "$DEFAULT_ROOT" "$DEFAULT_MANIFEST" final
    ;;
  --review-digest)
    compute_digest "$DEFAULT_ROOT" "$DEFAULT_MANIFEST" review
    ;;
  --self-test-manifest)
    self_test_manifest
    ;;
  --verify-review-closed)
    [ -f "$DEFAULT_ROOT/$REVIEW_PATH" ] || die "review artifact is missing: $REVIEW_PATH"
    grep -Fxq -- '- Review-status: CLOSED' "$DEFAULT_ROOT/$REVIEW_PATH" \
      || die "review status is not CLOSED"
    grep -Fxq -- '- Open-critical-high: 0' "$DEFAULT_ROOT/$REVIEW_PATH" \
      || die "review has unresolved critical/high findings"
    ;;
  --verify-review-source)
    [ -f "$DEFAULT_ROOT/$REVIEW_PATH" ] || die "review artifact is missing: $REVIEW_PATH"
    expected=$(extract_markdown_value "$DEFAULT_ROOT/$REVIEW_PATH" 'Reviewed-source-digest')
    actual=$(compute_digest "$DEFAULT_ROOT" "$DEFAULT_MANIFEST" review)
    verify_digest_value "$expected" "$actual"
    ;;
  --verify-final-before-report)
    [ -f "$DIGEST_RECORD" ] || die "gauntlet digest record is missing: $DIGEST_RECORD"
    expected=$(sed -n '1p' "$DIGEST_RECORD")
    [ "${#expected}" -eq 64 ] || die "gauntlet digest record is malformed"
    actual=$(compute_digest "$DEFAULT_ROOT" "$DEFAULT_MANIFEST" final)
    verify_digest_value "$expected" "$actual"
    ;;
  --verify-report-digest)
    report="$DEFAULT_ROOT/docs/evidence/phase-01.md"
    [ -f "$report" ] || die "evidence report is missing: docs/evidence/phase-01.md"
    expected=$(extract_markdown_value "$report" 'Source-digest')
    actual=$(compute_digest "$DEFAULT_ROOT" "$DEFAULT_MANIFEST" final)
    verify_digest_value "$expected" "$actual"
    ;;
  -h|--help) usage ;;
  *) usage >&2; exit 64 ;;
esac
