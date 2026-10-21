# workflowos/activity_agent/agent.py
"""Real Windows Desktop Activity Agent for WorkFlowOS.

Runs background observers on Windows to capture real user activity:
1. WindowObserver: Active window / foreground process transitions.
2. FileObserver: Real filesystem operations in monitored directories (watchdog).
3. ClipboardObserver: Non-sensitive clipboard change detections.

Emits structured, normalized activity events into an event queue / database.
"""

import os
import sys
import time
import queue
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .normalizer import EventNormalizer
from .sessionizer import ActivitySessionizer

logger = logging.getLogger("workflowos.activity_agent")

IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    try:
        import win32gui
        import win32process
        import win32con
    except ImportError:
        win32gui = None
        win32process = None
    try:
        import psutil
    except ImportError:
        psutil = None
    import ctypes
else:
    win32gui = None
    win32process = None
    psutil = None
    ctypes = None


class FileChangeHandler(FileSystemEventHandler):
    """Watches directories and translates filesystem changes to canonical events."""

    def __init__(self, emit_callback: Callable[[Dict[str, Any]], None]):
        super().__init__()
        self.emit_callback = emit_callback
        self._last_modified_times: Dict[str, float] = {}
        self._pending_deletions: Dict[str, float] = {}  # filename -> time for move matching

    def on_created(self, event: FileSystemEvent):
        src = os.path.normpath(event.src_path)
        filename = os.path.basename(src)
        if filename.startswith("~") or filename.startswith("."):
            return

        # Check if this creation is the destination half of a cross-folder move
        now = time.time()
        if filename in self._pending_deletions and (now - self._pending_deletions[filename]) < 2.0:
            del self._pending_deletions[filename]
            self.emit_callback({
                "application": "File Explorer",
                "action": "MOVE_FILE",
                "target": filename,
                "raw_data": {
                    "destination_path": src,
                    "dest_dir": os.path.dirname(src),
                    "filename": filename,
                    "is_directory": event.is_directory,
                }
            })
            return

        action = "CREATE_DIRECTORY" if event.is_directory else "CREATE_FILE"
        self.emit_callback({
            "application": "File Explorer",
            "action": action,
            "target": filename,
            "raw_data": {
                "path": src,
                "is_directory": event.is_directory,
                "parent_dir": os.path.dirname(src),
            }
        })

    def on_moved(self, event: FileSystemEvent):
        src = os.path.normpath(event.src_path)
        dest = os.path.normpath(event.dest_path)
        src_name = os.path.basename(src)
        dest_name = os.path.basename(dest)
        src_dir = os.path.dirname(src)
        dest_dir = os.path.dirname(dest)

        if dest_name.startswith("~") or dest_name.startswith("."):
            return

        if src_dir == dest_dir:
            action = "RENAME_FILE"
            target = f"{src_name} -> {dest_name}"
        else:
            action = "MOVE_FILE"
            target = dest_name

        self.emit_callback({
            "application": "File Explorer",
            "action": action,
            "target": target,
            "raw_data": {
                "source_path": src,
                "dest_path": dest,
                "source_dir": src_dir,
                "dest_dir": dest_dir,
                "old_name": src_name,
                "new_name": dest_name,
                "is_directory": event.is_directory,
            }
        })

    def on_deleted(self, event: FileSystemEvent):
        src = os.path.normpath(event.src_path)
        filename = os.path.basename(src)
        if filename.startswith("~") or filename.startswith("."):
            return

        # Record pending deletion to match potential cross-folder move
        self._pending_deletions[filename] = time.time()


class DesktopActivityAgent:
    """Core Desktop Activity Agent that monitors real Windows desktop actions."""

    def __init__(
        self,
        monitored_paths: Optional[List[str]] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        inactivity_timeout_seconds: float = 5.0,
    ):
        self.monitored_paths: List[str] = monitored_paths or []
        self.event_callback = event_callback
        self.sessionizer = ActivitySessionizer(inactivity_timeout_seconds=inactivity_timeout_seconds)
        self.event_queue: queue.Queue = queue.Queue()

        self._running = False
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []
        self._fs_observer: Optional[Observer] = None
        self._last_window_title: Optional[str] = None
        self._last_app_name: Optional[str] = None
        self._last_clipboard_seq: Optional[int] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def add_monitored_path(self, path: str):
        """Add a directory to monitor for filesystem activity."""
        norm_path = os.path.abspath(path)
        if norm_path not in self.monitored_paths:
            self.monitored_paths.append(norm_path)
            os.makedirs(norm_path, exist_ok=True)
            if self._fs_observer and self._fs_observer.is_alive():
                handler = FileChangeHandler(self._handle_raw_event)
                try:
                    self._fs_observer.schedule(handler, norm_path, recursive=True)
                    logger.info(f"Dynamically watching new path: {norm_path}")
                except Exception as e:
                    logger.error(f"Failed to schedule watch on {norm_path}: {e}")

    def _handle_raw_event(self, raw_data: Dict[str, Any]):
        """Normalizes and sessionizes an incoming raw event, then emits it."""
        if not self._running:
            return

        app = raw_data.get("application", "System")
        action = raw_data.get("action", "UNKNOWN")
        target = raw_data.get("target")
        event_time = raw_data.get("timestamp") or datetime.utcnow()

        session_id = self.sessionizer.get_or_create_session(
            event_time=event_time,
            application=app
        )

        normalized = EventNormalizer.create_event_dict(
            application=app,
            action=action,
            target=target,
            session_id=session_id,
            raw_data=raw_data.get("raw_data"),
            timestamp=event_time,
        )

        self.event_queue.put(normalized)

        if self.event_callback:
            try:
                self.event_callback(normalized)
            except Exception as e:
                logger.error(f"Error in event_callback: {e}")

    def _get_active_window_info(self) -> Optional[Dict[str, str]]:
        if not IS_WINDOWS:
            return None

        try:
            if win32gui and win32process and psutil:
                hwnd = win32gui.GetForegroundWindow()
                if not hwnd:
                    return None
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    proc = psutil.Process(pid)
                    app_name = proc.name()
                except Exception:
                    app_name = "Unknown"
                return {"title": title, "app_name": app_name}
            elif ctypes:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if not hwnd:
                    return None
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                return {"title": title, "app_name": "WindowsApp"}
        except Exception as e:
            logger.debug(f"Window fetch error: {e}")
        return None

    def _window_polling_loop(self):
        logger.info("Window observation thread started")
        while not self._stop_event.is_set():
            try:
                info = self._get_active_window_info()
                if info:
                    title = info["title"]
                    app_name = info["app_name"]

                    if title and title != self._last_window_title:
                        clean_app = app_name
                        if clean_app.lower().endswith(".exe"):
                            clean_app = clean_app[:-4].capitalize()
                        if clean_app.lower() in ("explorer", "fileexplorer"):
                            clean_app = "File Explorer"
                        elif clean_app.lower() == "chrome":
                            clean_app = "Chrome"
                        elif clean_app.lower() == "msedge":
                            clean_app = "Edge"
                        elif clean_app.lower() == "code":
                            clean_app = "VS Code"

                        self._last_window_title = title
                        self._last_app_name = clean_app

                        self._handle_raw_event({
                            "application": clean_app,
                            "action": "ACTIVE_WINDOW",
                            "target": title[:200],
                            "raw_data": {
                                "process_name": app_name,
                                "window_title": title,
                            }
                        })
            except Exception as e:
                logger.debug(f"Error in window polling: {e}")

            time.sleep(0.5)

    def _clipboard_polling_loop(self):
        logger.info("Clipboard observation thread started")
        if not IS_WINDOWS or not ctypes:
            return

        while not self._stop_event.is_set():
            try:
                seq = ctypes.windll.user32.GetClipboardSequenceNumber()
                if self._last_clipboard_seq is not None and seq != self._last_clipboard_seq:
                    self._handle_raw_event({
                        "application": self._last_app_name or "System",
                        "action": "CLIPBOARD_COPY",
                        "target": "Clipboard Content",
                        "raw_data": {"sequence_number": seq}
                    })
                self._last_clipboard_seq = seq
            except Exception as e:
                logger.debug(f"Clipboard poll error: {e}")

            time.sleep(0.5)

    def start(self):
        if self._running:
            return

        self._running = True
        self._stop_event.clear()

        # Simplify paths: if multiple paths share a common root, monitor the common root
        if self.monitored_paths:
            self._fs_observer = Observer()
            handler = FileChangeHandler(self._handle_raw_event)
            
            # Find unique non-nested roots
            roots = set()
            for p in self.monitored_paths:
                os.makedirs(p, exist_ok=True)
                roots.add(p)

            # Check if there is a common parent like C:\WorkFlowOS_Test
            if len(roots) > 1:
                common = os.path.commonpath(list(roots))
                if os.path.isdir(common) and len(common) > 3:
                    roots = {common}

            for r in roots:
                try:
                    self._fs_observer.schedule(handler, r, recursive=True)
                    logger.info(f"Observing directory root: {r}")
                except Exception as e:
                    logger.error(f"Failed to observe {r}: {e}")

            try:
                self._fs_observer.start()
            except Exception as e:
                logger.error(f"Watchdog start failed: {e}")

        t_win = threading.Thread(target=self._window_polling_loop, daemon=True, name="WindowObserver")
        t_win.start()
        self._threads.append(t_win)

        t_clip = threading.Thread(target=self._clipboard_polling_loop, daemon=True, name="ClipboardObserver")
        t_clip.start()
        self._threads.append(t_clip)

        logger.info("WorkFlowOS Desktop Activity Agent started successfully.")

    def stop(self):
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._fs_observer:
            try:
                self._fs_observer.stop()
                self._fs_observer.join(timeout=2.0)
            except Exception as e:
                logger.error(f"Error stopping filesystem observer: {e}")
            self._fs_observer = None

        for t in self._threads:
            if t.is_alive():
                t.join(timeout=1.0)
        self._threads.clear()

        self.sessionizer.reset()
        logger.info("WorkFlowOS Desktop Activity Agent stopped.")
