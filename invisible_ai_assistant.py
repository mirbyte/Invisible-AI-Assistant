import os
import threading
import keyboard
from PIL import ImageGrab
import google.generativeai as genai
from dotenv import load_dotenv
import time
import urllib.request
from gtts import gTTS
import pygame
import numpy
import tempfile
import colorama
from colorama import Fore, Style


# Version 1.0.1


def check_internet_connection():
    endpoints = [
        'https://www.google.com',
        'https://www.microsoft.com'
    ]
    for url in endpoints:
        try:
            urllib.request.urlopen(url, timeout=3)
            return True
        except Exception:
            continue
    return False


# --- Configuration ---
colorama.init()
os.system("title github.com/mirbyte")
load_dotenv()

# Hotkeys
HOTKEY_QUESTION = 'alt+q'
HOTKEY_CODE = 'alt+c'
HOTKEY_TRANSLATE = 'alt+t'
HOTKEY_MULTICHOICE = 'alt+m'
HOTKEY_EXPLAIN = 'alt+e'
REPEAT_HOTKEY = 'alt+r'


# Prompts
PROMPT_QUESTION = "Analyze this screenshot for a test question and provide a clear, well-structured answer. Don't use code blocks or other special text formatting."
PROMPT_CODE = "Analyze this screenshot and respond to the code problem visible, type an answer only."
PROMPT_TRANSLATE = "Translate the text of the main context in this screenshot to English. You can ignore unnessessary information like links. Names don't need translation and don't repeat text that's already in english. Don't use text formatting like * characters."
PROMPT_MULTICHOICE = "Analyze this screenshot and respond to the multiple choice question visible with an answer only, no text formatting."
PROMPT_EXPLAIN = "Analyze the data in this screenshot and provide a clear, concise explanation focusing on key insights and patterns. Avoid code blocks and special formatting."

# Global variables
last_spoken_response = None


# --- API Setup ---
while not check_internet_connection():
    print("Waiting for internet connection...")
    time.sleep(5)
try:
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    if not gemini_api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file.")
    genai.configure(api_key=gemini_api_key)
    gemini_model = genai.GenerativeModel('gemini-2.0-flash')
    print("Gemini API configured successfully.")
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    exit()

# --- TTS Functions ---
def _speak_worker_gtts(text_to_speak):
    """Internal worker function to run gTTS and pygame in a separate thread."""
    temp_audio_file = None
    pygame_initialized = False
    try:
        tts = gTTS(text=text_to_speak, lang='en')
        # Use tempfile for safer cross-platform temporary file creation
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            temp_audio_file = fp.name
        tts.save(temp_audio_file)

        # Playback using Pygame Sound
        pygame.mixer.init()
        pygame_initialized = True
        try:
            sound = pygame.mixer.Sound(temp_audio_file)
            sound_length = sound.get_length()
            sound.play()
            time.sleep(sound_length + 0.5)
        except pygame.error as pygame_load_error:
            print(f"gTTS Worker: Error loading/playing sound: {pygame_load_error}")

    except Exception as e:
        print(f"gTTS Worker Error: {e}")
    finally:
        if pygame_initialized:
            try:
                pygame.mixer.quit()
                print("gTTS Worker: Pygame mixer quit.")
            except Exception as pygame_e:
                print(f"gTTS Worker: Error quitting pygame mixer: {pygame_e}")
        if temp_audio_file and os.path.exists(temp_audio_file):
            try:
                os.remove(temp_audio_file)
                print(f"gTTS Worker: Deleted temp audio file: {temp_audio_file}")
            except Exception as remove_e:
                print(f"gTTS Worker: Error deleting temp audio file {temp_audio_file}: {remove_e}")


def speak_text(text_to_speak):
    """Starts a separate thread to generate and play speech using gTTS and pygame."""
    global last_spoken_response
    if not text_to_speak:
        print("Speak Text: No text provided.")
        return
    last_spoken_response = text_to_speak
    thread = threading.Thread(target=_speak_worker_gtts, args=(text_to_speak,))
    thread.daemon = True
    thread.start()
    # We don't return the thread object here as we don't need to join it typically

# --- Core Functions ---
def analyze_image_gemini(image, prompt):
    """Sends PIL image with the specified prompt to Gemini and returns analysis."""
    if not gemini_model:
        return "Gemini model not initialized."
    try:
        response = gemini_model.generate_content([prompt, image], request_options={"timeout": 30})
        response.resolve()
        return response.text
    except Exception as e:
        try:
             print(f"Prompt Feedback: {response.prompt_feedback}")
        except Exception:
             pass
        return f"Gemini API error: {e}"

def take_screenshot_and_analyze(prompt, mode):
    """Takes screenshot, analyzes with the given prompt, and outputs in the specified mode."""
    print(f"\nHotkey detected! Analyzing with prompt: '{prompt[:50]}...' Mode: {mode.upper()}")
    try:
        # 1. Take Screenshot
        screenshot = ImageGrab.grab()
        # Save screenshot for debugging
        try:
            save_path = "debug_screenshot.png"
            screenshot.save(save_path)
        except Exception as save_e:
            print(f"Error saving screenshot: {save_e}")

        # 2. Analyze Screenshot using Gemini
        result = analyze_image_gemini(screenshot, prompt)

        # 3. Show Result (Print)
        print("\n--- Gemini Analysis Result ---")
        print(result)
        print("------------------------------\n")

        # 4. Clean and Output Result (Type or Speak)
        if result and isinstance(result, str):
            print("Cleaning result...")
            # Strip potential code block fences
            cleaned_result = result.strip()
            if cleaned_result.startswith('```') and cleaned_result.endswith('```'):
                lines = cleaned_result.splitlines()
                if len(lines) > 1:
                    # Remove first line (```python or ```) and last line (```)
                    cleaned_result = '\n'.join(lines[1:-1]).strip()
                else:
                    # Handle case where only ``` is present
                    cleaned_result = ''

            if cleaned_result:
                if mode == 'type':
                    print("Typing result...")
                    time.sleep(0.5) # Small delay
                    keyboard.write(cleaned_result)
                    print("Finished typing.")
                elif mode == 'tts':
                    print("Speaking result...")
                    speak_text(cleaned_result)
                    # TTS happens in background thread
                else:
                    print(f"Unknown output mode: {mode}")
            else:
                 print("Result was empty after cleaning.")
        else:
            print("No valid text result to process.")
        print(f"Ready. Listening for hotkeys...")

    except Exception as e:
        print(f"An error occurred during screenshot or analysis: {e}")
        print(f"Ready. Listening for hotkeys...")


# --- Hotkey Functions ---
def repeat_last_tts():
    """Repeats the last spoken text if available."""
    global last_spoken_response
    print(f"\nHotkey '{REPEAT_HOTKEY}' detected!")
    if last_spoken_response:
        print("Repeating last TTS response...")
        # Re-use the speak_text function which handles threading
        speak_text(last_spoken_response)
    else:
        print("No previous TTS response to repeat.")
    print(f"Ready. Listening for hotkeys...")


def handle_text():
    print(f"\nHotkey '{HOTKEY_TRANSLATE}' detected!")
    take_screenshot_and_analyze(PROMPT_TRANSLATE, 'tts') # Use TTS for translation output


# --- Main Execution ---
def play_beep(frequency=440, duration=100):
    """Play a simple beep sound using pygame."""
    pygame.mixer.init()
    sample_rate = 44100
    samples = numpy.array([4096 * numpy.sin(2.0 * numpy.pi * frequency * x / sample_rate) 
                      for x in range(0, sample_rate * duration // 1000)]).astype(numpy.int16)
    arr = numpy.column_stack((samples, samples))  # Create 2D array for stereo
    sound = pygame.sndarray.make_sound(arr)
    sound.play()
    time.sleep(duration / 1000)
    pygame.mixer.quit()



def main():
    if not check_internet_connection():
        print("No internet connection detected. Please connect and restart the script.")
        exit()
    print("Internet connection confirmed.")
    
    # startup sound
    play_beep(660, 100)
    time.sleep(0.1)
    play_beep(880, 100)

    # Register hotkeys with specific prompts
    keyboard.add_hotkey(HOTKEY_QUESTION, lambda: take_screenshot_and_analyze(PROMPT_QUESTION, 'type'))
    keyboard.add_hotkey(HOTKEY_CODE, lambda: take_screenshot_and_analyze(PROMPT_CODE, 'type'))
    keyboard.add_hotkey(HOTKEY_TRANSLATE, handle_text)
    keyboard.add_hotkey(HOTKEY_MULTICHOICE, lambda: take_screenshot_and_analyze(PROMPT_MULTICHOICE, 'tts'))
    keyboard.add_hotkey(HOTKEY_EXPLAIN, lambda: take_screenshot_and_analyze(PROMPT_EXPLAIN, 'tts'))
    keyboard.add_hotkey(REPEAT_HOTKEY, repeat_last_tts)


    print("")
    print(f"Script started. Listening for hotkeys:")
    print(f" - General Question (Type): {Fore.CYAN}{HOTKEY_QUESTION}{Style.RESET_ALL}")
    print(f" - Coding Question (Type): {Fore.CYAN}{HOTKEY_CODE}{Style.RESET_ALL}")
    print(f" - Translate (TTS): {Fore.CYAN}{HOTKEY_TRANSLATE}{Style.RESET_ALL}")
    print(f" - Multiple Choice (TTS): {Fore.CYAN}{HOTKEY_MULTICHOICE}{Style.RESET_ALL}")
    print(f" - Explanation (TTS): {Fore.CYAN}{HOTKEY_EXPLAIN}{Style.RESET_ALL}")
    print(f" - Repeat Last TTS Answer: {Fore.CYAN}{REPEAT_HOTKEY}{Style.RESET_ALL}")

    print("")
    print("")
    print("Press alt+esc to stop.")

    # Keep the script running
    keyboard.wait('alt+esc') # Wait for ALT+ESC key to exit
    
    # quit sound
    play_beep(880, 100)
    time.sleep(0.1)
    play_beep(660, 100)

if __name__ == "__main__":
    main()

