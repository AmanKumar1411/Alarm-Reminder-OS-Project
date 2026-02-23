#!/usr/bin/env python3
"""
alarm_engine.py — Modular Alarm & Reminder Engine (Python)

A command-line Python program demonstrating core Operating System concepts:
  os.fork(), os.exec*(), os.waitpid(), time.sleep(), signals (SIGCHLD, SIGTERM),
  time.time(), time.mktime(), os.access(), subprocess, os.kill(),
  os.getpid(), os.getppid(), os.environ

This program acts as a miniature task scheduler — the core abstraction
that real operating systems use to manage timed events and process
lifecycle. Each alarm is a child process managed independently by the
kernel's process scheduler, mirroring how cron jobs, at(1), and
systemd timers work in production environments.

Usage:
  python3 alarm_engine.py worldclock                              Show world clock (8 timezones)
  python3 alarm_engine.py alarm "YYYY-MM-DD HH:MM" "msg" "sound"  Schedule a calendar alarm
  python3 alarm_engine.py sounds                                  List available sounds
  python3 alarm_engine.py list                                    List active alarm processes
  python3 alarm_engine.py cancel <PID>                            Cancel a scheduled alarm
  python3 alarm_engine.py test-sound <name>                       Play a sound immediately
  python3 alarm_engine.py status                                  Engine diagnostics
"""

import sys
import os
import signal
import time
import json
import errno
import subprocess
import platform
from datetime import datetime, timezone

# ================================================================
#  CONSTANTS
# ================================================================

MAX_ACTIVE_ALARMS = 64
PID_FILE = "/tmp/alarm_engine_pids.dat"

# ================================================================
#  PID TRACKING — File-based process registry for duplicate prevention
#
#  OS Concept: We use a shared file (/tmp/alarm_engine_pids.dat) as
#  an inter-process communication (IPC) mechanism. This mirrors how
#  PID files work in daemon management (e.g., /var/run/sshd.pid).
#  File locking isn't used here for simplicity, but in production,
#  fcntl.flock() would be employed for mutual exclusion.
# ================================================================


def register_pid(pid: int, dt: str, message: str, sound: str) -> None:
    """Append a PID entry to the tracking file."""
    try:
        with open(PID_FILE, "a") as f:
            # OS Concept: open("a") — atomic append on most POSIX systems.
            # The kernel ensures that writes with O_APPEND are serialized,
            # preventing data corruption from concurrent writers.
            f.write(f"{pid}|{dt[:19]}|{message[:127]}|{sound[:31]}|{int(time.time())}\n")
        print(f"[ALARM ENGINE] Registered PID {pid} in tracking file", file=sys.stderr)
    except OSError as e:
        print(f"[ALARM ENGINE] Failed to open PID file for writing: {e}", file=sys.stderr)


def unregister_pid(pid: int) -> None:
    """Remove a PID entry from the tracking file."""
    try:
        with open(PID_FILE, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return

    new_lines = []
    for line in lines:
        parts = line.strip().split("|")
        if parts and parts[0].isdigit() and int(parts[0]) == pid:
            continue  # Skip this entry
        new_lines.append(line)

    with open(PID_FILE, "w") as f:
        f.writelines(new_lines)
    print(f"[ALARM ENGINE] Unregistered PID {pid} from tracking file", file=sys.stderr)


def is_duplicate_alarm(dt: str, message: str) -> bool:
    """Check if an alarm for the same datetime and message already exists."""
    try:
        with open(PID_FILE, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False  # No tracking file = no duplicates

    for line in lines:
        parts = line.strip().split("|")
        if len(parts) >= 3:
            try:
                entry_pid = int(parts[0])
                entry_dt = parts[1]
                entry_msg = parts[2]
            except ValueError:
                continue

            # OS Concept: os.kill(pid, 0) — null signal
            # Tests whether a process exists and we have permission to
            # signal it, without actually sending a signal.
            try:
                os.kill(entry_pid, 0)
                # Process is alive — check if same datetime and message
                if entry_dt == dt and entry_msg == message:
                    return True  # Duplicate found
            except OSError:
                pass  # Process no longer exists

    return False


def cleanup_dead_pids() -> None:
    """Remove entries for processes that no longer exist."""
    try:
        with open(PID_FILE, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return

    new_lines = []
    removed = 0

    for line in lines:
        parts = line.strip().split("|")
        if parts and parts[0].isdigit():
            entry_pid = int(parts[0])
            # OS Concept: os.kill(pid, 0) checks process existence.
            # If the process has exited, os.kill() raises OSError with
            # errno == ESRCH ("No such process").
            try:
                os.kill(entry_pid, 0)
                new_lines.append(line)  # Process alive, keep entry
            except OSError as e:
                if e.errno == errno.ESRCH:
                    removed += 1  # Dead process — skip
                else:
                    new_lines.append(line)  # Permission error, keep entry
        else:
            new_lines.append(line)

    if removed > 0:
        with open(PID_FILE, "w") as f:
            f.writelines(new_lines)
        print(f"[ALARM ENGINE] Cleaned up {removed} dead process entries", file=sys.stderr)


def list_active_alarms_json() -> None:
    """Read PID tracking file and output active alarms as JSON."""
    cleanup_dead_pids()  # Remove stale entries first

    alarms = []
    try:
        with open(PID_FILE, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(json.dumps(alarms))
        sys.stdout.flush()
        return

    for line in lines:
        parts = line.strip().split("|")
        if len(parts) >= 4:
            try:
                entry_pid = int(parts[0])
                entry_dt = parts[1]
                entry_msg = parts[2]
                entry_sound = parts[3]
            except (ValueError, IndexError):
                continue

            # Verify the process is still alive
            try:
                os.kill(entry_pid, 0)
            except OSError:
                continue

            # Calculate remaining time
            try:
                target_time = time.mktime(time.strptime(entry_dt, "%Y-%m-%d %H:%M"))
                remaining = target_time - time.time()
                if remaining < 0:
                    remaining = 0
            except ValueError:
                remaining = 0

            alarms.append({
                "pid": entry_pid,
                "datetime": entry_dt,
                "message": entry_msg,
                "sound": entry_sound,
                "remaining_seconds": int(remaining),
            })

    print(json.dumps(alarms, indent=2))
    sys.stdout.flush()


# ================================================================
#  WORLD CLOCK — Timezone handling via os.environ["TZ"] + time.tzset()
#
#  OS Concept: Each assignment to os.environ["TZ"] modifies the process
#  environment block — a key-value store maintained by the kernel
#  for every process. time.tzset() re-reads TZ and updates the C library's
#  internal timezone state. time.localtime() then uses this state to convert
#  a UNIX timestamp (seconds since epoch) to broken-down local time.
#
#  This is the same mechanism that the `date` command and cron use
#  to handle timezone-aware scheduling.
# ================================================================

TIMEZONES = [
    {"tz": "Asia/Kolkata",        "label": "India (IST)"},
    {"tz": "America/New_York",    "label": "New York (EST)"},
    {"tz": "Europe/London",       "label": "London (GMT/BST)"},
    {"tz": "Asia/Tokyo",          "label": "Tokyo (JST)"},
    {"tz": "America/Los_Angeles", "label": "Los Angeles (PST)"},
    {"tz": "Europe/Berlin",       "label": "Berlin (CET)"},
    {"tz": "Asia/Dubai",          "label": "Dubai (GST)"},
    {"tz": "Australia/Sydney",    "label": "Sydney (AEST)"},
]


def get_world_clock_json() -> None:
    """Query the OS for current time in multiple timezones. Output JSON."""
    now = time.time()  # OS system call: get current UNIX timestamp

    results = []
    for tz_entry in TIMEZONES:
        # OS Concept: os.environ["TZ"] + time.tzset()
        # Modifies the process-level environment to switch the timezone
        # that time.localtime() uses, without affecting other processes.
        os.environ["TZ"] = tz_entry["tz"]
        time.tzset()

        local = time.localtime(now)  # Convert to local time in new TZ

        time_str = time.strftime("%H:%M:%S", local)
        date_str = time.strftime("%A, %b %d, %Y", local)

        # Compute UTC offset
        utc_off = local.tm_gmtoff
        off_h = utc_off // 3600
        off_m = abs((utc_off % 3600) // 60)
        offset_str = f"UTC{off_h:+d}:{off_m:02d}"

        results.append({
            "tz": tz_entry["tz"],
            "label": tz_entry["label"],
            "time": time_str,
            "date": date_str,
            "offset": offset_str,
        })

    print(json.dumps(results, indent=2))
    sys.stdout.flush()

    # Restore default timezone
    if "TZ" in os.environ:
        del os.environ["TZ"]
    time.tzset()


# ================================================================
#  SOUND PLAYBACK — Cross-platform with OS-level file access checks
# ================================================================

SOUNDS = [
    {"name": "glass",     "macos_file": "/System/Library/Sounds/Glass.aiff",     "description": "Glass chime"},
    {"name": "ping",      "macos_file": "/System/Library/Sounds/Ping.aiff",      "description": "Ping notification"},
    {"name": "hero",      "macos_file": "/System/Library/Sounds/Hero.aiff",      "description": "Hero fanfare"},
    {"name": "purr",      "macos_file": "/System/Library/Sounds/Purr.aiff",      "description": "Gentle purr"},
    {"name": "submarine", "macos_file": "/System/Library/Sounds/Submarine.aiff", "description": "Submarine sonar"},
    {"name": "basso",     "macos_file": "/System/Library/Sounds/Basso.aiff",     "description": "Deep bass tone"},
    {"name": "funk",      "macos_file": "/System/Library/Sounds/Funk.aiff",      "description": "Funky alert"},
    {"name": "pop",       "macos_file": "/System/Library/Sounds/Pop.aiff",       "description": "Pop sound"},
]


def play_sound(sound_name: str) -> None:
    """
    Play a named sound using OS-specific tools.

    OS Concepts demonstrated:
      - os.access() — kernel-level file existence verification
      - os.fork() + os.execlp() — replace child process image
      - os.waitpid() — synchronous wait for child completion
      - subprocess.run() — higher-level wrapper around fork+exec
    """
    print(f"[ALARM ENGINE] play_sound(\"{sound_name}\") — PID {os.getpid()}", file=sys.stderr)

    # Find the named sound
    filepath = None
    for s in SOUNDS:
        if s["name"] == sound_name:
            filepath = s["macos_file"]
            break

    # Strategy 1: macOS — use afplay with system sound file
    # OS Concept: os.access() — check file existence at kernel level
    # OS Concept: os.fork() + os.execlp() — replace process image (exec family)
    if filepath and os.access(filepath, os.F_OK):
        print(f"[ALARM ENGINE] Playing via afplay: {filepath}", file=sys.stderr)

        # Fork a child to play sound so we can also speak the message
        pid = os.fork()
        if pid == 0:
            # Child process
            try:
                os.execlp("afplay", "afplay", filepath)
            except OSError:
                os._exit(1)  # exec failed
        elif pid > 0:
            os.waitpid(pid, 0)  # Wait for sound to finish
        return

    # Strategy 2: Linux — try paplay (PulseAudio) or aplay (ALSA)
    # OS Concept: os.access() to check if binaries exist in standard paths
    if os.access("/usr/bin/paplay", os.X_OK):
        print("[ALARM ENGINE] Playing via paplay (Linux PulseAudio)", file=sys.stderr)
        pid = os.fork()
        if pid == 0:
            try:
                os.execlp("paplay", "paplay",
                          "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga")
            except OSError:
                os._exit(1)
        elif pid > 0:
            os.waitpid(pid, 0)
        return

    if os.access("/usr/bin/aplay", os.X_OK):
        print("[ALARM ENGINE] Playing via aplay (Linux ALSA)", file=sys.stderr)
        pid = os.fork()
        if pid == 0:
            try:
                os.execlp("aplay", "aplay",
                          "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga")
            except OSError:
                os._exit(1)
        elif pid > 0:
            os.waitpid(pid, 0)
        return

    # Strategy 3: Fallback — terminal beep
    # OS Concept: print("\a") sends BEL character to terminal
    print("[ALARM ENGINE] Fallback: terminal beep (\\a)", file=sys.stderr)
    for _ in range(3):
        print("\a", end="", flush=True)
        time.sleep(0.5)  # 0.5 second between beeps


def list_sounds_json() -> None:
    """Print available sound options as a JSON array to stdout."""
    results = []
    for s in SOUNDS:
        # Check if the sound file actually exists on this system
        available = os.access(s["macos_file"], os.F_OK)
        results.append({
            "name": s["name"],
            "description": s["description"],
            "available": available,
        })
    print(json.dumps(results, indent=2))
    sys.stdout.flush()


# ================================================================
#  ALARM SCHEDULING — Calendar-based with os.fork(), time.mktime()
#
#  This function implements a miniature task scheduler. It mirrors
#  how real OS scheduling works:
#    1. Parse the target time (like cron parsing crontab entries)
#    2. Compute delay until trigger (like the kernel's timer subsystem)
#    3. Validate inputs (safety checks, duplicate prevention)
#    4. os.fork() a child process (like cron spawning jobs)
#    5. Child sleeps until trigger time (kernel scheduler suspends it)
#    6. Child fires the alarm and exits (process cleanup)
#    7. Parent returns immediately (non-blocking scheduling)
# ================================================================


def schedule_alarm(dt: str, message: str, sound: str) -> None:
    """
    Schedule a calendar-based alarm.

    Parses "YYYY-MM-DD HH:MM" into time struct, converts to UNIX
    timestamp via time.mktime(), computes delay.
    os.fork()s a child process that time.sleep()s and then calls play_sound().
    Parent prevents zombies with SA_NOCLDWAIT on SIGCHLD.
    Registers the child PID in PID_FILE for tracking.

    Args:
        dt: Target time string "YYYY-MM-DD HH:MM"
        message: Reminder message to display
        sound: Sound name (e.g., "glass", "ping", "hero")
    """
    print(f"[ALARM ENGINE] schedule_alarm() — Parent PID {os.getpid()}", file=sys.stderr)

    # Parse datetime string "YYYY-MM-DD HH:MM" into time struct
    try:
        target_struct = time.strptime(dt, "%Y-%m-%d %H:%M")
    except ValueError:
        result = {"status": "error", "message": "Invalid datetime format. Use YYYY-MM-DD HH:MM"}
        print(json.dumps(result))
        sys.stdout.flush()
        return

    # OS Concept: time.mktime()
    # Converts broken-down local time (struct_time) → UNIX timestamp (float).
    # The kernel's timezone data and the process-level TZ environment
    # variable determine how local time maps to UTC.
    target_time = time.mktime(target_struct)
    if target_time == -1:
        result = {"status": "error", "message": "Failed to convert datetime to timestamp"}
        print(json.dumps(result))
        sys.stdout.flush()
        return

    # OS Concept: time.time()
    # System call to get the current UNIX timestamp from the kernel.
    # Internally reads the system clock maintained by timer interrupts.
    now = time.time()

    # OS Concept: Compute delay
    # difftime equivalent in Python — simple subtraction of timestamps
    delay_secs = target_time - now

    # Safety: reject past times — prevents negative sleep values
    if delay_secs <= 0:
        result = {"status": "error", "message": f"Cannot set alarm in the past ({-delay_secs:.0f} seconds ago)"}
        print(json.dumps(result))
        sys.stdout.flush()
        return

    # Duplicate Prevention — check if an identical alarm is already scheduled.
    # OS Concept: We use os.kill(pid, 0) to verify the existing process is still
    # alive. This prevents multiple fork()s for the same event, which would
    # waste system resources and cause duplicate triggers.
    if is_duplicate_alarm(dt, message):
        result = {"status": "error", "message": "Duplicate alarm already scheduled for this time"}
        print(json.dumps(result))
        sys.stdout.flush()
        return

    delay = int(delay_secs)
    print(f"[ALARM ENGINE] Alarm in {delay} seconds ({delay_secs / 60.0:.1f} minutes)", file=sys.stderr)

    # OS Concept: SIGCHLD + SA_NOCLDWAIT
    # When a child process exits, the kernel sends SIGCHLD to the parent.
    # Without handling, the child becomes a "zombie" — still in the process
    # table consuming a PID. Setting SIGCHLD to SIG_IGN (or SA_NOCLDWAIT on
    # some systems) tells the kernel to automatically reap children, freeing
    # system resources. This is critical for a long-running alarm manager
    # that spawns many child processes.
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    # OS Concept: os.fork()
    # Creates a new child process. The child receives an exact copy of the
    # parent's address space (using copy-on-write for efficiency). The child
    # inherits file descriptors, signal handlers, and environment.
    #
    # This mirrors how real OS task schedulers work:
    #   - cron: fork()s a child for each scheduled job
    #   - at(1): fork()s + sleep()s for delayed execution
    #   - systemd timers: create new process scopes for timed units
    #
    # The parent returns immediately (non-blocking), while the child
    # independently manages its own lifecycle — sleep, fire, cleanup.
    pid = os.fork()

    if pid < 0:
        print("[ALARM ENGINE] fork() failed", file=sys.stderr)
        result = {"status": "error", "message": "Failed to create alarm process"}
        print(json.dumps(result))
        sys.stdout.flush()
        return

    if pid == 0:
        # ── CHILD PROCESS ──────────────────────────────
        print(f"[ALARM ENGINE] Child PID {os.getpid()} (Parent PID {os.getppid()}) "
              f"— sleeping {delay} seconds...", file=sys.stderr)

        # OS Concept: time.sleep()
        # Puts the process into the SLEEPING state (S) in the kernel's
        # process table. The scheduler removes this process from the
        # run queue and sets a timer interrupt. When the timer fires,
        # the kernel moves the process back to READY (R) state.
        #
        # During sleep, the process consumes zero CPU but retains its
        # memory mapping. This is efficient for long-delayed alarms.
        time.sleep(delay)

        # ── Alarm fires! ──
        print(f"\n[ALARM ENGINE] ⏰ ALARM FIRED! PID {os.getpid()}", file=sys.stderr)
        print(f"[ALARM ENGINE] Message: {message}", file=sys.stderr)

        # Unregister from PID tracking — proper cleanup after execution
        unregister_pid(os.getpid())

        # Play the selected sound
        play_sound(sound)

        # Use macOS say command to speak the message
        # OS Concept: subprocess.run() wraps fork()+exec()
        try:
            subprocess.run(["say", f"Alarm: {message}"], check=False)
        except FileNotFoundError:
            pass  # 'say' command not available (non-macOS)

        os._exit(0)  # Child process exits cleanly

    # ── PARENT PROCESS ──────────────────────────────
    # Register the child PID for tracking and duplicate prevention
    register_pid(pid, dt, message, sound)

    # Parent returns immediately — child runs in background
    print(f"[ALARM ENGINE] Parent PID {os.getpid()} — alarm child spawned as PID {pid}",
          file=sys.stderr)

    formatted_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(target_time))

    result = {
        "status": "success",
        "message": "Alarm scheduled",
        "target": formatted_time,
        "delay_seconds": delay,
        "child_pid": pid,
        "sound": sound,
        "alarm_message": message,
    }
    print(json.dumps(result))
    sys.stdout.flush()


# ================================================================
#  CANCEL ALARM — Signal-based process termination
# ================================================================


def cancel_alarm(pid: int) -> int:
    """
    Cancel a scheduled alarm by sending SIGTERM.

    OS Concepts demonstrated:
      - os.kill(pid, 0) — null signal to check process existence
      - os.kill(pid, signal.SIGTERM) — graceful termination

    Args:
        pid: Process ID to cancel

    Returns:
        0 on success, -1 on error
    """
    if pid <= 0:
        result = {"status": "error", "message": "Invalid PID"}
        print(json.dumps(result))
        sys.stdout.flush()
        return -1

    # OS Concept: os.kill(pid, 0) — null signal
    # Sends signal 0 to check if a process exists and we have permission
    # to send signals to it. Does not actually terminate anything.
    try:
        os.kill(pid, 0)
    except OSError as e:
        print(f"[ALARM ENGINE] check PID failed: {e}", file=sys.stderr)
        result = {"status": "error", "message": f"Process {pid} not found or access denied"}
        print(json.dumps(result))
        sys.stdout.flush()
        return -1

    # OS Concept: os.kill(pid, signal.SIGTERM)
    # Sends SIGTERM (signal 15) to the specified process. SIGTERM is the
    # polite termination signal — it allows the process to perform cleanup.
    # Unlike SIGKILL (9), SIGTERM can be caught and handled gracefully.
    try:
        os.kill(pid, signal.SIGTERM)
        # Remove from PID tracking file
        unregister_pid(pid)
        print(f"[ALARM ENGINE] Killed PID {pid}", file=sys.stderr)
        result = {"status": "success", "message": f"Process {pid} cancelled"}
        print(json.dumps(result))
        sys.stdout.flush()
        return 0
    except OSError as e:
        print(f"[ALARM ENGINE] kill failed: {e}", file=sys.stderr)
        result = {"status": "error", "message": f"Failed to kill process {pid}"}
        print(json.dumps(result))
        sys.stdout.flush()
        return -1


# ================================================================
#  MAIN — CLI dispatcher
#
#  Routes subcommands to the appropriate engine function.
#  This mirrors how init systems dispatch service commands
#  (e.g., systemctl start/stop/status).
# ================================================================


def print_usage() -> None:
    """Print usage information."""
    print(
        "Alarm & Reminder Engine — OS Concepts Demo\n"
        "\n"
        "Usage:\n"
        f"  python3 {sys.argv[0]} worldclock                              Show world clock (8 timezones)\n"
        f"  python3 {sys.argv[0]} alarm \"YYYY-MM-DD HH:MM\" \"msg\" \"sound\"  Schedule a calendar alarm\n"
        f"  python3 {sys.argv[0]} sounds                                  List available sounds\n"
        f"  python3 {sys.argv[0]} list                                    List active alarm processes\n"
        f"  python3 {sys.argv[0]} cancel <PID>                            Cancel a scheduled alarm\n"
        f"  python3 {sys.argv[0]} test-sound <name>                       Play a sound immediately\n"
        f"  python3 {sys.argv[0]} status                                  Engine diagnostics",
        file=sys.stderr,
    )


def main() -> int:
    """CLI entry point — dispatch subcommands to engine functions."""
    if len(sys.argv) < 2:
        print_usage()
        return 1

    command = sys.argv[1]

    if command == "worldclock":
        get_world_clock_json()

    elif command == "alarm":
        if len(sys.argv) < 5:
            print(f"Usage: python3 {sys.argv[0]} alarm \"YYYY-MM-DD HH:MM\" \"message\" \"sound\"",
                  file=sys.stderr)
            result = {"status": "error", "message": "Missing arguments. Need: datetime, message, sound"}
            print(json.dumps(result))
            return 1
        schedule_alarm(sys.argv[2], sys.argv[3], sys.argv[4])

    elif command == "sounds":
        list_sounds_json()

    elif command == "list":
        # LIST ACTIVE ALARMS — Process inspection
        # OS Concept: Reads PID tracking file and uses os.kill(pid, 0)
        # to verify each process is still alive. Similar to how
        # `ps aux` or `top` queries /proc on Linux.
        list_active_alarms_json()

    elif command == "test-sound":
        # CLI test mode — plays a named sound immediately via the OS.
        # Useful for verifying backend sound works independently of
        # the browser/frontend. Separates OS audio from browser audio.
        name = sys.argv[2] if len(sys.argv) >= 3 else "glass"
        print(f"[TEST] Playing sound '{name}' via OS...", file=sys.stderr)
        play_sound(name)
        print("[TEST] Done.", file=sys.stderr)

    elif command == "cancel":
        # CANCEL ALARM — kills a background alarm process
        # OS Concept: os.kill() system call sends a signal to a process.
        if len(sys.argv) < 3:
            print(f"Usage: python3 {sys.argv[0]} cancel <PID>", file=sys.stderr)
            result = {"status": "error", "message": "Missing PID"}
            print(json.dumps(result))
            return 1
        try:
            pid = int(sys.argv[2])
        except ValueError:
            result = {"status": "error", "message": "Invalid PID (must be a number)"}
            print(json.dumps(result))
            return 1
        return 0 if cancel_alarm(pid) == 0 else 1

    elif command == "status":
        # ENGINE STATUS — Diagnostic information
        # OS Concepts: os.getpid(), os.getppid(), time.time()
        # Reports the engine's own process info and system state.
        now = time.time()
        timestr = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))

        plat = platform.system()
        if plat == "Darwin":
            plat_name = "macOS"
        elif plat == "Linux":
            plat_name = "Linux"
        else:
            plat_name = "Unknown"

        result = {
            "engine": "alarm_engine",
            "version": "2.0.0",
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "current_time": timestr,
            "platform": plat_name,
            "language": "Python",
            "python_version": platform.python_version(),
            "pid_file": PID_FILE,
        }
        print(json.dumps(result))
        sys.stdout.flush()

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
