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

# Global state
pipeline_in_progress = False

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
    "Extract only the exact text from any speech or text bubbles in the image, including the NPC's name if visible. "
    "**If there is no readable text, return 'No text detected.'** "
    "**Do not repeat or rephrase the user's question.** "
    "Do not include any additional commentary, explanation, or analysis."
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
    """Single keep-alive pulse for all models"""
    models = ["gemma3:27b-it-q8_0", "gemma3:4b"]
    try:
        logging.info("Sending keep-alive pings")
        for model in models:
            response = requests.post(
                "http://192.168.50.250:30068/api/chat",
                json={"model": model, "messages": []},
                timeout=10
            )
            if response.status_code != 200:
                logging.warning(f"Keep-alive failed for {model}: {response.status_code}")
    except Exception as e:
        logging.error(f"Keep-alive failed: {str(e)}", exc_info=True)



# ----------------------------------------------------------------
# 3) Keep-alive functionality
# ----------------------------------------------------------------
def keep_model_alive():
    """Single keep-alive pulse for all models"""
    models = ["gemma3:27b-it-q8_0", "gemma3:4b"]
    try:
        logging.info("Sending keep-alive pings")
        for model in models:
            response = requests.post(
                "http://192.168.50.250:30068/api/chat",
                json={"model": model, "messages": []},
                timeout=10
            )
            if response.status_code != 200:
                logging.warning(f"Keep-alive failed for {model}: {response.status_code}")
    except Exception as e:
        logging.error(f"Keep-alive failed: {str(e)}", exc_info=True)

def keep_alive_worker():
    """Runs keep-alives every 2 minutes"""
    while True:
        time.sleep(120)  # 2 minutes
        keep_model_alive()

# ----------------------------------------------------------------
# 4) Pipeline management
# ----------------------------------------------------------------
pipeline_in_progress = False

def pipeline_wrapper(target_func):
    """Handles pipeline execution in a thread with state management"""
    global pipeline_in_progress
    
    # Add lock to prevent race conditions
    with threading.Lock():
        if pipeline_in_progress:
            logging.info("Pipeline already running - ignoring request")
            return
        
    def wrapper():
        global pipeline_in_progress
        try:
            pipeline_in_progress = True
            target_func()
        finally:
            pipeline_in_progress = False
            
    threading.Thread(target=wrapper, daemon=True).start()

# ----------------------------------------------------------------
# 4) Revised pipeline functions using wrapper
# ----------------------------------------------------------------
def pipeline():
    """Full analysis pipeline"""
    try:
        logging.info("Pipeline started: capturing screenshot...")
        
        # Capture screenshot
        screenshot = pyautogui.screenshot()
        
        # Encode to base64
        with BytesIO() as buf:
            screenshot.save(buf, format="PNG")
            image_data = buf.getvalue()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # Send to LLM with default prompt
        logging.info("Sending screenshot to LLM...")
        llm_response = analyze_image_with_llm(image_base64)

        # Speak result
        speak_response(llm_response)

    except Exception as e:
        logging.error(f"Pipeline failed: {str(e)}", exc_info=True)

def pipeline_simple():
    """Simplified text extraction pipeline"""
    try:
        logging.info("Simplified pipeline started...")
        
        # Capture screenshot (same as regular pipeline)
        screenshot = pyautogui.screenshot()
        with BytesIO() as buf:
            screenshot.save(buf, format="PNG")
            image_data = buf.getvalue()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # Send to LLM with simple prompt and 4b model
        llm_response = analyze_image_with_llm(
            image_base64,
            prompt=SIMPLE_SYSTEM_PROMPT,
            model="gemma3:4b"  # Verify this is the correct model name
        )

        speak_response(llm_response)

    except Exception as e:
        logging.error(f"Simple pipeline failed: {str(e)}", exc_info=True)



# ----------------------------------------------------------------
# 6) Main entry point
# ----------------------------------------------------------------
def main():
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

    # Start background keep-alive thread
    threading.Thread(target=keep_alive_worker, name="KeepAlive", daemon=True).start()

    # Register hotkeys with lambda wrappers
    keyboard.add_hotkey('f9', lambda: pipeline_wrapper(pipeline))
    keyboard.add_hotkey('f12', lambda: pipeline_wrapper(pipeline_simple))
    
    # Debug hotkeys - remove after verification
    keyboard.add_hotkey('f9', lambda: logging.info("F9 pressed"))
    keyboard.add_hotkey('f12', lambda: logging.info("F12 pressed"))

    logging.info("Ready. Press F9/F12 for analysis. ESC to exit.")
    
    try:
        # Block on explicit key press instead of Ctrl+C
        keyboard.wait('esc')
    except KeyboardInterrupt:
        pass
    finally:
        keyboard.unhook_all()
        logging.info("Cleanup complete")


if __name__ == "__main__":
    main()
