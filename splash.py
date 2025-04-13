import tkinter as tk
import subprocess
import threading
import os
import time

LOCK_FILE = "training.lock"
EXECUTABLE = "Training.exe"  # Update if needed
TIMEOUT = 100  # Max wait time in seconds

# Function to check for training.lock and close the splash
def wait_for_lock(root):
    while not os.path.exists(LOCK_FILE):
        if os.path.exists(LOCK_FILE):
            root.destroy() # Close if lock file appears
            return
        time.sleep(0.5)  # Check every 0.5 seconds
    root.destroy()  # Auto-close after timeout

# Function to start Training.exe
def start_executable():
    subprocess.Popen([EXECUTABLE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

# Create the splash screen
root = tk.Tk()
root.title("Entypt Training")
root.overrideredirect(True)  # Remove window decorations

# Set window size and position in the center
width, height = 350, 180
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x_pos = (screen_width - width) // 2
y_pos = (screen_height - height) // 2
root.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

# Custom styling
root.configure(bg="#DCDAD5")

# Create a title label
title_label = tk.Label(root, text="Entypt", font=("Arial", 14, "bold"), fg="black", bg="#DCDAD5")
title_label.pack(pady=10)

# Create a message label
message_label = tk.Label(root, text="Please wait Application Loading...", font=("Arial", 11), fg="black", bg="#DCDAD5")
message_label.pack()

# Create a progress bar using canvas
canvas = tk.Canvas(root, width=250, height=10, bg="#000000", highlightthickness=0)
canvas.pack(pady=15)
progress_rect = canvas.create_rectangle(0, 0, 0, 10, fill="gray")  #gray progress bar

# Looping progress bar animation
def animate():
    while not os.path.exists(LOCK_FILE):
        for i in range(0, 251, 10):  # Forward animation
            if os.path.exists(LOCK_FILE):
                return
            canvas.coords(progress_rect, 0, 0, i, 10)
            root.update_idletasks()
            time.sleep(0.05)

        for i in range(0, 251, 10):  # Reverse animation
            if os.path.exists(LOCK_FILE):
                return
            canvas.coords(progress_rect, 0, 0, i, 10)
            root.update_idletasks()
            time.sleep(0.05)

# Smooth fade-in effect
def fade_in():
    alpha = 0.1
    while alpha < 1.0:
        root.attributes("-alpha", alpha)
        alpha += 0.1
        time.sleep(0.05)

# Track start time
start_time = time.time()

# Start Entypt.exe in a new thread
threading.Thread(target=start_executable, daemon=True).start()

# Start looping animation and fade-in effect
threading.Thread(target=animate, daemon=True).start()
threading.Thread(target=fade_in, daemon=True).start()

# Start the lock file checker in a new thread
threading.Thread(target=wait_for_lock, args=(root,), daemon=True).start()

# Run the splash screen
root.mainloop()