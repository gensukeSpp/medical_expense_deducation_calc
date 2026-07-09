# 2026-07-09-architecture.md

## Purpose
This document captures the architectural changes implemented in the `feature/name-separated-coords` branch, specifically focusing on introducing multi-box coordinate matching for handling split-field extractions and enhancing service layer robustness.

## Overview
The primary architectural shift involves upgrading the coordinate extraction pipeline to support multiple box regions for single fields, which is crucial for handling complex receipt layouts where labels or values are visually separated. 

### Core Components Changed
- **`app/coord_search.py`**: Added support for multi-box coordinate matching, allowing concatenation of text across disjointed regions.
- **`app/services/ocr_coordinate_service.py`**: Refactored to utilize a more flexible strategy-based approach for coordinate search, improving modularity.
- **`app/structural_parser.py`**: Updated to utilize the new multi-box proximity search strategy for template-based extraction.
- **`app/services/receipt_database_repository.py`**: Refined receipt lookup logic to be more resilient to varied file path formats.

## Dataflow
The extraction pipeline now performs the following for template-based matches:
1. Identify if a field in the template is mapped to a single-box or multi-box (list of boxes).
2. For multi-box fields, search proximity for each box, sort found entries by X-coordinate to maintain reading order, concatenate the text, and clean up suffixes (e.g., "様").
3. Update the extracted field value with the concatenated, cleaned result.

## Key Design Decisions
- **Backward Compatibility**: The new multi-box search functionality in `app/coord_search` is designed to be backward compatible, supporting both the legacy single-box format and the new multi-box list format.
- **Service Layer Modularization**: Moved search strategy logic out of the core coordinate service to improve testability and extendability.

## Changed Files
- `app/coord_search.py`
- `app/services/ocr_coordinate_service.py`
- `app/services/receipt_database_repository.py`
- `app/structural_parser.py`
- `app/template_feedback.py`
- `tests/test_coord_search.py`
- `tests/test_structural_parser.py`
