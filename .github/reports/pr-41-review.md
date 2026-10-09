# PR #41 Review — Issue #39 date 基準座標正規化 / Issue #40 基底不一致修正

## 参照資料・前提
- PR #41: `gh pr view 41` で本文・変更ファイル・コミットを確認。draft。目的はIssue #39のdate anchor導入とIssue #40のdate基準template誤上書き防止。
- Issue #39: `gh issue view 39` を確認。date座標が学習済みの場合にOCR boxをdate基準へ再正規化し、曖昧時はtopmostへfallbackする目的・受入条件を確認。
- Issue #40: `gh issue view 40` を確認。topmost rawとdate基準template間の座標照合不整合に対し、案Bの誤上書き防止を許容する内容。
- タスク計画: `tasks/issue_39/{overview.md,architecture.md,tasks.md,test_plan.md}`、`tasks/issue_40/{overview.md,architecture.md,tasks.md,test_plan.md}`を確認。双方ともPRの実装対象に対応。Issue #39の計画が期待するmigration/feedback/各処理経路検証に対し、主要な実装はあるが下記指摘あり。Issue #40のスコープはおおむね計画通り。
- 仕様: `specs/2026-10-06-spec.md`（Issue #39）と`specs/2026-10-08-spec.md`（Issue #40）を確認。加えて`.hermes/rules/coordinate-normalization.md`を確認。
- アーキテクチャ: `docs/architecture/2026-10-08-architecture.md`（Issue #39）と索引READMEを確認。Issue #40の詳細は`tasks/issue_40/architecture.md`を参照。背景として`docs/architecture/2026-10-02-architecture.md`、`tasks/issue_32/overview.md`を確認。
- Issue #39の概要に「`--input-json`でも一貫適用」とある一方、仕様・architecture・実装は`process_input_json`を無変更としており、ここは文書間の不一致。PRも仕様側の画像OCR/watcherのみの設計に従う。Issue #40は`process_input_json`を共通入口とする説明だが、date基準前方補正をスキップする処理と画像OCR/watcherでの統合は別論点。
- PR本文の旧Issue番号 `#261008` は実在する関連Issueとして解決できず（`gh issue view 261008` はnot found）。目的の根拠にはせず、明記された#39/#40と内容で評価。
- 比較対象: PR baseは`main`、ローカルに`main`がないため`origin/main...HEAD`で比較。作業ツリーの未追跡`requirements.txt`はレビュー対象外。
- 知識グラフ: `review(action="context", base="origin/main")`および依頼どおり`query(action="impact", changed_files=...)`を実行。グラフは古い/広範な候補を返し得るため、変更ソースとテストを確認して判断。impactは7実装ファイルから333ノード（payload内83件）・44追加ファイルを示し、広い影響範囲を示唆。

## 総評
PRの主目的は両Issueの範囲に沿っている。Issue #40のcoord_basisガードは意図どおりの防御策で、テストも追加されている。一方、Issue #39のtemplate基準移行に誤ったoffsetを用いる欠陥と、layout matchingが移行済みtemplateの座標をガード外で使う穴が確認された。前者はdate anchor機能の中心的な不整合で、修正前のマージは推奨しない。

## 良い点
- `coord_basis`追加と旧DB向けidempotent migrationを分け、template履歴保存と更新をトランザクション化している。
- date候補の曖昧性を考慮し、low-confidence時のanchorを抑止する設計で、通常のtopmost正規化へのfallbackもある。
- Issue #40の座標上書きをdate基準時にスキップし、 clinic名補正は維持する単体テストがある。
- 構造化parseの二重実行を避け、処理済みreceiptの二重登録を防ぐ方針は妥当。

## 指摘事項

### [P1] 初回anchorのoffsetがtopmost正規化後の座標から計算され、template座標変換が誤る
- 箇所: `app/date_anchor.py:191-203`
- `apply_date_anchor_normalization()`が受け取る`anchor_box`とraw boxは、画像経路ではすでに`normalize_coordinates()`によってtopmost offsetを差し引いた座標（topmost原点）である。一方、初回移行で`coords_corrections`を`shift_template_coords(coords, offset_x, offset_y)`で変換するときのoffsetは、topmost座標系でのdate位置であって、元の絶対座標系に対するdate anchor offsetではない。したがってdate templateのboxは原点に合わない。実データ同等の入力で検証すると、anchor raw左上は(0,0)になる一方、テンプレートdate左上が[-30,-20]となった（date位置(80,120)、template位置(50,100)の例）。
- 影響: 初回移行後、以降のdate基準rawとのtemplate座標がずれ、feedbackの近傍検索・座標マッチングが継続して正しい位置を参照できない。受入条件#39-4（移行後も近傍検索継続）を満たさない。
- 改善: 移行対象templateがtopmost基準ならrawと同じtopmost原点で引き算するため、offset差分（rawでanchorが持つtopmost座標）を正しく座標変換へ適用する。あわせてdate-templateの基準点が必ず(0,0)になるintegration testを、anchor位置がtopmost原点と一致しない値で追加する。

### [P1] layout matching経由ではIssue #40のdate-basisガードが適用されず、誤上書き可能
- 箇所: `app/structural_parser.py:120-157`; `app/db.py:204-234`; `app/coord_search.py:315-374`
- name完全一致/類似度でtemplateが見つからないと、`get_all_templates_with_names()`が返す全clinicのtemplateを`match_template_by_layout()`で座標照合する。しかしこのSELECT結果には`coord_basis`が含まれず、layout matchingはdate基準の座標をtopmost rawに照合する。matchしたtemplateは後段のガードで`coord_basis`が無い=topmost扱いされて、`search_fields_by_proximity()`で座標上書きされる。
- 影響: clinic名のOCR誤り等でname matchingが失敗した場面ほどlayout fallbackが使われるため、#40が防ぐべきdate/topmostの誤上書きが残る。PR本文・仕様の「date基準では座標駆動処理をスキップ」にも反する。
- 改善: `get_all_templates_with_names()`で`coord_basis`を返し、layout matching前にdate-basis templatesを除外するか、候補選定時と最終適用時の双方でその基準を保ったガードを行う。layout経由でdate templateがフィールド補正へ渡らない回帰テストを追加する。

### [P2] `parse_date()`は暦として無効な値も日付として採用する
- 箇所: `app/date_anchor.py:43-56`、日付パーサ実装`app/normalization.py:107-160`
- `parse_date()`は正規表現マッチ後、month/dayの範囲や実在日付を検証せずISO風文字列を返す（例: 2026-99-99）。新規anchor resolverがその戻り値を厳密一致とみなすので、OCRの誤認識とstructured dateが同じ無効値を返すケースでもanchorとして採用し、raw/templateを不正な基準で再正規化し得る。
- 影響: Issue #39の「信頼できる候補のみanchor」の前提が崩れ、座標データを誤移行する可能性がある。既存`parse_date()`全体を変更せずともanchor側で暦妥当性を確認可能。
- 改善: anchor採用前に`datetime.date.fromisoformat()`等で実日付として検証し、不正なら従来方式にfallbackするテスト（うるう日・月日境界を含む）を追加する。

### [P2] SQLite migrationが別々の接続で実行され、並列初期化時の競合に弱い
- 箇所: `app/db_migrations.py:43-57`
- schemaの`executescript()`後にconnectionを閉じ、別connectionで列有無確認と`ALTER TABLE`を行うため、複数プロセスが同時初期化すると両方が列なしと判定し、2つ目の`ALTER TABLE`がduplicate columnで失敗し得る。PRはidempotent migrationを要件としているが、逐次2回実行だけのテストではこの競合を検証していない。
- 影響: watcher/CLI等が初回に並行してDB初期化する構成では起動失敗になり得る。
- 改善: migrationを一つの接続・排他トランザクションで実施し、SQLiteのwrite lock取得後に列有無を確認する。必要ならduplicate-column raceを安全に再確認する。

## 改善提案
- PRにIssue #39/#40の実装、仕様、タスク計画、ドキュメント名変更が同居している。将来は機能実装と大きな文書整理・project metadata更新を分けるとレビュー範囲を追いやすい。
- `get_all_templates_with_names()`はcoord_basisを返さず、templateの他の一覧利用箇所にも影響するため、取得データ契約を更新する場合は関連consumerを検索・テストする。
- 新設した`tests/test_coord_normalizer.py`はblack `--check`で既存周辺行の整形差分が検出された（今回の追記が原因かは限定できない）。対象テスト群のblackチェックは成功扱いにせず、既存差分と今回追加行を区別して整形確認する。
- PRの主なIssue #39受入条件はanchor候補解決だけでなく、移行後のtemplate feedback・DB同期・両処理経路まで含む。実際のtemplate移行後にfeedback近傍検索が成立する統合テストを増やす。

## 検証結果
- `uv run --python 3.11 pytest tests/test_date_anchor.py tests/test_migrations.py tests/test_db.py tests/test_receipt_processor.py -q`: 48 passed。
- `uv run --python 3.11 pytest tests/test_coord_normalizer.py tests/test_structural_parser.py tests/test_image_processing_service.py -q`: 62 passed / 1 failed。失敗は`TestRunOcr.test_calls_process_image_and_logs`。
- 全体`uv run --python 3.11 pytest tests/ -q`: 229 passed / 1 failed。同じログ捕捉テストで、タスク・PR本文にも既知失敗と記載されている。baseとの同条件比較は本レビューでは実施していないため、独立にpre-existingとは断定しない。
- `uv run --python 3.11 black --check --target-version py311`の対象10ファイル: 9ファイル変更不要、`tests/test_coord_normalizer.py`は再整形を要求。diff上、追加箇所だけでなく既存テスト行の整形も出るため、失敗がPRで追加した行によるものとは断定しない。
- `uv lock --check --offline`: 成功。
- `git diff --check origin/main...HEAD`: 成功。
- template-shiftの確認スクリプトで移行後date box原点[-30,-20]を再現し、P1指摘を確認。
- 目視OCR品質検証: 実レシート画像を使った評価は未実施。

## 優先度まとめ
1. P1: 初回template基準移行でoffset座標系が誤り、date boxが(0,0)に揃わない。
2. P1: layout matching経路でdate-basis templateが引き続き照合・上書きされる。
3. P2: parse_dateの暦妥当性未検証により、無効日付がanchorになる可能性。
4. P2: 別connectionでのmigration処理が並列初期化raceに弱い。

---
> 比較対象: `origin/main...HEAD`（PR baseは`main`、ローカルmainなし）。作業ツリーの未追跡`requirements.txt`は対象外。
> 2026-10-09 レビュー記録。GitHubへのレビュー投稿は行っていない。
> 