Short summary
- main.py is concise and mostly correct for a small CLI entrypoint; it follows project conventions (CPU-first, PaddleOCR lang="japan").
- Risks: missing directory creation for processed/failed paths, weak error/log handling, and a few robustness issues that can cause runtime failures on edge cases.

Findings and suggestions

1) Missing creation of processed/failed directories (High)
- Location: lines ~49-51
- Problem: processed_dir and failed_dir are assigned but never mkdir'd. Any code that moves files into them will fail.
- Suggestion/patch:
  Add mkdir calls after assignment.
  Patch:
  +    processed_dir = Path(args.processed_dir)
  +    processed_dir.mkdir(parents=True, exist_ok=True)
  +    failed_dir = Path(args.failed_dir)
  +    failed_dir.mkdir(parents=True, exist_ok=True)

2) Weak error reporting (Medium)
- Location: lines 86-91
- Problem: Exception caught and printed, losing stacktrace/context. Prints used throughout make debugging harder.
- Suggestion: use logging and logging.exception to capture tracebacks; return non-zero exit status on fatal errors.
- Example change:
  - import logging at top; in main: logging.basicConfig(level=logging.INFO)
  - Replace print(f"Processing failed: {e}") with logging.exception("Processing failed") and call sys.exit(1)

3) Unsafe image path traversal / ambiguous path handling (Medium)
- Location: lines 77-81
- Problem: Passing arbitrary --image-name may allow referencing files outside input_dir (e.g., "../other.jpg").
- Suggestion: validate that image_path is inside input_dir using Path.is_relative_to (Python >=3.9/3.11). If not available, compare resolves.
- Example:
  +    image_path = (input_dir / args.image_name).resolve()
  +    input_dir_resolved = input_dir.resolve()
  +    if not image_path.is_relative_to(input_dir_resolved):
  +        logging.error("image-name must be inside input-dir")
  +        sys.exit(1)

4) Assumption about structured return shape (Medium)
- Location: line 88
- Problem: code does len(structured) assuming structured is an iterable/list. If process_image returns dict or None, message may be misleading or crash.
- Suggestion: validate/normalize returned value:
  Example:
  +    if structured is None:
  +        logging.warning("process_image returned None")
  +    elif isinstance(structured, dict):
  +        count = 1
  +    else:
  +        count = len(structured)
  +    logging.info("Saved %d items to %s", count, output_json_path)

5) PaddleOCR initialization and GPU flag handling (Low)
- Location: line 41 & 14-15
- Problem: CUDA_VISIBLE_DEVICES defaulting to "-1" is fine but there's no CLI flag to enable GPU. Also creating the OCR engine before importing app.* wastes resources if imports fail.
- Suggestion: add --use-gpu flag that skips setting CUDA_VISIBLE_DEVICES, or add --device option. Optionally move PaddleOCR init after imports or only when needed.

6) Imports order and wasted resources (Low)
- Location: lines 41, 43-44
- Problem: ocr is created before imports app.ocr_pipeline and app.watcher. If those imports fail, an expensive OCR model was initialized unnecessarily.
- Suggestion: import app modules first, then create ocr just before use.

7) No atomic write guarantee for JSON (Low)
- Location: process_image called with output_json_path (line 87)
- Problem: If process_image writes directly to output_json_path and program crashes mid-write, the output may be partially written.
- Suggestion: ensure process_image writes to a temporary file and os.replace() to atomically move the file into place, or document the contract. If changing process_image isn't desired, wrap file creation pattern in a helper.

8) Use of print for user messages & exit codes (Low)
- Location: multiple prints (lines 38, 55-66, 93-95)
- Suggestion: switch to logging.info/warn/error and use sys.exit(0|1) for CLI semantics.

9) Input directory creation behavior (Info)
- Location: lines 35-38
- Note: auto-creating the input_dir is helpful for first run, but might be surprising. Consider logging that the dir was created and instructing the user to place files there.

10) Minor: missing type hints & docstring (Low)
- Suggestion: add a module docstring and type hints for main() where useful; makes maintenance easier.

Suggested unit / manual tests
- Unit: CLI invocation tests (pytest) that simulate args with monkeypatch for:
  - Non-existing input-dir creates directory
  - image-name outside input-dir is rejected
  - process_image returns list/dict/None and main prints/logs appropriate counts (patch process_image)
- Integration: run process_image against a small known test image and assert result.json exists and contains expected keys [{text, confidence, box}]
- Watcher: simulate watcher.run_loop with a temp directory and small image to ensure processed/failed dirs are used.

Concise actionable diff (apply in main.py near existing assignments)
--- a/main.py
+++ b/main.py
@@
-    processed_dir = Path(args.processed_dir)
-    failed_dir = Path(args.failed_dir)
+    processed_dir = Path(args.processed_dir)
+    processed_dir.mkdir(parents=True, exist_ok=True)
+    failed_dir = Path(args.failed_dir)
+    failed_dir.mkdir(parents=True, exist_ok=True)
@@
-        if not image_path.exists():
-            print(f"Error: {image_path} not found.")
-            return
+        if not image_path.exists():
+            logging.error("Error: %s not found.", image_path)
+            sys.exit(1)
+        # Ensure image_path is inside input_dir
+        try:
+            if not image_path.resolve().is_relative_to(input_dir.resolve()):
+                logging.error("image-name must be inside input-dir: %s", input_dir)
+                sys.exit(1)
+        except AttributeError:
+            # For older Python versions fallback
+            if input_dir.resolve() not in image_path.resolve().parents and image_path.resolve() != input_dir.resolve():
+                logging.error("image-name must be inside input-dir: %s", input_dir)
+                sys.exit(1)
@@
-        try:
-            structured = process_image(image_path, output_json_path=output_json_path, ocr=ocr)
-            print(f"Saved {len(structured)} items to {output_json_path}")
-        except Exception as e:
-            print(f"Processing failed: {e}")
-            return
+        try:
+            structured = process_image(image_path, output_json_path=output_json_path, ocr=ocr)
+            if structured is None:
+                logging.warning("process_image returned None for %s", image_path)
+            elif isinstance(structured, dict):
+                logging.info("Saved 1 item to %s", output_json_path)
+            else:
+                logging.info("Saved %d items to %s", len(structured), output_json_path)
+        except Exception:
+            logging.exception("Processing failed for %s", image_path)
+            sys.exit(1)

Other small improvements
- Add logging.basicConfig(level=logging.INFO) at top of main or module init.
- Add a --use-gpu or --device CLI flag to control CUDA_VISIBLE_DEVICES instead of env-only behavior.
- Consider moving heavy model initialization until just before processing files, or lazy-initialize to reduce startup cost.
- Document expected contract of process_image (return type, JSON atomic write) in a short docstring or README.

If preferred, implement the three concrete changes (mkdir for processed/failed dirs; replace prints with logging & proper exit codes; validate image path containment). Ready to apply the edits and run a quick smoke test if desired.