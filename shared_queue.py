"""
Shared queue module for cross-process communication.
Uses a file-based queue mechanism that works across separate processes.
For this exercise, we use a simple JSONL (JSON Lines) file as the queue.
The file acts as the persistent storage, while each process maintains
an in-memory buffer for performance.
"""

import json
import os
import threading
import queue as std_queue
import time
import fcntl
import platform
from typing import Dict, Any, Optional

# Queue file path
QUEUE_FILE = 'event_queue.jsonl'
LOCK_FILE = 'event_queue.lock'
_queue_lock = threading.Lock()  # For thread safety within a process
_is_windows = platform.system() == 'Windows'


def _append_to_file(event_data: Dict[str, Any]):
    """Append event to the queue file."""
    try:
        with open(QUEUE_FILE, 'a') as f:
            _acquire_file_lock(f)
            try:
                f.write(json.dumps(event_data) + '\n')
                f.flush()  # Ensure data is written immediately
            finally:
                _release_file_lock(f)
    except Exception as e:
        raise RuntimeError(f"Failed to write to queue file: {e}")


def _acquire_file_lock(file_handle):
    """Acquire a file lock (cross-platform)."""
    if _is_windows:
        # On Windows, file locking is handled differently
        # For simplicity, we'll rely on the OS file system for atomic operations
        # In production, you'd use a proper cross-platform locking library
        pass
    else:
        # On Unix, use fcntl
        try:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX)
        except (AttributeError, OSError):
            pass  # Fallback: no locking if fcntl not available


def _release_file_lock(file_handle):
    """Release a file lock (cross-platform)."""
    if _is_windows:
        # On Windows, no explicit unlock needed
        pass
    else:
        try:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
        except (AttributeError, OSError):
            pass


def _read_from_file() -> Optional[Dict[str, Any]]:
    """Read and remove the first event from the queue file."""
    if not os.path.exists(QUEUE_FILE):
        return None
    
    try:
        # Use file locking for cross-process safety
        with open(QUEUE_FILE, 'r+') as f:
            _acquire_file_lock(f)
            try:
                # Read all lines
                lines = f.readlines()
                
                if not lines:
                    return None
                
                # Parse first line
                first_line = lines[0].strip()
                if not first_line:
                    return None
                
                event = json.loads(first_line)
                
                # Remove first line and write back
                f.seek(0)
                f.truncate()
                f.writelines(lines[1:])
                f.flush()
                
                return event
            finally:
                _release_file_lock(f)
    except json.JSONDecodeError:
        # If first line is invalid, remove it and try again
        try:
            with open(QUEUE_FILE, 'r+') as f:
                _acquire_file_lock(f)
                try:
                    lines = f.readlines()
                    if lines:
                        f.seek(0)
                        f.truncate()
                        f.writelines(lines[1:])
                        f.flush()
                finally:
                    _release_file_lock(f)
        except Exception:
            pass
        return None
    except Exception as e:
        return None


def _count_file_lines() -> int:
    """Count the number of events in the queue file."""
    if not os.path.exists(QUEUE_FILE):
        return 0
    
    try:
        with open(QUEUE_FILE, 'r') as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


class SharedQueue:
    """
    A queue-like interface that works across processes using a file backend.
    For the Ingestion API: uses in-memory queue for speed, syncs to file.
    For the Processor: reads directly from file (since it's a separate process).
    """
    
    def __init__(self, use_file_directly: bool = False):
        """
        Initialize the shared queue.
        
        Args:
            use_file_directly: If True, always read from file (for Processor).
                              If False, use in-memory queue with file sync (for Ingestion API).
        """
        self.use_file_directly = use_file_directly
        if not use_file_directly:
            self._in_memory_queue = std_queue.Queue()
            # Load any existing events from file into memory
            self._load_from_file()
    
    def _load_from_file(self):
        """Load existing events from file into in-memory queue."""
        if not os.path.exists(QUEUE_FILE):
            return
        
        try:
            with open(QUEUE_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            event = json.loads(line)
                            self._in_memory_queue.put(event)
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass
    
    def put(self, item: Dict[str, Any], block: bool = True, timeout: Optional[float] = None):
        """Put an item into the queue."""
        if self.use_file_directly:
            _append_to_file(item)
        else:
            self._in_memory_queue.put(item, block=block, timeout=timeout)
            _append_to_file(item)
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get an item from the queue."""
        if self.use_file_directly:
            # For Processor: read directly from file
            start_time = time.time()
            while True:
                event = _read_from_file()
                if event is not None:
                    return event
                
                if not block:
                    raise std_queue.Empty()
                
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        raise std_queue.Empty()
                
                time.sleep(0.1)  # Brief sleep before retrying
        else:
            # For Ingestion API: use in-memory queue
            return self._in_memory_queue.get(block=block, timeout=timeout)
    
    def qsize(self) -> int:
        """Return the approximate size of the queue."""
        if self.use_file_directly:
            return _count_file_lines()
        else:
            return self._in_memory_queue.qsize()
    
    def task_done(self):
        """Indicate that a formerly enqueued task is complete."""
        if not self.use_file_directly:
            self._in_memory_queue.task_done()
    
    def empty(self) -> bool:
        """Return True if the queue is empty."""
        if self.use_file_directly:
            return _count_file_lines() == 0
        else:
            return self._in_memory_queue.empty()


# Global queue instances (one for each process type)
_ingestion_queue = None
_processor_queue = None


def get_queue(use_file_directly: bool = False):
    """
    Get or create the shared queue.
    
    Args:
        use_file_directly: If True, always read from file (for Processor).
                          If False, use in-memory queue with file sync (for Ingestion API).
    
    Returns:
        SharedQueue instance
    """
    global _ingestion_queue, _processor_queue
    
    if use_file_directly:
        if _processor_queue is None:
            _processor_queue = SharedQueue(use_file_directly=True)
        return _processor_queue
    else:
        if _ingestion_queue is None:
            _ingestion_queue = SharedQueue(use_file_directly=False)
        return _ingestion_queue

