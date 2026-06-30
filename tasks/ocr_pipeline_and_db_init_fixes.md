OCR Pipeline and Database Initialization Fixes

  Problem Statement
  The user has reported three issues in the application:
   1. Redundant OCR: The pipeline appears to perform OCR twice for a single image, once
      before and once after resizing/grayscale conversion.
   2. Input Image Modification: The image resizing process writes resized_gray_*.jpg files
      directly into the input directory.
   3. Database Migration Failures: Database migrations in main.py are executed after image
      processing, causing issues if the database hasn't been initialized, and there are
      concerns about whether tables are created correctly.

  Proposed Solution

  1. Optimize OCR Pipeline
   - Consolidate all processing into a single, well-defined pipeline function
     (process_receipt in a new service or updated ocr_pipeline.py).
   - Ensure the pipeline explicitly:
       - Resizes/grayscales the image (once).
       - Performs OCR on the processed image (once).
       - Generates raw JSON.
  2. Protect Input Images
   - Modify app/image_resize.py (or the caller) to write resized images to a temporary
     directory or the output_dir, never the input_dir.
   - Ensure clean-up of temporary files if necessary.

  3. Initialize Database Early
   - Move the database migration call (run_migrations) in main.py to the very beginning of
     the main() function, immediately after argument parsing and before any processing.

  Implementation Steps

  Task 1: Fix Pipeline Order & Redundancy
   - [ ] Audit app/processor.py and app/watcher.py to confirm the redundant call site.
   - [ ] Refactor app/ocr_pipeline.py or create a new service function to unify the process.

  Task 2: Fix Input Image Protection
   - [ ] Update app/image_resize.py to accept an output_dir or temp_dir instead of writing
     to image_path.parent.

  Task 3: Fix DB Migration
   - [ ] Update main.py to move run_migrations execution before process_single_image.

  Verification & Testing
   - [ ] Run python main.py with a single image and verify only one OCR pass is performed.
   - [ ] Verify input_dir remains unchanged (no new files created).
   - [ ] Verify database initialization occurs before processing.
   - [ ] Run existing tests (pytest) to ensure no regressions.
   - [ ] Add a new test case in tests/ to verify DB initialization logic.