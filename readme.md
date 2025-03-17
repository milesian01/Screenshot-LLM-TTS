# Game Screen Text Reader

This Python script captures game screenshots, extracts text using an LLM (Ollama), and reads the extracted content aloud using TTS (Text-to-Speech). It is designed as a playful assistant for a 5-year-old, explaining game text in a fun and engaging way.

## Features

- **LLM-Based Text Recognition**: Extracts and interprets game text using an Ollama-based model.
- **Text-to-Speech (TTS)**: Reads out recognized text in a natural-sounding voice.
- **Screenshot Capture**: Takes a screenshot of the active screen and processes the image.
- **Two Modes**:
  - **F9 (Full Analysis)**: Extracts text with contextual interpretation for kids.
  - **F12 (Simple Extraction)**: Extracts text only, without added context.
- **Keep-Alive Mechanism**: Ensures the LLM models remain responsive.
- **Hotkey Controls**:
  - `F9` - Run full analysis pipeline
  - `F12` - Run simple text extraction
  - `ESC` - Exit the program

## Requirements

- Python 3.x
- Dependencies:
  ```
  pip install requests pyttsx3 keyboard pyautogui comtypes
  ```

## Usage

1. Run the script:
   ```
   python script.py
   ```
2. Press `F9` for full text interpretation or `F12` for raw text extraction.
3. Press `ESC` to exit.

## Configuration

- Update the `endpoint` variable in `analyze_image_with_llm` to match your Ollama server.
- Adjust the TTS settings in `speak_response` to customize voice and speed.

## Notes

- Ensure the LLM service is running and accessible before using the script.
- The keep-alive thread helps maintain API responsiveness.
- Designed for Windows with `pyttsx3` but may require adjustments for macOS/Linux.
