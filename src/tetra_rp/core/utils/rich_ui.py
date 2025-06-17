"""
Rich UI components for enhanced logging and progress display in Tetra.
This module provides Rich-based alternatives to standard logging output.
"""

import builtins
import logging
import os
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator, List, Union
from enum import Enum

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.panel import Panel
    from rich.table import Table
    from rich.status import Status
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    # Create dummy classes for type hints when Rich is not available
    class Console: pass
    class Status: pass


class TetraStatus(str, Enum):
    """Status types for visual styling"""
    READY = "READY"
    INITIALIZING = "INITIALIZING" 
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    THROTTLED = "THROTTLED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


def is_rich_enabled() -> bool:
    """Check if Rich UI should be enabled based on environment and availability"""
    return (
        RICH_AVAILABLE and 
        os.environ.get("TETRA_RICH_UI", "false").lower() in ("true", "1", "yes")
    )


class RichUIManager:
    """Central manager for Rich UI components"""
    
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self._enabled = is_rich_enabled()
        self._captured_prints: List[str] = []
        self._original_print = None
        self._print_capturing = False
    
    @property
    def enabled(self) -> bool:
        return self._enabled and self.console is not None
    
    def get_console(self) -> Optional["Console"]:
        return self.console if self.enabled else None
    
    def start_print_capture(self) -> None:
        """Start capturing print() calls"""
        if not self.enabled or self._print_capturing:
            return
            
        self._original_print = builtins.print
        self._captured_prints.clear()
        self._print_capturing = True
        
        def captured_print(*args, **kwargs):
            # Convert print arguments to string
            output = ' '.join(str(arg) for arg in args)
            
            # Handle common print kwargs
            end = kwargs.get('end', '\n')
            sep = kwargs.get('sep', ' ')
            if len(args) > 1:
                output = sep.join(str(arg) for arg in args)
            
            self._captured_prints.append(output + end.rstrip())
            
            # Also send to original print for fallback scenarios
            if not self.enabled:
                self._original_print(*args, **kwargs)
        
        builtins.print = captured_print
    
    def stop_print_capture(self) -> List[str]:
        """Stop capturing and return captured prints"""
        if not self._print_capturing:
            return []
            
        if self._original_print:
            builtins.print = self._original_print
            
        self._print_capturing = False
        captured = self._captured_prints.copy()
        self._captured_prints.clear()
        return captured


# Global Rich UI manager instance
rich_ui = RichUIManager()


class RichLoggingFilter(logging.Filter):
    """Filter to suppress verbose third-party logs when Rich UI is active"""
    
    def filter(self, record):
        # Suppress asyncio selector debug messages
        if record.name == "asyncio" and ("selector" in record.getMessage().lower() or "using selector" in record.getMessage().lower()):
            return False
        # Suppress other verbose third-party logs  
        if record.levelno <= logging.INFO and record.name.startswith(("urllib3", "requests", "boto3", "botocore")):
            return False
        # Suppress all DEBUG level logs when Rich UI is active (except errors/warnings)
        if record.levelno <= logging.DEBUG:
            return False
        return True


def get_rich_handler() -> logging.Handler:
    """Get Rich logging handler if available, otherwise return standard handler"""
    if rich_ui.enabled:
        handler = RichHandler(
            console=rich_ui.console,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True
        )
        # Add filter to suppress verbose logs when Rich UI is active
        handler.addFilter(RichLoggingFilter())
        return handler
    else:
        # Fallback to standard handler
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-5s | %(message)s"
        ))
        return handler


def get_status_color(status: str) -> str:
    """Get Rich color for status"""
    if not rich_ui.enabled:
        return ""
    
    color_map = {
        "READY": "green",
        "COMPLETED": "green",
        "RUNNING": "blue",
        "IN_QUEUE": "cyan",
        "INITIALIZING": "yellow", 
        "FAILED": "red",
        "CANCELLED": "red",
        "THROTTLED": "orange3",
        "UNHEALTHY": "red",
        "UNKNOWN": "dim"
    }
    return color_map.get(status.upper(), "white")


def format_status_text(status: str, message: str = "") -> str:
    """Format status text with color if Rich is enabled"""
    if not rich_ui.enabled:
        return f"{status}: {message}" if message else status
    
    color = get_status_color(status)
    formatted_status = f"[{color}]{status}[/{color}]"
    return f"{formatted_status}: {message}" if message else formatted_status


def create_deployment_panel(endpoint_name: str, endpoint_id: str, console_url: str) -> Union[str, "Panel"]:
    """Create a deployment summary panel"""
    if not rich_ui.enabled or not RICH_AVAILABLE:
        return f"Deployed: {endpoint_name} ({endpoint_id})"
    
    table = Table.grid(padding=1)
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    
    table.add_row("Endpoint:", f"[green]{endpoint_name}[/green]")
    table.add_row("ID:", f"[dim]{endpoint_id}[/dim]")
    table.add_row("Console:", f"[link={console_url}]{console_url}[/link]")
    
    panel = Panel(
        table,
        title="[bold green]🚀 Deployment Successful[/bold green]",
        border_style="green"
    )
    return panel


def create_reused_resource_panel(endpoint_name: str, endpoint_id: str, console_url: str) -> Union[str, "Panel"]:
    """Create a panel for reused existing resources"""
    if not rich_ui.enabled or not RICH_AVAILABLE:
        return f"Reusing: {endpoint_name} ({endpoint_id})"
    
    table = Table.grid(padding=1)
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    
    table.add_row("Endpoint:", f"[blue]{endpoint_name}[/blue]")
    table.add_row("ID:", f"[dim]{endpoint_id}[/dim]")
    table.add_row("Console:", f"[link={console_url}]{console_url}[/link]")
    
    panel = Panel(
        table,
        title="[bold blue]♻️  Using Existing Resource[/bold blue]",
        border_style="blue"
    )
    return panel


def create_metrics_table(delay_time: int, execution_time: int, worker_id: str) -> Union[str, "Panel"]:
    """Create a metrics display table"""
    if not rich_ui.enabled or not RICH_AVAILABLE:
        return f"Worker:{worker_id} | Delay: {delay_time}ms | Execution: {execution_time}ms"
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    
    table.add_row("Worker ID", f"[dim]{worker_id}[/dim]")
    table.add_row("Delay Time", f"{delay_time:,} ms")
    table.add_row("Execution Time", f"{execution_time:,} ms")
    
    return Panel(
        table,
        title="[bold blue]📊 Job Metrics[/bold blue]",
        border_style="blue"
    )


@contextmanager  
def job_progress_tracker(job_id: str, endpoint_name: str) -> Generator[Optional["JobProgressTracker"], None, None]:
    """Context manager for tracking job progress with Rich UI"""
    if rich_ui.enabled and rich_ui.console is not None:
        tracker = JobProgressTracker(job_id, endpoint_name, rich_ui.console)
        try:
            yield tracker
        finally:
            tracker.stop()
    else:
        yield None


class JobProgressTracker:
    """Tracks job progress with Rich live status display"""
    
    def __init__(self, job_id: str, endpoint_name: str, console: "Console"):
        self.job_id = job_id
        self.endpoint_name = endpoint_name  
        self.console = console
        self.start_time = time.time()
        self.last_status = "UNKNOWN"
        self.attempt_count = 0
        self.current_status_display = None
        self.status_printed = False
    
    def update_status(self, status: str, message: str = "") -> None:
        """Update the job status display"""
        if not rich_ui.enabled or not RICH_AVAILABLE:
            return
            
        elapsed = int(time.time() - self.start_time)
        
        if status != self.last_status:
            # Clean up previous status display
            if self.current_status_display:
                self.current_status_display.stop()
                self.current_status_display = None
            
            self.attempt_count = 0
            self.last_status = status
            self.status_printed = False
            
            # Handle different status types
            if status in ["IN_QUEUE", "INITIALIZING", "RUNNING"]:
                # Choose appropriate emoji and spinner based on status
                if status == "IN_QUEUE":
                    emoji = "⏳"
                    spinner = "simpleDotsScrolling"
                elif status == "INITIALIZING":
                    emoji = "⚡"
                    spinner = "dots12"
                else:  # RUNNING
                    emoji = "🏁"
                    spinner = "dots"
                    
                status_text = f"[{get_status_color(status)}]{status}[/{get_status_color(status)}]"
                full_message = f"{emoji} {status_text}"
                if message:
                    full_message += f" {message}"
                
                # Create live status display
                self.current_status_display = Status(
                    full_message,
                    spinner=spinner,
                    console=self.console
                )
                self.current_status_display.start()
            else:
                # Final status - print and finish
                color = get_status_color(status)
                self.console.print(
                    f"[{color}]●[/{color}] Job {self.job_id}: {status} ({elapsed}s)"
                )
        else:
            self.attempt_count += 1
    
    def show_progress_indicator(self) -> None:
        """Update the live status with progress indication"""
        if not rich_ui.enabled or not self.current_status_display:
            return
            
        # For live status, the spinner handles the animation automatically
        # We can optionally update the message to show progress
        if self.attempt_count > 0 and self.attempt_count % 5 == 0:  # Every 5th attempt
            elapsed = int(time.time() - self.start_time)
            status_text = f"[{get_status_color(self.last_status)}]{self.last_status}[/{get_status_color(self.last_status)}]"
            
            if self.last_status == "IN_QUEUE":
                emoji = "🕑"
                message = f"Waiting for worker... ({elapsed}s)"
            elif self.last_status == "INITIALIZING":
                emoji = "⚡"
                message = f"Starting up worker... ({elapsed}s)"
            else:  # RUNNING
                emoji = "⚙️"
                message = f"Executing function... ({elapsed}s)"
            
            full_message = f"{emoji} {status_text} {message}"
            self.current_status_display.update(full_message)
    
    def stop(self) -> None:
        """Stop the status display"""
        if self.current_status_display:
            self.current_status_display.stop()
            self.current_status_display = None


def print_with_rich(message: Any, style: str = "") -> None:
    """Print message with Rich styling if available"""
    if rich_ui.enabled and rich_ui.console:
        rich_ui.console.print(message, style=style)
    else:
        # Strip Rich markup for plain output if it's a string
        if isinstance(message, str):
            import re
            clean_message = re.sub(r'\[/?[^\]]*\]', '', message)
            print(clean_message)
        else:
            print(message)


def create_health_display(health_data: Dict[str, Any]) -> Union[str, "Panel"]:
    """Create health status display"""
    if not rich_ui.enabled or not RICH_AVAILABLE:
        return f"Health: {health_data}"
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right", style="green")
    
    workers = health_data.get("workers", {})
    for status, count in workers.items():
        if count > 0:
            color = get_status_color(status) 
            table.add_row(f"[{color}]{status.title()}[/{color}]", str(count))
    
    return Panel(
        table,
        title="[bold yellow]🏥 Endpoint Health[/bold yellow]",
        border_style="yellow"
    )


def create_user_output_panel(output_lines: List[str], source: str = "Local") -> Union[str, "Panel"]:
    """Create a panel for user print() output"""
    if not rich_ui.enabled or not RICH_AVAILABLE or not output_lines:
        return ""
    
    # Filter out empty lines and format content
    content_lines = [line for line in output_lines if line.strip()]
    
    if not content_lines:
        return ""
    
    # Create the content text
    content = '\n'.join(content_lines)
    
    # Choose icon and color based on source
    if source.lower() == "remote":
        icon = "🔧"
        border_color = "blue"
        title_color = "bold blue"
    else:
        icon = "💬"
        border_color = "green"
        title_color = "bold green"
    
    return Panel(
        content,
        title=f"[{title_color}]{icon} {source} Output[/{title_color}]",
        border_style=border_color,
        padding=(0, 1)
    )


def display_remote_output(stdout_lines: List[str]) -> None:
    """Display remote function output in a Rich panel"""
    if not rich_ui.enabled or not stdout_lines:
        return
    
    panel = create_user_output_panel(stdout_lines, "Remote")
    if panel:
        print_with_rich(panel)


@contextmanager
def capture_local_prints() -> Generator[None, None, None]:
    """Context manager to capture and display local print() calls"""
    if not rich_ui.enabled:
        yield
        return
    
    rich_ui.start_print_capture()
    try:
        yield
    finally:
        captured = rich_ui.stop_print_capture()
        if captured:
            panel = create_user_output_panel(captured, "Local")
            if panel:
                print_with_rich(panel)