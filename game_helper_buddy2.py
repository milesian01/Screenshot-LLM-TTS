import threading
import time
import logging
import base64
from datetime import datetime
import requests
import json
import pyttsx3
import comtypes
import keyboard
import pyautogui
from io import BytesIO

# ----------------------------------------------------------------
# 1) Ollama LLM client functionality (adapted from ollama_client.py)
# ----------------------------------------------------------------
DEFAULT_SYSTEM_PROMPT = (
    "You are a cheerful play assistant for a 5-year-old child. When shown a game screenshot: "
    "1. Carefully identify ALL text elements (dialogues, buttons, instructions, labels) "
    "2. Describe context (e.g., which character is speaking, where text appears) "
    "3. Explain in simple, playful language a kindergartener would understand "
    "4. Keep responses brief (1-2 sentences per text element) "
    "5. Add fun sound effects in parentheses where appropriate "
    "6. Never mention you're an AI or analyzing an image. "
    'Example: "Mario in his red hat says (boing!): \'Let\'s jump over the turtle!\' '
    'The green button says START - that\'s how we begin the adventure!"'
)

SIMPLE_SYSTEM_PROMPT = (
    "Identify speech/text bubbles in the image. Extract the text inside each bubble along with the NPC's name if applicable."
)

def analyze_image_with_llm(
    image_base64,
    prompt=DEFAULT_SYSTEM_PROMPT,
    endpoint="http://192.168.50.250:30068/api/chat",
    model="gemma3:27b-it-q8_0",
    timeout=60
):
    """
    Sends a base64-encoded image to the Ollama LLM with a provided prompt.
    """
    logging.info("Starting LLM API request")

    start_time = datetime.now()
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": "What's happening in my game right now? Please tell me!",
            "images": [image_base64]
        }
    ]

    try:
        response = requests.post(
            endpoint,
            json={
                "model": model,
                "messages": messages,
                "stream": True
            },
            timeout=timeout
        )
        response.raise_for_status()

        accumulated_text = ""
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode("utf-8"))
                    if "message" in data:
                        accumulated_text += data["message"]["content"]
                except json.JSONDecodeError:
                    continue

        elapsed = (datetime.now() - start_time).total_seconds()
        logging.info(f"LLM request completed in {elapsed:.2f}s")
        logging.debug(f"Accumulated response text: {accumulated_text}")
        return accumulated_text

    except Exception as e:
        logging.error(f"LLM request failed: {str(e)}", exc_info=True)
        return "Oops! Let's try that again. (error sound)"


# ----------------------------------------------------------------
# 2) TTS client functionality 
# ----------------------------------------------------------------
import threading
import logging
import pyttsx3
import comtypes
import time

tts_lock = threading.Lock()

def speak_response(text):
    """
    Converts the provided text to speech using pyttsx3 with thread-local COM initialization.
    
    Parameters:
        text (str): The text to be spoken.
    """
    with tts_lock:
        try:
            # Initialize COM for the current thread.
            comtypes.CoInitialize()
            
            # Initialize the TTS engine.
            engine = pyttsx3.init()
            engine.setProperty('rate', 140)
            engine.setProperty('volume', 1.0)
            
            # Try to find a female voice (commonly Zira on Windows).
            voices = engine.getProperty('voices')
            selected_voice = None
            for v in voices:
                # Common Windows voice ID substrings: 'Zira', 'Jenny', 'Heera'
                # Pick whichever "sounds" female or has female in the name.
                if "zira" in v.name.lower() or "female" in v.name.lower():
                    selected_voice = v
                    break
            
            if selected_voice:
                engine.setProperty('voice', selected_voice.id)
            
            logging.info(f"Speaking response: {text}")
            engine.say(text)
            engine.runAndWait()
            
        except Exception as e:
            logging.error("Error during speech synthesis", exc_info=True)
        finally:
            # Cleanup COM for this thread.
            comtypes.CoUninitialize()
            # Small delay to ensure proper resource cleanup.
            time.sleep(0.2)


# ----------------------------------------------------------------
# 3) Keep-alive functionality
# ----------------------------------------------------------------
def keep_model_alive():
    """
    Periodically sends a dummy request to keep the Ollama model loaded.
    (e.g., empty chat request every ~2 minutes)
    """
    while True:
        # Sleep 10 seconds less than 2 minutes (110 seconds)
        # so real pipeline calls won't overlap at exactly the same time
        time.sleep(110)
        try:
            logging.info("Sending keep-alive ping to keep the model loaded.")
            response = requests.post(
                "http://192.168.50.250:30068/api/chat",
                json={"model": "gemma3:27b-it-q8_0", "messages": []},
                timeout=5
            )
            if response.status_code == 200:
                logging.info("Keep-alive response received.")
            else:
                logging.warning(f"Keep-alive got non-200: {response.status_code}")
        except Exception as e:
            logging.error("Keep-alive ping failed: " + str(e), exc_info=True)


# ----------------------------------------------------------------
# 4) Main pipeline to: (a) screenshot -> (b) LLM -> (c) TTS
# ----------------------------------------------------------------
pipeline_in_progress = False
hotkey_registration = None

def pipeline():
    global pipeline_in_progress, hotkey_registration

    if pipeline_in_progress:
        # If we want to ignore re-trigger while in progress, just return.
        # This ensures no overlapping triggers.
        logging.info("Pipeline requested while another is running; ignoring.")
        return

    pipeline_in_progress = True  # Set the flag

    try:
        logging.info("Pipeline started: capturing screenshot...")

        # Take a screenshot
        screenshot = pyautogui.screenshot()

        # Encode to base64
        with BytesIO() as buf:
            screenshot.save(buf, format="PNG")
            image_data = buf.getvalue()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # Send to Ollama
        logging.info("Sending screenshot to LLM...")
        llm_response = analyze_image_with_llm(image_base64)

        # Speak out result
        speak_response(llm_response)

    finally:
        logging.info("Pipeline finished")
        pipeline_in_progress = False  # Release the lock

        import os, sys
        os.execv(sys.executable, [sys.executable] + sys.argv)

def pipeline_simple():
    global pipeline_in_progress
    if pipeline_in_progress:
        logging.info("Simplified pipeline requested while another is running; ignoring.")
        return

    pipeline_in_progress = True

    try:
        logging.info("Simplified pipeline started: capturing screenshot...")

        # Capture screenshot and encode to base64
        screenshot = pyautogui.screenshot()
        with BytesIO() as buf:
            screenshot.save(buf, format="PNG")
            image_data = buf.getvalue()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # Send to LLM with simplified prompt and model gemma3:1b-it-fp16
        logging.info(" sending screenshot to simplified LLM...")
        llm_response = analyze_image_with_llm(
            image_base64,
            prompt=SIMPLE_SYSTEM_PROMPT,
            model="gemma3:4b"  # Changed from 1b to 4
        )

        speak_response(llm_response)

    finally:
        logging.info("Simplified pipeline finished")
        pipeline_in_progress = False

        import os, sys
        os.execv(sys.executable, [sys.executable] + sys.argv)


# ----------------------------------------------------------------
# 5) Background keep-alive thread every 2 minutes
# ----------------------------------------------------------------
def keep_alive_worker():
    """
    Runs in the background and sends keep-alive every 2 minutes when pipeline is not running.
    """
    while True:
        time.sleep(120)  # Wait 2 minutes
        if not pipeline_in_progress:
            keep_model_alive()


# ----------------------------------------------------------------
# 6) Main entry point
# ----------------------------------------------------------------
def main():
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

    # Start background keep-alive thread
    threading.Thread(target=keep_model_alive, daemon=True).start()

    # Register the hotkey with progress check
    keyboard.on_press_key('f9', lambda event: pipeline() if not pipeline_in_progress else None)
    
    # Register the simplified pipeline hotkey for F12 with progress check
    keyboard.on_press_key('f12', lambda event: pipeline_simple() if not pipeline_in_progress else None)

    logging.info("Ready. Press F9 to capture screenshot and run pipeline, or F12 for simplified analysis. Ctrl+C to exit.")

    # Wait forever (until user kills process)
    keyboard.wait()


if __name__ == "__main__":
    main()
