import tkinter as tk
from tkinter import ttk
import mss
from PIL import Image
import base64
import requests
import pyttsx3
import io

import logging
from datetime import datetime

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
    """Convert PIL Image to base64 Data URI string"""
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64_str}"

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
            "content": (
                "What's happening in my game right now? Please tell me!\n\n"
                "![screenshot](data:image/jpeg;base64,{image_base64})"
            ).format(image_base64=image_base64)
        }
    ]
    
    try:
        response = requests.post(
            "http://192.168.50.250:30068/api/generate",
            json={
                "model": "gemma3:27b-it-q8_0",  # Your specified model
                "messages": messages,
                "stream": False
            }
        )
        response.raise_for_status()
        
        # Log full response data for debugging
        response_json = response.json()
        logging.debug("Full API response: %s", response_json)
        
        # Log successful response with timing
        elapsed = (datetime.now() - start_time).total_seconds()
        logging.info(f"API request completed in {elapsed:.2f}s")
        
        # Safely extract response text, default to empty string if missing
        response_text = response_json.get("response", "")
        logging.debug(f"Response text: {response_text}")
        return response_text
        
    except Exception as e:
        # Log detailed error information
        logging.error(f"API request failed: {str(e)}", exc_info=True)
        return f"Oops! Let's try that again. (error sound)"

def speak_response(text):
    """Convert text to child-friendly speech"""
    
    # Log speaking request
    logging.info(f"Speaking response: {text}")
    engine = pyttsx3.init()
    engine.setProperty('rate', 140)  # Slower speaking speed
    engine.setProperty('volume', 1.0)
    
    # Try to use a more animated voice if available
    voices = engine.getProperty('voices')
    if len(voices) > 1:
        engine.setProperty('voice', voices[1].id)  # Often female-sounding voice
    
    engine.say(text)
    engine.runAndWait()

def on_play_button_click():
    """Handle button press workflow"""
    
    # Log button click event
    logging.info("Button clicked - starting analysis")
    start_time = datetime.now()
    screenshot = capture_screenshot()
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

def main():
    """Main application entry point"""
    # Create child-friendly GUI
    root = tk.Tk()
    root.title("Game Helper Buddy")
    root.geometry("400x200")
    root.configure(bg="#2E8B57")

    style = ttk.Style()
    style.configure("TButton", 
                    font=("Comic Sans MS", 24, "bold"),
                    padding=20,
                    foreground="#FFD700",
                    background="#4169E1")
    
    button = ttk.Button(root, 
                       text=" What's This? ", 
                       command=on_play_button_click,
                       style="TButton")
    button.pack(expand=True, padx=20, pady=20)
    
    root.mainloop()

if __name__ == '__main__':
    main()
