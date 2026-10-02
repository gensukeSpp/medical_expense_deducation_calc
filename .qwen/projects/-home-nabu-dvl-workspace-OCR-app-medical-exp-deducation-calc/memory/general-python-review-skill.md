---
name: general-python-review-skill
description: 2026-07-27 — PRレビューから抽出した30の汎用Python教訓をサブエージェントスキル化
type: project
---

## Python 汎用レビューチェックリストスキル

2026-07-27、クローズされた全PR（#2〜#35）のレビューコメントを分析し、プロジェクトに依存しない汎用的なPython品質項目を `auto-skill-python-review-checklist` スキルとして登録した。

**30項目を9カテゴリに分類**:
- A: リソース管理（3項目）
- B: 辞書・Optional安全アクセス（3項目）
- C: 入力バリデーション・防御的プログラミング（3項目）
- D: パフォーマンス・冗長処理排除（5項目）
- E: 命名・一意性（2項目）
- F: フレームワーク特有の落とし穴（4項目）
- G: テキスト比較・正規化（2項目）
- H: エラーハンドリング・デバッグ（3項目）
- I: アーキテクチャ・設計（5項目）

**Why**: 過去のレビューで同じパターンの指摘が繰り返されていたため。スキル化することで、レビュー時に自動的に探索・指摘できるようにする。

**How to apply**: コードレビュー時に `skill("auto-skill-python-review-checklist")` を呼び出す。対象ファイルを指定する場合は `skill("auto-skill-python-review-checklist", args="path/to/file.py")` と引数で渡す。出力はカテゴリ別の問題レポートとして得られる。