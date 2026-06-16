---
name: architecture-update
description: "docs/architecture/ にスナップショットを追加し、目次自動更新スクリプトを追加。docs/architecture/README.md から差分をチェックし、Draft PR を自動生成する。Use when: Update architecture documentation."
---

# Agent skill: update-architecture-snapshots

目的: 変更されたソースコード差分を確認し、docs/architecture/ にスナップショットを追加したうえで、目次自動更新スクリプトを実行して（必要に応じて Draft PR を作成する）処理を自動化するエージェントスキル。

実行手順 (エージェントが実行する内容):
1. ベースブランチと現在ブランチの差分を取得する（例: git fetch origin && git diff --name-only origin/main...HEAD）。
2. 差分にソースコード変更が含まれていれば、スナップショットファイルを生成して docs/architecture/ に追加する。ファイル名は YYYY-MM-DD-architecture.md の形式とし、変更されたコミット摘要と変更ファイル一覧を含めるテンプレートを使用する。
3. 生成したスナップショットと（必要なら）README の更新をコミットする。ブランチ作成・PR 作成の挙動は下記実行コマンドに委ねる。
4. 目次自動更新スクリプトを実行する: .github/skills/architecture-update/scripts/copilot_update_arch.sh --pr --draft

期待される副作用:
- docs/architecture/ に新しい snapshot ファイルが追加される。
- docs/architecture/README.md が更新され、差分があれば新しいブランチが作られ Draft PR が作成される（スクリプトの --pr --draft フラグに依存）。

実行例（ローカル）:
# ベース更新を取り込む
git fetch origin
# エージェントのロジック（差分がある場合のみスナップショット追加）を実行
# (エージェントが自動で snapshot を作成した後)
.github/skills/architecture-update/scripts/copilot_update_arch.sh --pr --draft

注意:
- snapshot の本文は自動生成される概要に加え、レビュワーが手動で補足・編集する前提とする。
- ブランチ名や PR のターゲット（ここでは main を想定）は必要に応じて調整する。

Use when: Run after making code changes that affect architecture and want to capture a snapshot plus update the architecture index and create a draft PR.
