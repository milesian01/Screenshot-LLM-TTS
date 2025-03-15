import json
import logging  # Add this line to import the logging module
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
import comtypes

# Initialize COM in the main thread
comtypes.CoInitialize()

from datetime import datetime
import threading

# Global locks for thread-safe operations
tts_lock = threading.Lock()
processing_lock = threading.Lock()

# Thread-safe processing status variable
is_processing = False

last_processing_time = 0

def set_processing_status(status):
    """Set the processing status in a thread-safe manner"""
    global is_processing
    with processing_lock:
        prev = is_processing
        is_processing = status
        logging.debug(f"Status changed: {prev} -> {status}")

def get_processing_status():
    """Get the processing status in a thread-safe manner"""
    global is_processing
    with processing_lock:
        return is_processing

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
    """Convert text to child-friendly speech using thread-local TTS engine."""
    with tts_lock:
        engine = None
        try:
            comtypes.CoInitialize()
            engine = pyttsx3.init()
            engine.setProperty('rate', 140)
            engine.setProperty('volume', 1.0)
            voices = engine.getProperty('voices')
            if len(voices) > 1:
                engine.setProperty('voice', voices[1].id)
            
            logging.info(f"Speaking response: {text}")
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logging.error("TTS Error", exc_info=True)
        finally:
            try:
                if engine:
                    engine.endLoop()  # Add this first
                    engine.stop()  # Then stop
            except:
                pass
            comtypes.CoUninitialize()
            time.sleep(0.1)  # Add small cleanup delay

def hotkey_listener():
    """Listen for a global hotkey (F5) and trigger the screenshot analysis."""

    def hotkey_callback():
        global last_processing_time
        try:
            logging.debug("F5 pressed - input received")  # Add debug log
            
            if get_processing_status():
                elapsed = time.time() - last_processing_time
                logging.debug(f"Busy check: {elapsed:.1f}s since start")
                
                # Immediate reset if stuck
                if elapsed > 30:  # 30 second timeout
                    logging.warning("Force-resetting processing state")
                    set_processing_status(False)
                    return

                logging.info("F5 pressed but busy")
                return

            logging.info("Hotkey pressed - starting analysis")
            set_processing_status(True)
            threading.Thread(target=on_play_button_click, daemon=True).start()
            
        except Exception as e:
            logging.error("Hotkey error", exc_info=True)
            set_processing_status(False)

    keyboard.add_hotkey('f5', hotkey_callback)

def on_play_button_click():
    """Handle button press workflow"""
    global last_processing_time
    last_processing_time = time.time()
    try:
        logging.info("Button clicked - starting analysis")
        start_time = datetime.now()
        screenshot = capture_screenshot()
        
        filename = f"debug_screenshot_{int(time.time())}.jpg"
        screenshot.save(filename)
        logging.info(f"Screenshot saved as {filename}")
        image_b64 = image_to_base64(screenshot)
        
        response_text = analyze_image_with_llm(image_b64)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logging.info(f"Analysis completed in {elapsed:.2f}s")
    except Exception as e:
        logging.error("Error during analysis", exc_info=True)
        response_text = "Oops! Let's try that again."
    finally:
        # Move status update INSIDE the speaking block
        try:
            speak_response(response_text)
        except Exception as e:
            logging.error("Error during speech synthesis", exc_info=True)
        finally:
            # Add emergency reset before status update
            if time.time() - last_processing_time > 30:
                logging.warning("Emergency status reset")
            set_processing_status(False)
            logging.info("Processing status cleared")  # Add confirmation

def keep_model_alive():
    """Periodically sends a lightweight request to keep the server alive."""
    while True:
        time.sleep(2 * 60 - 15)  # Sleep 1:45 minutes
        try:
            # Use lightweight endpoint check instead of chat
            response = requests.get("http://192.168.50.250:30068/", timeout=5)
            logging.info(f"Keep-alive OK - Status {response.status_code}")
        except Exception as e:
            logging.error(f"Keep-alive failed: {str(e)}")

def main():
    """Main application entry point"""
    # Add this verification
    logging.info(f"Initial processing state: {get_processing_status()}")
    logging.info(f"Initial last_processing_time: {last_processing_time}")
    
    # Register the global hotkey in the main thread.
    hotkey_listener()
    
    # Start the keep-alive thread to keep the model loaded longer.
    threading.Thread(target=keep_model_alive, daemon=True).start()
    
    # Add watchdog thread
    def status_watchdog():
        while True:
            time.sleep(5)
            if get_processing_status():
                logging.debug("Processing status: BUSY")
            else:
                logging.debug("Processing status: READY")
    
    threading.Thread(target=status_watchdog, daemon=True).start()
    
    logging.info("Listening for global hotkey (F5)...")
    keyboard.wait()  # Keeps the program running and listening for hotkeys.

if __name__ == '__main__':
    main()
