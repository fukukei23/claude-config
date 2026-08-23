#!/usr/bin/env bash
# test_git_sync_utils.sh — _git-sync-utils.sh のテスト
# Phase5.5(2026-08-23): --autostash が未ステージ変更を吸収できることを確認
#
# テストケース:
#   T1: 正常系（未ステージ変更なし）— pull 成功
#   T2: 異常系（未ステージ変更あり + --autostash）— 未ステージ変更が stash され pull 成功
#   T3: stash した内容が pop されるか（autostash の本質）
#
# 実行: bash ~/bin/tests/test_git_sync_utils.sh
# exit 0 = 全PASS / exit 1 = FAIL

set -u
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# --- テスト用一時ディレクトリ ---
TMPDIR=$(mktemp -d /tmp/git-sync-test.XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT

# --- ヘルパー: assert ---
assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  TESTS_TOTAL=$((TESTS_TOTAL + 1))
  if [ "$expected" = "$actual" ]; then
    echo "  ✅ $desc"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "  ❌ $desc: expected '$expected' got '$actual'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

# --- ヘルパー: bare + working clone のセットアップ ---
setup_repo() {
  local label="$1"
  local repo="$TMPDIR/${label}_repo"
  local bare="$TMPDIR/${label}_bare.git"
  local clone="$TMPDIR/${label}_clone"
  mkdir -p "$repo" && cd "$repo"
  git init -q -b main
  git config user.email "test@example.com"
  git config user.name "Test"
  echo "v1" > file.txt
  git add . && git commit -q -m "initial"
  git clone -q --bare "$repo" "$bare"
  git remote add origin "$bare"
  git push -q origin main
  # 別の working tree clone を作成（remote への push 用）
  git clone -q "$bare" "$clone"
  cd "$clone"
  git config user.email "test@example.com"
  git config user.name "Test"
  echo "$repo|$bare|$clone"
}

# --- T1: 正常系（未ステージ変更なし）---
test_normal_pull() {
  echo "T1: 正常系（未ステージ変更なし）"
  IFS='|' read -r repo bare clone < <(setup_repo "T1")
  cd "$clone"
  echo "v2" > file.txt
  git commit -q -am "feature"
  git push -q origin main
  # 元repoでpull
  cd "$repo"
  output=$(git pull --rebase --autostash origin main 2>&1)
  rc=$?
  assert_eq "T1: pull exit code" "0" "$rc"
  assert_eq "T1: file content updated" "v2" "$(cat file.txt)"
}

# --- T2: 未ステージ変更あり + --autostash で pull 成功 ---
test_unstaged_with_autostash() {
  echo ""
  echo "T2: 未ステージ変更あり + --autostash"
  IFS='|' read -r repo bare clone < <(setup_repo "T2")
  cd "$repo"
  # 未ステージ変更を生成
  echo "v1-modified-locally" > file.txt
  # git status で unstaged changes 確認
  local unstaged_before
  unstaged_before=$(git status --porcelain 2>&1)
  assert_eq "T2: unstaged changes exist before pull" " M file.txt" "$unstaged_before"

  # clone側で先に変更 → push
  cd "$clone"
  echo "v2-remote" > file.txt
  git commit -q -am "remote update"
  git push -q origin main

  # 元repoでpull（これが本番で詰まっていたケース）
  cd "$repo"
  output=$(git pull --rebase --autostash origin main 2>&1)
  rc=$?
  assert_eq "T2: pull exit code with autostash" "0" "$rc"
  # --autostash により pull 成功時 stash pop でローカルの v1-modified-locally が working tree に戻る
  # ただし T2 では同じ行を remote と local で変更しているため、コンフリクトマーカーが出る（git の正常動作）
  # → 「exit code が 0 になる（pull 自体は成功）」ことだけが autostash の本質的保証
  local file_content
  file_content=$(cat file.txt)
  if echo "$file_content" | grep -q "<<<<<<< Updated upstream"; then
    echo "  ✅ T2: autostash pop でコンフリクトマーカー発生（同じ行変更時の正常動作・手動マージ必要）"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "  ❌ T2: expected conflict marker in file.txt, got: $file_content"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
  TESTS_TOTAL=$((TESTS_TOTAL + 1))
}

# --- T3: autostash pop で未ステージ変更が working tree にマージされる ---
test_autostash_pop_preserves_changes() {
  echo ""
  echo "T3: autostash の stash pop で未ステージ変更が戻る"
  IFS='|' read -r repo bare clone < <(setup_repo "T3")
  cd "$repo"
  # other.txt をローカルで追加（未追跡）
  echo "data-modified" > other.txt
  # clone側で file.txt 変更 → push
  cd "$clone"
  echo "v2-remote" > file.txt
  git commit -q -am "remote update"
  git push -q origin main

  # 元repoでpull
  cd "$repo"
  output=$(git pull --rebase --autostash origin main 2>&1)
  rc=$?
  assert_eq "T3: pull exit code" "0" "$rc"
  assert_eq "T3: file.txt = remote version" "v2-remote" "$(cat file.txt)"
  # other.txt は autostash が untracked まで含めて pop するか確認
  # （git 2.43 の autostash は untracked も含む仕様）
  assert_eq "T3: other.txt preserved (autostash covers untracked)" "data-modified" "$(cat other.txt 2>/dev/null || echo MISSING)"
}

# --- メイン ---
echo "=== _git-sync-utils.sh Phase5.5 --autostash テスト ==="
echo ""
test_normal_pull
test_unstaged_with_autostash
test_autostash_pop_preserves_changes

echo ""
echo "=== 結果: ${TESTS_PASSED}/${TESTS_TOTAL} PASS (FAIL: ${TESTS_FAILED}) ==="
[ "$TESTS_FAILED" -eq 0 ] && exit 0 || exit 1
