# Architecture Snapshot

**Date:** 2026-06-18
**Branch:** update-arch/20260618-133146

## Recent Commits (origin/main..HEAD)

- 8cd2418 docs: add architecture snapshot for update-arch/20260618-133146
- 7761782 Issue #4: Add E2E runner, expected outputs, and e2e tests; fix LLM date parsing; normalize clinic spacing in tests\n\nImplements tasks 06-1..08-4 (mock data, tests, docs notes, E2E).\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
- 5ff2ced architecture-update: append new entries to docs/architecture/README instead of overwriting
- 98d86c9 docs(architecture): add snapshot for Python changes vs origin/main
- 5ee5ade chore(docs): update architecture index (copilot slash)
- 7eb9d18 docs: add architecture snapshot for changes on feature/llm-analysis/4-03-
- 8ad6528 Issue #4: CLI integration, normalization, structural parser, and error logging; add tests\n\nImplements --input-json and --model CLI flags, normalization utilities (amount/date), structural_parser to call LLM and write structured output, and error logging to output_json/errors.log. Adds tests and updates.\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

## Changed Python Files

- .github/skills/architecture-update/scripts/update_arch_index.py
- app/args.py
- app/error_logging.py
- app/input.py
- app/llm_extractor.py
- app/normalization.py
- app/output.py
- app/structural_parser.py
- main.py
- tasks/issue_4/run_e2e.py
- tests/test_e2e_structured_outputs.py
- tests/test_llm_wrapper.py
- tests/test_normalization.py
