import sys
import tkinter as tk
from tkinter import ttk
import time
from datetime import datetime
import logging
import os
import ctypes
import win32con
import win32gui
import win32file
import win32api
import win32process
import random
import atexit
import threading
from ctypes import wintypes, windll

# Define fallback constants
FALLBACK_THRESHOLD = 70

# Lock file path
LOCK_FILE_PATH = "lockscreen.lock"
LOCK_FILE_HANDLE = None

# Global variable to track authentication scores
global_auth_scores = {
    "weighted_score": 0.0,
    "interval_score": 0.0,
    "pattern_score": 0.0,
    "speed_score": 0.0,
    "threshold": 0.0
}

# Set up logging
logging.basicConfig(
    filename='lockscreen_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

# Define WinAPI constants for better key blocking
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Initialize global values for keyboard hook
keyboard_hook = None
user32 = ctypes.WinDLL('user32', use_last_error=True)

# Create a C function type for the hook callback
HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

# Define the KBDLLHOOKSTRUCT structure for keyboard hook
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]

# Constants for keyboard hook
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10
LLKHF_ALTDOWN = 0x20
LLKHF_UP = 0x80

# Global flag to control keyboard hook behavior
security_mode_active = False

# Initialize _hook_references as a global dictionary to fix the error
_hook_references = {}

def create_temp_lock_file():
    """Create a temporary lock file that will be automatically removed when the process exits"""
    global LOCK_FILE_HANDLE
    
    try:
        # Check if file exists first and try to open it to see if another process has it locked
        if os.path.exists(LOCK_FILE_PATH):
            try:
                # Try to open and immediately close the file
                with open(LOCK_FILE_PATH, 'r+') as test_file:
                    logging.info("Lock file exists but is not locked by another process")
                
                # If we can open it, it's likely a stale file, so remove it
                os.remove(LOCK_FILE_PATH)
                logging.info("Removed stale lock file")
            except IOError:
                logging.info("Lock file is locked by another process")
                return False
        
        # Create a file with DELETE_ON_CLOSE flag
        LOCK_FILE_HANDLE = win32file.CreateFile(
            LOCK_FILE_PATH,                           # File name
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,  # Access mode
            0,                                        # Share mode - no sharing
            None,                                     # Security attributes
            win32file.CREATE_ALWAYS,                  # Creation disposition
            win32file.FILE_ATTRIBUTE_TEMPORARY | win32file.FILE_FLAG_DELETE_ON_CLOSE,  # Flags and attributes
            None                                      # Template file
        )
        
        # Write the current PID to the file
        win32file.WriteFile(LOCK_FILE_HANDLE, str(os.getpid()).encode('utf-8'))
        
        logging.info(f"Created temporary lock file with PID {os.getpid()}")
        
        # Register function to close the handle on exit
        atexit.register(close_lock_file)
        
        return True
    except Exception as e:
        logging.error(f"Error creating temporary lock file: {e}")
        return False

def close_lock_file():
    """Close the lock file handle which will trigger automatic deletion"""
    global LOCK_FILE_HANDLE
    
    try:
        if LOCK_FILE_HANDLE is not None:
            win32file.CloseHandle(LOCK_FILE_HANDLE)
            LOCK_FILE_HANDLE = None
            logging.info("Lock file handle closed and file will be automatically deleted")
    except Exception as e:
        logging.error(f"Error closing lock file handle: {e}")

@HOOKPROC
def keyboard_hook_proc(nCode, wParam, lParam):
    """Low level keyboard hook to intercept and block system keys"""
    global security_mode_active
    
    if nCode < 0:
        return user32.CallNextHookEx(keyboard_hook, nCode, wParam, lParam)
    
    # Always block dangerous system keys regardless of mode
    if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
        kbd = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        
        # Allow Windows+L and Ctrl+Alt+Del
        if kbd.vkCode == 0x4C and (user32.GetKeyState(win32con.VK_LWIN) & 0x8000 or 
                                user32.GetKeyState(win32con.VK_RWIN) & 0x8000):
            return user32.CallNextHookEx(keyboard_hook, nCode, wParam, lParam)
            
        if (kbd.vkCode == win32con.VK_DELETE and 
            (user32.GetKeyState(win32con.VK_CONTROL) & 0x8000) and 
            (user32.GetKeyState(win32con.VK_MENU) & 0x8000)):
            return user32.CallNextHookEx(keyboard_hook, nCode, wParam, lParam)
        
        # Block Alt+Tab, Alt+Esc, Ctrl+Esc, etc.
        if ((kbd.vkCode == win32con.VK_TAB and (kbd.flags & LLKHF_ALTDOWN)) or
            (kbd.vkCode == win32con.VK_ESCAPE and (kbd.flags & LLKHF_ALTDOWN)) or
            (kbd.vkCode == win32con.VK_ESCAPE and (user32.GetKeyState(win32con.VK_CONTROL) & 0x8000)) or
            (kbd.vkCode == win32con.VK_ESCAPE and (user32.GetKeyState(win32con.VK_SHIFT) & 0x8000) and 
             (user32.GetKeyState(win32con.VK_CONTROL) & 0x8000)) or
            kbd.vkCode == win32con.VK_LWIN or kbd.vkCode == win32con.VK_RWIN or
            (kbd.vkCode == win32con.VK_F4 and (kbd.flags & LLKHF_ALTDOWN))):
            return 1  # Block the key
            
        # Block Windows+R, Windows+E, Windows+X, etc.
        if ((user32.GetKeyState(win32con.VK_LWIN) & 0x8000 or 
             user32.GetKeyState(win32con.VK_RWIN) & 0x8000)):
            return 1  # Block Windows key combinations
            
        # Block Ctrl+Shift+Esc (Task Manager)
        if (kbd.vkCode == win32con.VK_ESCAPE and 
            (user32.GetKeyState(win32con.VK_CONTROL) & 0x8000) and 
            (user32.GetKeyState(win32con.VK_SHIFT) & 0x8000)):
            return 1  # Block the key
            
        # Block all function keys (F1-F12)
        if win32con.VK_F1 <= kbd.vkCode <= win32con.VK_F12:
            return 1  # Block function keys
            
        # Block Print Screen
        if kbd.vkCode == win32con.VK_SNAPSHOT:
            return 1  # Block Print Screen
            
        # Block Alt+Space (system menu)
        if kbd.vkCode == win32con.VK_SPACE and (kbd.flags & LLKHF_ALTDOWN):
            return 1  # Block Alt+Space
                
    return user32.CallNextHookEx(keyboard_hook, nCode, wParam, lParam)

class KeystrokeLockscreen:
    def __init__(self, root):
        self.root = root
        self.root.title("Security Lockscreen")
        
        # Flag to prevent double cleanup
        self.cleanup_done = False

        # Make it fullscreen and always on top
        self.root.attributes('-fullscreen', True, '-topmost', True)
        self.root.configure(bg='black')

        # Initialize basic variables
        self.matrix_rain_drops = []
        self.matrix_rain_running = True
        self.security_questions = {}
        self.current_question_index = 0
        self.security_mode = False
        self.current_security_input = ""  # For security questions input
        self.cursor_visible = True        # For blinking cursor effect
        self.matrix_settings = {
            "char_set": "alphanumeric",
            "custom_chars": "",
            "special_char": "o",
            "matrix_color": "lime",
            "matrix_speed": 10,
            "matrix_density": 5
        }
        self.current_input = ""
        self.keystroke_times = []
        self.last_keystroke_time = None
        self.model = None
        self.PASSWORD = ""
        self.THRESHOLD = FALLBACK_THRESHOLD
        self.hook_installed = False
        self.last_matrix_update = 0
        self.matrix_update_interval = 50  # ms
        self.char_image_cache = {}  # For caching character images
        
        # Create the canvas for the Matrix Rain effect - deferred initialization
        self.canvas = None
        
        # Performance optimization - Set process priority higher
        try:
            win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.ABOVE_NORMAL_PRIORITY_CLASS)
        except Exception as e:
            logging.warning(f"Failed to set process priority: {e}")
        
        # Create minimal GUI first for faster startup
        self.quick_setup_gui()
        
        # Start a thread to load the model and heavy components
        threading.Thread(target=self.deferred_initialization, daemon=True).start()
        
        # Start time update right away
        self.update_time()
        
        # Override window manager and block all escape methods
        self.setup_window_manager_override()

    def setup_window_manager_override(self):
        """Make sure window stays on top and intercepts all keys"""
        self.root.after(100, self.keep_on_top)
        
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        
        # Force the window to be active and focused
        ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

        try:
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        except Exception as e:
            logging.error(f"Error setting window position: {e}")

    def keep_on_top(self):
        """Ensure window stays topmost and focused"""
        if self.root.winfo_exists():
            self.root.attributes('-topmost', True)
            if not self.security_mode:  # Only force focus if not in security mode
                self.root.focus_force()
            self.root.after(100, self.keep_on_top)

    def deferred_initialization(self):
        """Load heavy components after initial GUI is shown"""
        # Create the canvas for the Matrix Rain effect - deferred for faster startup
        self.canvas = tk.Canvas(self.root, width=self.root.winfo_screenwidth(), 
                               height=self.root.winfo_screenheight(), 
                               bg='black', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.frame.lift()  # Keep UI elements on top of canvas
        
        # Import heavy modules only when needed
        import numpy as np
        from sklearn.preprocessing import StandardScaler
        import pickle
        
        # These imports are used later and can be loaded in background
        self.np = np
        
        # Hide taskbar (deferred to reduce startup time)
        self.root.after(100, self.hide_taskbar)
        
        # Install keyboard hook for system-wide key blocking
        self.root.after(200, self.install_keyboard_hook)
        
        # Block Windows keys using Tkinter bindings as backup
        self.root.after(300, self.block_windows_keys)
        
        # Load model (potentially slow operation)
        if not self.load_model():
            logging.error("No trained model found! Closing application.")
            self.root.after(0, lambda: self.show_error_and_close("Error: No trained model found! Please run training first."))
            self.root.after(2000, self.cleanup)  # Close after 2 seconds
            return
            
        # Now that we have the necessary data, initialize matrix effect
        # Use after() to ensure this runs on the main thread
        self.root.after(0, self.init_matrix_rain_effect_incremental)
        
        # Complete the GUI setup with all elements
        self.root.after(0, self.complete_gui_setup)

    def install_keyboard_hook(self):
        """Install keyboard hook with fixes for .exe compatibility"""
        global keyboard_hook, _hook_references

        if self.hook_installed:
            return

        try:
            # Store reference to prevent garbage collection
            _hook_references['proc'] = keyboard_hook_proc  

            # Get module handle for PyInstaller EXE
            if getattr(sys, 'frozen', False):  
                module_handle = ctypes.windll.kernel32.GetModuleHandleW(None)  # Use EXE handle
            else:
                module_handle = win32api.GetModuleHandle(None)  # Normal script execution

            # Use SetWindowsHookExW instead of SetWindowsHookExA
            keyboard_hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                _hook_references['proc'],  # Use stored reference
                module_handle,
                0
            )

            if not keyboard_hook:
                error_code = ctypes.get_last_error()
                logging.error(f"Failed to install keyboard hook: {error_code}")
            else:
                self.hook_installed = True
                _hook_references['hook_id'] = keyboard_hook  # Store hook handle
                logging.info("Keyboard hook installed successfully in .exe")

        except Exception as e:
            logging.error(f"Error installing keyboard hook: {e}")

    def uninstall_keyboard_hook(self):
        """Remove the low-level keyboard hook when exiting"""
        global keyboard_hook, _hook_references
        
        if keyboard_hook and self.hook_installed:
            try:
                if user32.UnhookWindowsHookEx(keyboard_hook):
                    keyboard_hook = None
                    self.hook_installed = False
                    logging.info("Keyboard hook uninstalled successfully")

                    # Don't reinstall the hook after closing
                    # time.sleep(1)  
                    # self.install_keyboard_hook()  
                else:
                    logging.error(f"Failed to uninstall keyboard hook: {ctypes.get_last_error()}")
            except Exception as e:
                logging.error(f"Error uninstalling keyboard hook: {e}")

    def quick_setup_gui(self):
        """Set up minimal GUI elements for fast initial display"""
        self.frame = ttk.Frame(self.root)
        self.frame.place(relx=0.5, rely=0.4, anchor='center')
        
        self.password_frame = ttk.Frame(self.frame)
        self.password_frame.pack()
        
        self.instruction_label = ttk.Label(
            self.password_frame,
            text="Initializing security lockscreen...",
            font=('Arial', 20)
        )
        self.instruction_label.pack(pady=10)
        
        self.error_label = ttk.Label(
            self.password_frame,
            text="",
            font=('Arial', 20),
            foreground='red'
        )
        self.error_label.pack(pady=5)
        
        self.password_display = ttk.Label(
            self.password_frame,
            text="",
            font=('Arial', 30)
        )
        self.password_display.pack(pady=10)
        
        self.time_label = ttk.Label(
            self.password_frame,
            text="",
            font=('Arial', 30)
        )
        self.time_label.pack(pady=10)
        
        # Set basic key binding
        self.root.bind('<Key>', self.on_key_press)
        self.time_label.bind("<Double-Button-1>", lambda e: self.toggle_matrix_rain())
        
        # Block Alt+F4 and other ways to close the window
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

    def complete_gui_setup(self):
        """Complete the GUI setup with all elements"""
        # Update instruction text
        self.instruction_label.config(text="Type your password and press Enter to unlock")
        
        # Create security questions frame (initially hidden)
        style = ttk.Style()
        style.configure("Custom.TButton", font=("Arial", 20))

        self.question_frame = ttk.Frame(self.frame)
        self.back_button = ttk.Button(
            self.question_frame,
            text="Back to Password",
            command=self.show_password_entry,
            style="Custom.TButton"
        )
        self.back_button.pack(pady=20)
        
        self.question_label = ttk.Label(
            self.question_frame,
            text="",
            font=('Arial', 20)
        )
        self.question_label.pack(pady=10)
        
        self.security_error_label = ttk.Label(
            self.question_frame,
            text="",
            font=('Arial', 20),
            foreground='red'
        )
        self.security_error_label.pack(pady=10)
        
        # Create custom entry field-like container for security questions
        self.answer_display_frame = tk.Frame(
            self.question_frame,
            bd=2,
            relief="sunken",
            bg="white",
            height=40,
            width=400
        )
        self.answer_display_frame.pack(pady=10, padx=20, fill="x")
        self.answer_display_frame.pack_propagate(False)  # Prevent frame from resizing to fit content
        
        # Create a label inside the frame to display input text
        self.answer_display = tk.Label(
            self.answer_display_frame,
            text="",
            font=('Arial', 18),
            bg="white",
            anchor="w",  # Left-aligned text
            padx=5
        )
        self.answer_display.pack(fill="x", expand=True, pady=5)
        
        self.submit_button = ttk.Button(
            self.question_frame,
            text="Submit",
            command=self.check_security_answer,
            style="Custom.TButton"
        )
        self.submit_button.pack(pady=20)
        
        # Start blinking cursor
        self.update_cursor()

    def update_cursor(self):
        """Create blinking cursor effect for security question input"""
        if not self.root.winfo_exists():
            return
            
        if self.security_mode:
            # Toggle cursor visibility
            self.cursor_visible = not self.cursor_visible
            
            # Update display with or without cursor
            cursor_char = "|" if self.cursor_visible else ""
            self.answer_display.config(text=self.current_security_input + cursor_char)
            
            # Schedule next cursor update
            self.root.after(500, self.update_cursor)
        else:
            # Always schedule next update to ensure cursor starts immediately when switching to security mode
            self.root.after(500, self.update_cursor)

    def hide_taskbar(self):
        """Hide Windows taskbar"""
        try:
            hwnd = win32gui.FindWindow("Shell_traywnd", None)
            win32gui.ShowWindow(hwnd, 0)
        except Exception as e:
            logging.error(f"Error hiding taskbar: {e}")
        
    def show_taskbar(self):
        """Show Windows taskbar (called when unlocking)"""
        try:
            hwnd = win32gui.FindWindow("Shell_traywnd", None)
            win32gui.ShowWindow(hwnd, 1)
        except Exception as e:
            logging.error(f"Error showing taskbar: {e}")
        
    def prevent_start_menu(self, event):
        """Prevent Windows key and Start menu"""
        if event.keycode in [win32con.VK_LWIN, win32con.VK_RWIN]:
            return 'break'
        
    def show_security_questions(self):
        """Switch to security questions mode - now using our custom input method"""
        global security_mode_active
        
        # Keep the keyboard hook installed
        self.security_mode = True
        security_mode_active = True
        self.current_question_index = 0
        self.current_security_input = ""  # Reset security input
        
        # Switch frames
        self.password_frame.pack_forget()
        self.question_frame.pack()
        
        # Switch key handler
        self.root.unbind('<Key>')
        self.root.bind('<Key>', self.on_security_key_press)

        # Show the current question
        self.show_current_question()
        
    def on_security_key_press(self, event):
        """Custom key handler for security question input"""
        if not self.security_mode:
            return 'break'

        # Handle Enter key to submit
        if event.keysym == 'Return':
            self.check_security_answer()
            return 'break'
        
        # Handle Escape to return to password mode
        if event.keysym == 'Escape':
            self.show_password_entry()
            return 'break'
        
        # Handle backspace
        if event.keysym == 'BackSpace':
            if self.current_security_input:
                self.current_security_input = self.current_security_input[:-1]
                # Update display (cursor will be added by update_cursor)
                self.answer_display.config(text=self.current_security_input)
            return 'break'
        
        # Only accept printable characters
        if event.char and event.char.isprintable():
            self.current_security_input += event.char
            # Update display (cursor will be added by update_cursor)
            self.answer_display.config(text=self.current_security_input)
            
        return 'break'
        
    def show_password_entry(self):
        """Switch back to password entry mode"""
        global security_mode_active
        self.security_mode = False
        security_mode_active = False
        self.question_frame.pack_forget()
        self.password_frame.pack()
        
        # Switch back to password key handler
        self.root.unbind('<Key>')
        self.root.bind('<Key>', self.on_key_press)
        
        self.reset_input()
        self.error_label.config(text="")
        self.instruction_label.config(text="Type your password and press Enter to unlock")
        
    def show_current_question(self):
        """Display the current security question"""
        if not self.security_questions:
            self.show_error_and_close("Error: No security questions configured.")
            return
            
        question = list(self.security_questions.keys())[self.current_question_index]
        self.question_label.config(text=question)
        self.security_error_label.config(text="")
        
        # Reset input for new question
        self.current_security_input = ""
        self.answer_display.config(text="")
        
    def check_security_answer(self):
        """Verify the answer to the security question"""
        if not hasattr(self, 'security_questions') or not self.security_questions:
            self.display_error("Security questions not initialized.")
            return
    
        # Get the current question safely with bounds checking
        questions = list(self.security_questions.keys())
        if not questions or self.current_question_index >= len(questions):
            self.display_error("No security questions available.")
            return
        
        current_question = questions[self.current_question_index]
        correct_answer = self.security_questions[current_question].lower().strip()
        user_answer = self.current_security_input.lower().strip()
        
        if user_answer == correct_answer:
            self.current_question_index += 1
            if self.current_question_index >= len(self.security_questions):
                self.unlock_system()
            else:
                self.show_current_question()
        else:
            self.security_error_label.config(text="Incorrect answer")
            self.blink_text(self.security_error_label)
            self.current_security_input = ""
            self.answer_display.config(text="")
        
    def block_windows_keys(self):
        """Block Windows key combinations"""
        user32 = ctypes.WinDLL('user32', use_last_error=True)

        # Define the hotkey combinations
        hotkeys = [
            (win32con.MOD_ALT, win32con.VK_TAB),
            (win32con.MOD_ALT, win32con.VK_F4),
            (win32con.MOD_CONTROL, win32con.VK_ESCAPE),
            (win32con.MOD_CONTROL | win32con.MOD_ALT, win32con.VK_DELETE),
            (0, win32con.VK_ESCAPE)
        ]

        # Register hotkeys
        for mod, vk in hotkeys:
            if not user32.RegisterHotKey(None, 1, mod, vk):
                print(f"Failed to register hotkey: MOD={mod}, VK={vk}")

        # Register hotkeys using tkinter bindings as backup to low-level hook
        self.root.bind('<Alt-Tab>', lambda e: 'break')
        self.root.bind('<Alt-F4>', lambda e: 'break')
        self.root.bind('<Control-Escape>', lambda e: 'break')
        self.root.bind('<Control-Shift-Escape>', lambda e: 'break')
        self.root.bind('<Shift-Escape>', lambda e: 'break')
        self.root.bind('<Alt-space>', lambda e: 'break')
        
        # Block all function keys
        for i in range(1, 13):
            self.root.bind(f'<F{i}>', lambda e: 'break')
            self.root.bind(f'<Alt-F{i}>', lambda e: 'break')
            self.root.bind(f'<Control-F{i}>', lambda e: 'break')
        
        # Block Print Screen
        self.root.bind('<Print>', lambda e: 'break')
        
        # Main key handler
        self.root.bind('<Key>', self.on_key_press)
        
        # Force focus back if it's lost
        self.root.bind_all("<FocusOut>", lambda e: self.root.focus_force())
        
    def load_model(self):
        """Load the trained keystroke model"""
        try:
            # Import pickle only when needed
            import pickle
            
            with open("typing_model.pkl", "rb") as model_file:
                self.model = pickle.load(model_file)
                
            # Get the password from the model - handle field name changes
            if "password" in self.model:
                self.PASSWORD = self.model["password"]
            else:
                logging.error("No password found in model!")
                return False
                
            # Get the threshold - handle field name changes
            if "threshold" in self.model:
                self.THRESHOLD = self.model["threshold"]
            else:
                logging.warning("No threshold found in model, using default")
                self.THRESHOLD = FALLBACK_THRESHOLD
                
            # Load security questions from model
            if "security_questions" in self.model:
                self.security_questions = self.model["security_questions"]
                if not self.security_questions:
                    logging.warning("Security questions dict is empty")
            else:
                logging.warning("No security questions found in model!")
                
            # Load matrix settings from model
            if "matrix_settings" in self.model:
                self.matrix_settings = self.model["matrix_settings"]
            
            # Verify critical components exist in the model
            if "train_data" not in self.model and "training_data" not in self.model:
                logging.error("No training data found in model!")
                return False
                
            # Handle potential field name differences between old and new model
            if "train_data" in self.model:
                self.model["training_data"] = self.model["train_data"]
                
            if "avg_self_similarity" not in self.model:
                logging.error("No average self similarity found in model!")
                return False
                
            logging.info("Model loaded successfully")
            return True
        except FileNotFoundError:
            logging.error("No trained model found!")
            return False
        except Exception as e:
            logging.error(f"Error loading model: {e}")
            return False
            
    def show_error_and_close(self, message):
        """Show error message and close on key press"""
        self.error_label.config(text=message)
        self.root.bind('<Key>', lambda e: self.cleanup())
        
    def update_time(self):
        """Update the time display"""
        if not self.root.winfo_exists():
            return
            
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            self.time_label.config(text=current_time)
            self.root.after(1000, self.update_time)
        except Exception:
            # This can fail during shutdown, just ignore
            pass
        
    def reset_input(self):
        """Reset all input-related variables"""
        self.current_input = ""
        self.keystroke_times = []
        self.last_keystroke_time = None
        self.password_display.config(text="")
        
    def blink_text(self, label):
        """Create blinking effect for text"""
        if not self.root.winfo_exists():
            return
            
        current_text = label.cget("text")
        label.config(text="")
        self.root.after(200, lambda: label.config(text=current_text) if self.root.winfo_exists() else None)
        
    def on_key_press(self, event):
        """Handle key press events for password input"""
        if self.security_mode:
            return

        if event.keysym == 'Return':
            self.verify_input()
            return 'break'
        
        if event.keysym == 'BackSpace':
            if self.current_input:
                self.current_input = self.current_input[:-1]
                self.keystroke_times = self.keystroke_times[:-1] if self.keystroke_times else []
                self.password_display.config(text="*" * len(self.current_input))
            return 'break'
            
        if event.char and event.char.isprintable():
            current_time = time.time()
            
            if self.last_keystroke_time is not None:
                interval = current_time - self.last_keystroke_time
                self.keystroke_times.append(interval)
            
            self.last_keystroke_time = current_time
            self.current_input += event.char
            
            self.password_display.config(text="*" * len(self.current_input))
                
        return 'break'

    def calculate_pattern_score(self, test_intervals):
        """Calculate pattern similarity score (0.0 to 1.0)"""
        import numpy as np
        # Import numpy here for late loading if needed
        if not hasattr(self, 'np'):
            import numpy as np
            self.np = np
            
        # Get required components from model
        scaler = self.model.get("scaler", None)
        train_data = self.model.get("train_data", self.model.get("training_data", None))
        avg_self_similarity = self.model.get("avg_self_similarity", 1.0)
        
        if scaler is None or train_data is None:
            return 0.0  # Cannot calculate without these components
            
        # Scale the test features for comparison    
        test_features = np.array([test_intervals])
        test_features_scaled = scaler.transform(test_features)
        
        # Calculate pattern similarity
        distances = [np.linalg.norm(test_features_scaled - train_sample) 
                   for train_sample in train_data]
        avg_distance = np.mean(distances)

        # Add a tolerance factor (0.5 means 50% more lenient)
        tolerance_factor = 0.5
        adjusted_distance = avg_distance * (1 - tolerance_factor)
        
        # Calculate similarity score (0.0 to 1.0)
        similarity = avg_self_similarity / (avg_self_similarity + adjusted_distance)
        
        # Cap at 1.0 and ensure non-negative
        return max(0.0, min(similarity, 1.0))

    def calculate_interval_score(self, test_intervals):
        """Calculate interval matching score (0.0 to 1.0)"""
        import numpy as np
        if "interval_lower_thresholds" not in self.model or "interval_upper_thresholds" not in self.model:
            return 0.0  # Cannot calculate without thresholds
            
        lower_bounds = self.model["interval_lower_thresholds"]
        upper_bounds = self.model["interval_upper_thresholds"]

        # Add padding to the bounds 
        lower_bounds = [bound * 0.00 for bound in lower_bounds]
        upper_bounds = [bound * 2.00 for bound in upper_bounds]
        
        # Check how many intervals are within acceptable ranges
        within_bounds = []
        for i, interval in enumerate(test_intervals):
            if i < len(lower_bounds) and lower_bounds[i] <= interval <= upper_bounds[i]:
                within_bounds.append(True)
            else:
                within_bounds.append(False)
        
        # Return percentage of intervals that match
        if not within_bounds:
            return 0.0
            
        return sum(within_bounds) / len(within_bounds)

    def calculate_speed_score(self, test_intervals):
        """Calculate speed consistency score (0.0 to 1.0)"""
        import numpy as np
        if "avg_typing_speed" not in self.model or "std_dev_typing_speed" not in self.model:
            return 0.0  # Cannot calculate without these parameters
            
        avg_typing_speed = self.model.get("avg_typing_speed", 0)
        std_dev_typing_speed = self.model.get("std_dev_typing_speed", 0.01)  # Prevent division by zero
        
        # Calculate current typing speed
        current_avg_speed = sum(test_intervals) / len(test_intervals)
        
        # Calculate z-score (how many standard deviations from mean)
        z_score = abs((current_avg_speed - avg_typing_speed) / std_dev_typing_speed)
        
        # Convert to score (0.0 to 1.0)
        # A z-score of 2.0 or greater results in a score of 0.0
        return max(0.0, min(1.0 - (z_score / 2.0), 1.0))

    def verify_input(self):
        """Verify password using the enhanced hybrid security approach"""
        import numpy as np
        if not hasattr(self, 'np'):
            import numpy as np
            self.np = np
            
        # Reset global auth scores for this attempt
        global_auth_scores = {
            "weighted_score": 0.0,
            "interval_score": 0.0,
            "pattern_score": 0.0,
            "speed_score": 0.0,
            "threshold": 0.0,
            "valid_scores": False
        }

        # Basic validation checks
        if len(self.current_input) != len(self.PASSWORD):
            error_message = f"AUTHENTICAION STATUS: Password:✘ Interval:✘ Pattern:✘ (score: -- < --)."
            self.handle_failed_attempt(error_message)
            self.reset_input()
            return
            
        if len(self.keystroke_times) != len(self.PASSWORD) - 1:
            self.handle_failed_attempt("Incomplete keystroke data")
            self.reset_input()
            return
            
        if self.current_input != self.PASSWORD:
            error_message = f"AUTHENTICAION STATUS: Password:✘ Interval:✘ Pattern:✘ (score: -- < --)."
            self.handle_failed_attempt(error_message)
            self.reset_input()
            return
                
        # STEP 1: Calculate individual scores using the hybrid approach
        pattern_score = self.calculate_pattern_score(self.keystroke_times)
        interval_score = self.calculate_interval_score(self.keystroke_times)
        speed_score = self.calculate_speed_score(self.keystroke_times)

        global_auth_scores["pattern_score"] = pattern_score
        global_auth_scores["interval_score"] = interval_score
        global_auth_scores["speed_score"] = speed_score
        
        # STEP 2: Security level settings
        security_settings = {
            "low":       (0.25, 0.30, 0.50),  # Much more forgiving
            "medium":    (0.30, 0.35, 0.60),  # More reasonable thresholds
            "high":      (0.40, 0.40, 0.65),  # Less strict than current
            "very_high": (0.50, 0.50, 0.70)   # Still strict but achievable
        }
        
        # Get security level from model or use default
        security_level = self.model.get("security_level", "high")
        interval_minimum, secondary_minimum, overall_threshold = security_settings.get(
            security_level, security_settings["high"])

        # Use the actual user-defined threshold 
        overall_threshold = self.THRESHOLD / 100.0

        # Convert percentage to decimal (e.g., 70 -> 0.70)
        user_threshold = self.THRESHOLD / 100.0

        # Calculate weighted score 
        weights = {"interval": 0.40, "pattern": 0.40, "speed": 0.20}
        weighted_score = (
            weights["interval"] * interval_score +
            weights["pattern"] * pattern_score +
            weights["speed"] * speed_score
        )
    
        # Add bonus for excellence in interval matching
        if interval_score > 0.70:  # If most intervals are already correct
            bonus = 0.05 + ((interval_score - 0.60) * 0.50)
            weighted_score += bonus

        # If ANY factor is excellent (>0.8), add bonus
        best_factor = max(pattern_score, speed_score)
        if best_factor > 0.8:
            bonus1 = (best_factor - 0.8) * 0.25
            weighted_score += bonus1

        # Consistency bonus if scores are similar
        if abs(pattern_score - interval_score) < 0.2:
            weighted_score += 0.05  # 5% bonus for consistent scores
        
        # Store the weighted score globally
        global_auth_scores["weighted_score"] = weighted_score
        global_auth_scores["valid_scores"] = True  # Now we have valid scores

        # Authentication criteria
        interval_passed = interval_score >= interval_minimum
        secondary_passed = pattern_score >= secondary_minimum or speed_score >= secondary_minimum
        threshold_passed = weighted_score >= overall_threshold

        # Status indicator
        password_status = "✔"
        interval_status = "✔" if interval_passed else "✘"
        secondary_status = "✔" if secondary_passed else "✘"
        score_display = f"score: {int(weighted_score*100)} {'≥' if threshold_passed else '<'} {int(overall_threshold*100)}"
            
        # STEP 6: Make authentication decision
        if threshold_passed and interval_passed and secondary_passed:
            # Authentication successful
            success_message = f"AUTHENTICATION STATUS: {int(weighted_score*100)} > {int(overall_threshold*100)}"
            logging.info(f"Authentication successful: {success_message}")
            self.unlock_system()
            return
    
        # Authentication failed - determine reason and create appropriate message
        if not interval_passed:
            error_message = f"AUTHENTICATION STATUS: Password:{password_status} Interval:✘ Pattern:{secondary_status} ({score_display})."
            logging.info("Authentication failed: Interval doesn't match")
        elif not secondary_passed:
            error_message = f"AUTHENTICATION STATUS: Password:{password_status} Interval:{interval_status} Pattern:✘ ({score_display})."
            logging.info("Authentication failed: Pattern factors don't match")
        else:
            error_message = f"AUTHENTICATION STATUS: Password:{password_status} Interval:{interval_status} Pattern:{secondary_status} ({score_display})."
            logging.info("Authentication failed: Overall score below threshold")
    
        self.handle_failed_attempt(error_message)
        self.reset_input()

    def handle_failed_attempt(self, message):
        """Handle failed authentication attempts"""
        global global_auth_scores
    
        # Only show scores if they're valid (have been calculated)
        if global_auth_scores.get("valid_scores", False):
            # We have valid scores, so display the message as provided
            self.error_label.config(text=message)
        else:
            # No valid scores (probably password validation failed), just show the original message
            self.error_label.config(text=message)
    
        self.blink_text(self.error_label)

    def unlock_system(self):
        """Unlock the system and close the lockscreen"""
        self.instruction_label.config(text="Access Granted! Unlocking...")
        logging.info("System unlocked successfully")
        self.show_taskbar()
        self.uninstall_keyboard_hook()
        self.root.after(1000, self.cleanup)

    def get_character_set(self):
        """Get characters for matrix rain based on settings"""
        char_set = self.matrix_settings["char_set"]
        
        if char_set == "alphanumeric":
            return 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        elif char_set == "latin":
            return 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        elif char_set == "numbers":
            return '0123456789'
        elif char_set == "symbols":
            return '!@#$%^&*()_+-=[]{}|;:,./<>?~`'
        elif char_set == "custom" and self.matrix_settings["custom_chars"]:
            return self.matrix_settings["custom_chars"]
        else:
            return 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

    def init_matrix_rain_effect_incremental(self):
        """Initialize the Matrix Rain effect with incremental loading for better performance"""
        # Check if canvas exists yet - it might not during startup
        if not self.canvas:
            return
            
        # Get settings from model
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Get density from settings
        density = self.matrix_settings["matrix_density"]
        density_factor = density / 10  # Convert 1-20 scale to a multiplier
        drop_spacing = max(5, int(7.5 / density_factor))  # Adjust spacing based on density
        
        # Characters to use
        chars = self.get_character_set()
        special_char = self.matrix_settings["special_char"]
        
        # Get speed from settings
        speed_setting = self.matrix_settings["matrix_speed"]
        base_speed = max(2, min(int(speed_setting / 2), 15))
        
        # Clear existing drops
        self.matrix_rain_drops = []
        
        # Create initial set of drops for immediate visual feedback
        # Use every column but fewer drops per column initially
        for x in range(0, screen_width, drop_spacing):
            # Initial number of drops in each column
            num_initial_drops = int(max(10, 20 * density_factor * 0.6))  # 60% of full density
            
            for i in range(num_initial_drops):
                # Distribute evenly across full height range
                y_position = int((i / num_initial_drops) * screen_height * 2) - screen_height // 2
                # Add some randomness to positions
                y_position += random.randint(-100, 100)
                
                speed = random.randint(base_speed, base_speed + 5)
                is_special = random.random() < 0.01  # 1% chance to be special
                
                drop = {
                    'x': x,
                    'y': y_position,
                    'speed': speed,
                    'char': special_char if is_special else random.choice(chars)
                }
                self.matrix_rain_drops.append(drop)
        
        # Start the animation with initial drops
        self.update_matrix_rain_effect()
        
        # Schedule adding remaining drops
        self.root.after(50, lambda: self.add_remaining_drops(drop_spacing, chars, special_char, base_speed, 
                                                            density_factor, screen_height, screen_width))

    def add_remaining_drops(self, drop_spacing, chars, special_char, base_speed, density_factor, screen_height, screen_width):
        """Add the remaining matrix drops to complete the effect to match original density"""
        # Check if window still exists
        if not self.root.winfo_exists():
            return
            
        # Calculate how many total drops we should have based on original algorithm
        total_columns = screen_width // drop_spacing
        target_drops_per_column = int(20 * density_factor)
        target_total_drops = total_columns * target_drops_per_column
        
        # Only add the difference between target and current
        current_drops = len(self.matrix_rain_drops)
        drops_to_add = target_total_drops - current_drops
        
        if drops_to_add <= 0:
            return  # Already at or above target
        
        # Add remaining drops in batches for better performance
        batch_size = min(500, drops_to_add)
        
        for _ in range(batch_size):
            # Random position in same columns as original
            x = random.choice(range(0, screen_width, drop_spacing))
            y_position = random.randint(-screen_height, screen_height)
            
            speed = random.randint(base_speed, base_speed + 5)
            is_special = random.random() < 0.01  # 1% chance
            
            drop = {
                'x': x,
                'y': y_position,
                'speed': speed,
                'char': special_char if is_special else random.choice(chars)
            }
            self.matrix_rain_drops.append(drop)
        
        # If we have more drops to add, schedule the next batch
        remaining = drops_to_add - batch_size
        if remaining > 0:
            self.root.after(20, lambda: self.add_remaining_drops(drop_spacing, chars, special_char, base_speed, 
                                                            density_factor, screen_height, screen_width))

    def update_matrix_rain_effect(self):
        """Update the Matrix Rain effect animation - optimized version"""
        if not self.matrix_rain_running or not self.canvas:
            return
        
        # Performance: Check if enough time has passed since last update
        current_time = time.time() * 1000
        if current_time - self.last_matrix_update < self.matrix_update_interval:
            self.root.after(self.matrix_update_interval, self.update_matrix_rain_effect)
            return
        
        self.last_matrix_update = current_time
        self.canvas.delete('all')
        
        char_set = self.get_character_set()
        special_char = self.matrix_settings["special_char"]
        color = self.matrix_settings["matrix_color"]
        screen_height = self.root.winfo_screenheight()
        screen_width = self.root.winfo_screenwidth()

        # Define the brighter color for special character
        special_color = color
        if color == "lime":
            special_color = "#AAFFAA"  # Brighter lime
        elif color == "green":
            special_color = "#228B22"  # Brighter green
        elif color == "cyan":
            special_color = "#AAFFFF"  # Brighter cyan
        elif color == "red":
            special_color = "#EE4B2B"  # Brighter red
        elif color == "white":
            special_color = "#FFFFFF"  # Pure white
        elif color == "yellow":
            special_color = "#FFFFAA"  # Brighter yellow

        # Font sizes
        standard_size = 15
        special_size = int(standard_size * 1.05)

        # Performance optimization: Only update drops within viewport with some margin
        visible_drops = []
        for drop in self.matrix_rain_drops:
            # Update position first
            drop['y'] += drop['speed']
            
            # If in visible area (with margin), add to visible drops
            if -100 <= drop['y'] <= screen_height + 100 and 0 <= drop['x'] <= screen_width:
                visible_drops.append(drop)
                
                # If drop goes off screen, reset it
                if drop['y'] > screen_height:
                    drop['y'] = random.randint(-100, 0)  # Start slightly above the screen
                    drop['char'] = random.choice(char_set)
                    
                    # Small chance to make it a special character
                    if random.random() < 0.01:  # 1% chance
                        drop['char'] = special_char
                    
                    # Update speed based on settings
                    speed_value = max(2, min(int(self.matrix_settings["matrix_speed"] / 2), 15))
                    drop['speed'] = random.randint(speed_value, speed_value + 5)
        
        # Performance optimization: Batch processing for rendering
        for drop in visible_drops:
            # Determine if this is a special character
            is_special = drop['char'] == special_char
            
            # Create text with appropriate properties
            if is_special:
                self.canvas.create_text(
                    drop['x'], drop['y'], 
                    text=drop['char'], 
                    fill=special_color,
                    font=('Courier', special_size, 'bold'),
                    tags=('matrix_char', 'special_char')
                )
            else:
                self.canvas.create_text(
                    drop['x'], drop['y'], 
                    text=drop['char'], 
                    fill=color,
                    font=('Courier', standard_size), 
                    tags='matrix_char'
                )
        
        # Ensure UI elements remain on top
        self.frame.lift()
                
        # Schedule next update with adaptive timing
        self.root.after(self.matrix_update_interval, self.update_matrix_rain_effect)
   
    def toggle_matrix_rain(self):
        """Toggle the Matrix Rain effect"""
        self.matrix_rain_running = not self.matrix_rain_running
        if self.matrix_rain_running:
            self.update_matrix_rain_effect()
            if self.canvas:
                self.canvas.tag_unbind('special_char', '<Double-1>')
        else:
            # Bind double-click event to check for special character when paused
            if self.canvas:
                self.canvas.tag_bind('special_char', '<Double-1>', self.matrix_double_click_handler)

    def matrix_double_click_handler(self, event):
        """Handle double-clicks on matrix characters"""
        if not self.matrix_rain_running:
            item = self.canvas.find_closest(event.x, event.y)
            try:
                char = self.canvas.itemcget(item, 'text')
                special_char = self.matrix_settings["special_char"]
                
                if char == special_char:
                    self.show_security_questions()
                    self.matrix_rain_running = True
                    self.update_matrix_rain_effect()
            except (tk.TclError, IndexError):
                pass  # Item might not exist anymore

    def cleanup(self):
        """Enhanced cleanup for .exe operation"""
        if self.cleanup_done:
            return
        
        self.cleanup_done = True
    
        # Explicit hook uninstallation with error handling
        global keyboard_hook, _hook_references
        try:
            if keyboard_hook:
                success = user32.UnhookWindowsHookEx(keyboard_hook)
                if not success:
                    logging.error(f"Failed to unhook: {ctypes.get_last_error()}")
                else:
                    logging.info("Hook successfully removed")
                    keyboard_hook = None
                    
            # Clear reference dictionary to help garbage collection
            if '_hook_references' in globals():
                _hook_references.clear()
                
        except Exception as e:
            logging.error(f"Exception during hook cleanup: {e}")

        # Show taskbar
        self.show_taskbar()
        
        # Restore normal process priority
        try:
            win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.NORMAL_PRIORITY_CLASS)
        except:
            pass
            
        # Only attempt to destroy window if it exists and Tkinter is still running
        try:
            if self.root and self.root.winfo_exists():
                self.root.destroy()
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

def main():
    # Create a temporary lock file
    if not create_temp_lock_file():
        print("Lockscreen is already running or cannot create lock file.")
        logging.info("Lockscreen is already running or cannot create lock file.")
        return
    
    try:
        # Increase process priority to ensure it stays responsive
        win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)
    except:
        pass
        
    root = tk.Tk()
    app = KeystrokeLockscreen(root)
    
    # Don't call install_keyboard_hook here since it's called in deferred_initialization
    root.protocol("WM_DELETE_WINDOW", lambda: None)  # Block window closure attempt
    
    # Register cleanup function for abnormal termination, but use a lambda
    # to check if app exists to prevent errors during shutdown
    atexit.register(lambda: app.cleanup() if 'app' in locals() else None)
    
    # Start the main event loop
    root.mainloop()

if __name__ == "__main__":
    main()