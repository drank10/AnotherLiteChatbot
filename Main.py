import os
import wave
import pyaudio
import requests
from subprocess import Popen, PIPE
import json  # Import the json module to handle JSON parsing
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog, ttk
from PIL import Image, ImageTk  # For handling image display in Tkinter
import cv2  # For video processing (opencv-python-headless)
import numpy as np
import queue
from flask import Flask, send_file, render_template_string, make_response
import shutil

# Theme definitions
THEMES = {
    'Light': {'bg': '#FFFFFF', 'fg': '#000000', 'btn_bg': '#E0E0E0', 'text_area': '#FFFFFF'},
    'Dark': {'bg': '#212121', 'fg': '#FFFFFF', 'btn_bg': '#424242', 'text_area': '#373737'},
    'Blue': {'bg': '#B0E0E6', 'fg': '#00008B', 'btn_bg': '#ADD8E6', 'text_area': '#AEEEEE'},
    # Add more themes as needed
}

# Default theme
current_theme = THEMES['Light']

# Queue for communicating between threads
response_queue = queue.Queue()

# Variable to hold the current AI response thread
current_ai_thread = None

# Variable to track if the chatbot is talking
is_talking = False

def apply_theme(theme_name):
    global current_theme
    current_theme = THEMES[theme_name]
    
    # Apply background and foreground colors
    root.configure(bg=current_theme['bg'])
    conversation_text.configure(bg=current_theme['text_area'], fg=current_theme['fg'], insertbackground=current_theme['fg'], highlightbackground=current_theme['fg'])
    text_entry.configure(bg=current_theme['text_area'], fg=current_theme['fg'], insertbackground=current_theme['fg'], highlightbackground=current_theme['fg'])
    system_role_entry.configure(bg=current_theme['text_area'], fg=current_theme['fg'], insertbackground=current_theme['fg'], highlightbackground=current_theme['fg'])
    
    # Apply button background color
    for button in [load_file_button, set_idle_avatar_button, set_talking_avatar_button, send_button, start_button, exit_button, stop_button, regenerate_button]:
        button.configure(bg=current_theme['btn_bg'], fg=current_theme['fg'])
    
    # Apply status label foreground and background color
    status_label.configure(fg=current_theme['fg'], bg=current_theme['bg'])
    
    # Update avatar label background
    avatar_label.config(bg=current_theme['bg'])
    
    # Update labels' background colors
    system_role_label.config(bg=current_theme['bg'])
    type_message_label.config(bg=current_theme['bg'])
    
    # Update system_role_frame background
    system_role_frame.config(bg=current_theme['bg'])

# Configuration settings
WHISPER_MODEL = "models/ggml-base.en.bin"
PIPER_MODEL = "en_US-kristin-medium.onnx"
PIPER_CONFIG = "en_US-kristin-medium.onnx.json"
LLM_URL = "http://127.0.0.1:1234/v1/chat/completions"

# Variables to hold the paths for idle and talking avatars
idle_avatar_path = "static/idle.png"
talking_avatar_path = "static/talking.gif"

def record_audio():
    update_status("Recording audio...")
    # Record audio from the microphone and save to input.wav
    chunk = 1024  # Record in chunks of 1024 samples
    sample_format = pyaudio.paInt16  # 16 bits per sample
    channels = 1
    fs = 16000  # Sampling frequency (Hz)
    seconds = 5  # Duration of recording

    silence_threshold = 1000  # Threshold for silence detection (adjust this value as needed)
    max_silence_duration = 2 * fs // chunk  # Maximum number of silent chunks before stopping (adjust this duration)

    p = pyaudio.PyAudio()  # Create an interface to PortAudio

    stream = p.open(format=sample_format,
                    channels=channels,
                    rate=fs,
                    frames_per_buffer=chunk,
                    input=True)

    frames = []  # Initialize array to store frames
    silent_chunks_count = 0  # Counter for consecutive silent chunks

    while True:
        data = np.frombuffer(stream.read(chunk), dtype=np.int16)
        
        # Check if the chunk is silence
        if np.abs(data).mean() < silence_threshold:
            silent_chunks_count += 1
            if silent_chunks_count >= max_silence_duration:
                break  # Stop recording if we've had enough silence
        else:
            silent_chunks_count = 0

        frames.append(data.tobytes())

    # Stop and close the stream
    stream.stop_stream()
    stream.close()

    # Terminate the PortAudio interface
    p.terminate()

    # Save the recorded data as a WAV file
    wf = wave.open("input.wav", 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(sample_format))
    wf.setframerate(fs)
    wf.writeframes(b''.join(frames))
    wf.close()
    update_status("Audio recording completed.")

def transcribe_audio():
    # Transcribe the recorded audio using whisper-cli
    cmd = f"whisper-cli -m {WHISPER_MODEL} -f input.wav"
    output = os.popen(cmd).read().strip()
    return output

def get_llm_response(prompt, system_role):
    update_status("Waiting for LLM response...")
    # Send the prompt to the locally hosted LLM and get a plain text response
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "<your-model-here>",
        "messages": [
            {"role": "system", "content": system_role},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False
    }

    response = requests.post(LLM_URL, headers=headers, json=data)
    
    # Parse the JSON response to extract the 'content' field
    response_json = response.json()
    llm_response_content = response_json['choices'][0]['message']['content']
    
    update_status("LLM response received.")
    return llm_response_content

def synthesize_speech(text):
    update_status("Synthesizing speech...")
    # Use piper TTS to convert text to speech and save as welcome.wav
    cmd = f"./piper --model {PIPER_MODEL} --config {PIPER_CONFIG} --output_file welcome.wav"
    process = Popen(cmd, stdin=PIPE)
    process.communicate(input=text.encode())
    process.wait()  # Ensure the process completes before moving on
    update_status("Speech synthesis completed.")

def play_audio(file_name="welcome.wav"):
    global is_talking
    
    update_status("Playing audio...")
    
    # Use pyaudio to play the generated audio file
    chunk = 1024  # Record in chunks of 1024 samples

    wf = wave.open(file_name, 'rb')

    p = pyaudio.PyAudio()  # Create an interface to PortAudio

    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True)

    data = wf.readframes(chunk)
    
    while data:
        stream.write(data)
        data = wf.readframes(chunk)

    # Stop and close the stream
    stream.stop_stream()
    stream.close()

    # Terminate the PortAudio interface
    p.terminate()
    update_status("Audio playback completed.")

    # Update the avatar image back to the idle avatar
    idle_img = ImageTk.PhotoImage(Image.open(idle_avatar_path))
    avatar_label.config(image=idle_img)
    avatar_label.image = idle_img  # Keep a reference to avoid garbage collection
    
    # Set the chatbot as not talking
    is_talking = False

def handle_input():
    global current_ai_thread
    
    # Stop any ongoing AI response generation
    if current_ai_thread is not None and current_ai_thread.is_alive():
        current_ai_thread.join(timeout=0)
    
    user_input = text_entry.get().strip()
    system_role = system_role_entry.get().strip()  # Get the system role from its entry field
    
    if user_input.lower() in ["exit", "quit"]:
        print("Exiting chatbot. Goodbye!")
        root.destroy()
        return

    conversation_text.insert(tk.END, f"You: {user_input}\n")
    conversation_text.yview(tk.END)  # Scroll to the end of the text widget
    root.update_idletasks()  # Allow the GUI to update
    
    # Get a response from the LLM in a separate thread
    current_ai_thread = threading.Thread(target=get_and_display_llm_response, args=(user_input, system_role))
    current_ai_thread.start()

def get_and_display_llm_response(prompt, system_role):
    global talking_img  # Declare this as a global variable if not already

    # Update the avatar image to the talking avatar before making the request
    talking_img = ImageTk.PhotoImage(Image.open(talking_avatar_path))
    avatar_label.config(image=talking_img)
    avatar_label.image = talking_img  # Keep a reference to avoid garbage collection

    # Set is_talking to True to indicate the chatbot is talking
    global is_talking
    is_talking = True
    
    llm_response = get_llm_response(prompt, system_role).strip()
    
    conversation_text.insert(tk.END, f"Chatbot: {llm_response}\n")
    conversation_text.yview(tk.END)  # Scroll to the end of the text widget
    root.update_idletasks()  # Allow the GUI to update

    # Synthesize the LLM's response into speech and play it
    synthesize_speech(llm_response)
    play_audio()

    # Clear the entry field for the next input
    text_entry.delete(0, tk.END)

def stop_ai_response():
    global current_ai_thread
    
    if current_ai_thread is not None and current_ai_thread.is_alive():
        current_ai_thread.join(timeout=0)  # Forcefully terminate the thread (not recommended for all use cases)
    
    conversation_text.insert(tk.END, "AI response generation stopped.\n")
    conversation_text.yview(tk.END)  # Scroll to the end of the text widget

    # Update the avatar image back to the idle avatar
    idle_img = ImageTk.PhotoImage(Image.open(idle_avatar_path))
    avatar_label.config(image=idle_img)
    avatar_label.image = idle_img  # Keep a reference to avoid garbage collection

def regenerate_last_response():
    global current_ai_thread
    
    if current_ai_thread is not None and current_ai_thread.is_alive():
        current_ai_thread.join(timeout=0)
    
    # Extract the last user input from the conversation text
    lines = conversation_text.get("1.0", tk.END).splitlines()
    last_user_input = ""
    for line in reversed(lines):
        if line.startswith("You: "):
            last_user_input = line[5:]  # Remove "You: "
            break
    
    system_role = system_role_entry.get().strip()  # Get the system role from its entry field
    
    if not last_user_input:
        conversation_text.insert(tk.END, "No previous user input found to regenerate response.\n")
        conversation_text.yview(tk.END)  # Scroll to the end of the text widget
        return

    # Generate and display the AI response in a separate thread
    current_ai_thread = threading.Thread(target=get_and_display_llm_response, args=(last_user_input, system_role))
    current_ai_thread.start()

def start_chat():
    threading.Thread(target=chat_loop).start()

def chat_loop():
    while True:
        # Record and transcribe the user's speech
        record_audio()
        transcription = transcribe_audio().strip()

        root.update_idletasks()  # Allow the GUI to update

        if "exit" in transcription.lower() or "quit" in transcription.lower():
            print("Exiting chatbot. Goodbye!")
            break

        conversation_text.insert(tk.END, f"You: {transcription}\n")
        conversation_text.yview(tk.END)  # Scroll to the end of the text widget
        root.update_idletasks()  # Allow the GUI to update

        # Get a response from the LLM
        system_role = system_role_entry.get().strip()  # Get the system role from its entry field
        llm_response = get_llm_response(transcription, system_role).strip()
        
        conversation_text.insert(tk.END, f"Chatbot: {llm_response}\n")
        conversation_text.yview(tk.END)  # Scroll to the end of the text widget
        root.update_idletasks()  # Allow the GUI to update

        # Synthesize the LLM's response into speech and play it
        synthesize_speech(llm_response)
        play_audio()

        root.update_idletasks()  # Allow the GUI to update

def exit_chat():
    if messagebox.askokcancel("Exit", "Do you want to exit?"):
        root.destroy()

# Function to browse and load a text file into the text entry field
def load_text_file():
    file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
    if file_path:
        with open(file_path, 'r') as file:
            content = file.read()
            system_role_entry.delete(0, tk.END)
            system_role_entry.insert(tk.END, content)

def update_status(message):
    status_label.config(text=message)

def update_avatar(file_path, avatar_type):
    global idle_avatar_path, talking_avatar_path
    
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
        # It's an image, save as is
        if avatar_type == 'idle':
            idle_avatar_path = "static/idle.gif" if file_path.lower().endswith('.gif') else "static/idle.png"
        else:
            talking_avatar_path = "static/talking.gif" if file_path.lower().endswith('.gif') else "static/talking.png"
            
        shutil.copy(file_path, idle_avatar_path if avatar_type == 'idle' else talking_avatar_path)
        
        photo_img = ImageTk.PhotoImage(Image.open(idle_avatar_path if avatar_type == 'idle' else talking_avatar_path))
        
        if avatar_type == 'idle':
            avatar_label.config(image=photo_img)
            avatar_label.image = photo_img  # Keep a reference to avoid garbage collection
        else:
            avatar_label.config(image=photo_img)
            avatar_label.image = photo_img  # Keep a reference to avoid garbage collection
    else:
        messagebox.showerror("Error", "Unsupported file format. Please use an image.")


def set_avatar(avatar_type):
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif")])
    if file_path:
        update_avatar(file_path, avatar_type)

# Setup the main window for the chatbot
root = tk.Tk()
root.title("Chatbot")

# Create a frame for the left pane (image and conversation)
left_pane = tk.Frame(root, bg=current_theme['bg'])
left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Use grid instead of pack for avatar_label and conversation_text
avatar_img = ImageTk.PhotoImage(Image.open(idle_avatar_path))
avatar_label = tk.Label(left_pane, image=avatar_img)
avatar_label.grid(row=0, column=0, pady=(10, 20), sticky="nsew")

conversation_text = scrolledtext.ScrolledText(left_pane, wrap=tk.WORD, width=60, height=15)
conversation_text.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")

# Configure grid rows and columns to expand properly
left_pane.grid_rowconfigure(0, weight=1)
left_pane.grid_rowconfigure(1, weight=1)
left_pane.grid_columnconfigure(0, weight=1)

# Create a frame for the right pane (controls)
right_pane = tk.Frame(root, bg=current_theme['bg'])
right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

# Create a variable to hold the selected theme name
theme_var = tk.StringVar(root)
theme_var.set('Light')  # Set default value

# Function to change theme
def change_theme(*args):
    apply_theme(theme_var.get())

# Create and place the dropdown menu in the right pane
theme_menu = ttk.OptionMenu(right_pane, theme_var, *THEMES.keys(), command=change_theme)
theme_menu.pack(pady=(10, 5))  # Add some padding at the top and bottom

# Create a status label to show the current operation in the right pane
status_label = tk.Label(right_pane, text="", fg="blue")
status_label.pack(pady=(0, 10))  # Add some padding

system_role_frame = tk.Frame(right_pane, bg='white')
system_role_frame.pack(pady=5)  # Add some vertical padding


# Create a label above the system role entry field with white background
system_role_label = tk.Label(system_role_frame, text="System Role Prompt:", bg='white')
system_role_label.pack(side=tk.LEFT, pady=(5, 5))  # Adjusted padding

# Create an entry widget for the system role prompt
system_role_entry = tk.Entry(system_role_frame, width=50)
system_role_entry.insert(tk.END, "Always answer in rhymes.")  # Default system role
system_role_entry.pack(side=tk.LEFT, pady=5)

# Create a load file button to select a text file and pack it into the new frame
load_file_button = tk.Button(system_role_frame, text="Load Text File", command=load_text_file)
load_file_button.pack(side=tk.LEFT, fill=tk.X, padx=(0, 5), pady=(0, 5))  # Add horizontal padding between buttons

# Create a button to set the idle avatar image
set_idle_avatar_button = tk.Button(right_pane, text="Set Idle Avatar", command=lambda: set_avatar('idle'))
set_idle_avatar_button.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))

# Create a button to set the talking avatar image
set_talking_avatar_button = tk.Button(right_pane, text="Set Talking Avatar", command=lambda: set_avatar('talking'))
set_talking_avatar_button.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))

# Create a start button and pack it into the right pane
start_button = tk.Button(right_pane, text="Start Chat", command=start_chat)
start_button.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))

# Create a label above the text entry field with white background
type_message_label = tk.Label(right_pane, text="Type Message:", bg='white')
type_message_label.pack(pady=(10, 5))

# Create an entry widget for text input in the right pane and move it to the bottom
text_entry = tk.Entry(right_pane, width=75)
text_entry.insert(tk.END, "")  # Default text can be left empty or set as needed
text_entry.pack(pady=10)

# Bind the Enter key to the handle_input function
text_entry.bind("<Return>", lambda event: handle_input())

# Create a new frame to hold the buttons in one row
buttons_frame = tk.Frame(right_pane, bg=current_theme['bg'])
buttons_frame.pack(side=tk.TOP, fill=tk.X)  # Pack at the bottom

send_button = tk.Button(buttons_frame, text="Send", command=handle_input)
send_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

stop_button = tk.Button(buttons_frame, text="Stop AI Response", command=stop_ai_response)
stop_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

regenerate_button = tk.Button(buttons_frame, text="Regenerate Last Response", command=regenerate_last_response)
regenerate_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

exit_button = tk.Button(buttons_frame, text="Exit", command=exit_chat)
exit_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

# Initialize Flask app and route to serve the avatar
from flask import Flask, send_file

app = Flask(__name__, static_folder='static')

# HTML template with JavaScript to refresh the avatar image
html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chatbot Avatar</title>
    <style>
        #avatar {
            max-width: 200px;
            max-height: 200px;
        }
    </style>
</head>
<body>
    
    <img id="avatar" src="/avatar?rand=<?=rand(1,1000);?" alt="Chatbot Avatar">
    <script>
        // Function to refresh the avatar image
        function refreshAvatar() {
            const img = document.getElementById('avatar');
            fetch('/avatar?' + new Date().getTime())
                .then(response => response.blob())
                .then(blob => {
                    const url = URL.createObjectURL(blob);
                    img.src = url;
                    // Revoke the object URL to free up memory
                    setTimeout(() => URL.revokeObjectURL(url), 1000);  // Adjust timeout as needed
                })
                .catch(error => console.error('Error fetching avatar:', error));
        }

        // Refresh the avatar every 5 seconds (or adjust as needed)
        setInterval(refreshAvatar, 2000);  // Change interval to 1 second for faster testing
    </script>
</body>
</html>
"""

# Flask route to serve the HTML template
@app.route('/')
def index():
    return render_template_string(html_template)

# Flask route to serve the avatar
@app.route('/avatar')
def avatar():
    global talking_avatar_path, idle_avatar_path
    
    # Determine which avatar image to serve based on whether the chatbot is talking or not
    avatar_path = talking_avatar_path if is_talking else idle_avatar_path

    response = make_response(send_file(avatar_path))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

# Start Flask app in a separate thread
import threading
def run_flask_app():
    app.run(host='0.0.0.0', port=5000)

flask_thread = threading.Thread(target=run_flask_app)
flask_thread.daemon = True  # Daemonize the thread to ensure it exits with the program
flask_thread.start()

# Apply the default theme on startup
apply_theme(theme_var.get())

# Run the GUI application
root.mainloop()
