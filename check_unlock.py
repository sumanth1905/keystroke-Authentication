import win32gui
import win32process
import psutil
import time
import subprocess
import logging
from datetime import datetime, timedelta
import ctypes

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Using DEBUG level to help troubleshoot
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('LockDetector')

# Path to your lockscreen script
LOCKSCREEN_PATH = "Lockscreen.exe"

class LockDetector:
    def __init__(self):
        self.lock_detected = False
        self.lock_confirmation_counter = 0
        self.confirmations_required = 2  # Reduced to 2 for faster response
        self.check_interval = 0.25  # Check 4 times per second for better responsiveness
        
        # UAC detection
        self.uac_detected_time = None
        self.uac_cooldown = 3  # Seconds to ignore lock after UAC
        
        # Trigger control
        self.last_trigger_time = 0
        self.min_trigger_interval = 3  # Minimum seconds between triggers
        
        # State tracking
        self.last_foreground_window = None
        self.last_idle_time = 0
        self.last_window_count = 0
        
        logger.info(f"Enhanced Lock Detector started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Using lockscreen executable: {LOCKSCREEN_PATH}")

    def get_idle_time(self):
        """Get system idle time in milliseconds."""
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ('cbSize', ctypes.c_uint),
                ('dwTime', ctypes.c_uint),
            ]
        
        lastInputInfo = LASTINPUTINFO()
        lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo)):
            millis = ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime
            return millis
        return 0

    def get_window_count(self):
        """Count the number of visible windows."""
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                windows.append(hwnd)
            return True
            
        windows = []
        win32gui.EnumWindows(callback, windows)
        return len(windows)

    def is_uac_active(self):
        """Check if UAC (User Account Control) is active."""
        # Check for consent.exe which is the UAC process
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'].lower() == 'consent.exe':
                    logger.debug("UAC process detected (consent.exe)")
                    self.uac_detected_time = datetime.now()
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    def detect_logon_ui(self):
        """Check if LogonUI.exe is running (appears during lock screens)."""
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'].lower() == 'logonui.exe':
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    def is_lock_condition(self):
        """
        Enhanced detection for Windows+L lock events
        """
        # Get current foreground window
        current_foreground = win32gui.GetForegroundWindow()
        foreground_zero = (current_foreground == 0)
        
        # Get current idle time
        current_idle_time = self.get_idle_time()
        
        # Check for sudden changes in idle time (happens with Win+L)
        idle_time_reset = False
        if self.last_idle_time > 1000 and current_idle_time < 500:
            idle_time_reset = True
            logger.debug(f"Idle time reset: {self.last_idle_time} -> {current_idle_time}")
            
        # Update last idle time
        self.last_idle_time = current_idle_time
        
        # Get window count for additional validation
        current_window_count = self.get_window_count()
        window_count_changed = False
        
        if self.last_window_count > 0 and current_window_count < self.last_window_count * 0.7:
            window_count_changed = True
            logger.debug(f"Window count changed: {self.last_window_count} -> {current_window_count}")
            
        self.last_window_count = current_window_count
        
        # Track sudden foreground window change
        foreground_changed = (self.last_foreground_window is not None and 
                            self.last_foreground_window != 0 and
                            current_foreground == 0)
                            
        # Update last foreground window
        self.last_foreground_window = current_foreground
        
        # LogonUI.exe check for additional confirmation
        logon_ui_running = self.detect_logon_ui()
        
        # Check if UAC is active
        if self.is_uac_active():
            return False
            
        # Check if we're within the UAC cooldown period
        if self.uac_detected_time:
            elapsed = (datetime.now() - self.uac_detected_time).total_seconds()
            if elapsed < self.uac_cooldown:
                logger.debug(f"Within UAC cooldown period ({elapsed:.1f}s < {self.uac_cooldown}s)")
                return False
        
        # Calculate a lock score based on indicators
        lock_score = 0
        
        if foreground_zero:
            lock_score += 2  # Strong indicator
            logger.debug("Foreground window is 0")
            
        if foreground_changed:
            lock_score += 1  # Moderate indicator
            logger.debug("Foreground window suddenly changed to 0")
            
        if idle_time_reset:
            lock_score += 1  # Moderate indicator
            
        if logon_ui_running:
            lock_score += 1  # Supplemental indicator
            logger.debug("LogonUI.exe is running")
            
        if window_count_changed:
            lock_score += 1  # Supplemental indicator
        
        # Determine if locked based on score
        is_locked = lock_score >= 2
        
        if is_locked:
            logger.debug(f"Lock condition detected (score: {lock_score})")
            
        return is_locked

    def trigger_lockscreen(self):
        """Trigger the lockscreen executable with safety checks."""
        # Check the time since last trigger
        current_time = time.time()
        if current_time - self.last_trigger_time < self.min_trigger_interval:
            logger.debug("Skipping trigger - too soon since last trigger")
            return
            
        logger.info("🔒 LOCK CONFIRMED - Triggering lockscreen application")
        try:
            subprocess.run([LOCKSCREEN_PATH], shell=True)
            self.last_trigger_time = current_time
        except Exception as e:
            logger.error(f"Error triggering lockscreen: {e}")

    def run(self):
        """Main detector loop."""
        try:
            # Initialize with current window state
            self.last_foreground_window = win32gui.GetForegroundWindow()
            self.last_idle_time = self.get_idle_time()
            self.last_window_count = self.get_window_count()
            
            logger.info(f"Initial state: foreground={self.last_foreground_window}, idle={self.last_idle_time}ms, windows={self.last_window_count}")
            
            while True:
                try:
                    # Check lock condition
                    current_lock = self.is_lock_condition()
                    
                    if current_lock:
                        # Increment confirmation counter
                        self.lock_confirmation_counter += 1
                        
                        if self.lock_confirmation_counter == 1:
                            logger.debug("Initial lock detection - starting confirmation")
                            
                        # Only trigger after enough consecutive lock detections
                        if self.lock_confirmation_counter >= self.confirmations_required and not self.lock_detected:
                            self.lock_detected = True
                            self.trigger_lockscreen()
                    else:
                        # Reset detection state if not locked
                        if self.lock_confirmation_counter > 0:
                            logger.debug(f"Lock state ended after {self.lock_confirmation_counter} confirmations")
                            
                        self.lock_confirmation_counter = 0
                        self.lock_detected = False
                    
                    # Sleep for the check interval
                    time.sleep(self.check_interval)
                    
                except Exception as e:
                    logger.error(f"Error in detection cycle: {e}")
                    time.sleep(5)  # Longer delay after error
                    
        except KeyboardInterrupt:
            logger.info("Lock detector stopped by user")

if __name__ == "__main__":
    detector = LockDetector()
    detector.run()