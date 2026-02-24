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
  python3 alarm_engine.py todo add "YYYY-MM-DD" "title" ["desc"]  Add a todo item
  python3 alarm_engine.py todo list                               List all todos
  python3 alarm_engine.py todo complete <id>                      Mark a todo complete
  python3 alarm_engine.py todo delete <id>                        Delete a todo
  python3 alarm_engine.py todo edit <id> "title" ["desc"]         Edit a todo
  python3 alarm_engine.py todo date "YYYY-MM-DD"                  List todos for a date
  python3 alarm_engine.py calendar "YYYY-MM"                      Calendar data for a month
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
TODO_FILE = "/tmp/alarm_engine_todos.json"

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
#  TODO MANAGEMENT — File-based todo/task tracker
#
#  OS Concept: Uses a JSON file as a persistent data store,
#  demonstrating file I/O system calls (open, read, write, close).
#  Each read/write goes through the kernel's VFS layer.
#  The todo system complements the alarm scheduler — alarms are
#  time-triggered processes, while todos are date-anchored tasks
#  managed via file-based persistence.
# ================================================================


def _load_todos() -> list:
    """Load todos from the JSON file."""
    try:
        with open(TODO_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_todos(todos: list) -> None:
    """Save todos to the JSON file."""
    with open(TODO_FILE, "w") as f:
        json.dump(todos, f, indent=2)


def _next_todo_id(todos: list) -> int:
    """Generate the next unique todo ID."""
    if not todos:
        return 1
    return max(t.get("id", 0) for t in todos) + 1


def todo_add(date_str: str, title: str, description: str = "") -> None:
    """Add a new todo item for a specific date."""
    # Validate date format
    try:
        time.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        result = {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}
        print(json.dumps(result))
        sys.stdout.flush()
        return

    todos = _load_todos()
    new_id = _next_todo_id(todos)

    todo = {
        "id": new_id,
        "date": date_str,
        "title": title[:200],
        "description": description[:500],
        "completed": False,
        "created_at": int(time.time()),
    }
    todos.append(todo)
    _save_todos(todos)

    print(f"[ALARM ENGINE] Todo #{new_id} added for {date_str}", file=sys.stderr)
    result = {"status": "success", "message": f"Todo added", "todo": todo}
    print(json.dumps(result))
    sys.stdout.flush()


def todo_list_all() -> None:
    """List all todos as JSON."""
    todos = _load_todos()
    print(json.dumps(todos, indent=2))
    sys.stdout.flush()


def todo_list_by_date(date_str: str) -> None:
    """List todos for a specific date."""
    todos = _load_todos()
    filtered = [t for t in todos if t.get("date") == date_str]
    print(json.dumps(filtered, indent=2))
    sys.stdout.flush()


def todo_complete(todo_id: int) -> None:
    """Mark a todo as complete or toggle it back."""
    todos = _load_todos()
    for t in todos:
        if t.get("id") == todo_id:
            t["completed"] = not t["completed"]
            _save_todos(todos)
            state = "completed" if t["completed"] else "incomplete"
            print(f"[ALARM ENGINE] Todo #{todo_id} marked {state}", file=sys.stderr)
            result = {"status": "success", "message": f"Todo marked {state}", "todo": t}
            print(json.dumps(result))
            sys.stdout.flush()
            return

    result = {"status": "error", "message": f"Todo #{todo_id} not found"}
    print(json.dumps(result))
    sys.stdout.flush()


def todo_delete(todo_id: int) -> None:
    """Delete a todo by ID."""
    todos = _load_todos()
    new_todos = [t for t in todos if t.get("id") != todo_id]

    if len(new_todos) == len(todos):
        result = {"status": "error", "message": f"Todo #{todo_id} not found"}
        print(json.dumps(result))
        sys.stdout.flush()
        return

    _save_todos(new_todos)
    print(f"[ALARM ENGINE] Todo #{todo_id} deleted", file=sys.stderr)
    result = {"status": "success", "message": f"Todo #{todo_id} deleted"}
    print(json.dumps(result))
    sys.stdout.flush()


def todo_edit(todo_id: int, title: str, description: str = "") -> None:
    """Edit a todo's title and description."""
    todos = _load_todos()
    for t in todos:
        if t.get("id") == todo_id:
            t["title"] = title[:200]
            if description:
                t["description"] = description[:500]
            _save_todos(todos)
            print(f"[ALARM ENGINE] Todo #{todo_id} updated", file=sys.stderr)
            result = {"status": "success", "message": "Todo updated", "todo": t}
            print(json.dumps(result))
            sys.stdout.flush()
            return

    result = {"status": "error", "message": f"Todo #{todo_id} not found"}
    print(json.dumps(result))
    sys.stdout.flush()


# ================================================================
#  CALENDAR DATA — Aggregates alarms, reminders and todos for a month
#
#  OS Concept: Combines data from the PID tracking file (active
#  alarm processes) with the todo JSON file to build a unified
#  calendar view. Demonstrates reading multiple data sources
#  through file I/O and process inspection (os.kill(pid, 0)).
# ================================================================

import calendar as cal_module


def get_calendar_data(year_month: str) -> None:
    """
    Generate calendar data for a given month (YYYY-MM).
    Returns JSON with: month info, days with events, active alarms, todos.
    """
    try:
        parts = year_month.split("-")
        year = int(parts[0])
        month = int(parts[1])
    except (ValueError, IndexError):
        result = {"status": "error", "message": "Invalid format. Use YYYY-MM"}
        print(json.dumps(result))
        sys.stdout.flush()
        return

    # Get calendar info for the month
    first_weekday, num_days = cal_module.monthrange(year, month)
    month_name = cal_module.month_name[month]

    # Collect active alarms from PID file
    cleanup_dead_pids()
    alarms_list = []
    try:
        with open(PID_FILE, "r") as f:
            lines = f.readlines()
        for line in lines:
            parts = line.strip().split("|")
            if len(parts) >= 4:
                try:
                    entry_pid = int(parts[0])
                    os.kill(entry_pid, 0)  # Verify alive
                    alarm_date = parts[1][:10]  # YYYY-MM-DD
                    alarm_time = parts[1][11:16] if len(parts[1]) > 10 else ""
                    alarms_list.append({
                        "pid": entry_pid,
                        "date": alarm_date,
                        "time": alarm_time,
                        "message": parts[2],
                        "sound": parts[3],
                        "type": "alarm",
                    })
                except (ValueError, OSError):
                    continue
    except FileNotFoundError:
        pass

    # Collect todos
    todos = _load_todos()

    # Build date→events map for the requested month
    month_prefix = f"{year:04d}-{month:02d}"
    date_events = {}
    for day in range(1, num_days + 1):
        date_key = f"{month_prefix}-{day:02d}"
        day_alarms = [a for a in alarms_list if a["date"] == date_key]
        day_todos = [t for t in todos if t.get("date") == date_key]
        if day_alarms or day_todos:
            date_events[date_key] = {
                "alarms": day_alarms,
                "todos": day_todos,
                "count": len(day_alarms) + len(day_todos),
            }

    result = {
        "year": year,
        "month": month,
        "month_name": month_name,
        "first_weekday": first_weekday,  # 0=Monday
        "num_days": num_days,
        "today": time.strftime("%Y-%m-%d", time.localtime()),
        "events": date_events,
    }
    print(json.dumps(result, indent=2))
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
        f"  python3 {sys.argv[0]} status                                  Engine diagnostics\n"
        f"  python3 {sys.argv[0]} todo add \"YYYY-MM-DD\" \"title\" [\"desc\"]  Add a todo\n"
        f"  python3 {sys.argv[0]} todo list                               List all todos\n"
        f"  python3 {sys.argv[0]} todo complete <id>                      Toggle todo completion\n"
        f"  python3 {sys.argv[0]} todo delete <id>                        Delete a todo\n"
        f"  python3 {sys.argv[0]} todo edit <id> \"title\" [\"desc\"]         Edit a todo\n"
        f"  python3 {sys.argv[0]} todo date \"YYYY-MM-DD\"                  List todos for a date\n"
        f"  python3 {sys.argv[0]} calendar \"YYYY-MM\"                      Calendar data for a month",
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
            "todo_file": TODO_FILE,
        }
        print(json.dumps(result))
        sys.stdout.flush()

    elif command == "todo":
        # TODO MANAGEMENT — File-based task tracking
        # OS Concept: Persistent state via file I/O (open/read/write).
        if len(sys.argv) < 3:
            print(f"Usage: python3 {sys.argv[0]} todo <add|list|complete|delete|edit|date> ...",
                  file=sys.stderr)
            result = {"status": "error", "message": "Missing todo subcommand"}
            print(json.dumps(result))
            return 1

        subcmd = sys.argv[2]

        if subcmd == "add":
            if len(sys.argv) < 5:
                result = {"status": "error", "message": "Usage: todo add YYYY-MM-DD title [description]"}
                print(json.dumps(result))
                return 1
            desc = sys.argv[5] if len(sys.argv) >= 6 else ""
            todo_add(sys.argv[3], sys.argv[4], desc)

        elif subcmd == "list":
            todo_list_all()

        elif subcmd == "date":
            if len(sys.argv) < 4:
                result = {"status": "error", "message": "Usage: todo date YYYY-MM-DD"}
                print(json.dumps(result))
                return 1
            todo_list_by_date(sys.argv[3])

        elif subcmd == "complete":
            if len(sys.argv) < 4:
                result = {"status": "error", "message": "Usage: todo complete <id>"}
                print(json.dumps(result))
                return 1
            try:
                todo_complete(int(sys.argv[3]))
            except ValueError:
                result = {"status": "error", "message": "Invalid todo ID"}
                print(json.dumps(result))
                return 1

        elif subcmd == "delete":
            if len(sys.argv) < 4:
                result = {"status": "error", "message": "Usage: todo delete <id>"}
                print(json.dumps(result))
                return 1
            try:
                todo_delete(int(sys.argv[3]))
            except ValueError:
                result = {"status": "error", "message": "Invalid todo ID"}
                print(json.dumps(result))
                return 1

        elif subcmd == "edit":
            if len(sys.argv) < 5:
                result = {"status": "error", "message": "Usage: todo edit <id> title [description]"}
                print(json.dumps(result))
                return 1
            try:
                desc = sys.argv[5] if len(sys.argv) >= 6 else ""
                todo_edit(int(sys.argv[3]), sys.argv[4], desc)
            except ValueError:
                result = {"status": "error", "message": "Invalid todo ID"}
                print(json.dumps(result))
                return 1

        else:
            result = {"status": "error", "message": f"Unknown todo subcommand: {subcmd}"}
            print(json.dumps(result))
            return 1

    elif command == "calendar":
        # CALENDAR DATA — Aggregates alarms and todos for a month
        # OS Concept: Combines PID file (process tracking) and todo
        # file (persistent storage) for a unified view.
        if len(sys.argv) < 3:
            # Default to current month
            ym = time.strftime("%Y-%m", time.localtime())
        else:
            ym = sys.argv[2]
        get_calendar_data(ym)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
