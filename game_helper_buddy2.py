import threading
import time
import logging
import base64
import requests
import json
import pyttsx3
import comtypes
import keyboard
import pyautogui
from datetime import datetime
from io import BytesIO

# ----------------------------------------------------------------
# 1) Ollama LLM client functionality (adapted from ollama_client.py)
# ----------------------------------------------------------------
DEFAULT_SYSTEM_PROMPT = (
    "You are a cheerful play assistant for a 5-year-old child. When shown a game screenshot: "
    "1. Carefully identify ALL text elements (dialogues, buttons, instructions, labels) "
    "2. Describe context (e.g., which character is speaking, where text appears) "
    "3. Explain in simple, playful language a kindergartener would understand "
    "4. Add fun sound effects in parentheses where appropriate "
    "5. Never mention you're an AI or analyzing an image. "
    'Example: "Mario in his red hat says (boing!): \'Let\'s jump over the turtle!\' '
    'The green button says START - that\'s how we begin the adventure!"'
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
# 2) TTS client functionality (adapted from tts_client.py)
# ----------------------------------------------------------------
import threading
tts_lock = threading.Lock()

def speak_response(text):
    """
    Converts the provided text to speech with proper COM initialization.
    """
    with tts_lock:
        engine = None
        try:
            comtypes.CoInitializeEx(comtypes.COINIT_APARTMENTTHREADED)
            
            engine = pyttsx3.init()
            engine.setProperty('rate', 140)

            engine.say(text, 'response')
            engine.startLoop(False)

            while not done_speaking.wait(0.1):
                pass

        except Exception as e:
            logging.error("TTS Error", exc_info=True)
        finally:
            if engine:
                try:
                    engine.endLoop()
                    engine.stop()
                except Exception as e:
                    logging.error("Error stopping TTS engine", exc_info=True)
            time.sleep(0.2)


# ----------------------------------------------------------------
# 3) Keep-alive functionality
# ----------------------------------------------------------------
def send_keep_alive():
    """
    Sends a keep-alive request to the Ollama server. Adjust the endpoint as needed.
    """
    try:
        # Example keep-alive endpoint (customize as needed)
        endpoint = "http://192.168.50.250:30068/api/keep_alive"
        logging.info("Sending keep-alive request")
        resp = requests.post(endpoint, timeout=5)
        resp.raise_for_status()
        logging.info("Keep-alive success")
    except Exception as e:
        logging.warning(f"Keep-alive request failed: {e}")


# ----------------------------------------------------------------
# 4) Main entry point
# ----------------------------------------------------------------
def main():
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

    # Create background thread for keep-alives
    threading.Thread(target=send_keep_alive, daemon=True).start()

    # Register the hotkey
    global hotkey_registration
    hotkey_registration = keyboard.add_hotkey('f9', pipeline)

    logging.info("Ready. Press F9 to capture screenshot and run pipeline. Ctrl+C to exit.")

    # Wait forever (until user kills process)
    keyboard.wait()


if __name__ == "__main__":
    main()
