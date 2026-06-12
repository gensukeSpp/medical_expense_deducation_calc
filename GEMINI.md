# Project: Medical Expense Deduction Calculator

This project is an automated OCR application designed to streamline the extraction and management of data from medical receipts for tax deduction purposes.

## Project Overview

The primary goal is to simplify data entry for medical expenses within a household. It follows a "Human-in-the-Loop" design, allowing the system to learn from user corrections to improve OCR accuracy over time, specifically for clinic-specific document layouts.

## Architecture & Technologies

- **Language**: Python (>=3.11)
- **OCR Engine**: [PaddleOCR] (for text and coordinate extraction)
- **Image Processing**: OpenCV
- **Future Components**:
    - **LLM**: For structure extraction (JSON) and clinic name identification.
    - **Data Management**: SQLite (for template and correction storage).

## Key Files & Directories

- `main.py`: Main entry point for OCR execution.
- `image_resize.py`: Image pre-processing utility for OCR.
- `要件定義書.md`: Detailed requirements and roadmap.
- `pyproject.toml`: Project configuration and dependencies.

## Running the Application

Ensure your environment is set up (see `pyproject.toml`). The current application can be run with:

```bash
python main.py
```

*Note: The current implementation assumes a specific directory structure (`~/Downloads/receipts/`) and hardcoded file names, as defined in `main.py`.*

## Development Conventions

- **Type Safety**: Use type hints where appropriate.
- **Code Style**: Adhere to PEP 8 standards. Use `black` for formatting (line length 119).
- **Docstrings**: All functions should include descriptive docstrings detailing parameters and purpose.
- **Modularity**: Maintain clean separation between processing logic (OCR, resizing) and management logic (data persistence).
- **Security**: Never hardcode credentials, paths, or sensitive data. Use environment variables for configuration.
