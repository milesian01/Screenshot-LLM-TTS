import json
import tkinter as tk
from tkinter import ttk
import mss
import keyboard
import threading
from PIL import Image
import base64
import requests
import pyttsx3
import io
import time

import logging
from datetime import datetime
import threading

# Global lock for TTS operations
tts_lock = threading.Lock()

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('game_helper_buddy.log'),
        logging.StreamHandler()
    ]
)

def capture_screenshot():
    """Capture full screen screenshot and return as PIL Image"""
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Primary monitor
        sct_img = sct.grab(monitor)
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

def image_to_base64(img):
    """Convert PIL Image to base64 string"""
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def analyze_image_with_llm(image_base64):
    """Send screenshot to Ollama LLM with crafted system prompt"""
    
    # Log request start
    logging.info("Starting API request")
    start_time = datetime.now()
    """Send screenshot to Ollama LLM with crafted system prompt"""
    system_prompt = (
        "You are a cheerful play assistant for a 5-year-old child. When shown a game screenshot: "
        "1. Carefully identify ALL text elements (dialogues, buttons, instructions, labels) "
        "2. Describe context (e.g., which character is speaking, where text appears) "
        "3. Explain in simple, playful language a kindergartener would understand "
        "4. Keep responses brief (1-2 sentences per text element) "
        "5. Add fun sound effects in parentheses where appropriate "
        "6. Never mention you're an AI or analyzing an image"
        "Example: 'Mario in his red hat says (boing!): \"Let's jump over the turtle!\" "
        "The green button says START - that's how we begin the adventure!'"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "What's happening in my game right now? Please tell me!",
            "images": [image_base64]
        }
    ]
    
    try:
        response = requests.post(
            "http://192.168.50.250:30068/api/chat",
            json={
                "model": "gemma3:27b-it-q8_0",
                "messages": messages,
                "stream": True
            },
            timeout=60  # Optional timeout after 60 seconds
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

        # Log successful response with timing
        elapsed = (datetime.now() - start_time).total_seconds()
        logging.info(f"API request completed in {elapsed:.2f}s")
        logging.debug(f"Accumulated response text: {accumulated_text}")

        return accumulated_text
        
    except Exception as e:
        # Log detailed error information
        logging.error(f"API request failed: {str(e)}", exc_info=True)
        return f"Oops! Let's try that again. (error sound)"

def speak_response(text):
    """Convert text to child-friendly speech"""

def hotkey_listener():
    """Listen for a global hotkey (Ctrl+Shift+S) and trigger the screenshot analysis."""
    def hotkey_callback():
        logging.info("Hotkey pressed - starting analysis in new thread")
        threading.Thread(target=on_play_button_click, daemon=True).start()

    keyboard.add_hotkey('ctrl+shift+s', hotkey_callback)

def speak_response(text):
    """Convert text to child-friendly speech"""
    with tts_lock:
        try:
            logging.info(f"Speaking response: {text}")
            
            # Initialize COM for this thread on Windows
            import comtypes
            comtypes.CoInitialize()
            
            engine = pyttsx3.init()
            engine.setProperty('rate', 140)  # Slower speaking speed
            engine.setProperty('volume', 1.0)
            
            voices = engine.getProperty('voices')
            if len(voices) > 1:
                engine.setProperty('voice', voices[1].id)  # Often female-sounding voice
            
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logging.error(f"Error speaking response: {str(e)}", exc_info=True)
        finally:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass


def on_play_button_click():
    """Handle button press workflow"""
    
    # Log button click event
    logging.info("Button clicked - starting analysis")
    start_time = datetime.now()
    screenshot = capture_screenshot()
    
    # Save with a timestamp
    import time
    filename = f"debug_screenshot_{int(time.time())}.jpg"
    screenshot.save(filename)
    logging.info(f"Screenshot saved as {filename}")
    image_b64 = image_to_base64(screenshot)
    try:
        response_text = analyze_image_with_llm(image_b64)
        
        # Log successful processing with timing
        elapsed = (datetime.now() - start_time).total_seconds()
        logging.info(f"Analysis completed in {elapsed:.2f}s")
        
    except Exception as e:
        logging.error("Error during analysis", exc_info=True)
        response_text = "Oops! Let's try that again."
    speak_response(response_text)

def keep_model_alive():
    """Periodically sends a dummy request to keep the Ollama model loaded."""
    while True:
        time.sleep(25 * 60)  # Sleep for 25 minutes.
        try:
            logging.info("Sending keep-alive ping to keep the model loaded.")
            dummy_message = [{"role": "system", "content": "ping"}]
            response = requests.post(
                "http://192.168.50.250:30068/api/chat",
                json={
                    "model": "gemma3:27b-it-q8_0",
                    "messages": dummy_message,
                    "stream": False
                },
                timeout=30
            )
            response.raise_for_status()
            logging.info("Keep-alive response received.")
        except Exception as e:
            logging.error("Keep-alive ping failed: " + str(e), exc_info=True)

def main():
    """Main application entry point"""
    # Register the global hotkey in the main thread.
    hotkey_listener()
    
    # Start the keep-alive thread to keep the model loaded longer.
    threading.Thread(target=keep_model_alive, daemon=True).start()
    
    logging.info("Listening for global hotkey (ctrl+shift+s)...")
    keyboard.wait()  # Keeps the program running and listening for hotkeys.

if __name__ == '__main__':
    main()
