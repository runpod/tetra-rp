"""
Terminal utilities for enhancing command line interfaces with rich formatting.

This module provides a collection of functions and classes for creating beautiful,
informative terminal user interfaces with colors, formatting, progress indicators,
and interactive elements.

Features:
- Automatic terminal capability detection (colors, emoji support)
- Dynamic width adjustment for different terminal sizes
- Styled text with colors and formatting
- Icons and emoji with fallbacks for different terminals
- Progress bars with ETA calculation
- Spinners with multiple animation styles
- Boxed messages and headers
- Operation summaries and statistics

Examples:
    # Basic styled messages
    print_info("This is an informational message")
    print_success("Operation completed successfully")
    print_warning("This might need attention")
    print_error("Something went wrong")
    
    # Progress tracking
    with Spinner("Processing...", spinner_type="dots"):
        # Do some work
        time.sleep(2)
    
    # Progress bar
    items = list(range(100))
    for item in SmartProgress(items, desc="Processing items"):
        # Process item
        time.sleep(0.01)
        
    # Boxed messages
    print_box(
        "Your task has completed successfully!",
        title="Success",
        color="bright_green"
    )
"""
import sys
import time
import threading
import shutil
import os
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable

# Detect color support
def supports_color():
    """Determine if the terminal supports color output.
    
    Returns False if:
    - NO_COLOR environment variable is set
    - Output is not a TTY
    - Running on certain platforms/environments known to not support color
    """
    # Check NO_COLOR environment variable (standard for disabling color)
    if os.environ.get('NO_COLOR', ''):
        return False
        
    # Check if output is a TTY
    if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
        return False
        
    # Check platform-specific issues
    plat = sys.platform
    if plat == 'Pocket PC':
        return False
        
    # Windows support
    if plat == 'win32' and 'ANSICON' not in os.environ:
        # Check for Windows Terminal, Windows ConPTY or modern PowerShell
        if not any(term in os.environ.get('TERM_PROGRAM', '') 
                   for term in ['vscode', 'Windows Terminal']):
            return os.environ.get('WT_SESSION', '') != ''
            
    return True

# Color mode setting
USE_COLORS = supports_color()

# Get terminal width
def get_term_width():
    """Get current terminal width, defaults to 80 if can't be determined"""
    try:
        return shutil.get_terminal_size().columns
    except:
        return 80

TERM_WIDTH = get_term_width()  # Initial width

# ANSI escape codes for colors and styles
# Use raw strings or actual escape sequences to prevent double escaping
COLORS = {
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_black": "\033[90m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
    "bright_white": "\033[97m",
    "reset": "\033[0m",
}

# Empty color codes for terminals that don't support color
NO_COLORS = {color: "" for color in COLORS}

STYLES = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "italic": "\033[3m",
    "underline": "\033[4m",
    "blink": "\033[5m",
    "reverse": "\033[7m",
    "hidden": "\033[8m",
    "strikethrough": "\033[9m",
    "reset": "\033[0m",
}

# Detect emoji support
def supports_emoji():
    """Determine if the terminal might support emoji characters."""
    # Most modern terminals support emoji, but some older ones don't
    # This is a very rough heuristic - in reality it's complex to detect
    term = os.environ.get('TERM', '')
    if term in ['dumb', 'vt100', 'vt102', 'xterm-mono']:
        return False
    if sys.platform == 'win32' and not ('CMDER_ROOT' in os.environ or 'WT_SESSION' in os.environ):
        # Basic Windows cmd.exe doesn't support emoji well
        return False
    return True

USE_EMOJI = supports_emoji()

# Icons with fallbacks for terminals that don't support emoji
ICONS = {
    "info": COLORS["bright_blue"] + ("ℹ" if USE_EMOJI else "i") + COLORS["reset"],
    "success": COLORS["bright_green"] + ("✓" if USE_EMOJI else "+") + COLORS["reset"],
    "warning": COLORS["bright_yellow"] + ("⚠" if USE_EMOJI else "!") + COLORS["reset"],
    "error": COLORS["bright_red"] + ("✖" if USE_EMOJI else "x") + COLORS["reset"],
    "debug": COLORS["bright_magenta"] + ("⚙" if USE_EMOJI else "D") + COLORS["reset"],
    "tetra": COLORS["bright_cyan"] + ("◊" if USE_EMOJI else "T") + COLORS["reset"],
    "rocket": COLORS["bright_yellow"] + ("🚀" if USE_EMOJI else ">") + COLORS["reset"],
    "server": COLORS["bright_cyan"] + ("🖥️" if USE_EMOJI else "S") + COLORS["reset"],
    "network": COLORS["bright_blue"] + ("🌐" if USE_EMOJI else "N") + COLORS["reset"],
    "function": COLORS["bright_magenta"] + ("⚡" if USE_EMOJI else "F") + COLORS["reset"],
    "timer": COLORS["bright_yellow"] + ("⏱️" if USE_EMOJI else "t") + COLORS["reset"],
    "ml": COLORS["bright_green"] + ("🧠" if USE_EMOJI else "ML") + COLORS["reset"],
    "compute": COLORS["bright_yellow"] + ("🔢" if USE_EMOJI else "C") + COLORS["reset"],
}

# Box drawing characters
BOX = {
    "tl": "╭",  # top left
    "tr": "╮",  # top right
    "bl": "╰",  # bottom left
    "br": "╯",  # bottom right
    "h": "─",   # horizontal
    "v": "│",   # vertical
    "ltee": "├", # left tee
    "rtee": "┤", # right tee
    "ttee": "┬", # top tee
    "btee": "┴", # bottom tee
    "cross": "┼", # cross
}

def get_horiz_line():
    """Get a horizontal line with current terminal width"""
    return COLORS["bright_black"] + BOX["h"] * (get_term_width() - 2) + COLORS["reset"]

HORIZ_LINE = get_horiz_line()  # Initial line

def style_text(text: str, color: Optional[str] = None, style: Optional[str] = None) -> str:
    """Applies color and style to text using ANSI escape codes."""
    if not USE_COLORS:
        return text
        
    prefix = ""
    if color and color in COLORS:
        prefix += COLORS[color]
    if style and style in STYLES:
        prefix += STYLES[style]

    if prefix:
        return f"{prefix}{text}{STYLES['reset']}"
    return text

def print_styled(text: str, color: Optional[str] = None, style: Optional[str] = None, icon: Optional[str] = None, end: str = "\n"):
    """Prints styled text with an optional icon."""
    icon_str = f"{ICONS[icon]} " if icon and icon in ICONS else ""
    styled_msg = style_text(text, color, style)
    print(f"{icon_str}{styled_msg}", end=end)

def print_info(text: str):
    print_styled(text, color="bright_blue", icon="info")

def print_success(text: str):
    print_styled(text, color="bright_green", icon="success")

def print_warning(text: str):
    print_styled(text, color="bright_yellow", icon="warning")

def print_error(text: str):
    print_styled(text, color="bright_red", icon="error")

def print_debug(text: str):
    print_styled(text, color="bright_magenta", icon="debug")

def print_tetra(text: str, style: Optional[str] = None):
    """Prints messages related to Tetra core operations."""
    print_styled(text, color="bright_cyan", style=style, icon="tetra")

def print_header(text: str, icon: Optional[str] = None):
    """Prints a prominent header that adjusts to terminal width."""
    term_width = get_term_width()
    padding = (term_width - len(text) - 6) // 2
    left_pad = BOX["h"] * padding
    right_pad = BOX["h"] * (padding if len(text) % 2 == 0 else padding + 1)
    
    icon_str = f"{ICONS[icon]} " if icon and icon in ICONS else ""
    
    header = f"{BOX['tl']}{left_pad} {icon_str}{style_text(text, 'bright_white', 'bold')} {right_pad}{BOX['tr']}"
    print(style_text(header, "bright_cyan"))

def print_subheader(text: str, icon: Optional[str] = None):
    """Prints a subheading."""
    icon_str = f"{ICONS[icon]} " if icon and icon in ICONS else ""
    styled_text = style_text(text, "bright_white", "bold")
    print(f"{icon_str}{styled_text}")
    print(style_text(BOX["h"] * len(text), "bright_black"))

def print_box(content: str, title: Optional[str] = None, color: str = "bright_cyan"):
    """Prints content in a box with an optional title, adjusting to terminal width."""
    term_width = get_term_width()
    
    # Split content by newlines and find the longest line to determine box width
    lines = content.split("\n")
    width = max(max(len(line) for line in lines), len(title) if title else 0) + 4
    
    # Ensure the box fits in the terminal
    width = min(width, term_width - 2)
    
    # Top border with title if provided
    if title:
        title_styled = style_text(f" {title} ", color, "bold")
        title_len = len(title) + 2
        left_pad = (width - title_len) // 2
        right_pad = width - left_pad - title_len
        
        top_border = f"{BOX['tl']}{BOX['h'] * left_pad}{title_styled}{BOX['h'] * right_pad}{BOX['tr']}"
    else:
        top_border = f"{BOX['tl']}{BOX['h'] * width}{BOX['tr']}"
    
    print(style_text(top_border, color))
    
    # Content lines
    for line in lines:
        # Truncate line if it's too long for the box
        if len(line) > width - 2:
            display_line = line[:width-5] + "..."
        else:
            display_line = line
        
        padding = width - len(display_line) - 2
        print(style_text(f"{BOX['v']} {display_line}{' ' * padding} {BOX['v']}", color))
    
    # Bottom border
    bottom_border = f"{BOX['bl']}{BOX['h'] * width}{BOX['br']}"
    print(style_text(bottom_border, color))

def print_step(step_num: int, title: str, description: Optional[str] = None):
    """Prints a step in a multi-step process."""
    step_header = f"{style_text(str(step_num), 'bright_white', 'bold')}. {style_text(title, 'bright_cyan', 'bold')}"
    print(step_header)
    if description:
        print(f"   {description}")

def print_separator():
    """Prints a horizontal separator line that adjusts to terminal width."""
    print(get_horiz_line())

def timestamp():
    """Returns current time formatted as a string."""
    return datetime.now().strftime("%H:%M:%S")

def print_timestamp(message: str, color: Optional[str] = None):
    """Prints a message with timestamp."""
    time_str = style_text(f"[{timestamp()}]", "bright_black")
    msg = style_text(message, color) if color else message
    print(f"{time_str} {msg}")

class Spinner:
    """A fancy terminal spinner with multiple animation options."""
    SPINNERS = {
        "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
        "classic": ["◐", "◓", "◑", "◒"],
        "arrows": ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
        "bounce": ["⠁", "⠂", "⠄", "⡀", "⢀", "⠠", "⠐", "⠈"],
        "moon": ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"],
        "pulse": [" ", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃"],
    }

    def __init__(self, message: str = "Working...", 
                 delay: float = 0.1, 
                 spinner_type: str = "dots",
                 color: str = "bright_cyan",
                 icon: Optional[str] = None,
                 throttle_after: float = 30.0):
        self.spinner = self.SPINNERS.get(spinner_type, self.SPINNERS["dots"])
        self.delay = delay
        self.message = message
        self.color = color
        self.icon = icon
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = 0
        self.throttle_after = throttle_after  # Time in seconds after which to throttle updates
        self.throttle_factor = 1.0  # Starts at normal speed

    def _spin(self):
        i = 0
        self._start_time = time.time()
        icon_str = f"{ICONS[self.icon]} " if self.icon and self.icon in ICONS else ""
        last_update_time = self._start_time
        
        while self._running:
            current_time = time.time()
            elapsed = current_time - self._start_time
            
            # Implement throttling for long-running spinners
            # Gradually reduce update frequency to save CPU
            if elapsed > self.throttle_after:
                # Calculate throttle factor based on elapsed time
                # The longer it runs, the less frequently we update
                self.throttle_factor = min(5.0, 1.0 + (elapsed - self.throttle_after) / 30.0)
            
            # Only update if enough time has passed based on throttle factor
            if current_time - last_update_time >= (self.delay * self.throttle_factor):
                spinner_frame = self.spinner[i % len(self.spinner)]
                elapsed_str = f" ({elapsed:.1f}s)" if elapsed > 3.0 else ""
                
                # Compose the entire spinner line
                spinner_line = f"\r{icon_str}{style_text(spinner_frame, self.color)} {self.message}{elapsed_str}"
                
                sys.stdout.write(spinner_line)
                sys.stdout.flush()
                i += 1
                last_update_time = current_time
                
            # Sleep for a fixed small time to avoid CPU hogging
            time.sleep(self.delay)
            
        # Clear spinner line when done
        sys.stdout.write("\r" + " " * (len(self.message) + 20) + "\r")
        sys.stdout.flush()

    def start(self):
        if not self._thread or not self._thread.is_alive():
            self._running = True
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()

    def stop(self):
        if self._thread and self._thread.is_alive():
            self._running = False
            self._thread.join()
            self._thread = None
            
    def update_message(self, message: str):
        """Update the spinner message while it's running."""
        self.message = message

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        if exc_type:
            print_error(f"Operation failed: {exc_val}")
        return False

class SmartProgress:
    """Advanced progress bar with ETA and flexible customization."""
    def __init__(self, 
                 iterable=None, 
                 total=None,
                 desc="Processing", 
                 unit="it",
                 color="bright_cyan",
                 bar_format=None,
                 width=40):
        self.iterable = iterable
        self.total = total if total is not None else len(iterable) if iterable is not None else 100
        self.desc = desc
        self.unit = unit
        self.color = color
        self.width_setting = width  # Store width setting
        self.n = 0
        self.start_t = None
        self.last_print_n = 0
        self.bar_format = bar_format or self._default_bar_format
        
    def _default_bar_format(self, n, total, elapsed):
        """Default format for the progress bar."""
        # Use dynamic width that adapts to current terminal size
        term_width = get_term_width()
        bar_length = min(self.width_setting, term_width - 30)
        filled_len = int(round(bar_length * n / float(total))) if total > 0 else 0
        filled_len = min(filled_len, bar_length)
        
        # Progress bar
        bar = '█' * filled_len + '▯' * (bar_length - filled_len)
        
        # Percentage 
        percent = f"{100 * (n / float(total)):.1f}%" if total > 0 else "0.0%"
        
        # ETA calculation
        if n > 0 and elapsed > 0:
            rate = n / elapsed
            remaining_items = total - n
            eta = remaining_items / rate if rate > 0 else 0
            eta_str = f"ETA: {self._format_interval(eta)}" if n < total else f"Time: {self._format_interval(elapsed)}"
        else:
            eta_str = "ETA: --:--"
                
        return f"{style_text(self.desc, self.color)}: |{style_text(bar, self.color)}| {percent} ({n}/{total}, {eta_str})"
    
    def _format_interval(self, t):
        """Format a time interval in a human-readable way."""
        mins, s = divmod(int(t), 60)
        h, m = divmod(mins, 60)
        if h > 0:
            return f"{h:d}:{m:02d}:{s:02d}"
        else:
            return f"{m:02d}:{s:02d}"
    
    def update(self, n=1):
        """Update the progress bar by advancing n units."""
        self.n += n
        if self.start_t is None:
            self.start_t = time.time()
        
        # Only refresh display occasionally to avoid slowdowns from terminal rendering
        if self.n == self.total or (self.n - self.last_print_n) >= max(1, self.total / 100):
            elapsed = time.time() - self.start_t
            display = self.bar_format(self.n, self.total, elapsed)
            sys.stdout.write(f"\r{display}")
            sys.stdout.flush()
            self.last_print_n = self.n
        
        if self.n >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()
    
    def close(self):
        """Close the progress bar."""
        if self.start_t is not None:
            self.update(self.total - self.n)  # Fill to 100%
    
    def __iter__(self):
        """Iterate over the wrapped iterable."""
        if self.iterable is None:
            raise ValueError("Iterable not provided")
        
        self.n = 0
        self.start_t = time.time()
        for obj in self.iterable:
            yield obj
            self.update()
        
        self.close()
    
    def __enter__(self):
        if self.iterable is None:
            self.start_t = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def show_summary(operations: List[Dict[str, Any]]):
    """Displays a summary of operations that were performed."""
    if not operations:
        return
    
    title = "Operation Summary"
    print_header(title)
    
    # Calculate field widths
    op_field = max(len(op["operation"]) for op in operations) + 2
    result_field = max(len(op.get("result", "")) for op in operations) + 2
    time_field = 8  # Fixed width for time
    
    # Print header row
    header = f"{style_text('Operation', 'bright_white', 'bold'):{op_field}} " \
             f"{style_text('Result', 'bright_white', 'bold'):{result_field}} " \
             f"{style_text('Time', 'bright_white', 'bold'):{time_field}}"
    print(header)
    print(style_text("-" * (op_field + result_field + time_field + 2), "bright_black"))
    
    # Print each operation
    for op in operations:
        status_color = "bright_green" if op.get("success", True) else "bright_red"
        status_icon = "✓" if op.get("success", True) else "✗"
        
        operation = style_text(op["operation"], "bright_cyan")
        result = style_text(f"{status_icon} {op.get('result', '')}", status_color)
        duration = op.get("duration", "")
        duration_text = style_text(duration, "bright_black") if duration else ""
        
        print(f"{operation:{op_field}} {result:{result_field}} {duration_text:{time_field}}")
    
    print_separator()

# Custom notification classes for distinct messages with personality
class TetraNotifier:
    """Creates themed notifications with personality."""
    
    @staticmethod
    def server_ready(server_name: str, details: Optional[Dict] = None):
        """Notification when a server is ready."""
        print_box(
            f"Server {style_text(server_name, 'bright_green', 'bold')} is ready and waiting for your tasks!\n" +
            (f"Details: {details}" if details else ""),
            title="Server Ready",
            color="bright_green"
        )
    
    @staticmethod
    def job_submitted(func_name: str, server: str):
        """Notification when a job is submitted."""
        print_timestamp(
            f"{ICONS['rocket']} Job {style_text(func_name, 'bright_yellow', 'bold')} sent to " +
            f"{style_text(server, 'bright_cyan')}. Fasten your seatbelts!",
            "bright_white"
        )
    
    @staticmethod
    def job_completed(func_name: str, duration: float):
        """Notification when a job completes."""
        duration_str = f"{duration:.2f}s" if duration < 60 else f"{int(duration/60)}m {int(duration%60)}s"
        print_box(
            f"The function {style_text(func_name, 'bright_magenta', 'bold')} has completed in {duration_str}. " +
            "Your results are ready!",
            title="Task Complete", 
            color="bright_green"
        )
    
    @staticmethod
    def welcome():
        """Welcome message with Tetra ASCII art."""
        tetra_art = r"""
  _______    _            
 |__   __|  | |           
    | | ____| |_ _ __ __ _ 
    | |/ _ \ __| '__/ _` |
    | |  __/ |_| | | (_| |
    |_|\___|\__|_|  \__,_|
        """
        
        print_box(
            style_text(tetra_art, "bright_cyan") + 
            "\nWelcome to Tetra - Distributed Inference Made Simple" +
            "\nPowering your ML functions across the compute universe",
            color="bright_cyan"
        )

# Example usage (can be removed or kept for testing)
if __name__ == "__main__":
    TetraNotifier.welcome()
    
    print_header("Terminal UX Demo", "rocket")
    
    print_step(1, "Basic Message Styles")
    print_info("This is an informational message.")
    print_success("Operation completed successfully.")
    print_warning("Something might need attention.")
    print_error("An error occurred during the process.")
    print_debug("Here's some debug information.")
    print_tetra("Initializing Tetra core components...", style="bold")
    print_separator()
    
    print_step(2, "Spinner Demo")
    for spinner_type in ["classic", "dots", "arrows", "bounce", "moon", "pulse"]:
        with Spinner(f"Testing {spinner_type} spinner...", spinner_type=spinner_type, icon="compute"):
            time.sleep(1.5)
        print_success(f"{spinner_type.capitalize()} spinner works!")
    print_separator()
    
    print_step(3, "Progress Bar Demo")
    items = list(range(100))
    for _ in SmartProgress(items, desc="Processing items", unit="items", color="bright_green"):
        time.sleep(0.01)
    print_separator()
    
    print_step(4, "Box Messages")
    TetraNotifier.server_ready("gpu-server-01", {"gpu": "RTX 4090", "mem": "24GB"})
    TetraNotifier.job_submitted("image_generation", "gpu-cluster")
    TetraNotifier.job_completed("transformer_inference", 45.3)
    print_separator()
    
    print_step(5, "Operation Summary")
    operations = [
        {"operation": "Initialize model", "result": "Success", "duration": "5.2s", "success": True},
        {"operation": "Load dataset", "result": "Success", "duration": "2.1s", "success": True},
        {"operation": "Server connection", "result": "Failed", "duration": "0.5s", "success": False},
        {"operation": "Fallback execution", "result": "Success", "duration": "8.7s", "success": True},
    ]
    show_summary(operations) 