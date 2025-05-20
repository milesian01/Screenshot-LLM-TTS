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
import sys
import os
from obsws_python import ReqClient
import subprocess

# Global state
pipeline_in_progress = False

# Global list for hotkey handles
registered_hotkeys = []

def restart_program():
    logging.info("Detected system resume; restarting program.")
    python = sys.executable
    os.execl(python, python, *sys.argv)

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

EXPLAIN_WORDS_PROMPT = (
    "You're a friendly and fun learning buddy for a 5-year-old child. The child saw this moment in a game "
    "and didn't understand some of the words. Your job is to explain what's happening clearly, and also teach "
    "any tricky or new words like a caring teacher would.\n"
    "Keep it cheerful and short. Use examples or simple comparisons when helpful.\n"
    "Always use playful language and sound effects (like *boing!* or *whoosh!*) to make it fun.\n"
    "Never say you're an AI or analyzing the image. Just be a buddy helping out.\n"
    "Focus on helping the child learn something new in a kind and encouraging way."
)

REPHRASE_FOR_KID_PROMPT = (
    "You will be shown some game dialogue text.\n"
    "If any words or phrases are too hard for a 5-year-old child, rewrite the text in simpler, playful language.\n"
    "If the original text is already simple, return it as-is.\n"
    "**Respond with just the simplified version, nothing else.**\n"
    "**Keep it short so the game can keep moving.**"
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
        logging.error(f"LLM request failed: {str(e)}")
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
            logging.error("Error during speech synthesis")
        finally:
            # Cleanup COM for this thread.
            comtypes.CoUninitialize()
            # Small delay to ensure proper resource cleanup.
            time.sleep(0.2)

def play_ready_sound():
    """Play a brief confirmation sound using TTS"""
    try:
        # Use minimal TTS setup for the sound cue
        comtypes.CoInitialize()
        engine = pyttsx3.init()
        engine.setProperty('rate', 250)  # Faster speaking rate
        engine.say("(ding!)")
        engine.runAndWait()
    except Exception as e:
        logging.debug(f"Ready sound error: {str(e)}")
    finally:
        try:
            comtypes.CoUninitialize()
        except:
            pass



# ----------------------------------------------------------------
# 3) Keep-alive functionality
# ----------------------------------------------------------------
def keep_model_alive():
    """Single keep-alive pulse for all models"""
    models = ["gemma3:27b-it-q8_0"]
    for model in models:
        try:
            logging.debug(f"Sending keep-alive ping for {model}")  # Changed to debug
            response = requests.post(
                "http://192.168.50.250:30068/api/chat",
                json={"model": model, "messages": []},
                timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logging.warning(f"Keep-alive HTTP error for {model}: {str(e)}")
        except requests.exceptions.RequestException as e:
            logging.warning(f"Keep-alive connection issue for {model}: {str(e)}")
        except Exception as e:
            logging.warning(f"Keep-alive unexpected error for {model}: {str(e)}")

# New helper to actively load the model via /api/generate
def warmup_model(model="gemma3:27b-it-q8_0"):
    """Trigger the model to load by sending a short generate request."""
    try:
        logging.info(f"Warming up model {model}")
        response = requests.post(
            "http://192.168.50.250:30068/api/generate",
            json={"model": model, "prompt": "hi", "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        logging.debug("Model warmup complete")
    except Exception as e:
        logging.warning(f"Model warmup failed for {model}: {e}")

# def keep_alive_worker():
#     """Runs keep-alives every 2 minutes"""
#     while True:
#         time.sleep(120)  # 2 minutes
#         keep_model_alive()

def register_hotkeys():
    global registered_hotkeys
    # Remove previously registered hotkeys
    for handle in registered_hotkeys:
        keyboard.remove_hotkey(handle)
    registered_hotkeys = []

    # Register your analysis and simple pipeline hotkeys and store their handles
    registered_hotkeys.append(keyboard.add_hotkey('f9', lambda: pipeline_wrapper(pipeline)))
    registered_hotkeys.append(keyboard.add_hotkey('f10', lambda: pipeline_wrapper(pipeline_simple_with_rephrase)))
    registered_hotkeys.append(keyboard.add_hotkey('`', lambda: pipeline_wrapper(pipeline_simple_with_rephrase)))  # <-- make sure this is here
    registered_hotkeys.append(keyboard.add_hotkey('pause', lambda: pipeline_wrapper(pipeline_explain_words)))
    registered_hotkeys.append(keyboard.add_hotkey('f12', lambda: pipeline_wrapper(pipeline_simple)))
    
    # Optional: Send keep-alive and warmup without blocking startup
    threading.Thread(target=keep_model_alive, daemon=True).start()
    threading.Thread(target=warmup_model, daemon=True).start()

# ----------------------------------------------------------------
# 4) Pipeline management
# ----------------------------------------------------------------
pipeline_in_progress = False

def pipeline_wrapper(target_func):
    """Handles pipeline execution in a thread with state management"""
    global pipeline_in_progress
    
    # Use the lock for both check AND state update
    with threading.Lock():
        if pipeline_in_progress:
            logging.info("Pipeline busy - ignoring request")
            return
        pipeline_in_progress = True  # Set flag BEFORE starting thread

    def wrapper():
        global pipeline_in_progress
        try:
            target_func()
        finally:
            with threading.Lock():
                pipeline_in_progress = False
            play_ready_sound()  # Add this line
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
        logging.error(f"Pipeline failed: {str(e)}")

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
            model="gemma3:27b-it-q8_0"
        )

        speak_response(llm_response)

    except Exception as e:
        logging.error(f"Simple pipeline failed: {str(e)}")

def handle_obs_recording_on_resume():
    import time
    host, port = "localhost", 4455

    # small buffer to let OBS & system stabilize after wake
    logging.info("Waiting 10s for system/OBS to stabilize after wake")
    time.sleep(10)

    # 1) Try to connect
    try:
        client = ReqClient(host=host, port=port, password="", timeout=5)
    except Exception as e:
        logging.error(f"OBS connect failed: {e}")
        logging.info("Launching OBS...")
        try:
            subprocess.Popen(r"C:\Program Files\obs-studio\bin\64bit\obs64.exe")
            time.sleep(10)
            client = ReqClient(host=host, port=port, password="", timeout=5)
        except Exception as ex:
            logging.error(f"OBS launch/connect failed: {ex}")
            return

    try:
        # Check and stop any existing recording, then wait (with retries)
        status = client.get_record_status()
        if status.output_active:
            logging.info("Stopping existing recording…")
            client.stop_record()
            logging.info("Waiting for OBS to finalize previous recording…")
            max_wait, retries = 30, 3
            for attempt in range(retries):
                start = time.time()
                while client.get_record_status().output_active and time.time() - start < max_wait:
                    time.sleep(1)
                if not client.get_record_status().output_active:
                    logging.info("Previous recording finalized.")
                    break
                logging.warning(f"Still active after {max_wait}s, retrying stop_record (attempt {attempt+2}/{retries})…")
                client.stop_record()
            else:
                logging.error("Failed to stop recording after multiple attempts.")

        # 3) Start a fresh recording
        logging.info("Starting new recording…")
        client.start_record()
    except Exception as e:
        logging.error(f"OBS control error: {e}")
    finally:
        client.disconnect()

def pipeline_simple_with_rephrase():
    """Text extraction + simplified rephrasing for kids"""
    try:
        logging.info("Pipeline (F10) started: extracting text...")

        # Screenshot and encode
        screenshot = pyautogui.screenshot()
        with BytesIO() as buf:
            screenshot.save(buf, format="PNG")
            image_data = buf.getvalue()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # Step 1: Extract original text
        original_text = analyze_image_with_llm(
            image_base64,
            prompt=SIMPLE_SYSTEM_PROMPT,
            model="gemma3:27b-it-q8_0"
        )

        speak_response(original_text)

        # If no text was found, skip rephrasing
        if "no text detected" in original_text.lower():
            return

        # Step 2: Rephrase if needed
        logging.info("Requesting rephrased version for child...")
        simplified_text = analyze_image_with_llm(
            base64.b64encode(original_text.encode()).decode("utf-8"),  # Encode as if it's image input
            prompt=REPHRASE_FOR_KID_PROMPT,
            model="gemma3:27b-it-q8_0"
        )

        speak_response(simplified_text)

    except Exception as e:
        logging.error(f"F10 pipeline failed: {str(e)}")

def pipeline_explain_words():
    """Capture screenshot and explain tricky words simply for a child"""
    try:
        logging.info("Pipeline (~) started: capturing screenshot...")

        # Screenshot and encode
        screenshot = pyautogui.screenshot()
        with BytesIO() as buf:
            screenshot.save(buf, format="PNG")
            image_data = buf.getvalue()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # Send to LLM with explain prompt
        llm_response = analyze_image_with_llm(
            image_base64,
            prompt=EXPLAIN_WORDS_PROMPT,
            model="gemma3:27b-it-q8_0"
        )

        speak_response(llm_response)

    except Exception as e:
        logging.error(f"Explain-words pipeline failed: {str(e)}")



# ----------------------------------------------------------------
# 6) Main entry point
# ----------------------------------------------------------------
def main():
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

    # Optional: Send one-time keep-alive when hotkeys are (re)registered
    # threading.Thread(target=keep_alive_worker, name="KeepAlive", daemon=True).start()

    # Register hotkeys on startup
    register_hotkeys()

    logging.info("Ready! Press F9 (playful summary), F10 or ` (simple + rephrase), F12 (exact text only), or Pause (explain & learn).")
    
    last_time = time.time()
    try:
        # Block indefinitely to keep the program running
        while True:
            time.sleep(1)
            current_time = time.time()
            # If more than 2 seconds have passed, it's likely the system resumed from sleep
            if current_time - last_time > 2:
                logging.info("System resume detected. Handling OBS recording before restart.")
                handle_obs_recording_on_resume()
                logging.info("Waiting 15 seconds before restarting program.")
                time.sleep(15)
                restart_program()
            last_time = current_time
    except KeyboardInterrupt:
        pass
    finally:
        keyboard.unhook_all()
        logging.info("Cleanup complete")


if __name__ == "__main__":
    main()
