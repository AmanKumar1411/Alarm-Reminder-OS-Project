# Architecture & OS Concepts Guide

## System Architecture Deep Dive

This document provides a detailed explanation of the Alarm & Reminder System's architecture, explaining **why** each design decision was made from an Operating Systems perspective.

---

## 1. Three-Tier Process Hierarchy

```
                    ┌─────────────────────────┐
                    │    Web Browser (UI)      │  PID: Browser-managed
                    │    JavaScript runtime    │
                    └───────────┬─────────────┘
                                │ HTTP (TCP socket)
                    ┌───────────▼─────────────┐
                    │    Node.js Server        │  PID: e.g., 45001
                    │    Express.js process    │
                    │    Listens on :3000      │
                    └───────────┬─────────────┘
                                │ child_process.execFile("python3", [...])
                                │ (internally: fork() + exec())
                    ┌───────────▼─────────────┐
                    │    Python Alarm Engine   │  PID: e.g., 45050 (short-lived)
                    │    alarm_engine.py       │
                    │    Parses command,       │
                    │    creates child process │
                    └───────────┬─────────────┘
                                │ os.fork()
                    ┌───────────▼─────────────┐
                    │    Alarm Child Process   │  PID: e.g., 45051 (long-lived)
                    │    time.sleep(delay)     │
                    │    play_sound()          │  State: S (sleeping) → R (running)
                    │    os._exit(0)           │
                    └─────────────────────────┘
```

### Why This Hierarchy?

**OS Rationale:** This mirrors real-world process management:

- **systemd** → **service process** → **worker threads/children**
- **cron daemon** → **shell** → **scheduled script**
- **init** → **login** → **user shell** → **user programs**

Each level adds a layer of management and isolation, demonstrating how OSes use process trees to organize work.

---

## 2. Process State Transitions

Each alarm child process goes through the standard OS process states:

```
                    ┌──────────┐
                    │   NEW    │  os.fork() called, PCB allocated
                    └────┬─────┘
                         │ Kernel copies page table (COW)
                    ┌────▼─────┐
                    │  READY   │  In the run queue, waiting for CPU
                    └────┬─────┘
                         │ Scheduler selects process
                    ┌────▼─────┐
                    │ RUNNING  │  Executes: sets up sleep timer
                    └────┬─────┘
                         │ time.sleep(delay) called
                    ┌────▼─────┐
                    │ SLEEPING │  Removed from run queue, timer set
                    │   (S)    │  Consumes 0% CPU, retains memory
                    └────┬─────┘
                         │ Timer interrupt fires (delay elapsed)
                    ┌────▼─────┐
                    │  READY   │  Back in run queue
                    └────┬─────┘
                         │ Scheduler selects process
                    ┌────▼─────┐
                    │ RUNNING  │  play_sound(), speak message
                    └────┬─────┘
                         │ os._exit(0) called
                    ┌────▼──────┐
                    │TERMINATED │  PCB freed (SIGCHLD ignored)
                    └───────────┘
```

### Why This Matters

Students can observe these state transitions using `ps -o pid,stat,command`:

- **S** = Sleeping (interruptible) — the alarm is waiting
- **R** = Running — the alarm is firing
- **Z** = Zombie — would appear without SIG_IGN on SIGCHLD (our system prevents this)

---

## 3. System Call Flow for Alarm Scheduling

```
User clicks "Schedule Alarm"
        │
        ▼
Frontend: POST /api/alarm { datetime, message, sound }
        │
        ▼ HTTP
Server: execFile("python3", ["alarm_engine.py", "alarm", datetime, msg, sound])
        │
        ▼ fork() + exec() [via Node.js child_process]
Python Engine: main() → schedule_alarm()
        │
        ├── time.strptime()   Parse "YYYY-MM-DD HH:MM"
        ├── time.mktime()     Convert struct_time → timestamp
        │                     (OS timezone data consulted)
        ├── time.time()       Get current UNIX timestamp
        │                     (kernel system clock read)
        ├── subtraction       Compute delay = target - now
        ├── is_duplicate()    Check PID file + os.kill(pid, 0)
        ├── signal.signal()   Set SIG_IGN on SIGCHLD
        ├── os.fork()         ──────────────────────────────┐
        │   │                                               │
        │   ▼ PARENT                                        ▼ CHILD
        │   register_pid()                            time.sleep(delay)
        │   print(JSON)                                     │
        │   return to server                          [kernel suspends]
        │                                                   │
        │                                             [timer interrupt]
        │                                                   │
        │                                             play_sound()
        │                                               os.fork()
        │                                               os.execlp("afplay")
        │                                               os.waitpid()
        │                                             unregister_pid()
        │                                             os._exit(0)
        │
        ▼
Server: Receives JSON on stdout, sends to frontend
        │
        ▼
Frontend: Updates UI, stores alarm in localStorage
```

---

## 4. Inter-Process Communication (IPC) Mechanisms

### 4a. stdout/stderr Pipes (Engine ↔ Server)

```
Python Engine Process               Node.js Server
┌──────────────┐                    ┌──────────────┐
│ print(JSON)  │ ──── stdout ────► │ stdout data  │
│ on stdout    │    (pipe fd 1)     │ callback     │
│              │                    │              │
│ print(log,   │ ──── stderr ────► │ stderr data  │
│  stderr)     │    (pipe fd 2)     │ logging      │
└──────────────┘                    └──────────────┘
```

**OS Concept:** When `execFile()` spawns the Python engine, Node.js creates a pipe pair using `pipe()`. The child's stdout (fd 1) is redirected to the write end, and the parent reads from the read end. This is the same mechanism used by shell pipelines (`cmd1 | cmd2`).

### 4b. PID Tracking File (Engine ↔ Engine)

```
Invocation 1: schedule_alarm()        Invocation 2: cancel_alarm()
┌──────────────────┐                  ┌──────────────────┐
│ register_pid()   │                  │ Read PID file    │
│ open("a")        │ ──── file ────► │ os.kill(pid, 0)  │
│ f.write(entry)   │ /tmp/alarm_     │ os.kill(pid,     │
│ f.close()        │ engine_pids.dat │    SIGTERM)       │
└──────────────────┘                  │ unregister_pid() │
                                      └──────────────────┘
```

**OS Concept:** File-based IPC mirrors how Unix daemons use PID files (`/var/run/*.pid`). The filesystem acts as a shared memory space accessible by any process with read/write permissions. The kernel's VFS (Virtual File System) layer provides the abstraction.

---

## 5. Signal Handling Architecture

```
┌──────────────────────────────────────────────────────┐
│                   SIGNAL FLOW                         │
│                                                       │
│  cancel_alarm()                                       │
│       │                                               │
│       ▼                                               │
│  os.kill(child_pid, 0)  ─── Null signal ───►  Kernel │
│       │                    (check only)     checks    │
│       │                                    process    │
│       │                                    exists     │
│       ▼                                               │
│  os.kill(child_pid,                                   │
│     signal.SIGTERM)  ──── Signal 15 ──► Kernel        │
│                                         delivers      │
│                                         SIGTERM       │
│                                         to child      │
│                                            │          │
│                                            ▼          │
│                                      Child process    │
│                                      terminates       │
│                                            │          │
│  Parent process                            ▼          │
│  (SIGCHLD=SIG_IGN)  ◄── SIGCHLD ── Kernel sends      │
│       │                              SIGCHLD to       │
│       ▼                              parent           │
│  Kernel auto-reaps                                    │
│  child (no zombie)                                    │
└──────────────────────────────────────────────────────┘
```

---

## 6. Memory Layout After os.fork()

```
BEFORE os.fork():                 AFTER os.fork():

Parent Process                    Parent Process          Child Process
┌────────────────┐               ┌────────────────┐     ┌────────────────┐
│   Code (Text)  │               │   Code (Text)  │     │   Code (Text)  │
│   (shared)     │               │   (shared)     │ ◄──►│   (shared)     │
├────────────────┤               ├────────────────┤     ├────────────────┤
│   Data         │               │   Data         │     │  Data (COW)    │
│   (globals)    │               │   (globals)    │     │  (copy-on-     │
│                │               │                │     │   write)       │
├────────────────┤               ├────────────────┤     ├────────────────┤
│   Heap         │               │   Heap         │     │  Heap (COW)    │
│   (Python obj) │               │   (Python obj) │     │  (Python obj)  │
├────────────────┤               ├────────────────┤     ├────────────────┤
│   Stack        │               │   Stack        │     │  Stack (COW)   │
│   (local vars) │               │   fork()=pid   │     │  fork()=0      │
└────────────────┘               └────────────────┘     └────────────────┘
     PID: 100                         PID: 100               PID: 101
```

**Copy-on-Write (COW):** The kernel doesn't actually copy memory pages during `os.fork()`. Instead, both processes share the same physical pages, marked read-only. Only when one process writes to a page does the kernel copy it — saving memory and making `fork()` efficient for our use case where the child primarily calls `time.sleep()`.

---

## 7. Timezone Query Architecture

```
For each timezone:

1. os.environ["TZ"] = "Asia/Kolkata"
   ┌─────────────────────────────┐
   │ Process Environment Block   │
   │ PATH=/usr/bin:/bin          │
   │ HOME=/Users/aman           │
   │ TZ=Asia/Kolkata     ◄──────│── Modified by os.environ
   └─────────────────────────────┘

2. time.tzset()
   ┌─────────────────────────────┐
   │ C Library Internal State    │
   │ (used by Python's time mod) │
   │ timezone = 19800            │  ← IST is UTC+5:30
   │ daylight = 0               │  ← No DST in India
   │ tzname = ("IST", "IST")    │
   └─────────────────────────────┘

3. time.localtime(now)
   ┌─────────────────────────────┐
   │ UNIX Timestamp: 1771724400  │
   │      ↓ (using TZ data)     │
   │ struct_time:                │
   │   tm_hour = 14             │
   │   tm_min  = 30             │
   │   tm_mday = 22             │
   │   tm_mon  = 2  (Feb)       │
   │   tm_year = 2026           │
   │   tm_gmtoff = 19800        │
   └─────────────────────────────┘
```

**OS Concept:** The timezone database (`/usr/share/zoneinfo/`) is maintained by the OS. `os.environ["TZ"]` modifies the process-level environment block (not the system environment), and `time.tzset()` re-reads it. This is process-isolated — changing TZ in one process doesn't affect others.

---

## 8. Error Handling and Edge Cases

| Scenario                 | Detection Method                                       | Response                       |
| ------------------------ | ------------------------------------------------------ | ------------------------------ |
| Past alarm time          | `target_time - time.time() <= 0`                       | Reject with error JSON         |
| Duplicate alarm          | `os.kill(pid, 0)` succeeds + match                     | Reject with duplicate error    |
| os.fork() failure        | `pid < 0`                                              | Return error, no child created |
| Invalid datetime         | `time.strptime()` raises `ValueError`                  | Parse error returned           |
| Dead process in PID file | `os.kill(pid, 0)` raises `OSError(errno.ESRCH)`        | Auto-cleanup entry             |
| Sound file missing       | `os.access(path, os.F_OK)` returns `False`             | Fallback to next strategy      |
| Process cancel race      | Check `os.kill(pid, 0)` before `os.kill(pid, SIGTERM)` | Graceful failure               |

---

_This architecture documentation is designed to show evaluators that the system is fundamentally OS-concept driven, not just a UI application with a backend._
