# Alarm & Reminder System — OS Task Scheduling Mini-Project

> **"Exploring How the Operating System Manages Time-Based Events and Process Triggers"**

![Python](https://img.shields.io/badge/Python-3.6%2B-blue?logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-14%2B-green?logo=node.js&logoColor=white)
![Express](https://img.shields.io/badge/Express.js-4.x-lightgrey?logo=express)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS-informational)
![License](https://img.shields.io/badge/License-Academic-orange)

An Operating Systems mini-project that implements a **miniature task scheduler** demonstrating how real operating systems handle process creation, scheduling, signal handling, timezone management, and background task execution — using a Python backend engine, Node.js bridge server, and modern web frontend.

---

## At a Glance

| | |
|---|---|
| **What it is** | An OS-concepts demonstration built as a working Alarm & Reminder web app |
| **Who it's for** | CS students learning Operating Systems (process management, scheduling, signals) |
| **Tech stack** | Python 3 (core engine) · Node.js/Express (server) · HTML/CSS/JS (frontend) |
| **Key features** | Schedule alarms, manage todos, view world clock, monthly calendar |
| **OS concepts** | `os.fork()`, `os.kill()`, `time.sleep()`, `os.execlp()`, signals, PID tracking |
| **Run it** | `make install-deps && make run` → open http://localhost:3000 |
| **Lines of code** | ~3,950 (Python: 1,042 · JS: 1,449 · CSS: 1,459) |
| **Dependencies** | Express.js, CORS — zero Python dependencies (stdlib only) |

---

## Table of Contents

1. [At a Glance](#at-a-glance)
2. [Architecture Overview](#architecture-overview)
3. [OS Concepts Demonstrated](#os-concepts-demonstrated)
4. [Calendar & Todo Module](#calendar--todo-module)
5. [Feature Implementation Map](#feature-implementation-map)
6. [Design Decisions & OS Rationale](#design-decisions--os-rationale)
7. [Project Structure](#project-structure)
8. [Setup Instructions](#setup-instructions)
9. [Run Instructions](#run-instructions)
10. [Testing Steps](#testing-steps)
11. [Debugging Workflow](#debugging-workflow)
12. [Shell Commands Used](#shell-commands-used)
13. [Process Inspection & Monitoring](#process-inspection--monitoring)
14. [Tooling Evidence & OS Learning](#tooling-evidence--os-learning)
15. [Known Limitations](#known-limitations)
16. [Future Work](#future-work)

---

## Architecture Overview

The system follows a **three-tier architecture** where each layer demonstrates distinct OS concepts:

```
┌─────────────────────────────┐
│     FRONTEND (Browser)      │    Layer 3: User Interface
│     HTML / CSS / JavaScript │    - Real-time clock display
│     - Alarm scheduling UI   │    - Browser notifications API
│     - Reminder management   │    - Web Audio API for sounds
│     - Calendar & todo view  │    - Calendar date navigation
│     - World clock display   │    - LocalStorage persistence
└──────────────┬──────────────┘
               │ HTTP (GET/POST JSON)
               ▼
┌─────────────────────────────┐
│     NODE.JS SERVER          │    Layer 2: Process Manager
│     Express.js :3000        │    - child_process.execFile()
│     - /api/worldclock       │    - Process spawning (fork+exec)
│     - /api/alarm            │    - Detached background tasks
│     - /api/sounds           │    - IPC via stdout pipes
│     - /api/cancel           │    - Health monitoring
│     - /api/active           │
│     - /api/status           │
│     - /api/calendar/:ym     │    - Calendar data aggregation
│     - /api/todo (CRUD)      │    - Todo management via file I/O
└──────────────┬──────────────┘
               │ fork() + exec() (via child_process)
               ▼
┌─────────────────────────────┐
│     PYTHON ALARM ENGINE     │    Layer 1: OS Interface
│     alarm_engine.py         │    - os.fork() → child processes
│     - worldclock command    │    - time.sleep() → kernel scheduler
│     - alarm command         │    - time.mktime() → time conversion
│     - sounds command        │    - os.environ["TZ"] → timezones
│     - list command          │    - os.kill() → signal handling
│     - cancel command        │    - os.execlp() → process replace
│     - status command        │    - os.access() → file checks
│     - todo command          │    - json file I/O → todo CRUD
│     - calendar command      │    - calendar module → date math
└──────────────┬──────────────┘
               │ System calls (via Python's os module)
               ▼
┌─────────────────────────────┐
│     OPERATING SYSTEM KERNEL │    Foundation
│     Process scheduler       │    - Timer interrupts
│     Memory manager          │    - Copy-on-write fork
│     Filesystem              │    - PID table management
│     Signal subsystem        │    - Zombie prevention
└─────────────────────────────┘
```

### Why This Architecture?

| Layer              | OS Concept Demonstrated | Rationale                                                                                                 |
| ------------------ | ----------------------- | --------------------------------------------------------------------------------------------------------- |
| **Python Engine**  | Direct system calls     | Shows raw OS interaction — os.fork(), os.exec\*(), signals — using Python's thin wrappers over POSIX APIs |
| **Node.js Server** | Process management      | Demonstrates how higher-level process managers (like systemd, cron) spawn and monitor child processes     |
| **Frontend**       | User-space application  | Shows how end-user applications communicate with OS services through well-defined APIs                    |

### How an Alarm Flows Through the System

```
1. User clicks "Schedule Alarm" → Frontend sends POST /api/alarm
2. Server receives request → calls execFile("python3", ["alarm_engine.py", "alarm", ...])
3. Python engine parses datetime → time.mktime() converts to UNIX timestamp
4. Python engine computes delay → target_time - time.time() = seconds to wait
5. Python engine checks for duplicates → reads PID file, os.kill(pid, 0) to verify
6. Python engine calls os.fork() → kernel creates child process (copy-on-write)
7. Parent returns JSON → { status: "success", child_pid: 12345 }
8. Child process calls time.sleep(delay) → kernel suspends process
9. Kernel timer interrupt fires → kernel moves child to READY state
10. Child wakes up → plays sound via os.execlp("afplay", ...)
11. Child unregisters PID → cleans up tracking file
12. Child calls os._exit(0) → kernel reaps process (SIGCHLD ignored)
```

---

## OS Concepts Demonstrated

| #   | OS Concept                  | Python API / System Call           | Where Used                                                                             | Why It Matters                                                              |
| --- | --------------------------- | ---------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| 1   | **Process Creation**        | `os.fork()`                        | [alarm_engine.py](src/alarm_engine.py) — `schedule_alarm()`                            | Each alarm becomes an independent process, just like how cron spawns jobs   |
| 2   | **Process Replacement**     | `os.execlp()`                      | [alarm_engine.py](src/alarm_engine.py) — `play_sound()`                                | Replaces child image with `afplay`, demonstrating the exec family           |
| 3   | **Zombie Prevention**       | `signal.signal(SIGCHLD, SIG_IGN)`  | [alarm_engine.py](src/alarm_engine.py) — `schedule_alarm()`                            | Prevents resource leaks from terminated child processes                     |
| 4   | **Process Waiting**         | `os.waitpid()`                     | [alarm_engine.py](src/alarm_engine.py) — `play_sound()`                                | Synchronous wait for sound playback completion                              |
| 5   | **Signal Sending**          | `os.kill(pid, signal.SIGTERM)`     | [alarm_engine.py](src/alarm_engine.py) — `cancel_alarm()`                              | Graceful process termination for alarm cancellation                         |
| 6   | **Process Existence Check** | `os.kill(pid, 0)`                  | [alarm_engine.py](src/alarm_engine.py) — `is_duplicate_alarm()`, `cleanup_dead_pids()` | Null signal to verify if a process is alive                                 |
| 7   | **Time Management**         | `time.time()`, `time.localtime()`  | [alarm_engine.py](src/alarm_engine.py) — `get_world_clock_json()`                      | Reading the kernel's system clock                                           |
| 8   | **Timezone Handling**       | `os.environ["TZ"]`, `time.tzset()` | [alarm_engine.py](src/alarm_engine.py) — `get_world_clock_json()`                      | Modifying process environment for timezone queries                          |
| 9   | **Calendar Conversion**     | `time.mktime()`                    | [alarm_engine.py](src/alarm_engine.py) — `schedule_alarm()`                            | Converting human-readable time to UNIX timestamp                            |
| 10  | **Time Difference**         | `target_time - time.time()`        | [alarm_engine.py](src/alarm_engine.py) — `schedule_alarm()`                            | Computing delay in seconds for safe scheduling                              |
| 11  | **Process Sleeping**        | `time.sleep()`                     | [alarm_engine.py](src/alarm_engine.py) — `schedule_alarm()`                            | Kernel scheduler suspends process until timer interrupt                     |
| 12  | **File Access Check**       | `os.access()`                      | [alarm_engine.py](src/alarm_engine.py) — `play_sound()`, `list_sounds_json()`          | Kernel-level file existence verification                                    |
| 13  | **Process IDs**             | `os.getpid()`, `os.getppid()`      | [alarm_engine.py](src/alarm_engine.py) — throughout                                    | Identifying processes in the PID namespace                                  |
| 14  | **File-based IPC**          | `open()`, `f.write()`, `f.read()`  | [alarm_engine.py](src/alarm_engine.py) — PID tracking functions                        | Inter-process communication via shared file (like PID files in `/var/run/`) |
| 15  | **Process Spawning**        | `child_process.execFile()`         | [server.js](server/server.js) — all API routes                                         | Node.js wrapper around fork()+exec()                                        |
| 16  | **Child Process Exit**      | `os._exit(0)`                      | [alarm_engine.py](src/alarm_engine.py) — child process                                 | Clean exit without flushing parent's stdio buffers                          |
| 17  | **File-based Persistence**  | `json.load()`, `json.dump()`       | [alarm_engine.py](src/alarm_engine.py) — todo CRUD functions                           | Persistent task storage via kernel VFS file I/O                             |
| 18  | **Calendar Computation**    | `calendar.monthrange()`            | [alarm_engine.py](src/alarm_engine.py) — `get_calendar_data()`                         | Date math for month layouts using stdlib                                    |

---

## Calendar & Todo Module

The calendar module provides a **visual layer over the task scheduling system**, demonstrating how OS-level scheduling maps to calendar-based task management.

### Architecture

```
┌──────────────────────────────────────────────┐
│              Calendar View (Browser)          │
│  ┌──────────┬──────────┬──────────┐          │
│  │ Mon      │ Tue      │ ...      │  Monthly │
│  │          │ ●○       │          │  Grid    │
│  │          │ 2 events │          │          │
│  └──────────┴──────────┴──────────┘          │
│         ↓ Click date                          │
│  ┌────────────────────────────────┐          │
│  │ Day Detail Panel               │          │
│  │  ⏰ Alarm:  Meeting (PID 123) │ ← Active │
│  │  🔔 Reminder: Call mom        │   process │
│  │  📋 Todo: Buy groceries  [✓]  │ ← File   │
│  │  [+ Add]                       │   stored  │
│  └────────────────────────────────┘          │
└──────────────┬───────────────────────────────┘
               │ HTTP API
               ▼
┌──────────────────────────────────────────────┐
│  GET /api/calendar/2026-02                    │
│  → python3 alarm_engine.py calendar "2026-02" │
│  → Reads PID file (active processes)          │
│  → Reads todo JSON file (persistent tasks)    │
│  → Returns unified calendar JSON              │
│                                               │
│  POST/PUT/DELETE /api/todo                    │
│  → python3 alarm_engine.py todo <subcommand>  │
│  → CRUD operations on /tmp/todos.json         │
└──────────────────────────────────────────────┘
```

### Two Types of Calendar Entries

| Type              | Storage                 | Scheduling                           | Lifecycle                              |
| ----------------- | ----------------------- | ------------------------------------ | -------------------------------------- |
| **Time Reminder** | PID file + localStorage | `os.fork()` → `time.sleep()` process | Background process; triggers at time   |
| **Date Todo**     | JSON file (persistent)  | No process — date-anchored task      | Persists until marked complete/deleted |

This distinction mirrors real OS concepts:

- **Reminders** = scheduled processes (like cron jobs) — they consume a kernel process slot and trigger at a specific time
- **Todos** = persistent data (like filesystem entries) — they exist as file data managed through I/O system calls

### OS Concepts in the Calendar Module

| Concept                | Implementation                                        | Why It Matters                                       |
| ---------------------- | ----------------------------------------------------- | ---------------------------------------------------- |
| **File I/O**           | `open()`, `json.load()`, `json.dump()` for todos      | Every read/write goes through the kernel's VFS layer |
| **Data Aggregation**   | Calendar reads both PID file and todo file            | Demonstrates reading multiple OS-level data sources  |
| **Process Inspection** | `os.kill(pid, 0)` to verify alarm processes are alive | Calendar reflects true process state, not stale data |
| **Calendar Math**      | `calendar.monthrange()` for month layout              | Standard library wrapping POSIX time functions       |

---

## Feature Implementation Map

This section maps each promised feature to its implementation location, showing that all kickoff features are visibly implemented:

| Proposed Feature             | Implementation Location                                                                                              | OS Concept Used                                          |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| **Alarm Scheduling**         | [alarm_engine.py → `schedule_alarm()`](src/alarm_engine.py)                                                          | `os.fork()`, `time.sleep()`, `time.mktime()`             |
| **Calendar Reminder System** | [script.js → `saveReminder()`](frontend/script.js), [server.js → `POST /api/alarm`](server/server.js)                | Same scheduling pipeline, with notes/metadata            |
| **Calendar Todo System**     | [alarm*engine.py → `todo*\*()`](src/alarm_engine.py), [script.js → calendar tab](frontend/script.js)                 | File I/O (`json.load/dump`), VFS kernel calls            |
| **Calendar View**            | [script.js → `renderCalendar()`](frontend/script.js), [alarm_engine.py → `get_calendar_data()`](src/alarm_engine.py) | Aggregates process table + file data                     |
| **World Clock**              | [alarm_engine.py → `get_world_clock_json()`](src/alarm_engine.py)                                                    | `os.environ["TZ"]`, `time.tzset()`, `time.localtime()`   |
| **Task Cancellation**        | [alarm_engine.py → `cancel_alarm()`](src/alarm_engine.py)                                                            | `os.kill(pid, signal.SIGTERM)`, `os.kill(pid, 0)`        |
| **Sound Triggering**         | [alarm_engine.py → `play_sound()`](src/alarm_engine.py)                                                              | `os.execlp("afplay")`, `os.access()`, `os.fork()`        |
| **Duplicate Prevention**     | [alarm_engine.py → `is_duplicate_alarm()`](src/alarm_engine.py)                                                      | `os.kill(pid, 0)`, file-based PID tracking               |
| **Active Process Listing**   | [alarm_engine.py → `list_active_alarms_json()`](src/alarm_engine.py)                                                 | PID file scanning + `os.kill(pid, 0)`                    |
| **Background Execution**     | [alarm_engine.py → child process](src/alarm_engine.py)                                                               | `os.fork()` → parent returns, child sleeps independently |
| **Zombie Prevention**        | [alarm_engine.py → `schedule_alarm()`](src/alarm_engine.py)                                                          | `signal.signal(SIGCHLD, SIG_IGN)`                        |
| **Multi-timezone Time**      | [alarm_engine.py → `get_world_clock_json()`](src/alarm_engine.py)                                                    | 8 IANA timezones via process environment manipulation    |

---

## Design Decisions & OS Rationale

### Why os.fork() instead of threads?

**Decision:** Each alarm runs as a separate child process created via `os.fork()`.

**OS Rationale:** Processes provide stronger isolation than threads. If one alarm crashes, it doesn't affect others. This mirrors how `cron` and `at(1)` create separate processes for each job. The kernel's copy-on-write optimization makes `fork()` efficient — child pages are only copied when modified. Python's `os.fork()` is a thin wrapper around the POSIX `fork()` system call.

### Why time.sleep() instead of timer signals?

**Decision:** The child process uses `time.sleep(delay)` to wait for the alarm time.

**OS Rationale:** `time.sleep()` puts the process into the SLEEPING state (S), removing it from the CPU run queue. The kernel's scheduler uses timer interrupts to track when to wake the process. This is the simplest and most portable approach, and directly demonstrates how the kernel manages process states (READY → RUNNING → SLEEPING → READY).

### Why signal.SIG_IGN instead of explicit waitpid()?

**Decision:** The parent sets `signal.signal(signal.SIGCHLD, signal.SIG_IGN)` instead of calling `os.waitpid()` in a loop.

**OS Rationale:** For a daemon-like process that spawns many children, a SIGCHLD handler with waitpid() adds complexity. Setting SIGCHLD to SIG_IGN tells the kernel to auto-reap children, preventing zombie accumulation. This is used in production servers like Apache and Nginx.

### Why file-based PID tracking?

**Decision:** Active alarm PIDs are stored in `/tmp/alarm_engine_pids.dat`.

**OS Rationale:** This mirrors how Unix daemons use PID files (`/var/run/sshd.pid`, `/var/run/nginx.pid`) for process management. The file acts as a simple IPC mechanism accessible by any process, enabling the `list` and `cancel` commands to inspect and control alarm processes across separate invocations.

### Why Python with os module?

**Decision:** The alarm engine is written in Python using the `os` module for direct system call access.

**OS Rationale:** Python's `os` module provides thin wrappers around POSIX system calls — `os.fork()`, `os.kill()`, `os.execlp()`, `os.waitpid()`, `os.access()`, `os.getpid()`, `os.getppid()`. This gives direct access to OS primitives while providing a more readable codebase. The Node.js server uses `child_process.execFile("python3", [...])` to invoke the engine, demonstrating the same fork+exec pattern.

---

## Project Structure

```
os_alarm_system/
├── Makefile                        # Build system with test, run targets
├── README.md                       # This file — project documentation
├── REPORT.md                       # IEEE-format project report
├── requirements.txt                # Python dependencies (stdlib only)
│
├── src/
│   └── alarm_engine.py             # Core engine: scheduling, sounds, timezones,
│                                   # PID tracking, duplicate prevention, cancellation
│
├── server/
│   ├── package.json                # Node.js dependencies (express, cors)
│   └── server.js                   # HTTP bridge: routes API calls to Python engine
│
├── frontend/
│   ├── index.html                  # UI: tabs for alarms, reminders, world clock
│   ├── script.js                   # Frontend logic: API calls, local state, audio
│   └── styles.css                  # Premium dark theme with animations
│
└── docs/
    └── ARCHITECTURE.md             # Detailed architecture & OS concepts guide
```

---

## Setup Instructions

### Prerequisites

- **Python 3.6+**: `python3 --version`
- **Node.js** (v14+): `node --version`
- **npm**: `npm --version`
- **macOS** (primary target) or **Linux**

### Step 1: Install Node.js Dependencies

```bash
# Install Express.js and CORS middleware
make install-deps
# Or manually:
cd server && npm install
```

### Step 2: Verify the Engine

```bash
# Test the engine CLI
python3 src/alarm_engine.py status
python3 src/alarm_engine.py worldclock
python3 src/alarm_engine.py sounds
```

---

## Run Instructions

### Option A: Full System (Recommended)

```bash
# Start everything with one command
make run
```

Then open **http://localhost:3000** in your browser.

### Option B: Manual Start

```bash
# Terminal 1: Start the server
cd server && npm start
```

### Option C: CLI Only (No Browser)

```bash
# World clock
python3 src/alarm_engine.py worldclock

# Schedule an alarm (use a future time)
python3 src/alarm_engine.py alarm "2026-03-01 14:30" "Team meeting" "glass"

# List active alarms
python3 src/alarm_engine.py list

# Cancel an alarm by PID
python3 src/alarm_engine.py cancel <PID>

# Test a sound
python3 src/alarm_engine.py test-sound hero
```

---

## Testing Steps

### Automated Test Suite

```bash
# Run all engine tests
make test
```

This runs:

1. **World Clock JSON** — Verifies timezone output is valid
2. **Sound List JSON** — Verifies sound enumeration
3. **Engine Status** — Verifies diagnostics output
4. **Active Alarms List** — Verifies PID tracking
5. **Cancel Invalid PID** — Verifies error handling for non-existent processes
6. **Past Time Rejection** — Verifies the engine rejects past datetimes

### Manual Testing Checklist

| #   | Test Case       | Command / Action                                                          | Expected Result                         |
| --- | --------------- | ------------------------------------------------------------------------- | --------------------------------------- |
| 1   | World clock     | `python3 src/alarm_engine.py worldclock`                                  | JSON with 8 timezone entries            |
| 2   | Sound list      | `python3 src/alarm_engine.py sounds`                                      | JSON with 8 sounds, availability flags  |
| 3   | Schedule alarm  | `python3 src/alarm_engine.py alarm "2026-12-25 09:00" "Christmas" "hero"` | Success JSON with child_pid             |
| 4   | List active     | `python3 src/alarm_engine.py list`                                        | Shows the scheduled alarm               |
| 5   | Duplicate check | Run same alarm command again                                              | Error: duplicate alarm                  |
| 6   | Cancel alarm    | `python3 src/alarm_engine.py cancel <pid>`                                | Success: process cancelled              |
| 7   | Past time       | `python3 src/alarm_engine.py alarm "2020-01-01 00:00" "test" "glass"`     | Error: past time rejected               |
| 8   | Play sound      | `python3 src/alarm_engine.py test-sound glass`                            | Audible glass chime                     |
| 9   | Server start    | `cd server && npm start`                                                  | Server on port 3000                     |
| 10  | Frontend load   | Open http://localhost:3000                                                | UI with 3 tabs, real-time clock         |
| 11  | UI alarm        | Click "Add Alarm", set future time, save                                  | Alarm appears in list, backend confirms |
| 12  | World clock tab | Click "World Clock" tab                                                   | 8 timezone cards with live times        |
| 13  | Cancel from UI  | Delete an alarm from the list                                             | Backend process killed                  |

### Process Verification During Testing

```bash
# While an alarm is sleeping, verify the child process:
ps aux | grep alarm_engine

# Check process state (S = sleeping):
ps -o pid,stat,command -p <child_pid>

# Monitor in real-time:
watch -n 1 'python3 src/alarm_engine.py list'
```

---

## Debugging Workflow

### Using Python Debugger (pdb)

```bash
# Start the Python debugger
python3 -m pdb src/alarm_engine.py alarm "2026-12-25 09:00" "Test" "glass"

# Set breakpoint at alarm scheduling
(Pdb) break schedule_alarm
(Pdb) continue

# Step through code
(Pdb) next          # Step over
(Pdb) step          # Step into
(Pdb) print(delay)  # Inspect variable

# Continue after fork — in child process
(Pdb) continue
```

### Key Debugging Scenarios

1. **Debugging os.fork():** Set a breakpoint after `os.fork()` and observe the PID returned — 0 in child, positive in parent
2. **Debugging time.sleep():** Verify the delay computation before `time.sleep()` is called
3. **Debugging time.mktime():** Inspect the `target_struct` to ensure correct parsing
4. **Debugging signals:** Check if `signal.SIG_IGN` is properly set on SIGCHLD before `os.fork()`

### stderr Logging

The engine outputs detailed logs to stderr (visible in terminal but not in JSON responses):

```bash
# Run and see debug logs
python3 src/alarm_engine.py alarm "2026-06-15 10:00" "Debug test" "glass"
# Output on stderr:
# [ALARM ENGINE] schedule_alarm() — Parent PID 12345
# [ALARM ENGINE] Alarm in 3600 seconds (60.0 minutes)
# [ALARM ENGINE] Registered PID 12346 in tracking file
# [ALARM ENGINE] Parent PID 12345 — alarm child spawned as PID 12346
# [ALARM ENGINE] Child PID 12346 (Parent PID 12345) — sleeping 3600 seconds...
```

---

## Shell Commands Used

These shell commands were used during development and demonstrate OS-level interaction:

| Command                                                 | Purpose                       | OS Concept                            |
| ------------------------------------------------------- | ----------------------------- | ------------------------------------- |
| `python3 src/alarm_engine.py worldclock`                | Query OS for timezone data    | Process execution, `os.environ["TZ"]` |
| `python3 src/alarm_engine.py alarm "..." "..." "..."`   | Schedule alarm via fork+sleep | `os.fork()`, `time.sleep()`           |
| `ps aux \| grep alarm_engine`                           | List running alarm processes  | Process table inspection              |
| `ps -o pid,ppid,stat,time,command -p <pid>`             | Detailed process state        | Process state (R/S/Z/T)               |
| `kill -TERM <pid>`                                      | Send termination signal       | Signal delivery                       |
| `kill -0 <pid>`                                         | Check if process exists       | Null signal for process verification  |
| `pgrep -lf alarm_engine`                                | Find processes by name        | Pattern-based process search          |
| `lsof -p <pid>`                                         | List open files/connections   | File descriptor inspection            |
| `strace python3 src/alarm_engine.py worldclock` (Linux) | Trace system calls            | Kernel call tracing                   |
| `dtruss python3 src/alarm_engine.py worldclock` (macOS) | Trace system calls            | macOS equivalent of strace            |
| `python3 -m pdb src/alarm_engine.py`                    | Interactive debugger          | Runtime inspection                    |
| `env TZ=Asia/Tokyo date`                                | Test timezone setting         | Environment variable effect           |

---

## Process Inspection & Monitoring

### Viewing Running Alarm Processes

```bash
# Using the engine's built-in list command
python3 src/alarm_engine.py list

# Using the API
curl http://localhost:3000/api/active | python3 -m json.tool

# Using standard Unix tools
ps -ef | grep alarm_engine
pgrep -la alarm_engine
```

### Monitoring Process States

```bash
# Watch process state changes in real-time
# S = sleeping (waiting for timer), R = running, Z = zombie
watch -n 1 'ps -o pid,ppid,stat,%cpu,%mem,etime,command | grep alarm_engine'
```

### Process Tree Visualization

```bash
# Show parent-child relationships
pstree -p $(pgrep -f "node server.js")

# macOS alternative
ps -axo pid,ppid,command | grep alarm
```

---

## Tooling Evidence & OS Learning

### Why Makefile?

The Makefile is not just a convenience — it demonstrates OS-level concepts:

- **Timestamp-based dependency tracking:** `make` uses the filesystem's `mtime` metadata (maintained by the kernel) to decide if targets need rebuilding
- **Phony targets:** `.PHONY` bypasses file existence checks, showing the difference between file-backed and non-file targets
- **Environment inheritance:** Make passes environment variables to child processes, demonstrating how `fork()` inherits the parent's environment

### Why Python's os module?

Python's `os` module provides direct access to POSIX system calls:

- **`os.fork()`** — Calls the kernel's `fork()` system call directly
- **`os.kill(pid, sig)`** — Calls the kernel's `kill()` system call
- **`os.execlp()`** — Calls the exec family of system calls
- **`os.waitpid()`** — Calls the kernel's `waitpid()` system call
- **`os.access()`** — Calls the kernel's `access()` system call
- **`os.getpid()`, `os.getppid()`** — Read from the kernel's process table

These are **not abstractions** — they are thin wrappers that behave identically to their C counterparts, making Python an effective tool for demonstrating OS concepts.

### Why pdb Debugging?

Debugging is essential for understanding OS behavior:

- **Breakpoints at os.fork():** Observe process duplication and PID assignment
- **Stepping through time.sleep():** See the process enter SLEEPING state
- **Signal inspection:** Verify SIGCHLD handling and zombie prevention
- **Variable inspection:** Watch delay computation and timestamp conversion

### Why Shell Commands?

Shell commands provide direct access to OS information:

- **`ps`**: Reads the kernel's process table (via `/proc` on Linux or `sysctl` on macOS)
- **`kill`**: Delivers signals through the kernel's signal subsystem
- **`strace`/`dtruss`**: Traces actual system calls made by the process — the raw interface between user-space and kernel-space
- **`lsof`**: Shows open file descriptors managed by the kernel's VFS layer

### Why Process Inspection?

Monitoring running processes verifies that our scheduling model works correctly:

- Confirming child processes are created with correct PIDs
- Verifying process states (SLEEPING during delay, RUNNING during alarm fire)
- Checking that zombie processes are prevented
- Ensuring cancelled processes are actually terminated

---

## Known Limitations

1. **Single-machine scope:** Alarms run as local processes — no distributed scheduling across machines
2. **sleep() granularity:** `time.sleep()` has second-level precision; sub-second timing requires different approaches
3. **No persistence across reboot:** Scheduled alarms (child processes) don't survive system restart, unlike cron which persists in crontab files
4. **Concurrent file access:** PID tracking file doesn't use `fcntl.flock()` for mutual exclusion — unlikely but possible race condition under very high load
5. **macOS sound dependency:** Sound playback via `afplay` is macOS-specific; Linux fallback may not have the same sound files
6. **No recurring alarms in Python engine:** Repeat/recurring logic is handled in the frontend; the Python engine handles one-shot scheduling
7. **Process limit:** Maximum 64 concurrent alarms (defined by `MAX_ACTIVE_ALARMS`)
8. **os.fork() on macOS:** Python's `os.fork()` works on macOS/Linux but is not available on Windows

---

## Future Work

1. **`signal.timer_settime()` integration:** Use POSIX timer API for kernel-level timer management
2. **`fcntl.flock()` file locking:** Mutual exclusion for PID file to handle concurrent writes safely
3. **`mmap` shared memory:** Replace file-based IPC with memory-mapped shared state for faster PID tracking
4. **`threading` module:** Thread-based alternative to demonstrate threading vs. forking tradeoffs
5. **Crontab-style persistence:** Save alarms to disk so they survive reboots (like real cron)
6. **`select`/`poll` file watching:** Monitor alarm config changes in real-time
7. **Signal handler chains:** Implement custom SIGTERM handler in child for graceful shutdown with cleanup
8. **Resource limits:** Use `resource.setrlimit()` to demonstrate OS resource management
9. **`multiprocessing` module:** Compare with os.fork() approach for educational purposes
10. **Container isolation:** Demonstrate namespace separation using Linux namespaces

---

## Authors

- **Aman Kumar** — B.Tech Computer Science and AI

---

## License

This project is created as an academic submission for the Operating Systems course.

---

_Built to demonstrate that alarms and reminders are fundamentally **OS-level scheduling problems** — every alarm is a process, every delay is a kernel timer, and every cancellation is a signal._
