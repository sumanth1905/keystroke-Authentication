import time
import numpy as np
from sklearn.preprocessing import StandardScaler
import pickle
import tkinter as tk
import winshell
from win32com.client import Dispatch
from tkinter import ttk, messagebox, scrolledtext
from tkinter.font import Font
import os
import atexit
import psutil
import subprocess
import ctypes
import sys
import winreg
import shutil

LOCK_FILE = "training.lock"

# Function to check if a process is running
def is_process_running(pid):
    return psutil.pid_exists(pid)

# Check if lock file exists and validate the stored PID
if os.path.exists(LOCK_FILE):
    try:
        with open(LOCK_FILE, "r") as lock:
            existing_pid = int(lock.read().strip())

        # If the process with this PID is still running, exit
        if is_process_running(existing_pid):
            print("train_auth.py is already running.")
            sys.exit(1)

        # If the process is NOT running, remove the stale lock file
        os.remove(LOCK_FILE)
    except Exception as e:
        print(f"Error checking lock file: {e}")
        os.remove(LOCK_FILE)  # Remove corrupted lock file

# Create the lock file with the current process ID
with open(LOCK_FILE, "w") as lock:
    lock.write(str(os.getpid()))

# Ensure lock file is deleted when script exits
def remove_lock_file():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

atexit.register(remove_lock_file)

try:
    import win32com.client
except ImportError:
    # Handle case where pywin32 is not installed
    pass

# Constants
THRESHOLD = 70  # Default threshold in percentage

# Default security questions (Windows-style security questions)
DEFAULT_SECURITY_QUESTIONS = [
    "What was your pet's name?",
    "What was your childhood nickname?",
    "In what city were you born?",
    "What is your favourite sport?",
    "What was the name of your first school?",
    "What is the name of your childhood friend?",
    "Custom Question..."
]

class KeystrokeAuthApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Entypt")
        self.root.geometry("700x600")
        self.root.state('zoomed')  # Open in maximized mode
        
        # Initialize model attribute to prevent errors
        self.model = None
        
        # Initialize wizard state
        self.current_step = 0
        self.steps = ["password", "training", "threshold", "security", "matrix", "summary"]
        self.completed_steps = {step: False for step in self.steps}
        
        # In-memory configuration storage
        self.wizard_state = {
            # Configuration data
            "password": "",
            "training_data": [],
            "scaler": None,
            "threshold_value": THRESHOLD,
            "security_questions": {},
            "matrix_settings": {
                "char_set": "alphanumeric",
                "special_char": "",
                "matrix_color": "lime",
                "matrix_speed": 10,  # Fixed value
                "matrix_density": 5   # Fixed value
            },
            "security_level": "high"  # Default security level for hybrid system
        }
        
        # Set password variable
        self.password = tk.StringVar(value="")
        self.num_features = 0  # Will be updated when password changes
        
        # Track if we're in edit mode
        self.edit_mode = False
        
        # Set theme and styles
        self.setup_styles()
        
        # Check if model exists before showing UI
        self.has_existing_model = os.path.exists("typing_model.pkl")
        
        # Setup main UI components
        self.setup_ui()
        
        # Block all UI interaction initially with a transparent overlay
        if not self.has_existing_model:
            self.block_ui_interaction()
        
        # Load model if exists
        if self.has_existing_model:
            self.load_model()
        else:
            # Show instruction overlay if no model exists
            self.setup_instruction_overlay()
    
    def block_ui_interaction(self):
        """Create a transparent overlay to block UI interaction until proceeding from instructions"""
        self.blocker_overlay = tk.Frame(self.root, bg="#ffffff")
        self.blocker_overlay.place(x=0, y=0, relwidth=1, relheight=1)
    
    def unblock_ui_interaction(self):
        """Remove the UI blocker overlay"""
        if hasattr(self, 'blocker_overlay'):
            self.blocker_overlay.place_forget()
            self.blocker_overlay.destroy()
    
    def setup_styles(self):
        # Configure ttk styles
        self.style = ttk.Style()
        
        # Use a modern theme if available
        try:
            self.style.theme_use('clam')  # More modern looking theme
        except:
            pass  # Fallback to default if theme not available
            
        # Configure fonts
        self.heading_font = Font(family="Arial", size=14, weight="bold")
        self.subheading_font = Font(family="Arial", size=12, weight="bold")
        self.text_font = Font(family="Arial", size=10)
        
        # Configure button styles
        self.style.configure('TButton', font=('Arial', 11))
        self.style.configure('Action.TButton', font=('Arial', 11, 'bold'))
        self.style.configure('Wizard.TButton', font=('Arial', 12, 'bold'), padding=10)
        self.style.configure('Delete.TButton', foreground='red', font=('Arial', 11))
        
        # Close button style
        self.style.configure('Close.TButton', font=('Arial', 10), padding=3)
        
        # Configure tab styles
        self.style.configure('TNotebook.Tab', font=('Arial', 11))
        self.style.configure('TNotebook', background='#f0f0f0')
        
        # Configure progress bar
        self.style.configure("TProgressbar", thickness=20)
    
    def setup_instruction_overlay(self):
        """Create an instruction overlay that appears before starting the setup process"""
        # Create a semi-transparent overlay frame
        self.instruction_overlay = tk.Frame(self.root, bg="#f5f5f5", bd=2, relief=tk.RIDGE)
        
        # Size and position the overlay in the center of the screen
        overlay_width = 700
        overlay_height = 500
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x_pos = (screen_width - overlay_width) // 2
        y_pos = (screen_height - overlay_height) // 2
        self.instruction_overlay.place(x=x_pos, y=y_pos, width=overlay_width, height=overlay_height)
        
        # Add header frame with close button
        header_frame = tk.Frame(self.instruction_overlay, bg="#f5f5f5")
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Add close button in the top-right corner
        self.close_button = ttk.Button(
            header_frame, 
            text="×", 
            style='Close.TButton',
            command=self.close_application
        )
        self.close_button.pack(side=tk.RIGHT)
        
        # Add content to the overlay
        # Title
        title_label = tk.Label(
            self.instruction_overlay,
            text="Welcome to Entypt - Keystroke Authentication",
            font=("Arial", 18, "bold"),
            bg="#f5f5f5"
        )
        title_label.pack(pady=(5, 20))
        
        # Instructions frame with scrollable text
        instructions_frame = tk.Frame(self.instruction_overlay, bg="#f5f5f5")
        instructions_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)
        
        instructions_text = scrolledtext.ScrolledText(
            instructions_frame,
            font=("Arial", 11),
            wrap=tk.WORD,
            height=15,
            width=70,
            bg="#ffffff"
        )
        instructions_text.pack(fill=tk.BOTH, expand=True)
        
        # Add instruction text
        instructions = """
This application will create an authentication profile based on your unique typing pattern.

The steps involved in setup process:
• Password Setup: Choose a password you can type consistently.
• Training: Type your password multiple times with same pattern to establish your typing pattern.
• Threshold Setting: Adjust how strictly the system should match your typing pattern.
• Security Questions: Set up backup questions in case the system fails to recognize you.
• Matrix Effect: Customize the appearance of the Matrix-style lock screen.
• Confirmation: Review and save your configuration.

Note: 
Double click on the clock to pause matrix. when matrix is paused double click on the special character to bring up security questions.
Please ensure you are in a comfortable typing position and typing naturally during the training process.
Once setup is complete, Restart your system. The application will provide security protection for your system.
The user bears full responsibility, if any inappropriate occurance by the application.
"""
        instructions_text.insert(tk.END, instructions)
        instructions_text.config(state=tk.DISABLED)
        
        # Checkbox to acknowledge instructions
        checkbox_frame = tk.Frame(self.instruction_overlay, bg="#f5f5f5")
        checkbox_frame.pack(pady=10)
        
        self.acknowledged = tk.BooleanVar(value=False)
        acknowledge_checkbox = ttk.Checkbutton(
            checkbox_frame,
            text="I have read and understood the instructions",
            variable=self.acknowledged,
            command=self.update_proceed_button
        )
        acknowledge_checkbox.pack()
        
        # Button to proceed
        button_frame = tk.Frame(self.instruction_overlay, bg="#f5f5f5")
        button_frame.pack(pady=(10, 20))
        
        self.proceed_button = ttk.Button(
            button_frame,
            text="Proceed to Setup",
            command=self.hide_instruction_overlay,
            style='Wizard.TButton',
            state=tk.DISABLED  # Initially disabled until checkbox is checked
        )
        self.proceed_button.pack()
    
    def update_proceed_button(self):
        """Enable or disable the proceed button based on checkbox state"""
        if self.acknowledged.get():
            self.proceed_button.config(state=tk.NORMAL)
        else:
            self.proceed_button.config(state=tk.DISABLED)
    
    def close_application(self):
        """Close the application when the instruction overlay close button is clicked"""
        self.root.destroy()
    
    def hide_instruction_overlay(self):
        """Hide the instruction overlay and continue with the normal flow"""
        self.instruction_overlay.place_forget()
        # Unblock UI interaction after proceeding
        self.unblock_ui_interaction()
    
    def setup_ui(self):
        # Create a canvas with scrollbar for the main content
        self.main_canvas = tk.Canvas(self.root)
        self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add scrollbar to the canvas
        try:
            self.scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.main_canvas.yview)
            self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Configure the canvas to use the scrollbar
            self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
            self.main_canvas.bind('<Configure>', lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))
        except:
            # If scrollbar module is not available, continue without it
            pass
        
        # Main frame with padding
        self.main_frame = ttk.Frame(self.main_canvas)
        self.main_canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        
        # Application title
        title_label = ttk.Label(self.main_frame, text="Entypt - Keystroke Authentication", font=("Arial", 16, "bold"))
        title_label.pack(pady=(10, 5))
        
        # Progress indicator frame
        self.setup_progress_indicator()
        
        # Navigation controls (side-by-side)
        self.setup_navigation_controls()
        
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create tabs with padding
        self.password_tab = ttk.Frame(self.notebook, padding="10 10 10 10")
        self.training_tab = ttk.Frame(self.notebook, padding="10 10 10 10")
        self.threshold_tab = ttk.Frame(self.notebook, padding="10 10 10 10")
        self.security_tab = ttk.Frame(self.notebook, padding="10 10 10 10")
        self.matrix_tab = ttk.Frame(self.notebook, padding="10 10 10 10")
        self.summary_tab = ttk.Frame(self.notebook, padding="10 10 10 10")
        
        self.notebook.add(self.password_tab, text="1. Password Setup")
        self.notebook.add(self.training_tab, text="2. Training")
        self.notebook.add(self.threshold_tab, text="3. Threshold")
        self.notebook.add(self.security_tab, text="4. Security Questions")
        self.notebook.add(self.matrix_tab, text="5. Matrix Effect")
        self.notebook.add(self.summary_tab, text="6. Confirmation")
        
        # Setup tabs
        self.setup_password_tab()
        self.setup_training_tab()
        self.setup_threshold_tab()
        self.setup_security_tab()
        self.setup_matrix_tab()
        self.setup_summary_tab()
        
        # Add mouse wheel scrolling to canvas
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Disable tabs initially except the first one
        self.update_tab_states()
        
        # Bind tab change event
        self.root.after(100, lambda: self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed))
        
        # Prepare the lock overlay (but don't show it yet)
        self.setup_lock_overlay()
    
    def setup_lock_overlay(self):
        """Create a lock overlay that will be shown when model exists"""
        # Create frame for lock overlay
        self.lock_frame = ttk.Frame(self.main_frame)
        
        # Simply use the text emoji directly
        lock_label = ttk.Label(self.lock_frame, text="🔒", font=("Arial", 50))
        lock_label.pack(pady=10)
        
        # Add text below the lock
        lock_text = ttk.Label(
            self.lock_frame,
            text="Authentication model is locked.\nUse buttons above to edit or delete.",
            font=self.subheading_font,
            justify=tk.CENTER
        )
        lock_text.pack(pady=10)
        
        # Don't pack the lock_frame yet - will be shown when needed
    
    def show_lock_overlay(self):
        """Display the lock overlay when model exists"""
        if hasattr(self, 'lock_frame'):
            # Place the lock overlay at the center of the main frame
            self.lock_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    
    def hide_lock_overlay(self):
        """Hide the lock overlay"""
        if hasattr(self, 'lock_frame'):
            self.lock_frame.place_forget()
    
    def setup_progress_indicator(self):
        # Create a progress frame
        self.progress_frame = ttk.Frame(self.main_frame)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Create step indicators
        self.step_indicators = {}
        step_texts = ["Password", "Training", "Threshold", "Security", "Matrix", "Summary"]
        
        for i, (step, text) in enumerate(zip(self.steps, step_texts)):
            step_frame = ttk.Frame(self.progress_frame)
            step_frame.pack(side=tk.LEFT, padx=5)
            
            # Step number and text
            self.step_indicators[step] = {
                'frame': step_frame,
                'label': ttk.Label(step_frame, text=f"{i+1}. {text}")
            }
            self.step_indicators[step]['label'].pack()
            
            # Add separator between steps (except last)
            if i < len(self.steps) - 1:
                ttk.Separator(self.progress_frame, orient=tk.HORIZONTAL).pack(
                    side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.update_progress_indicators()
    
    def update_progress_indicators(self):
        """Update the visual indicators for each step"""
        for step, indicator in self.step_indicators.items():
            if self.completed_steps[step]:
                indicator['label'].config(text=f"✓ {step.capitalize()}", foreground="green")
            else:
                index = self.steps.index(step)
                if index == self.current_step:
                    indicator['label'].config(foreground="blue")
                else:
                    indicator['label'].config(foreground="black")
    
    def setup_navigation_controls(self):
        # Create navigation frame at the top
        self.nav_frame = ttk.Frame(self.main_frame)
        self.nav_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Navigation buttons side-by-side
        self.prev_btn = ttk.Button(self.nav_frame, text="◀ Previous", command=self.go_to_prev_step)
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        
        self.next_btn = ttk.Button(self.nav_frame, text="Next ▶", command=self.go_to_next_step)
        self.next_btn.pack(side=tk.LEFT, padx=5)
        
        # Add a model management frame that will be centered
        self.model_buttons_container = ttk.Frame(self.nav_frame)
        self.model_buttons_container.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Instruction label and save button
        instruction_frame = ttk.Frame(self.nav_frame)
        instruction_frame.pack(side=tk.RIGHT)
        
        self.save_instruction = ttk.Label(instruction_frame, 
                                          text="Complete all steps to enable", 
                                          font=('Arial', 9), 
                                          foreground='gray')
        self.save_instruction.pack(side=tk.TOP, pady=(0, 2))
        
        self.save_btn = ttk.Button(
            instruction_frame, 
            text="Complete Setup & Save Model", 
            style='Wizard.TButton', 
            command=self.save_final_model,
            state=tk.DISABLED
        )
        self.save_btn.pack(side=tk.BOTTOM)
        
        self.update_navigation_buttons()
    
    def update_navigation_buttons(self):
        """Update navigation button states based on current step"""
        # If in edit mode, disable previous and next buttons
        if self.edit_mode:
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)
            
            # Always enable save button in edit mode
            self.save_btn.config(state=tk.NORMAL)
            self.save_instruction.config(
                text="Save changes to model", 
                foreground="green"
            )
            return
        
        # Normal mode - Enable/disable navigation based on steps
        # Disable previous button on first step
        self.prev_btn.config(state=tk.DISABLED if self.current_step == 0 else tk.NORMAL)
        
        # Control next button based on step completion
        current_step_name = self.steps[self.current_step]
        is_last_step = self.current_step == len(self.steps) - 1
        
        if is_last_step:
            self.next_btn.config(state=tk.DISABLED)
        else:
            self.next_btn.config(state=tk.NORMAL if self.completed_steps[current_step_name] else tk.DISABLED)
        
        # Normal mode - enable save button only on summary page with all steps completed
        all_completed = all([self.completed_steps[s] for s in self.steps[:-1]])  # All except summary
        is_summary_page = self.current_step == len(self.steps) - 1
        is_confirmed = True  # Default to True if checkbox doesn't exist yet
        if hasattr(self, 'confirm_var'):
            is_confirmed = self.confirm_var.get()
        
        self.save_btn.config(state=tk.NORMAL if all_completed and is_summary_page and is_confirmed else tk.DISABLED)
        
        # Update instruction text
        if all_completed and is_summary_page:
            if is_confirmed:
                self.save_instruction.config(text="Click to save your configuration", foreground="green")
            else:
                self.save_instruction.config(text="Check the confirmation box to enable save", foreground="gray")
        else:
            self.save_instruction.config(text="Complete all steps to enable", foreground="gray")
    
    def go_to_next_step(self):
        """Navigate to the next step in the wizard"""
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            self.notebook.select(self.current_step)
            if self.current_step == len(self.steps) - 1:  # If moving to summary tab
                self.update_summary()
            self.main_canvas.yview_moveto(0)
            self.update_navigation_buttons()
            self.update_progress_indicators()
    
    def go_to_prev_step(self):
        """Navigate to the previous step in the wizard"""
        if self.current_step > 0:
            self.current_step -= 1
            self.notebook.select(self.current_step)
            self.main_canvas.yview_moveto(0)
            self.update_navigation_buttons()
            self.update_progress_indicators()
    
    def on_tab_changed(self, event):
        """Handle tab change events"""
        try:
            # Make sure notebook exists and has tabs
            if not hasattr(self, 'notebook') or not self.notebook.winfo_exists():
                return
            
            # Get current tab index safely
            try:
                new_index = self.notebook.index("current")
                # Convert to int if it's a string
                if isinstance(new_index, str):
                    if new_index.isdigit():
                        new_index = int(new_index)
                    else:
                        return  # Not a valid index
            except (tk.TclError, ValueError):
                return  # Any error means we should ignore this event
            
            # Save the current step
            self.current_step = new_index
        
            # If we're moving to the summary tab, update it
            if new_index == len(self.steps) - 1:
                self.update_summary()

            # Reset scroll position to top when changing tabs
            self.main_canvas.yview_moveto(0)
        
            # Update UI
            self.update_navigation_buttons()
            self.update_progress_indicators()
        except Exception:
            # Ignore all errors during tab changes
            pass
    
    def update_tab_states(self):
        """Enable/disable tabs based on step completion"""
        # If we have an existing model, disable all tabs and show lock
        if self.has_existing_model:
            for i in range(len(self.steps)):
                self.notebook.tab(i, state="disabled")
            # Add model buttons if not already present
            self.add_model_buttons()
            # Show the lock overlay
            self.show_lock_overlay()
            return
        else:
            # Hide the lock overlay
            self.hide_lock_overlay()
            
        # If in edit mode, only allow access to training, threshold, and matrix tabs
        if self.edit_mode:
            for i in range(len(self.steps)):
                if i == 1 or i == 2 or i == 4:  # Training, threshold, or matrix tab
                    self.notebook.tab(i, state="normal")
                else:
                    self.notebook.tab(i, state="disabled")
            return
            
        # Normal mode - sequential tab access
        for i, step in enumerate(self.steps):
            # Allow access to steps that are complete or the next incomplete step
            can_access = False
            
            # First step is always accessible (unless model exists)
            if i == 0:
                can_access = True
            # Other steps require all previous steps to be complete
            else:
                previous_complete = all(self.completed_steps[self.steps[j]] for j in range(i))
                can_access = previous_complete
            
            # Set state
            self.notebook.tab(i, state="normal" if can_access else "disabled")
    
    def _on_mousewheel(self, event):
        try:
            self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except:
            # Alternative for platforms with different event structure
            try:
                if event.num == 5:
                    move = 1
                else:
                    move = -1
                self.main_canvas.yview_scroll(move, "units")
            except:
                pass
    
    def setup_password_tab(self):
        # Create a main content frame for the tab
        main_frame = ttk.Frame(self.password_tab)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create left frame for controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Create right frame for status
        right_frame = ttk.LabelFrame(main_frame, text="Status")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Top frame for instructions in left frame
        top_frame = ttk.Frame(left_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Instructions
        ttk.Label(top_frame, text="Set Your Password", font=self.heading_font).pack(anchor=tk.W)
        ttk.Label(top_frame, text="Choose a password you can type consistently.", 
                  font=self.text_font).pack(anchor=tk.W, pady=(5, 0))
        
        # Password setup frame
        pass_setup_frame = ttk.LabelFrame(left_frame, text="Password Entry", padding="10 10 10 10")
        pass_setup_frame.pack(fill=tk.X, pady=10)
        
        # Password entry layout
        pass_entry_frame = ttk.Frame(pass_setup_frame)
        pass_entry_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pass_entry_frame, text="Enter password:", 
                 font=self.text_font).pack(side=tk.LEFT, padx=(0, 10))
        
        # Frame to contain password entry and eye icon
        pwd_container_frame = ttk.Frame(pass_entry_frame)
        pwd_container_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        self.password_entry = ttk.Entry(pwd_container_frame, textvariable=self.password, width=20, show="•")
        self.password_entry.pack(side=tk.LEFT)
        # Add Enter key binding
        self.password_entry.bind("<Return>", lambda event: self.stage_password())
        
        # Variable to track password visibility
        self.password_visible = False
        
        # Add eye icon button for password visibility toggle
        self.eye_button = ttk.Button(pwd_container_frame, text="👁️", width=3, command=self.toggle_password_visibility)
        self.eye_button.pack(side=tk.LEFT)
        
        self.set_password_btn = ttk.Button(pass_entry_frame, text="Set Password", 
                                          command=self.stage_password,
                                          style='Action.TButton')
        self.set_password_btn.pack(side=tk.LEFT)
        
        # Password requirements
        ttk.Label(pass_setup_frame, 
                 text="• Password must be at least 4 characters\n• Choose a password you can type consistently", 
                 font=self.text_font).pack(anchor=tk.W, pady=5)
        
        # Status area in right frame
        self.password_status_text = scrolledtext.ScrolledText(right_frame, font=('Consolas', 10), height=15)
        self.password_status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.password_status_text.insert(tk.END, "Enter a password and click 'Set Password' or press Enter.\n")
        self.password_status_text.config(state=tk.DISABLED)
    
    def toggle_password_visibility(self):
        # Toggle password visibility
        self.password_visible = not self.password_visible
        if self.password_visible:
            self.password_entry.config(show="")
            self.eye_button.config(text="🔒")
        else:
            self.password_entry.config(show="•")
            self.eye_button.config(text="👁️")
    
    def stage_password(self):
        """Store the password in memory for later saving"""
        new_password = self.password.get()
        
        # Validate password
        if len(new_password) < 4:
            messagebox.showerror("Invalid Password", "Password must be at least 4 characters long.")
            return
        
        # Store in wizard state
        self.wizard_state["password"] = new_password
        self.num_features = len(new_password) - 1
        
        # Update UI
        self.update_status(self.password_status_text, 
                           f"Password staged successfully. It has {len(new_password)} characters.", 
                           clear=True)
        
        # Mark step complete
        self.completed_steps["password"] = True
        self.update_progress_indicators()
        self.update_navigation_buttons()
        self.update_tab_states()
        
        # Enable next step
        self.go_to_next_step()
    
    def setup_training_tab(self):
        # Create a main content frame for the tab
        main_frame = ttk.Frame(self.training_tab)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create left frame for controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Create right frame for status
        right_frame = ttk.LabelFrame(main_frame, text="Training Status")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Top frame for instructions in left frame
        top_frame = ttk.Frame(left_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Instructions
        ttk.Label(top_frame, text="Training Your Typing Pattern", font=self.heading_font).pack(anchor=tk.W)
        ttk.Label(top_frame, text="Train the system to recognize your unique typing rhythm.", 
                  font=self.text_font).pack(anchor=tk.W, pady=(5, 0))
        
        # Progress frame
        progress_frame = ttk.Frame(left_frame)
        progress_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(progress_frame, text="Training Progress:", font=self.text_font).pack(side=tk.LEFT)
        
        # Progress bar for attempts
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, 
                                           length=200, mode='determinate', 
                                           variable=self.progress_var, maximum=5)
        self.progress_bar.pack(side=tk.LEFT, padx=10)
        
        self.attempt_label = ttk.Label(progress_frame, text="0/5 attempts", font=self.text_font)
        self.attempt_label.pack(side=tk.LEFT)
        
        # Input frame
        input_frame = ttk.LabelFrame(left_frame, text="Training Input", padding="10 10 10 10")
        input_frame.pack(fill=tk.X, pady=10)
        
        # Clearer instructions
        ttk.Label(input_frame, 
                  text="Click Start Training and Type your password below and press ENTER after each attempt.",
                  font=self.text_font).pack(anchor=tk.W, pady=(0, 10))
        
        # Action buttons at the top
        button_frame = ttk.Frame(input_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.train_button = ttk.Button(button_frame, text="Start Training", style='Action.TButton',
                                       command=self.start_training)
        self.train_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Add Save Training button
        self.save_training_button = ttk.Button(button_frame, text="Save Training", 
                                            style='Action.TButton',
                                            command=self.save_training,
                                            state=tk.DISABLED)
        self.save_training_button.pack(side=tk.LEFT)
        
        # Password entry with visual cue (moved below buttons)
        entry_frame = ttk.Frame(input_frame)
        entry_frame.pack(fill=tk.X)
        
        # Initially disabled until training starts
        self.train_entry = ttk.Entry(entry_frame, width=20, font=('Arial', 12), show="•", state=tk.DISABLED)
        self.train_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.train_entry.bind("<Key>", self.on_key_press_training)
        self.train_entry.bind("<Return>", self.on_return_press_training)
        
        # Status area in right frame
        self.train_status_text = scrolledtext.ScrolledText(right_frame, font=('Consolas', 10), height=15)
        self.train_status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.train_status_text.insert(tk.END, "Click 'Start Training' when you're ready.\n")
        self.train_status_text.insert(tk.END, "Click 'Save Training' after successful training.\n")
        self.train_status_text.insert(tk.END, "Ready to begin training...\n")
        self.train_status_text.config(state=tk.DISABLED)
        
        # Training variables
        self.training_data = []
        self.current_attempt = 0
        self.max_attempts = 5
        self.recording = False
        self.key_times = []
        self.last_key_time = None
    
    def start_training(self):
        # Get the password from wizard state
        password = self.wizard_state["password"]
        if not password:
            messagebox.showerror("Password Required", "Please set your password first.")
            self.notebook.select(0)  # Go to password tab
            return
        
        self.recording = False
        self.current_attempt = 0
        self.training_data = []
        
        # Reset UI
        self.progress_var.set(0)
        self.attempt_label.config(text="0/5 attempts")
        self.update_status(self.train_status_text, "Starting new training session...", clear=True)
        self.update_status(self.train_status_text, "You will need to type your password 5 times with same typing pattern.")
        self.update_status(self.train_status_text, "Choose your own typing pattern that can be typed consistently.")
        
        # Update button text and enable entry field
        self.train_button.config(text="Reset Training", command=self.reset_training)
        self.train_entry.config(state=tk.NORMAL)  # Enable entry field
        self.save_training_button.config(state=tk.DISABLED)  # Disable save button during training
        
        # Start first attempt
        self.prepare_for_next_attempt()
    
    def reset_training(self):
        self.recording = False
        self.current_attempt = 0
        self.training_data = []
        
        # Reset UI
        self.progress_var.set(0)
        self.attempt_label.config(text="0/5 attempts")
        self.train_button.config(text="Start Training", command=self.start_training)
        self.train_entry.config(state=tk.DISABLED)  # Disable entry field
        self.train_entry.delete(0, tk.END)
        self.save_training_button.config(state=tk.DISABLED)  # Disable save button
        self.update_status(self.train_status_text, "Training reset. Ready to begin.", clear=True)
        
        # Mark step as incomplete
        self.completed_steps["training"] = False
        self.update_progress_indicators()
        self.update_navigation_buttons()
        self.update_tab_states()
    
    def prepare_for_next_attempt(self):
        if self.current_attempt < self.max_attempts:
            self.update_status(self.train_status_text, f"\nAttempt {self.current_attempt + 1} of {self.max_attempts}")
            self.update_status(self.train_status_text, "Type your password and press ENTER when done.")
            self.train_entry.delete(0, tk.END)  # Clear the entry field
            self.train_entry.focus()
            
            # Update progress
            self.attempt_label.config(text=f"{self.current_attempt}/5 attempts")
            
            # Reset key times for new attempt
            self.key_times = []
            self.last_key_time = None
            
            # Ready to record
            self.recording = True
        else:
            # Training complete, enable save button
            self.train_button.config(text="Start Training", state=tk.NORMAL)
            self.train_entry.config(state=tk.DISABLED)  # Disable entry field after training
            self.save_training_button.config(state=tk.NORMAL)  # Enable save button
            
            # Process the training data but don't stage it yet
            self.process_training_data()
    
    def on_key_press_training(self, event):
        if self.recording:
            if event.char and event.char.isalnum():
                current_time = time.time()
                if self.last_key_time is not None:
                    self.key_times.append(current_time - self.last_key_time)
                self.last_key_time = current_time

    def on_return_press_training(self, event):
        if not self.recording:
            return
            
        typed = self.train_entry.get()
        current_password = self.wizard_state["password"]
        
        if typed != current_password:
            self.update_status(self.train_status_text, "❌ Incorrect password entered. Please try again.")
            self.train_entry.delete(0, tk.END)
            # Reset for this attempt
            self.key_times = []
            self.last_key_time = None
            return
            
        if len(self.key_times) == self.num_features:

            if self.training_data:
                if len(self.training_data) > 1:
                    prev_attempt = self.training_data[-1]  # Compare with last saved attempt (not failed ones)
                else:
                    prev_attempt = self.key_times  # First attempt, no comparison needed
                deviation = np.linalg.norm(np.array(self.key_times) - np.array(prev_attempt))  # Euclidean distance
        
                max_allowed_deviation = 0.75  # Adjust this value based on testing
        
                if deviation > max_allowed_deviation:
                    self.update_status(self.train_status_text, "❌ Training attempt rejected: Typing too inconsistent.")
                    self.train_entry.delete(0, tk.END)
                    self.key_times = []  # Reset this attempt
                    self.last_key_time = None
                    return  # Reject the attempt

            self.training_data.append(self.key_times)
            self.update_status(self.train_status_text, f"✓ Attempt {self.current_attempt + 1} recorded successfully.")
            self.update_status(self.train_status_text, f"  Typing intervals: {[f'{t:.3f}s' for t in self.key_times]}")
            
            # Update progress
            self.current_attempt += 1
            self.progress_var.set(self.current_attempt)
            self.attempt_label.config(text=f"{self.current_attempt}/5 attempts")
            
            # Prepare for next attempt
            self.recording = False
            self.root.after(1000, self.prepare_for_next_attempt)
        else:
            self.update_status(self.train_status_text, f"❌ Invalid recording. Expected {self.num_features} intervals, got {len(self.key_times)}.")
            # Reset for this attempt
            self.key_times = []
            self.last_key_time = None
            self.train_entry.delete(0, tk.END)

    def process_training_data(self):
        """Process training data but don't stage it yet"""
        if not self.training_data or len(self.training_data) < 3:
            self.update_status(self.train_status_text, "❌ Not enough training samples. Please complete the training.", clear=True)
            return False
                
        train_data = np.array(self.training_data)
        scaler = StandardScaler()
        scaled_train_data = scaler.fit_transform(train_data)
        
        # Calculate self-similarity scores for training data
        self_similarities = []
        for i in range(len(scaled_train_data)):
            test_sample = scaled_train_data[i:i+1]
            remaining_samples = np.delete(scaled_train_data, i, axis=0)
            sim = self.similarity_score(test_sample, remaining_samples, 1)  # Using 1 to calculate raw similarity
            self_similarities.append(sim)

        avg_typing_speed_per_interval = np.mean(train_data, axis=0) if train_data.shape[0] > 0 else np.zeros(train_data.shape[1])
        std_dev_typing_speed_per_interval = np.std(train_data, axis=0) if train_data.shape[0] > 0 else np.ones(train_data.shape[1]) * 0.01

        global_avg_speed = np.mean(avg_typing_speed_per_interval)
        global_std_dev = np.mean(std_dev_typing_speed_per_interval)
        if global_std_dev == 0:
            global_std_dev = 0.01
        
        avg_self_similarity = np.mean(self_similarities)
        min_self_similarity = np.min(self_similarities)

        interval_means = np.mean(train_data, axis=0)
        interval_stds = np.std(train_data, axis=0)
        lower_thresholds = interval_means - 1.5 * interval_stds
        upper_thresholds = interval_means + 1.5 * interval_stds
        
        # Store temporarily
        self.processed_training = {
            "avg_typing_speed": global_avg_speed,
            "std_dev_typing_speed": global_std_dev,
            "train_data": scaled_train_data,
            "scaler": scaler,
            "avg_self_similarity": avg_self_similarity,
            "min_self_similarity": min_self_similarity,
            "raw_training_data": train_data,  # Add raw data
            "interval_lower_thresholds": lower_thresholds,  # Add lower thresholds
            "interval_upper_thresholds": upper_thresholds   # Add upper thresholds
        }
        
        # Add hybrid security elements
        self.processed_training["security_level"] = self.wizard_state.get("security_level", "high")
        self.processed_training["weights"] = {
            "interval": 0.5,
            "pattern": 0.3,
            "speed": 0.2
        }
        
        interval_stds = np.std(train_data, axis=0)
        consistency_factor = 1.0 - (np.mean(interval_stds) / np.mean(np.mean(train_data, axis=0)))

        # Get training data
        raw_data = self.processed_training.get("raw_training_data", [])
    
        # Calculate consistency ratio (lower = more consistent)
        avg_intervals = np.mean(raw_data, axis=0)
        std_devs = np.std(raw_data, axis=0)
    
        # Simple ratio of average standard deviation to average interval
        consistency_ratio = np.mean(std_devs) / np.mean(avg_intervals)
    
        # Convert to consistency score (higher = more consistent)
        # Typical values range from 0.1 (very consistent) to 0.5+ (inconsistent)
        consistency_score = max(0, min(1, 1 - (consistency_ratio * 2)))
    
        # Map to threshold range
        recommended = 50 + (consistency_score * 35)
    
        # Recommended threshold
        recommended_threshold =(int(recommended / 5) * 5) - 3

        # Update UI
        self.update_status(self.train_status_text, "\n✅ Training Complete!")
        self.update_status(self.train_status_text, "\nYour typing rhythm statistics:", clear=True)
        self.update_status(self.train_status_text, f"\n• Average intervals: {[f'{t:.3f}s' for t in np.mean(train_data, axis=0)]}")
        self.update_status(self.train_status_text, f"• Standard deviations: {[f'{t:.3f}s' for t in np.std(train_data, axis=0)]}")
        self.update_status(self.train_status_text, "\nClick 'Save Training' to save these results.")
        self.update_status(self.train_status_text, f"\n✅ RECOMMENDED THRESHOLD based on the training: {recommended_threshold}%")
        
        return True

    def save_training(self):
        """Save training data to wizard state"""
        if not hasattr(self, 'processed_training'):
            success = self.process_training_data()  # Force processing before saving
            if not success:
                messagebox.showerror("Error", "No processed training data available. Please complete the training first.")
                return
        
        # Save processed data to wizard state
        self.wizard_state["training_data"] = self.processed_training["train_data"]
        self.wizard_state["scaler"] = self.processed_training["scaler"]
        self.wizard_state["avg_self_similarity"] = self.processed_training["avg_self_similarity"]
        self.wizard_state["min_self_similarity"] = self.processed_training["min_self_similarity"]
        self.wizard_state["raw_training_data"] = self.processed_training["raw_training_data"]
        self.wizard_state["interval_lower_thresholds"] = self.processed_training["interval_lower_thresholds"]
        self.wizard_state["interval_upper_thresholds"] = self.processed_training["interval_upper_thresholds"]
        self.wizard_state["avg_typing_speed"] = self.processed_training.get("avg_typing_speed", 0)
        self.wizard_state["std_dev_typing_speed"] = self.processed_training.get("std_dev_typing_speed", 0)

        if self.model is None:
            self.model = {}

        self.model["avg_typing_speed"] = self.wizard_state["avg_typing_speed"]
        self.model["std_dev_typing_speed"] = self.wizard_state["std_dev_typing_speed"]
        
        # Mark step complete
        self.completed_steps["training"] = True
        self.update_progress_indicators()
        self.update_navigation_buttons()
        self.update_tab_states()
        
        # Confirmation message
        self.update_status(self.train_status_text, "\n✅ Training saved successfully!", append=True)
        
        # Move to the threshold tab automatically
        self.go_to_next_step()

    def similarity_score(self, test_features, train_features, avg_self_similarity):
        """Calculate similarity score without threshold comparison."""
        # Calculate distances to all training samples
        distances = [np.linalg.norm(test_features - train_sample) 
                    for train_sample in train_features]
        
        # Average distance to all training samples
        avg_distance = np.mean(distances)
        
        # Convert distance to similarity score (closer to 1.0 is better)
        similarity = avg_self_similarity / (avg_self_similarity + avg_distance)
        
        # Cap at 1.0 and ensure non-negative
        return max(0.0, min(similarity, 1.0))

    # NEW FUNCTION: Calculate pattern score
    def calculate_pattern_score(self, test_features, train_features, avg_self_similarity):
        """Calculate pattern similarity score (0.0 to 1.0)."""
        # Calculate distances to all training samples
        distances = [np.linalg.norm(test_features - train_sample) for train_sample in train_features]
        avg_distance = np.mean(distances)

        # Add a tolerance factor (0.3 means 30% more lenient)
        tolerance_factor = 0.3
        adjusted_distance = avg_distance * (1 - tolerance_factor)
        
        # Convert distance to similarity score (closer to 1.0 is better)
        similarity = avg_self_similarity / (avg_self_similarity + avg_distance)
        
        # Cap at 1.0 and ensure non-negative
        return max(0.0, min(similarity, 1.0))
    
    # NEW FUNCTION: Calculate interval score
    def calculate_interval_score(self, test_intervals, lower_thresholds, upper_thresholds):
        """Calculate interval matching score (0.0 to 1.0)."""
        # Check how many intervals are within acceptable ranges
        within_bounds = []
        for i, interval in enumerate(test_intervals):
            if i < len(lower_thresholds):
                lower = lower_thresholds[i]
                upper = upper_thresholds[i]
                within_bounds.append(lower <= interval <= upper)
        
        # Return percentage of intervals that match
        if not within_bounds:
            return 0.0
        
        return sum(within_bounds) / len(within_bounds)

    # NEW FUNCTION: Calculate speed score  
    def calculate_speed_score(self, test_intervals, avg_typing_speed, std_dev_typing_speed):
        """Calculate speed consistency score (0.0 to 1.0)."""
        # Calculate current typing speed
        current_avg_speed = np.mean(test_intervals)
        
        # Calculate how many standard deviations from the mean
        z_score = abs((current_avg_speed - avg_typing_speed) / max(std_dev_typing_speed, 0.001))
        
        # Convert to score (0.0 to 1.0)
        # A z-score of 2.0 or greater results in a score of 0.0
        return max(0.0, min(1.0 - (z_score / 2.0), 1.0))

    def verify_hybrid(self, keystroke_times, model):
        """
        Verify keystroke pattern using the enhanced hybrid security approach.
        
        Args:
            keystroke_times: List of keystroke timings to verify
            model: Authentication model 
            
        Returns:
            Tuple of (is_authenticated, security_score, details)
        """
        # Convert to numpy array
        keystroke_times = np.array(keystroke_times)
        
        # Calculate pattern score
        test_features = keystroke_times.reshape(1, -1)
        test_scaled = model["scaler"].transform(test_features)[0]
        train_data = model.get("train_data", model.get("training_data", None))
        pattern_score = self.calculate_pattern_score(test_scaled, train_data, model["avg_self_similarity"])
        
        # Calculate interval score
        lower_bounds = model["interval_lower_thresholds"]
        upper_bounds = model["interval_upper_thresholds"]

        # Add padding to the bounds 
        lower_bounds = [bound * 0.80 for bound in lower_bounds]
        upper_bounds = [bound * 1.20 for bound in upper_bounds]

        interval_score = self.calculate_interval_score(keystroke_times, lower_bounds, upper_bounds)
        
        # Calculate speed score
        speed_score = self.calculate_speed_score(
            keystroke_times, 
            model.get("avg_typing_speed", 0), 
            model.get("std_dev_typing_speed", 0.001)
        )
        
        # Get security level settings
        security_settings = {
            # Each entry contains (interval_minimum, secondary_minimum, overall_threshold)
            "low":       (0.50, 0.40, 0.70),
            "medium":    (0.65, 0.52, 0.80),
            "high":      (0.75, 0.60, 0.85),
            "very_high": (0.85, 0.68, 0.90)
        }
        
        # Get security level from model or use default
        security_level = model.get("security_level", "high")
        interval_minimum, secondary_minimum, overall_threshold = security_settings.get(
            security_level, security_settings["high"])
        
        # Check if interval score meets the minimum requirement
        if interval_score < interval_minimum:
            return False, 0.0, {
                "reason": "Interval score below minimum requirement",
                "scores": {
                    "interval": interval_score,
                    "pattern": pattern_score,
                    "speed": speed_score
                }
            }
        
        # Check if at least one secondary factor meets minimum requirement
        if pattern_score < secondary_minimum and speed_score < secondary_minimum:
            return False, 0.0, {
                "reason": "Both secondary factors below minimum requirements",
                "scores": {
                    "interval": interval_score,
                    "pattern": pattern_score,
                    "speed": speed_score
                }
            }
        
        # Calculate weighted score with 50/30/20 weighting
        weights = {"interval": 0.5, "pattern": 0.3, "speed": 0.2}
        weighted_score = (
            weights["interval"] * interval_score +
            weights["pattern"] * pattern_score +
            weights["speed"] * speed_score
        )
        
        # Add bonus for excellence in interval matching
        if interval_score > 0.90:
            weighted_score += 0.05
        
        # Check overall threshold
        is_authenticated = weighted_score >= overall_threshold
        
        details = {
            "scores": {
                "interval": interval_score,
                "pattern": pattern_score,
                "speed": speed_score,
                "weighted": weighted_score
            },
            "threshold": overall_threshold,
            "security_level": security_level
        }
        
        return is_authenticated, weighted_score, details

     # UPDATED FUNCTION: Modified setup_threshold_tab
    def setup_threshold_tab(self):
        # Create a main content frame for the tab
        main_frame = ttk.Frame(self.threshold_tab)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create left frame for controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Create right frame for status
        right_frame = ttk.LabelFrame(main_frame, text="Status")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Top frame for instructions in left frame
        top_frame = ttk.Frame(left_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Instructions
        ttk.Label(top_frame, text="Set Authentication Threshold", font=self.heading_font).pack(anchor=tk.W)
        ttk.Label(top_frame, text="Adjust how strictly the system should match your typing pattern.", 
                 font=self.text_font).pack(anchor=tk.W, pady=(5, 0))
        
        # Threshold slider frame
        threshold_frame = ttk.LabelFrame(left_frame, text="Authentication Threshold", padding="10 10 10 10")
        threshold_frame.pack(fill=tk.X, pady=10)
        
        # Threshold slider
        slider_frame = ttk.Frame(threshold_frame)
        slider_frame.pack(fill=tk.X, pady=10)
        
        self.threshold_var = tk.IntVar(value=self.wizard_state["threshold_value"])
        self.threshold_slider = ttk.Scale(
            slider_frame, 
            from_=50, 
            to=100, 
            orient=tk.HORIZONTAL, 
            length=300, 
            variable=self.threshold_var,
            command=self.on_threshold_change
        )
        self.threshold_slider.pack(side=tk.LEFT, padx=(0, 10))
        
        self.threshold_label = ttk.Label(slider_frame, text=f"{self.threshold_var.get()}%", font=self.text_font)
        self.threshold_label.pack(side=tk.LEFT)
        
        # Threshold description
        threshold_desc_frame = ttk.Frame(threshold_frame)
        threshold_desc_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(threshold_desc_frame, text="Lower: More forgiving, less secure", 
                 font=('Arial', 9)).pack(side=tk.LEFT)
        ttk.Label(threshold_desc_frame, text="Higher: Stricter, more secure", 
                 font=('Arial', 9)).pack(side=tk.RIGHT)
                 
        ttk.Separator(threshold_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Add security level display
        security_display_frame = ttk.Frame(threshold_frame)
        security_display_frame.pack(fill=tk.X, pady=10)
    
        ttk.Label(security_display_frame, text="Security Threshold:", 
                font=self.subheading_font).pack(side=tk.LEFT, padx=(0, 10))
            
        # Create a label that will display the security level dynamically
        self.security_level_display = ttk.Label(
            security_display_frame,
            text="Medium Security",
            font=('Arial', 12, 'bold'),
            foreground="#ffc107"  # Yellow color for emphasis
        )
        self.security_level_display.pack(side=tk.LEFT)
        
        # Save button
        save_button_frame = ttk.Frame(threshold_frame)
        save_button_frame.pack(fill=tk.X, pady=10)
        
        self.save_threshold_btn = ttk.Button(
            save_button_frame,
            text="Save Threshold Setting",
            command=self.save_threshold,
            style='Action.TButton'
        )
        self.save_threshold_btn.pack(side=tk.LEFT)
        
        # Add security level selector
        security_level_frame = ttk.LabelFrame(left_frame, text="Security Threshold", padding="10 10 10 10")
        security_level_frame.pack(fill=tk.X, pady=10)

        security_level_text = "Security Threshold for the authentication system:"
        ttk.Label(security_level_frame, text=security_level_text, font=self.text_font).pack(anchor=tk.W, pady=5)

        self.security_level_var = tk.StringVar(value=self.wizard_state.get("security_level", "high"))
        security_levels = [
            ("Low Security", "low", "Basic protection, most forgiving"),
            ("Medium Security", "medium", "Standard protection, balanced approach"),
            ("High Security", "high", "Enhanced protection, tightened security"),
            ("Very High Security", "very_high", "Maximum protection, strictest verification")
        ]


        # Display description text for each security level
        for text, value, description in security_levels:
            level_frame = ttk.Frame(security_level_frame)
            level_frame.pack(fill=tk.X, pady=2)
    
            # Just show text 
            level_label = ttk.Label(level_frame, text=text, font=('Arial', 10))
            level_label.pack(side=tk.LEFT)
    
            # Store reference to label for highlighting the active level later
            if not hasattr(self, 'level_labels'):
                self.level_labels = {}
            self.level_labels[value] = level_label
    
            ttk.Label(level_frame, text=f" - {description}", font=('Arial', 9)).pack(side=tk.LEFT, padx=5)
        
        # Status area in right frame
        self.threshold_status_text = scrolledtext.ScrolledText(right_frame, font=('Consolas', 10), height=15)
        self.threshold_status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.threshold_status_text.insert(tk.END, "Adjust the threshold slider and click 'Save Threshold Setting'.\n")
        self.threshold_status_text.insert(tk.END, "Higher values provide better security but may be harder to authenticate.\n")
        self.threshold_status_text.insert(tk.END, "Use recommended Threshold based on training.\n")
        self.threshold_status_text.config(state=tk.DISABLED)

    def update_security_level(self):
        """Update the wizard state when security level changes"""
        self.wizard_state["security_level"] = self.security_level_var.get()

    def on_threshold_change(self, value):
        """Update threshold value display and security level display"""
        threshold_value = int(float(value))
        self.threshold_label.config(text=f"{threshold_value}%")
        self.wizard_state["threshold_value"] = threshold_value

        # Reset all level labels to normal style
        if hasattr(self, 'level_labels'):
            for label in self.level_labels.values():
                label.config(font=('Arial', 10), foreground="black")
    
        # Update security level based on threshold
        if threshold_value < 65:
            security_level = "low"
            display_text = "Low Security"
            color = "#28a745"  # Green
        elif threshold_value < 80:
            security_level = "medium"
            display_text = "Medium Security"
            color = "#ffc107"  # Yellow
        elif threshold_value < 90:
            security_level = "high"
            display_text = "High Security"
            color = "#fd7e14"  # Orange
        else:
            security_level = "very_high"
            display_text = "Very High Security"
            color = "#dc3545"  # Red
    
        # Update the security level variable and display
        self.security_level_var.set(security_level)
        self.security_level_display.config(text=display_text, foreground=color)

        # Highlight the active level label
        if hasattr(self, 'level_labels') and security_level in self.level_labels:
            self.level_labels[security_level].config(font=('Arial', 10, 'bold'), foreground=color)

        self.update_security_level()
    
    def save_threshold(self):
        """Save threshold setting to wizard state"""
        # Store in wizard state
        security_level = self.security_level_var.get()
        
        # Update UI
        self.update_status(self.threshold_status_text, 
                        f"Threshold set to {self.threshold_var.get()}% with {self.security_level_var.get()} security Threshold", 
                        clear=True)
        
        # Mark step complete
        self.completed_steps["threshold"] = True
        self.update_progress_indicators()
        self.update_navigation_buttons()
        self.update_tab_states()
        
        # Only go to next step if not in edit mode
        if not self.edit_mode:
            self.go_to_next_step()

    def _stop_propagation(self, event):
        """Stop event propagation to prevent affecting the main canvas scroll"""
        return "break"

    def _on_mousewheel(self, event):
        # Check if the event originated from a combobox or entry
        if isinstance(event.widget, ttk.Combobox) or isinstance(event.widget, ttk.Entry):
            return
        
        try:
            self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except:
            # Alternative for platforms with different event structure
            try:
                if event.num == 5:
                    move = 1
                else:
                    move = -1
                self.main_canvas.yview_scroll(move, "units")
            except:
                pass
            
    def setup_security_tab(self):
        # Create a main content frame for the tab
        main_frame = ttk.Frame(self.security_tab)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create left frame for controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Create right frame for status
        right_frame = ttk.LabelFrame(main_frame, text="Status")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Top frame for instructions in left frame
        top_frame = ttk.Frame(left_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Instructions
        ttk.Label(top_frame, text="Configure Security Questions", font=self.heading_font).pack(anchor=tk.W)
        ttk.Label(top_frame, text="Set up security questions as a backup to unlock your system.", 
                font=self.text_font).pack(anchor=tk.W, pady=(5, 0))
        
        # Security questions section
        questions_frame = ttk.LabelFrame(left_frame, text="Security Questions", padding="10 10 10 10")
        questions_frame.pack(fill=tk.X, pady=10)
        
        # Note about mandatory questions
        ttk.Label(questions_frame, 
               text="All three security questions and answers are required.", 
               font=self.text_font).pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(questions_frame, 
               text="Questions and answers must be unique.", 
               font=self.text_font).pack(anchor=tk.W, pady=(0, 10))

        
        # Question 1
        q1_frame = ttk.Frame(questions_frame)
        q1_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(q1_frame, text="Question 1:", font=self.text_font).pack(anchor=tk.W, pady=5)
        
        # ComboBox with ability to enter custom questions directly
        self.question1_var = tk.StringVar()
        self.question1_combo = ttk.Combobox(q1_frame, textvariable=self.question1_var, width=40)
        self.question1_combo.pack(anchor=tk.W, pady=2)
        self.question1_combo["values"] = DEFAULT_SECURITY_QUESTIONS
        self.question1_combo.bind("<<ComboboxSelected>>", lambda e: self.on_question_selection(1))
        
        # Set up placeholder text
        self.question1_combo.insert(0, "Choose a security question...")
        self.question1_combo.bind("<FocusIn>", lambda e: self.on_question_field_focus_in(1))
        self.question1_combo.bind("<FocusOut>", lambda e: self.on_question_field_focus_out(1))
        self.question1_combo.bind("<MouseWheel>", self._stop_propagation)
        
        ttk.Label(q1_frame, text="Answer:", font=self.text_font).pack(anchor=tk.W, pady=5)
        self.answer1 = tk.StringVar(value="")
        answer1_entry = ttk.Entry(q1_frame, textvariable=self.answer1, width=30)
        answer1_entry.pack(anchor=tk.W, pady=2)
        
        # Question 2
        q2_frame = ttk.Frame(questions_frame)
        q2_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(q2_frame, text="Question 2:", font=self.text_font).pack(anchor=tk.W, pady=5)
        
        # ComboBox with ability to enter custom questions directly
        self.question2_var = tk.StringVar()
        self.question2_combo = ttk.Combobox(q2_frame, textvariable=self.question2_var, width=40)
        self.question2_combo.pack(anchor=tk.W, pady=2)
        self.question2_combo["values"] = DEFAULT_SECURITY_QUESTIONS
        self.question2_combo.bind("<<ComboboxSelected>>", lambda e: self.on_question_selection(2))
        
        # Set up placeholder text
        self.question2_combo.insert(0, "Choose a security question...")
        self.question2_combo.bind("<FocusIn>", lambda e: self.on_question_field_focus_in(2))
        self.question2_combo.bind("<FocusOut>", lambda e: self.on_question_field_focus_out(2))
        self.question1_combo.bind("<MouseWheel>", self._stop_propagation)
        
        ttk.Label(q2_frame, text="Answer:", font=self.text_font).pack(anchor=tk.W, pady=5)
        self.answer2 = tk.StringVar(value="")
        answer2_entry = ttk.Entry(q2_frame, textvariable=self.answer2, width=30)
        answer2_entry.pack(anchor=tk.W, pady=2)
        
        # Question 3
        q3_frame = ttk.Frame(questions_frame)
        q3_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(q3_frame, text="Question 3:", font=self.text_font).pack(anchor=tk.W, pady=5)
        
        # ComboBox with ability to enter custom questions directly
        self.question3_var = tk.StringVar()
        self.question3_combo = ttk.Combobox(q3_frame, textvariable=self.question3_var, width=40)
        self.question3_combo.pack(anchor=tk.W, pady=2)
        self.question3_combo["values"] = DEFAULT_SECURITY_QUESTIONS
        self.question3_combo.bind("<<ComboboxSelected>>", lambda e: self.on_question_selection(3))
        
        # Set up placeholder text
        self.question3_combo.insert(0, "Choose a security question...")
        self.question3_combo.bind("<FocusIn>", lambda e: self.on_question_field_focus_in(3))
        self.question3_combo.bind("<FocusOut>", lambda e: self.on_question_field_focus_out(3))
        self.question1_combo.bind("<MouseWheel>", self._stop_propagation)
        
        ttk.Label(q3_frame, text="Answer:", font=self.text_font).pack(anchor=tk.W, pady=5)
        self.answer3 = tk.StringVar(value="")
        answer3_entry = ttk.Entry(q3_frame, textvariable=self.answer3, width=30)
        answer3_entry.pack(anchor=tk.W, pady=2)
        
        # Save button
        save_frame = ttk.Frame(questions_frame)
        save_frame.pack(fill=tk.X, pady=10)
        
        self.save_questions_button = ttk.Button(
            save_frame, 
            text="Save Security Questions", 
            style='Action.TButton',
            command=self.stage_security_questions
        )
        self.save_questions_button.pack(pady=10)
        
        # Status area in right frame
        self.security_status_text = scrolledtext.ScrolledText(right_frame, font=('Consolas', 10), height=15)
        self.security_status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.security_status_text.insert(tk.END, "Select security questions from the dropdown menus or enter your own custom questions.\n"
                                                 "Then click 'Save Security Questions'.\n")
        self.security_status_text.config(state=tk.DISABLED)

    def on_question_field_focus_in(self, question_num):
        """Handle focus in event for the question combo boxes - clear placeholder text"""
        if question_num == 1:
            combo = self.question1_combo
        elif question_num == 2:
            combo = self.question2_combo
        elif question_num == 3:
            combo = self.question3_combo
        
        # If the current text is the placeholder, clear it
        if combo.get() == "Choose a security question...":
            combo.delete(0, tk.END)

    def on_question_field_focus_out(self, question_num):
        """Handle focus out event for the question combo boxes - restore placeholder if empty"""
        if question_num == 1:
            combo = self.question1_combo
        elif question_num == 2:
            combo = self.question2_combo
        elif question_num == 3:
            combo = self.question3_combo
        
        # If the field is empty, put the placeholder back
        if combo.get() == "":
            combo.insert(0, "Choose a security question...")

    def on_question_selection(self, question_num):
        """Handle dropdown question selection"""
        if question_num == 1:
            combo = self.question1_combo
        elif question_num == 2:
            combo = self.question2_combo
        elif question_num == 3:
            combo = self.question3_combo
        else:
            return
        
        # If "Custom Question..." was selected, clear the field to allow user input
        if combo.get() == "Custom Question...":
            combo.delete(0, tk.END)
            combo.focus()

    def get_question_text(self, question_num):
        """Get the actual question text"""
        if question_num == 1:
            text = self.question1_var.get().strip()
        elif question_num == 2:
            text = self.question2_var.get().strip()
        elif question_num == 3:
            text = self.question3_var.get().strip()
        else:
            return ""
        
        # Don't return the placeholder text
        if text == "Choose a security question...":
            return ""
        return text

    def stage_security_questions(self):
        # Get all questions and answers
        q1 = self.get_question_text(1)
        a1 = self.answer1.get().strip().lower()
        q2 = self.get_question_text(2)
        a2 = self.answer2.get().strip().lower()
        q3 = self.get_question_text(3)
        a3 = self.answer3.get().strip().lower()
        
        # Validate all questions and answers are provided
        if not q1 or not a1 or not q2 or not a2 or not q3 or not a3:
            messagebox.showerror("Incomplete Information", 
                             "All three security questions and answers are required.")
            return
            
        # Check for uniqueness in questions and answers
        questions = [q1, q2, q3]
        answers = [a1, a2, a3]
        
        # Check for duplicate questions
        if len(set(questions)) < 3:
            messagebox.showerror("Duplicate Questions", 
                             "All security questions must be unique.")
            return
            
        # Check for duplicate answers
        if len(set(answers)) < 3:
            messagebox.showerror("Duplicate Answers", 
                             "All security question answers must be unique.")
            return
        
        # Store in wizard state
        security_questions = {
            q1: a1,
            q2: a2,
            q3: a3
        }
        self.wizard_state["security_questions"] = security_questions
        
        # Update UI
        self.update_status(self.security_status_text, "All security questions saved successfully.", clear=True)
        
        # Mark step complete
        self.completed_steps["security"] = True
        self.update_progress_indicators()
        self.update_navigation_buttons()
        self.update_tab_states()
        
        # Go to next step
        self.go_to_next_step()

    def setup_matrix_tab(self):
        """Setup tab for matrix effect configuration"""
        # Create a main content frame for the tab
        main_frame = ttk.Frame(self.matrix_tab)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create left frame for controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Create right frame for status
        right_frame = ttk.LabelFrame(main_frame, text="Status")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Top frame for instructions in left frame
        top_frame = ttk.Frame(left_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Instructions
        ttk.Label(top_frame, text="Configure Matrix Effect", font=self.heading_font).pack(anchor=tk.W)
        ttk.Label(top_frame, text="Customize the appearance of the Matrix effect on your lockscreen.", 
                font=self.text_font).pack(anchor=tk.W, pady=(5, 0))
        
        # Character selection frame
        char_frame = ttk.LabelFrame(left_frame, text="Matrix Characters", padding="10 10 10 10")
        char_frame.pack(fill=tk.X, pady=10)
        
        # Character set selection
        ttk.Label(char_frame, text="Select character set:", font=self.text_font).pack(anchor=tk.W, pady=5)
        
        self.char_set = tk.StringVar(value="alphanumeric")
        char_sets = [
            ("Alphanumeric (a-z, A-Z, 0-9) (RECOMMENDED)", "alphanumeric"),
            ("Alphabets only (a-z, A-Z)", "latin"),
            ("Numbers only (0-9)", "numbers")
        ]
        
        for text, value in char_sets:
            ttk.Radiobutton(char_frame, text=text, variable=self.char_set, value=value, 
                         command=self.update_allowed_special_chars).pack(anchor=tk.W, pady=2)
        
        # Special character settings
        special_frame = ttk.LabelFrame(left_frame, text="Special Character Setting", padding="10 10 10 10")
        special_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(special_frame, text="Security bypass character:", 
               font=self.text_font).pack(anchor=tk.W, pady=5)
        ttk.Label(special_frame, 
               text="Double click on the clock to pause Matrix."
                    "\nWhen the Matrix effect is paused, double-clicking this character\nwill bring up the security questions.", 
               font=self.text_font).pack(anchor=tk.W, pady=5)
        ttk.Label(special_frame,
               text="Must be a single character from the selected character set.",
               font=self.text_font).pack(anchor=tk.W, pady=5)
        
        self.special_char = tk.StringVar(value="")
        self.special_char_entry = ttk.Entry(special_frame, textvariable=self.special_char, width=5)
        self.special_char_entry.pack(anchor=tk.W, pady=5)
        
        # Bind validation to special char entry
        self.special_char_entry.bind("<KeyRelease>", self.validate_special_char)
        
        # Visual settings with color preview
        visual_frame = ttk.LabelFrame(left_frame, text="Visual Settings", padding="10 10 10 10")
        visual_frame.pack(fill=tk.X, pady=10)
        
        # Color selection with preview
        color_frame = ttk.Frame(visual_frame)
        color_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(color_frame, text="Text color:", font=self.text_font).pack(side=tk.LEFT, padx=(0, 10))
        
        self.matrix_color = tk.StringVar(value="lime")
        colors = ["lime", "red", "green", "yellow", "cyan", "white"]
        
        color_combo = ttk.Combobox(color_frame, textvariable=self.matrix_color, values=colors, width=10, state="readonly")
        color_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # Color preview label
        self.color_preview = ttk.Label(color_frame, text="Password", width=8, background="black")
        self.color_preview.pack(side=tk.LEFT, padx=5)
        
        # Update color preview when color changes
        self.update_color_preview()
        color_combo.bind("<<ComboboxSelected>>", lambda e: self.update_color_preview())
        
        # Save button
        save_frame = ttk.Frame(visual_frame)
        save_frame.pack(fill=tk.X, pady=10)
        
        self.save_matrix_button = ttk.Button(
            save_frame, 
            text="Save Matrix Settings", 
            style='Action.TButton',
            command=self.stage_matrix_settings
        )
        self.save_matrix_button.pack(pady=10)
        
        # Status area in right frame
        self.matrix_status_text = scrolledtext.ScrolledText(right_frame, font=('Consolas', 10), height=15)
        self.matrix_status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.matrix_status_text.insert(tk.END, "Configure Matrix effect appearance and click 'Save Matrix Settings'.\n")
        self.matrix_status_text.config(state=tk.DISABLED)
        
        # Initialize allowed special characters
        self.update_allowed_special_chars()

    def update_allowed_special_chars(self):
        """Update which special characters are allowed based on selected character set"""
        self.special_char.set("")
        
    def validate_special_char(self, event):
        """Validate the special character input in real time"""
        current = self.special_char.get()
        if len(current) > 1:
            # Truncate to one character
            self.special_char.set(current[-1:])
            
        # Check if character is in the allowed set
        char_set = self.char_set.get()
        current = self.special_char.get()
        
        if current:
            valid = False
            if char_set == "alphanumeric" and (current.isalnum()):
                valid = True
            elif char_set == "latin" and (current.isalpha()):
                valid = True
            elif char_set == "numbers" and (current.isdigit()):
                valid = True
                
            if not valid:
                self.special_char.set("")  # Don't set default if invalid
                self.update_status(self.matrix_status_text, 
                                f"❌ Character must be from the selected character set.")

    def update_color_preview(self):
        """Update the color preview label with the selected color"""
        color = self.matrix_color.get()
        self.color_preview.config(foreground=color)
        
    def stage_matrix_settings(self):
        """Store the matrix settings in memory for later saving"""
        # Get all matrix settings (with fixed rain speed and density)
        matrix_settings = {
            "char_set": self.char_set.get(),
            "custom_chars": "",
            "special_char": self.special_char.get(),
            "matrix_color": self.matrix_color.get(),
            "matrix_speed": 10,  # Fixed value
            "matrix_density": 5   # Fixed value
        }
        
        # Validate special character
        if not matrix_settings["special_char"]:
            messagebox.showerror("Missing Input", "Please select a special character for security bypass.")
            return
        
        # Check if special char is a single character from the allowed set
        special_char = matrix_settings["special_char"]
        char_set = matrix_settings["char_set"]
        valid = False
        
        if char_set == "alphanumeric" and (special_char.isalnum()):
            valid = True
        elif char_set == "latin" and (special_char.isalpha()):
            valid = True
        elif char_set == "numbers" and (special_char.isdigit()):
            valid = True
            
        if not valid:
            messagebox.showerror("Invalid Character", 
                             "Please enter a valid character from the selected character set.")
            return
        
        # Store in wizard state
        self.wizard_state["matrix_settings"] = matrix_settings
        
        # Update UI
        self.update_status(self.matrix_status_text, "Matrix settings saved successfully!", clear=True)
        
        # Mark step complete
        self.completed_steps["matrix"] = True
        self.update_progress_indicators()
        self.update_navigation_buttons()
        self.update_tab_states()
        
        # Go to next step if not in edit mode
        if not self.edit_mode:
            self.go_to_next_step()

    def setup_summary_tab(self):
        """Setup the summary tab that shows all configurations before final save"""
        # Create a main content frame for the tab
        main_frame = ttk.Frame(self.summary_tab)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create left frame for controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Create right frame for confirmation message and checkbox
        right_frame = ttk.LabelFrame(main_frame, text="Confirmation")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Top frame for instructions in left frame
        top_frame = ttk.Frame(left_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Instructions
        ttk.Label(top_frame, text="Configuration Summary", font=self.heading_font).pack(anchor=tk.W)
        ttk.Label(top_frame, text="Review your settings before saving the complete training.", 
                font=self.text_font).pack(anchor=tk.W, pady=(5, 0))
        
        # Create scrollable frame for summary content
        summary_canvas = tk.Canvas(left_frame)
        summary_canvas.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(summary_canvas, orient=tk.VERTICAL, command=summary_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        summary_canvas.configure(yscrollcommand=scrollbar.set)
        
        summary_frame = ttk.Frame(summary_canvas)
        summary_canvas.create_window((0, 0), window=summary_frame, anchor="nw")
        summary_frame.bind("<Configure>", lambda e: summary_canvas.configure(scrollregion=summary_canvas.bbox("all")))
        
        # Password summary section
        self.password_section = ttk.LabelFrame(summary_frame, text="Password", padding="10 10 10 10")
        self.password_section.pack(fill=tk.X, pady=5, padx=5)
        
        self.password_summary = ttk.Label(self.password_section, text="Not set", font=self.text_font)
        self.password_summary.pack(anchor=tk.W)
        
        # Training summary section
        self.training_section = ttk.LabelFrame(summary_frame, text="Training", padding="10 10 10 10")
        self.training_section.pack(fill=tk.X, pady=5, padx=5)
        
        self.training_summary = ttk.Label(self.training_section, text="Not completed", font=self.text_font)
        self.training_summary.pack(anchor=tk.W)
        
        # Threshold summary section
        self.threshold_section = ttk.LabelFrame(summary_frame, text="Similarity Threshold", padding="10 10 10 10")
        self.threshold_section.pack(fill=tk.X, pady=5, padx=5)
        
        self.threshold_summary = ttk.Label(self.threshold_section, text="Not set", font=self.text_font)
        self.threshold_summary.pack(anchor=tk.W)
        
        # Security questions summary section
        self.security_section = ttk.LabelFrame(summary_frame, text="Security Questions", padding="10 10 10 10")
        self.security_section.pack(fill=tk.X, pady=5, padx=5)
        
        self.security_summary = ttk.Label(self.security_section, text="Not configured", font=self.text_font)
        self.security_summary.pack(anchor=tk.W)
        
        # Matrix settings summary section
        self.matrix_section = ttk.LabelFrame(summary_frame, text="Matrix Effect", padding="10 10 10 10")
        self.matrix_section.pack(fill=tk.X, pady=5, padx=5)
        
        self.matrix_summary = ttk.Label(self.matrix_section, text="Not configured", font=self.text_font)
        self.matrix_summary.pack(anchor=tk.W)
        
        # Create content in right frame - message box with checkbox
        message_frame = ttk.Frame(right_frame)
        message_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add confirmation message
        confirm_message = ttk.Label(message_frame, 
                                  text="Please review your configuration carefully before saving."
                                        "\nOnce saved, your biometric profile will be used for authentication.",
                                  font=self.text_font,
                                  wraplength=500)
        confirm_message.pack(fill=tk.X, pady=10)
        
        # Add checkbox for confirmation
        self.confirm_var = tk.BooleanVar(value=False)
        confirm_checkbox = ttk.Checkbutton(message_frame, 
                                        text="I have reviewed my settings", 
                                        variable=self.confirm_var,
                                        command=self.update_confirm_status)
        confirm_checkbox.pack(fill=tk.X, pady=10, anchor=tk.W)

    def update_confirm_status(self):
        """Update save button state based on confirmation checkbox"""
        all_completed = all([self.completed_steps[s] for s in self.steps[:-1]])  # All except summary
        is_confirmed = self.confirm_var.get()
        
        if all_completed and is_confirmed:
            self.save_btn.config(state=tk.NORMAL)
            self.save_instruction.config(text="Click to save your configuration", foreground="green")
        else:
            self.save_btn.config(state=tk.DISABLED if not is_confirmed else tk.DISABLED)
            self.save_instruction.config(text="Check the confirmation box to enable save", 
                                     foreground="gray")

    def update_summary(self):
        """Update the summary page with current settings"""
        # Update password summary
        if self.wizard_state["password"]:
            masked_pwd = "•" * len(self.wizard_state["password"])
            self.password_summary.config(text=f"Password set ({masked_pwd})", foreground="green")
        else:
            self.password_summary.config(text="Not set", foreground="red")
        
        # Update training summary
        if "training_data" in self.wizard_state and self.wizard_state["training_data"] is not None:
            sample_count = len(self.wizard_state["training_data"])
            self.training_summary.config(
                text=f"Completed with {sample_count} samples", 
                foreground="green"
            )
        else:
            self.training_summary.config(text="Not completed", foreground="red")
        
        # Update threshold summary
        if self.completed_steps["threshold"]:
            threshold = self.wizard_state["threshold_value"]
            security_level = self.wizard_state.get("security_level", "high")
            self.threshold_summary.config(
                text=f"Set to {threshold}% ({security_level} security)", 
                foreground="green"
            )
        else:
            self.threshold_summary.config(text="Not set", foreground="red")
        
        # Update security questions summary
        if self.completed_steps["security"]:
            questions = self.wizard_state["security_questions"]
            num_questions = len(questions)
            self.security_summary.config(
                text=f"Configured ({num_questions} questions)", 
                foreground="green"
            )
        else:
            self.security_summary.config(text="Not configured", foreground="red")
        
        # Update matrix settings summary
        if self.completed_steps["matrix"]:
            matrix = self.wizard_state["matrix_settings"]
            self.matrix_summary.config(
                text=f"Configured ({matrix['char_set']} characters, {matrix['matrix_color']} color)", 
                foreground="green"
            )
        else:
            self.matrix_summary.config(text="Not configured", foreground="red")
            
        # Reset confirmation checkbox when updating summary
        self.confirm_var.set(False)
        self.update_confirm_status()

    def create_bat_shortcut(self):
        """Create a shortcut to 0.bat, set it to run minimized, and add to registry for startup"""
        try:
            if getattr(sys, 'frozen', False):
                script_dir = os.path.dirname(sys.executable)  # PyInstaller EXE
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))  # Normal script execution
            bat_path = os.path.join(script_dir, "0.bat")
            shortcut_path = os.path.join(script_dir, "0.bat.lnk")  # Save shortcut in the same directory

            if not os.path.exists(bat_path):
                messagebox.showerror("Error", "0.bat file not found in the application directory.")
                return False

            # Create a shortcut (.lnk) for 0.bat
            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(shortcut_path)
            shortcut.TargetPath = bat_path
            shortcut.WorkingDirectory = script_dir
            shortcut.IconLocation = bat_path
            shortcut.WindowStyle = 7  # 7 = Minimized
            shortcut.Save()

            # Add the shortcut to the Windows Registry (HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\Run)
            reg_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            reg_name = "EntyptSecurity"

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, shortcut_path)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create startup entry: {str(e)}")
            return False

    def delete_bat_shortcut(self):
        """Remove the shortcut of 0.bat from the registry startup entry"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            shortcut_path = os.path.join(script_dir, "0.bat.lnk")  # Path of the shortcut

            # Remove the registry entry
            reg_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            reg_name = "EntyptSecurity"

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, reg_name)

            # Delete the shortcut file
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
            return True
        except FileNotFoundError:
            return False  # Registry entry does not exist
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove startup entry: {str(e)}")
            return False


    def save_final_model(self):
        """Final save of the model at completion of the wizard"""
        if not self.edit_mode:
            if not all([self.completed_steps[s] for s in self.steps[:-1]]):
                messagebox.showwarning("Incomplete Setup", "Please complete all steps before saving.")
                return

        try:
            # Verify password used for training matches current password
            if hasattr(self, 'processed_training') and self.processed_training:
                # If we have processed training data but the password has changed
                training_password_length = len(self.processed_training["raw_training_data"][0]) + 1
                current_password_length = len(self.wizard_state["password"])
            
                if training_password_length != current_password_length:
                    messagebox.showerror(
                        "Password Mismatch", 
                        "The password used for training doesn't match your current password. " +
                        "Please retrain with your current password."
                    )
                    return

            # IMPORTANT: Check for unsaved but processed training data
            if hasattr(self, 'processed_training') and self.processed_training:
                # User has completed training but didn't click "Save Training"
                # Automatically save the processed training data without asking
                self.wizard_state["training_data"] = self.processed_training["train_data"]
                self.wizard_state["scaler"] = self.processed_training["scaler"]
                self.wizard_state["avg_self_similarity"] = self.processed_training["avg_self_similarity"]
                self.wizard_state["min_self_similarity"] = self.processed_training["min_self_similarity"]
                self.wizard_state["raw_training_data"] = self.processed_training["raw_training_data"]
                self.wizard_state["interval_lower_thresholds"] = self.processed_training["interval_lower_thresholds"]
                self.wizard_state["interval_upper_thresholds"] = self.processed_training["interval_upper_thresholds"]
                self.wizard_state["avg_typing_speed"] = self.processed_training.get("avg_typing_speed", 0)
                self.wizard_state["std_dev_typing_speed"] = self.processed_training.get("std_dev_typing_speed", 0)

            elif self.edit_mode and self.model:
                training_data = self.wizard_state.get("training_data")
                if training_data is None or (isinstance(training_data, (list, np.ndarray)) and len(training_data) == 0):

                    # No new training data, but we're in edit mode - use original data
                    self.wizard_state["training_data"] = self.model.get("train_data", [])
                    self.wizard_state["scaler"] = self.model.get("scaler", None)
                    self.wizard_state["avg_self_similarity"] = self.model.get("avg_self_similarity", 0)
                    self.wizard_state["min_self_similarity"] = self.model.get("min_self_similarity", 0)
                    self.wizard_state["raw_training_data"] = self.model.get("raw_training_data", [])
                    self.wizard_state["interval_lower_thresholds"] = self.model.get("interval_lower_thresholds", [])
                    self.wizard_state["interval_upper_thresholds"] = self.model.get("interval_upper_thresholds", [])
                    self.wizard_state["avg_typing_speed"] = self.model.get("avg_typing_speed", 0)
                    self.wizard_state["std_dev_typing_speed"] = self.model.get("std_dev_typing_speed", 0)

            # Create model if it doesn't exist
            if self.model is None:
                self.model = {}
            
            # Copy core data from wizard state
            self.model["password"] = self.wizard_state["password"]
            self.model["train_data"] = self.wizard_state["training_data"]
            self.model["scaler"] = self.wizard_state["scaler"]
            self.model["threshold"] = self.wizard_state["threshold_value"]
            self.model["security_questions"] = self.wizard_state["security_questions"]
            self.model["matrix_settings"] = self.wizard_state["matrix_settings"]
            
            # Add hybrid security parameters
            self.model["security_level"] = self.wizard_state.get("security_level", "high")
            self.model["weights"] = {
                "interval": 0.5,
                "pattern": 0.3,
                "speed": 0.2
            }
            
            # Copy other parameters from training model
            if "avg_self_similarity" in self.wizard_state:
                self.model["avg_self_similarity"] = self.wizard_state["avg_self_similarity"]
            if "min_self_similarity" in self.wizard_state:
                self.model["min_self_similarity"] = self.wizard_state["min_self_similarity"]
            if "raw_training_data" in self.wizard_state:
                self.model["raw_training_data"] = self.wizard_state["raw_training_data"]
            if "interval_lower_thresholds" in self.wizard_state:
                self.model["interval_lower_thresholds"] = self.wizard_state["interval_lower_thresholds"]
            if "interval_upper_thresholds" in self.wizard_state:
                self.model["interval_upper_thresholds"] = self.wizard_state["interval_upper_thresholds"]
            if "avg_typing_speed" in self.wizard_state:
                self.model["avg_typing_speed"] = self.wizard_state["avg_typing_speed"]
            if "std_dev_typing_speed" in self.wizard_state:
                self.model["std_dev_typing_speed"] = self.wizard_state["std_dev_typing_speed"]
            
            # Save the final model
            with open("typing_model.pkl", "wb") as f:
                pickle.dump(self.model, f)
            
            # Create startup shortcut
            self.create_bat_shortcut()
            
            # Show success message
            messagebox.showinfo("Setup Complete", 
                             "Configuration saved successfully!\n\n" + 
                             "Please RESTART YOUR COMPUTER for the security to take effect.")

            # Transition to "model exists" state
            self.has_existing_model = True
            self.add_model_buttons()
            self.update_tab_states()
            self.show_lock_overlay()

            # Reset edit mode flag
            self.edit_mode = False
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
    
    def complete_model_save(self, loading_frame):
        """Complete the model saving process after loading animation"""
        # Create the final model dictionary
        model = {
            "password": self.wizard_state["password"],
            "train_data": self.wizard_state["training_data"],
            "scaler": self.wizard_state["scaler"],
            "avg_self_similarity": self.wizard_state["avg_self_similarity"],
            "min_self_similarity": self.wizard_state["min_self_similarity"],
            "threshold": self.wizard_state["threshold_value"],
            "security_questions": self.wizard_state["security_questions"],
            "matrix_settings": self.wizard_state["matrix_settings"]
        }
        
        # Save to disk
        with open("typing_model.pkl", "wb") as model_file:
            pickle.dump(model, model_file)
        
        # Store in self.model so we can access it later
        self.model = model
        
        # Create shortcut to 0.bat in the Startup folder
        shortcut_created = self.create_bat_shortcut()
        
        # Remove loading frame
        loading_frame.destroy()
        
        # Mark final step as complete
        self.completed_steps["summary"] = True
        self.update_progress_indicators()
        
        # Reset edit mode flag
        self.edit_mode = False
        
        # Show confirmation message about model and shortcut
        if shortcut_created:
            messagebox.showinfo("Setup Complete", 
                              "Your biometric authentication model has been successfully saved.\n"
                              "RESTART your system to implement this SECURITY FEATURE.")
        else:
            messagebox.showinfo("Setup Complete", 
                              "Your biometric authentication model has been successfully saved.\n"
                              "Note: Could not create shortcut. Please check permissions.")
        
        # Instead of closing, transition to "model exists" state
        self.has_existing_model = True
        self.add_model_buttons()
        self.update_tab_states()
        # Show the lock overlay
        self.show_lock_overlay()

    def update_status(self, text_widget, message, clear=False, append=False):
        text_widget.config(state=tk.NORMAL)
        if clear:
            text_widget.delete(1.0, tk.END)
        if append:
            # Don't add a newline at the start if we're appending
            text_widget.insert(tk.END, message)
        else:
            text_widget.insert(tk.END, message + "\n")
        text_widget.see(tk.END)
        text_widget.config(state=tk.DISABLED)

    def add_model_buttons(self):
        """Add delete and edit buttons for existing model"""
        # Check if button frame already exists
        if hasattr(self, 'model_button_frame'):
            # Clear existing buttons first
            for widget in self.model_button_frame.winfo_children():
                widget.destroy()
            self.model_button_frame.destroy()
        
        # Create model button frame centered in the container
        self.model_button_frame = ttk.Frame(self.model_buttons_container)
        self.model_button_frame.pack(side=tk.TOP, pady=5, anchor=tk.CENTER)
        
        # Add edit button
        self.edit_button = ttk.Button(self.model_button_frame, text="Edit Model", 
                                    command=self.verify_edit_model)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        
        # Add delete button with red color
        self.delete_button = ttk.Button(self.model_button_frame, text="Delete Model", 
                                      command=self.verify_delete_model,
                                      style='Delete.TButton')
        self.delete_button.pack(side=tk.LEFT, padx=5)

    def verify_edit_model(self):
        """Verify user before allowing model editing"""
        if self.model is None:
            messagebox.showerror("Error", "Model not loaded properly. Please restart the application.")
            return
            
        # Create verification window
        verify_window = tk.Toplevel(self.root)
        verify_window.title("Verification Required")
        verify_window.geometry("400x300")
        verify_window.transient(self.root)
        verify_window.grab_set()
        
        # Center the window
        verify_window.update_idletasks()
        width = verify_window.winfo_width()
        height = verify_window.winfo_height()
        x = (verify_window.winfo_screenwidth() // 2) - (width // 2)
        y = (verify_window.winfo_screenheight() // 2) - (height // 2)
        verify_window.geometry(f'+{x}+{y}')
        
        # Add padding
        main_frame = ttk.Frame(verify_window, padding="20 20 20 20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        ttk.Label(main_frame, text="Verification Required", 
                 font=self.heading_font).pack(pady=(0, 10))
        
        ttk.Label(main_frame, text="To edit your model, please enter your password:", 
                 font=self.text_font).pack(pady=(0, 15))
        
        # Password entry
        entry_frame = ttk.Frame(main_frame)
        entry_frame.pack(fill=tk.X, pady=10)
        
        password_var = tk.StringVar()
        password_entry = ttk.Entry(entry_frame, textvariable=password_var, show="•", width=25)
        password_entry.pack(pady=5)
        password_entry.focus()
        
        # Status message
        status_var = tk.StringVar()
        status_label = ttk.Label(main_frame, textvariable=status_var, font=self.text_font)
        status_label.pack(pady=5)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        
        # Function to verify password (reference to model is now fixed)
        def verify_password():
            entered_password = password_var.get()
            actual_password = self.model["password"]
            
            if entered_password == actual_password:
                verify_window.destroy()
                self.edit_model()
            else:
                status_var.set("Incorrect password. Please try again.")
                password_entry.delete(0, tk.END)
                password_entry.focus()
        
        # Verify button
        verify_button = ttk.Button(button_frame, text="Verify", command=verify_password)
        verify_button.pack(side=tk.RIGHT, padx=5)
        
        # Cancel button
        cancel_button = ttk.Button(button_frame, text="Cancel", 
                                  command=verify_window.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key
        password_entry.bind("<Return>", lambda event: verify_password())
        
        # Security reminder
        ttk.Label(main_frame, text="This verification helps protect your authentication model.",
                 font=('Arial', 9), foreground='gray').pack(side=tk.BOTTOM, pady=(15, 0))

    def verify_delete_model(self):
        """Verify user before allowing model deletion with typing pattern verification"""
        if self.model is None:
            messagebox.showerror("Error", "Model not loaded properly. Please restart the application.")
            return
            
        # Create verification window
        verify_window = tk.Toplevel(self.root)
        verify_window.title("Verification Required")
        verify_window.geometry("450x400")
        verify_window.transient(self.root)
        verify_window.grab_set()
        
        # Center the window
        verify_window.update_idletasks()
        width = verify_window.winfo_width()
        height = verify_window.winfo_height()
        x = (verify_window.winfo_screenwidth() // 2) - (width // 2)
        y = (verify_window.winfo_screenheight() // 2) - (height // 2)
        verify_window.geometry(f'+{x}+{y}')
        
        # Add padding
        main_frame = ttk.Frame(verify_window, padding="20 20 20 20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        ttk.Label(main_frame, text="Verification Required", 
                 font=self.heading_font).pack(pady=(0, 10))
        
        ttk.Label(main_frame, text="To delete your model, please type your password:", 
                 font=self.text_font).pack(pady=(0, 15))
        
        ttk.Label(main_frame, text="Both the password and your typing pattern will be verified.", 
                 font=self.text_font).pack(pady=(0, 5))
        
        # Password entry
        entry_frame = ttk.Frame(main_frame)
        entry_frame.pack(fill=tk.X, pady=10)
        
        password_var = tk.StringVar()
        password_entry = ttk.Entry(entry_frame, textvariable=password_var, show="•", width=25)
        password_entry.pack(pady=5)
        password_entry.focus()
        
        # Status message
        status_var = tk.StringVar()
        status_label = ttk.Label(main_frame, textvariable=status_var, font=self.text_font)
        status_label.pack(pady=5)
        
        # Warning label
        warning_label = ttk.Label(main_frame, 
                                 text="Warning: This action cannot be undone!",
                                 font=("Arial", 10, "bold"),
                                 foreground="red")
        warning_label.pack(pady=10)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        
        # Variables to track typing pattern verification
        key_times = []
        last_key_time = [None]  # Use list to allow modification in nested functions
        password = self.model["password"]
        num_features = len(password) - 1
        
        # Function to verify password and typing pattern
        def verify_authentication():
            entered_password = password_var.get()
            actual_password = self.model["password"]
    
            # First verify password matches
            if entered_password != actual_password:
                status_var.set("STATUS: Password:✘ Interval:✘ Pattern:✘")
                password_entry.delete(0, tk.END)
                key_times.clear()
                last_key_time[0] = None
                password_entry.focus()
                return
        
            # Then verify typing pattern
            if len(key_times) != num_features:
                status_var.set("STATUS: Password:✘ Interval:✘ Pattern:✘")
                password_entry.delete(0, tk.END)
                key_times.clear()
                last_key_time[0] = None
                password_entry.focus()
                return
        
            # Use the verification logic
            # 1. Calculate pattern score
            test_features = np.array([key_times])
            test_features_scaled = self.model["scaler"].transform(test_features)
            train_data = self.model["train_data"]
            avg_self_similarity = self.model["avg_self_similarity"]
            pattern_score = self.calculate_pattern_score(test_features_scaled[0], train_data, avg_self_similarity)
    
            # 2. Calculate interval score
            lower_bounds = self.model["interval_lower_thresholds"]
            upper_bounds = self.model["interval_upper_thresholds"]

            # Add padding to the bounds for more forgiveness (15% additional tolerance)
            lower_bounds = [bound * 0.00 for bound in lower_bounds]
            upper_bounds = [bound * 2.00 for bound in upper_bounds]
            interval_score = self.calculate_interval_score(key_times, lower_bounds, upper_bounds)
    
            # 3. Calculate speed score
            avg_typing_speed = self.model.get("avg_typing_speed", 0)
            std_dev_typing_speed = self.model.get("std_dev_typing_speed", 0.01)
            speed_score = self.calculate_speed_score(
                key_times, 
                avg_typing_speed, 
                std_dev_typing_speed
            )
    
            # Get security level settings
            security_settings = {
                "low":       (0.25, 0.30, 0.50),
                "medium":    (0.30, 0.35, 0.60),
                "high":      (0.40, 0.40, 0.65),
                "very_high": (0.50, 0.50, 0.70)
            }
    
            # Get security level from model or use default
            security_level = self.model.get("security_level", "high")
            interval_minimum, secondary_minimum, overall_threshold = security_settings.get(
                security_level, security_settings["high"])
    
            # IMPORTANT: Use the user's configured threshold instead
            user_threshold = self.model["threshold"] / 100.0  # Convert percentage to decimal
            overall_threshold = user_threshold

            # Calculate weighted score with 40/40/20 weighting
            weights = {"interval": 0.40, "pattern": 0.40, "speed": 0.20}
            weighted_score = (
                weights["interval"] * interval_score +
                weights["pattern"] * pattern_score +
                weights["speed"] * speed_score
            )

            # Bonus for excellent interval matching
            if interval_score > 0.90:
                interval_bonus = 0.05 + ((interval_score - 0.70) * 0.80)
                weighted_score += interval_bonus

            # Bonus for excellence in any factor
            best_factor = max(pattern_score, speed_score)
            if best_factor > 0.8:
                factor_bonus = (best_factor - 0.8) * 0.25
                weighted_score += factor_bonus

            # Consistency bonus
            if abs(pattern_score - interval_score) < 0.2:
                weighted_score += 0.05
            
            # STEP 5: Evaluate authentication criteria
            interval_passed = interval_score >= interval_minimum
            secondary_passed = pattern_score >= secondary_minimum or speed_score >= secondary_minimum
            threshold_passed = weighted_score >= overall_threshold
        
            # Create status indicators
            password_status = "✔"
            interval_status = "✔" if interval_passed else "✘"
            secondary_status = "✔" if secondary_passed else "✘"
            score_display = f"score: {int(weighted_score*100)} {'≥' if threshold_passed else '<'} {int(overall_threshold*100)}"
        
            if threshold_passed and interval_passed and secondary_passed:
                # Authentication successful - delete model
                verify_window.destroy()
                self.delete_model()
                return
        
            # Authentication failed - determine reason and create appropriate message
            if not interval_passed:
                status_var.set(f"STATUS: Password:{password_status} Interval:✘ Pattern:{secondary_status} ({score_display})")
            elif not secondary_passed:
                status_var.set(f"STATUS: Password:{password_status} Interval:{interval_status} Pattern:✘ ({score_display})")
            else:
                status_var.set(f"STATUS: Password:{password_status} Interval:{interval_status} Pattern:{secondary_status} ({score_display})")
        
            # Reset for another attempt
            password_entry.delete(0, tk.END)
            key_times.clear()
            last_key_time[0] = None
            password_entry.focus()
            
        
        # Capture key press times
        def on_key_press(event):
            if event.char and event.char.isalnum():
                current_time = time.time()
                if last_key_time[0] is not None:
                    key_times.append(current_time - last_key_time[0])
                last_key_time[0] = current_time
        
        # Handle the Enter key pressed
        def on_return_press(event):
            verify_authentication()
            
        # Bind key events
        password_entry.bind("<Key>", on_key_press)
        password_entry.bind("<Return>", on_return_press)
        
        # Verify button
        verify_button = ttk.Button(button_frame, text="Verify & Delete", 
                                  style='Delete.TButton',
                                  command=verify_authentication)
        verify_button.pack(side=tk.RIGHT, padx=5)
        
        # Cancel button
        cancel_button = ttk.Button(button_frame, text="Cancel", 
                                  command=verify_window.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)
        
        # Security reminder
        ttk.Label(main_frame, text="Your model will only be deleted if both your password\nand typing pattern are verified.",
                 font=('Arial', 9), foreground='gray').pack(side=tk.BOTTOM, pady=(15, 0))

    def load_model(self):
        """Load an existing model file"""
        try:
            with open("typing_model.pkl", "rb") as model_file:
                self.model = pickle.load(model_file)
                
            # Add buttons to edit and delete model
            self.add_model_buttons()
            
            # Disable all tabs including password setup
            self.update_tab_states()
        except Exception as e:
            print(f"Error loading model: {e}")
            self.model = None
            self.has_existing_model = False

    def edit_model(self):
        """Edit the existing model"""
        if hasattr(self, 'model') and self.model:
            # Hide the lock overlay when entering edit mode
            self.hide_lock_overlay()
            
            # Transfer model data to wizard state
            self.wizard_state["password"] = self.model["password"]
            self.wizard_state["training_data"] = self.model["train_data"]
            self.wizard_state["scaler"] = self.model["scaler"]
            self.wizard_state["avg_self_similarity"] = self.model["avg_self_similarity"]
            self.wizard_state["min_self_similarity"] = self.model["min_self_similarity"]
            self.wizard_state["threshold_value"] = self.model["threshold"]
            self.wizard_state["security_questions"] = self.model["security_questions"]
            self.wizard_state["matrix_settings"] = self.model["matrix_settings"]
            self.wizard_state["security_level"] = self.model.get("security_level", "high")
            
            # Set password variable
            self.password.set(self.model["password"])
            self.num_features = len(self.model["password"]) - 1
            
            # Mark steps as completed
            for step in self.steps[:-1]:  # All except summary
                self.completed_steps[step] = True
            
            # Set edit mode flag
            self.edit_mode = True
            
            # Remove model exists flag to enable editing
            self.has_existing_model = False
            
            # Update UI
            self.update_progress_indicators()
            self.update_navigation_buttons()
            self.update_tab_states()  # This will enable training, threshold, and matrix tabs
            
            # Remove model buttons frame if it exists
            if hasattr(self, 'model_button_frame'):
                self.model_button_frame.destroy()
                delattr(self, 'model_button_frame')
            
            # Set save button text for edit mode
            self.save_btn.config(text="Save Changes")
            
            # Go to training tab (first editable tab)
            self.current_step = 1
            self.notebook.select(1)
            
            # Update fields in tabs with loaded model data
            self.update_tabs_with_model_data()
            
            # Show a message about edit mode
            messagebox.showinfo("Edit Mode", 
                             "You are now in edit mode. You can modify the training, threshold, and matrix settings.")

    def update_tabs_with_model_data(self):
        """Update all tab fields with loaded model data"""
        # Update threshold tab - Get the current threshold from the model itself
        threshold = self.model["threshold"]  # Get from model instead of wizard_state
        self.threshold_var.set(threshold)
        self.threshold_label.config(text=f"{threshold}%")  # Update percentage display
    
        security_level = self.wizard_state.get("security_level", "high")
        self.security_level_var.set(security_level)

        # Define color and display_text based on security level
        display_text = "Medium Security"  # Default value
        color = "#ffc107"  # Default yellow color
    
        # Determine correct text and color based on security level
        if security_level == "low":
            display_text = "Low Security"
            color = "#28a745"  # Green
        elif security_level == "medium":
            display_text = "Medium Security"
            color = "#ffc107"  # Yellow 
        elif security_level == "high":
            display_text = "High Security"
            color = "#007bff"  # Blue
        elif security_level == "very_high":
            display_text = "Very High Security"
            color = "#dc3545"  # Red

        # Update security level display if exists
        if hasattr(self, 'security_level_display'):
            self.security_level_display.config(text=display_text, foreground=color)
            # Also update the level labels if they exist
            if hasattr(self, 'level_labels') and security_level in self.level_labels:
                # Reset all labels first
                for label in self.level_labels.values():
                    label.config(font=('Arial', 10), foreground="black")
                
                # Highlight the active one
                self.level_labels[security_level].config(font=('Arial', 10, 'bold'), foreground=color)
        
        self.update_status(self.threshold_status_text, 
                        f"Threshold loaded from existing model: {threshold}% ({security_level} security)", 
                        clear=True)
        
        # Load existing training data instead of resetting
        if "raw_training_data" in self.model:
            # Handle numpy array conversion
            if hasattr(self.model["raw_training_data"], "tolist"):
                self.training_data = self.model["raw_training_data"].tolist()
            else:
                self.training_data = self.model["raw_training_data"]

            self.current_attempt = len(self.training_data)
        
            # Update UI to show training is already complete
            self.progress_var.set(5)  # Set to max
            self.attempt_label.config(text="5/5 attempts")
            self.train_button.config(text="Start Training", state=tk.NORMAL)
            self.train_entry.config(state=tk.DISABLED)
            self.save_training_button.config(state=tk.NORMAL)  # Enable save button
            self.completed_steps["training"] = True  # Mark as complete
        
            self.update_status(self.train_status_text, 
                          f"Previous training data loaded ({len(self.training_data)} samples).", 
                          clear=True)
            self.update_status(self.train_status_text, 
                          "Click 'Start Training' only if you want to replace the existing training data.")
        else:
            # Only reset if no data found
            self.training_data = []
            self.current_attempt = 0
            self.progress_var.set(0)
            self.attempt_label.config(text="0/5 attempts")
            self.train_button.config(text="Start Training", state=tk.NORMAL)
            self.save_training_button.config(state=tk.DISABLED)
            self.completed_steps["training"] = False
        
            self.update_status(self.train_status_text, 
                          "No previous training data found. Click 'Start Training'.", 
                          clear=True)
                      
        self.train_entry.config(state=tk.DISABLED)
        self.train_entry.delete(0, tk.END)
                      
        # Update matrix tab
        matrix_settings = self.wizard_state["matrix_settings"]
        self.char_set.set(matrix_settings["char_set"])
        self.special_char.set(matrix_settings["special_char"])
        self.matrix_color.set(matrix_settings["matrix_color"])
        self.update_color_preview()
        
        self.update_status(self.matrix_status_text, 
                      "Matrix settings loaded from existing model.", 
                      clear=True)

    def delete_model(self):
        """Delete the existing model file"""
        # Delete file if it exists
        if os.path.exists("typing_model.pkl"):
            os.remove("typing_model.pkl")
            
        self.delete_bat_shortcut()
            
        # Reset wizard state - completely new instance to ensure no data remains
        self.wizard_state = {
            "password": "",
            "training_data": [],
            "scaler": None,
            "threshold_value": THRESHOLD,
            "security_questions": {},
            "matrix_settings": {
                "char_set": "alphanumeric",
                "special_char": "",
                "matrix_color": "lime",
                "matrix_speed": 10,
                "matrix_density": 5
            },
            "security_level": "high"
        }
        
        # Clear model reference
        self.model = None
        
        # Reset completion status
        for step in self.steps:
            self.completed_steps[step] = False
        
        # Remove model exists flag
        self.has_existing_model = False
        
        # Reset all form fields
        self.reset_all_fields()
        
        # Update UI
        self.update_progress_indicators()
        self.update_navigation_buttons()
        self.update_tab_states()
        
        # Hide the lock overlay
        self.hide_lock_overlay()
        
        # Remove model buttons frame if it exists
        if hasattr(self, 'model_button_frame'):
            self.model_button_frame.destroy()
            delattr(self, 'model_button_frame')
        
        # Show message
        messagebox.showinfo("Model Deleted", "The existing model has been deleted. You can now create a new model.")
        
        # Start at first step
        self.current_step = 0
        self.notebook.select(0)

    def reset_all_fields(self):
        """Reset all form fields after model deletion"""
        # Reset password tab
        self.password.set("")
        self.update_status(self.password_status_text, "Enter a new password and click 'Set Password'.", clear=True)
        
        # Reset training tab
        self.training_data = []
        self.current_attempt = 0
        self.progress_var.set(0)
        self.attempt_label.config(text="0/5 attempts")
        self.train_button.config(text="Start Training", state=tk.NORMAL)
        self.train_entry.config(state=tk.DISABLED)
        self.train_entry.delete(0, tk.END)
        self.save_training_button.config(state=tk.DISABLED)
        self.update_status(self.train_status_text, "Ready to begin training...\nClick 'Start Training' when you're ready.", clear=True)
        
        # Reset threshold tab
        self.threshold_var.set(THRESHOLD)
        self.security_level_var.set("high")
        self.update_status(self.threshold_status_text, "Adjust the threshold slider and click 'Save Threshold Setting'.", clear=True)
        
        # Reset security questions tab
        # Reset dropdown selections to default
        self.question1_combo.delete(0, tk.END)
        self.question1_combo.insert(0, "Choose a security question...")
        self.question2_combo.delete(0, tk.END)
        self.question2_combo.insert(0, "Choose a security question...")
        self.question3_combo.delete(0, tk.END)
        self.question3_combo.insert(0, "Choose a security question...")
        
        # Clear answers
        self.answer1.set("")
        self.answer2.set("")
        self.answer3.set("")
        
        self.update_status(self.security_status_text, 
                       "Select security questions from the dropdown menus or enter your own custom questions. Then click 'Save Security Questions'.", 
                       clear=True)
        
        # Reset matrix tab
        self.char_set.set("alphanumeric")
        self.special_char.set("")
        self.matrix_color.set("lime")
        self.update_color_preview()
        self.update_status(self.matrix_status_text, 
                       "Configure Matrix effect appearance and click 'Save Matrix Settings'.", 
                       clear=True)
        
        # Reset save button text
        self.save_btn.config(text="Complete Setup & Save Model")


if __name__ == "__main__":
    root = tk.Tk()
    app = KeystrokeAuthApp(root)
    root.mainloop()