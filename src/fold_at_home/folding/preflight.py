"""Pre-launch safety checks and runtime memory watchdog.

Prevents system freezes from ColabFold/AlphaFold memory exhaustion:
- Pre-launch: Checks available RAM, kills stale processes
- Runtime: MemoryWatchdog monitors RAM during folds, kills process before freeze
- OOM priority: preexec helper ensures kernel OOM killer targets fold process first
"""

import logging
import os
import signal
import threading
import time

logger = logging.getLogger(__name__)

# Minimum available RAM (GB) before launching fold.
MIN_MEMORY_GB = 16

# Kill fold process if available RAM drops below this.
WATCHDOG_KILL_THRESHOLD_GB = 4

# How often the watchdog checks memory (seconds).
WATCHDOG_INTERVAL = 5

# Proteins above this residue count get reduced MSA/models.
LARGE_PROTEIN_THRESHOLD = 1000


def get_available_memory_gb() -> float:
    """Return available system memory in GB.

    Uses /proc/meminfo on Linux, falls back to psutil or -1.
    """
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    return kb / (1024 * 1024)
    except OSError:
        pass

    # Fallback: try psutil
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 ** 3)
    except ImportError:
        pass

    return -1.0


def check_memory(min_gb: float = MIN_MEMORY_GB) -> tuple[bool, float, str]:
    """Verify sufficient memory for a fold run.

    Returns:
        (ok, available_gb, message)
    """
    available = get_available_memory_gb()
    if available < 0:
        return True, available, "Could not read memory info, skipping check"

    if available < min_gb:
        return False, available, (
            f"Only {available:.1f} GB available (need {min_gb} GB). "
            "Close other applications or kill stale fold processes."
        )

    return True, available, f"Memory OK: {available:.1f} GB available"


def kill_stale_colabfold(current_pid: int | None = None) -> int:
    """Kill any lingering colabfold_batch processes.

    Only works on Linux (/proc filesystem).
    """
    if current_pid is None:
        current_pid = os.getpid()
    parent_pid = os.getppid()
    exclude = {current_pid, parent_pid}

    killed = 0
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            pid = int(entry)
            if pid in exclude:
                continue
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().decode("utf-8", errors="replace")
                if "colabfold_batch" in cmdline or "colabfold-conda" in cmdline:
                    logger.warning(f"Killing stale ColabFold process PID {pid}")
                    os.kill(pid, signal.SIGTERM)
                    killed += 1
            except (OSError, PermissionError):
                continue
    except OSError:
        pass  # /proc not available (non-Linux)

    if killed:
        time.sleep(3)
        logger.info(f"Killed {killed} stale ColabFold process(es)")

    return killed


def preflight(min_gb: float = MIN_MEMORY_GB) -> tuple[bool, str]:
    """Run all pre-launch checks.

    Returns:
        (ok, summary_message)
    """
    ok, available, msg = check_memory(min_gb)
    if ok:
        logger.info(msg)
        return True, msg

    # Memory low — try cleaning up stale processes
    logger.warning(msg)
    killed = kill_stale_colabfold()

    if killed == 0:
        return False, f"Insufficient memory ({available:.1f} GB) and no stale processes found"

    # Re-check after cleanup
    ok, available, msg = check_memory(min_gb)
    if ok:
        logger.info(f"Memory recovered after killing {killed} stale process(es)")
        return True, msg

    return False, f"Memory still insufficient ({available:.1f} GB) after cleanup"


def get_sequence_length(fasta_path) -> int:
    """Return total residue count from a FASTA file."""
    length = 0
    try:
        with open(fasta_path) as f:
            for line in f:
                if not line.startswith(">"):
                    length += len(line.strip())
    except OSError:
        pass
    return length


def set_oom_priority():
    """Set oom_score_adj to maximum so OOM killer targets this process first.

    Use as preexec_fn in subprocess.Popen to apply to the child process.
    """
    try:
        with open("/proc/self/oom_score_adj", "w") as f:
            f.write("1000")
    except OSError:
        pass


class MemoryWatchdog:
    """Monitor available RAM during a fold and kill process if dangerously low."""

    def __init__(
        self,
        pid: int,
        kill_threshold_gb: float = WATCHDOG_KILL_THRESHOLD_GB,
        check_interval: float = WATCHDOG_INTERVAL,
    ):
        self.pid = pid
        self.kill_threshold_gb = kill_threshold_gb
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.killed = False

    def start(self):
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()
        logger.info(
            f"Memory watchdog started for PID {self.pid} "
            f"(kill below {self.kill_threshold_gb} GB, "
            f"checking every {self.check_interval}s)"
        )

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.check_interval + 1)

    def _monitor(self):
        while not self._stop_event.is_set():
            available = get_available_memory_gb()
            if available < 0:
                self._stop_event.wait(self.check_interval)
                continue

            if available < self.kill_threshold_gb:
                logger.critical(
                    f"WATCHDOG: {available:.1f} GB available < "
                    f"{self.kill_threshold_gb} GB — killing PID {self.pid}"
                )
                try:
                    os.kill(self.pid, signal.SIGKILL)
                    self.killed = True
                except OSError as e:
                    logger.error(f"WATCHDOG: Failed to kill PID {self.pid}: {e}")
                return

            self._stop_event.wait(self.check_interval)
