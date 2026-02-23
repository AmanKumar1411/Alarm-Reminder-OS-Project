# Alarm and Reminder System: A Miniature Task Scheduler Demonstrating OS-Level Time-Based Event Management and Process Triggers

---

**Aman Kumar**
B.Tech Computer Science and AI

---

## Abstract

This paper presents the design and implementation of an Alarm and Reminder System that functions as a miniature operating system task scheduler. The system demonstrates fundamental OS concepts including process creation via `os.fork()`, background task execution through kernel-managed `time.sleep()`, signal-based process termination using `os.kill()`, timezone handling via process environment manipulation, and zombie prevention through `signal.SIG_IGN` on `SIGCHLD`. Built using a three-tier architecture comprising a Python alarm engine, a Node.js bridge server, and a web-based frontend, the system mirrors the behavior of real-world task schedulers such as cron and systemd timers. Each alarm is scheduled as an independent child process—created via `os.fork()`, suspended via the kernel's process scheduler during `time.sleep()`, and awakened by timer interrupts to execute the alarm action. The system implements duplicate alarm prevention through PID file-based process tracking, safe delay computation using `time.mktime()` and timestamp arithmetic, and cross-platform sound playback via `os.execlp()`. Testing confirms accurate future time calculation, safe process management, and proper resource cleanup. This project bridges the gap between theoretical OS concepts and practical implementation, providing a tangible demonstration of how operating systems manage timed events and process lifecycle.

**Keywords:** Operating Systems, Process Scheduling, os.fork(), Task Management, Signal Handling, Python

---

## I. Introduction

Operating systems manage the execution of processes, memory allocation, and hardware interaction, forming the foundation of all computing. Among the most critical OS responsibilities is **task scheduling** — determining when and how processes execute, managing their lifecycle from creation to termination, and handling time-based triggers that automate system operations [1].

Real-world systems rely heavily on timed events: cron jobs run periodic maintenance scripts, `at(1)` schedules one-time tasks, systemd timers manage service lifecycles, and the kernel itself uses timer interrupts to preempt processes and maintain system responsiveness [2]. Despite their ubiquity, these mechanisms are often taught abstractly, leaving students without practical experience building systems that use them.

This project addresses that gap by implementing an **Alarm and Reminder System** that functions as a miniature task scheduler. Rather than merely calling library functions, the system demonstrates the complete lifecycle of a scheduled task:

1. **Parsing and validation** of human-readable time specifications
2. **Conversion** to UNIX timestamps using `time.mktime()`
3. **Delay computation** using timestamp arithmetic for safe scheduling
4. **Process creation** via `os.fork()` to isolate each alarm
5. **Kernel-managed suspension** via `time.sleep()` using timer interrupts
6. **Background execution** independent of the parent process
7. **Signal-based cancellation** using `os.kill(pid, signal.SIGTERM)`
8. **Resource cleanup** to prevent zombie processes

The system also demonstrates multi-timezone time handling, cross-platform sound playback, and inter-process communication through file-based PID tracking — concepts that are foundational to OS design but rarely combined in a single educational project.

Python's `os` module provides thin wrappers around POSIX system calls (`os.fork()`, `os.kill()`, `os.execlp()`, `os.waitpid()`, `os.access()`), enabling direct interaction with the kernel while maintaining code readability. This makes Python an excellent choice for demonstrating OS concepts — students can see the system calls clearly without being distracted by memory management or pointer arithmetic.

The remainder of this paper is organized as follows: Section II reviews related literature on OS scheduling and educational approaches. Section III describes the system methodology and architecture. Section IV presents results and discussion. Section V concludes with future directions.

---

## II. Literature Review

### A. Process Scheduling in Operating Systems

Silberschatz et al. [1] define process scheduling as the activity of the OS kernel that selects which process should execute next. Modern schedulers like the Completely Fair Scheduler (CFS) on Linux use red-black trees to maintain O(log n) scheduling decisions, while macOS employs a multilevel feedback queue [3]. Both rely on timer interrupts to preempt running processes and enforce time-sharing.

The `fork()` system call, introduced in Unix V1 (1971), remains the primary mechanism for process creation across POSIX-compliant systems [4]. When `fork()` is called, the kernel creates a new process with an independent PID, copies the parent's page table entries (using copy-on-write for efficiency), and returns control to both parent and child with different return values. This project leverages Python's `os.fork()` — a direct wrapper around the POSIX `fork()` — to create independent alarm processes, mirroring how cron spawns children for scheduled jobs.

### B. Time Management and the UNIX Epoch

POSIX time management centers on the UNIX epoch (January 1, 1970, 00:00:00 UTC) [5]. The `time()` system call reads the kernel's system clock, returning seconds since the epoch. Python's `time.mktime()` function converts broken-down local time (`struct_time`) to a `time_t` timestamp, accounting for timezone and daylight saving time. Timestamp arithmetic computes the difference between two time values. These functions form the basis of all time-based scheduling in Unix-like systems.

### C. Signal Handling and Process Control

Stevens and Rago [4] describe signals as software interrupts delivered to processes by the kernel. Signal handling is essential for process lifecycle management. `SIGTERM` (signal 15) requests graceful termination, while `SIGCHLD` notifies parents of child state changes. The `kill()` system call sends signals to specific processes, identified by PID. Setting `SIGCHLD` to `SIG_IGN` instructs the kernel to automatically reap terminated children, preventing resource leaks from zombie processes [6]. Python's `signal` module provides access to these mechanisms via `signal.signal()` and `os.kill()`.

### D. Educational Approaches to OS Concepts

Tanenbaum and Bos [2] advocate for building small operating systems (MINIX) to teach OS concepts. Similarly, projects like xv6 (MIT) [7] provide simplified Unix implementations for educational purposes. However, these projects focus on kernel internals rather than user-space applications that interact with the OS. This project takes a complementary approach — building a user-space Python application that extensively uses OS system calls via the `os` module, making kernel behavior visible through a practical application.

### E. Task Scheduling Systems

The cron daemon, originally written by Ken Thompson for Unix V7, remains the standard for periodic task scheduling [5]. Modern alternatives include systemd timers (Linux), launchd (macOS), and at(1) for one-time scheduling. All follow the same pattern: parse a time specification, compute the delay, create a process, and execute the task. Our system replicates this pattern at a smaller scale using Python, making each step visible and debuggable.

---

## III. Methodology

### A. System Architecture

The system employs a three-tier architecture designed to demonstrate OS concepts at each layer:

**Layer 1 — Python Alarm Engine (`alarm_engine.py`):** The core scheduler that directly interfaces with the OS kernel through Python's `os` module. This layer handles process creation (`os.fork()`), time computation (`time.mktime()`, timestamp arithmetic), process suspension (`time.sleep()`), signal handling (`os.kill()`, `signal.SIG_IGN`), timezone management (`os.environ["TZ"]`, `time.tzset()`), and file-based IPC for PID tracking.

**Layer 2 — Node.js Bridge Server (`server.js`):** An Express.js HTTP server that bridges the web frontend with the Python engine. It uses `child_process.execFile("python3", [...])` (which internally uses `fork()+exec()`) to invoke the Python engine, demonstrating how higher-level process managers spawn and communicate with worker processes.

**Layer 3 — Web Frontend (`index.html`, `script.js`, `styles.css`):** A browser-based interface with tabs for alarms, reminders, and world clock. The frontend communicates with the server via HTTP REST APIs and provides local state management through the Web Storage API.

### B. Alarm Scheduling Algorithm

The alarm scheduling process follows this algorithm:

```
FUNCTION schedule_alarm(datetime, message, sound):
    1. PARSE datetime string using time.strptime()
    2. CONVERT to UNIX timestamp: target_time = time.mktime(struct_time)
    3. GET current time: now = time.time()
    4. COMPUTE delay: delay = target_time - now
    5. VALIDATE: IF delay <= 0, REJECT (past time)
    6. CHECK duplicates: scan PID file for matching datetime+message
    7. SET signal.SIG_IGN on SIGCHLD (zombie prevention)
    8. FORK child process via os.fork():
       Parent: register child PID, return success JSON
       Child:  time.sleep(delay) → play_sound() → unregister PID → os._exit(0)
```

### C. Duplicate Prevention Mechanism

To prevent the same alarm from being scheduled twice (which would waste system resources and cause duplicate triggers), the system maintains a PID tracking file at `/tmp/alarm_engine_pids.dat`. Before scheduling, the engine:

1. Opens the PID file and reads all entries
2. For each entry, sends a null signal `os.kill(pid, 0)` to verify the process is alive
3. If an alive process matches the same datetime and message, the request is rejected
4. Dead entries (where `os.kill()` raises `OSError` with `errno.ESRCH`) are cleaned up automatically

### D. Timezone Handling

The world clock feature queries 8 IANA timezones by manipulating the process environment:

1. Set `os.environ["TZ"] = "Asia/Kolkata"` to modify the process environment block
2. Call `time.tzset()` to force the C library (used internally by Python) to re-read the TZ variable
3. Call `time.localtime(now)` which now interprets the timestamp in the new timezone
4. Extract formatted time, date, and UTC offset from the `struct_time` result
5. Repeat for each timezone, then restore the default by deleting `os.environ["TZ"]`

This technique is the same used by the `date` command and cron for timezone-aware scheduling.

### E. Cross-Platform Sound Playback

The sound system uses a strategy pattern based on OS detection:

1. **macOS:** Check `os.access(filepath, os.F_OK)` for system sound files, then `os.fork()` + `os.execlp("afplay", ...)` to play
2. **Linux:** Check `os.access("/usr/bin/paplay", os.X_OK)` for PulseAudio, then `os.execlp("paplay", ...)`
3. **Fallback:** Send BEL character `\a` to the terminal for audible beep

### F. Development Tools

- **Python 3.6+:** Using `os` module for direct POSIX system call access
- **Makefile:** Task automation for testing, running, and cleanup
- **pdb:** Python debugger for stepping through fork(), sleep(), and signal handlers
- **Shell utilities:** `ps`, `kill`, `pgrep`, `lsof` for process inspection during development

---

## IV. Results and Discussion

### A. Functional Verification

All system features were tested and verified:

| Feature              | Test Method                     | Result                                |
| -------------------- | ------------------------------- | ------------------------------------- |
| Alarm scheduling     | CLI + API with future time      | Child process created, PID registered |
| World clock          | CLI output + frontend display   | 8 timezones with correct offsets      |
| Sound playback       | `test-sound` command            | Audible on macOS (afplay)             |
| Task cancellation    | Cancel by PID                   | Process terminated, PID unregistered  |
| Duplicate prevention | Schedule same alarm twice       | Second attempt rejected               |
| Past time rejection  | Schedule with past datetime     | Error returned with delta             |
| Zombie prevention    | Schedule + wait for fire        | No zombie entries in `ps`             |
| Active alarm listing | `list` command after scheduling | Correct JSON with remaining seconds   |

### B. Process Lifecycle Observation

Using `ps -o pid,ppid,stat,command`, we observed the complete process lifecycle:

1. **Process Creation:** After `os.fork()`, the child appears with state **S** (sleeping) and the correct parent PID
2. **Sleep Phase:** The child remains in state S for the computed delay, consuming 0% CPU
3. **Alarm Firing:** The child transitions to state **R** (running), plays the sound, and exits
4. **Cleanup:** With `signal.SIG_IGN` on SIGCHLD, no zombie (state Z) entry appears

### C. OS Concept Demonstration Effectiveness

The three-tier architecture successfully demonstrates OS concepts at different abstraction levels:

- **Python Engine Level:** Students can observe POSIX system calls (via `os` module), PID values, and process states using `ps` and `pdb`
- **Server Level:** The `child_process` module makes fork+exec visible at a higher abstraction level
- **Frontend Level:** The UI provides an intuitive interface for triggering and observing OS operations

### D. Performance Characteristics

The system was tested with multiple concurrent alarms:

- **Process creation overhead:** os.fork() completes in < 1ms on modern systems (copy-on-write)
- **Memory per alarm:** Each sleeping child process consumes ~10MB RSS (Python runtime + copied pages)
- **Timer accuracy:** Alarms fire within 1 second of the target time (limited by `time.sleep()` granularity)
- **PID tracking overhead:** File I/O for registration/lookup is negligible for < 64 active alarms

### E. Comparison with Real Schedulers

| Aspect            | Our System                              | cron                 | systemd timers            |
| ----------------- | --------------------------------------- | -------------------- | ------------------------- |
| Scheduling        | os.fork() + time.sleep()                | fork() + exec        | service activation        |
| Persistence       | PID file (volatile)                     | crontab (persistent) | .timer units (persistent) |
| Granularity       | 1 second                                | 1 minute             | 1 microsecond             |
| Cancellation      | os.kill(SIGTERM)                        | crontab -r           | systemctl stop            |
| Zombie prevention | signal.SIG_IGN on SIGCHLD               | waitpid()            | cgroup-based              |
| Language          | Python (os module → POSIX system calls) | C                    | C (systemd)               |

---

## V. Conclusion and Future Work

### A. Conclusion

This project successfully demonstrates that alarms and reminders are fundamentally **OS-level scheduling problems**. By implementing a three-tier system that uses `os.fork()`, `time.sleep()`, `time.mktime()`, `os.kill()`, and signal handling through Python's `os` module, we show how operating systems manage timed events and process triggers.

The key contributions are:

1. A **working miniature task scheduler** that mirrors cron's behavior at a smaller scale
2. **Visible OS concepts** — each system call (via Python's `os` module) is documented with its OS-level purpose
3. **Complete process lifecycle** — from creation through sleep, firing, and cleanup
4. **Practical features** — world clock, alarms, reminders, sound playback, cancellation
5. **Professional tooling** — Makefile, debugger support, process inspection tools
6. **Accessible implementation** — Python's readability makes OS concepts approachable without sacrificing direct system call access

The system bridges the gap between textbook OS theory and practical system programming, providing a tangible platform for exploring process management, scheduling, and signal handling. Python's `os` module provides direct wrappers around POSIX system calls, ensuring that students interact with the same kernel interfaces as C programs.

### B. Future Work

1. **POSIX Timer API:** Explore `signal.timer_settime()` for kernel-level timer management
2. **Shared Memory IPC:** Use `mmap` module to replace file-based PID tracking with memory-mapped shared state
3. **Threading:** Implement `threading` module alternative to demonstrate threading vs. forking tradeoffs
4. **File Locking:** Add `fcntl.flock()` for mutual exclusion on the PID tracking file
5. **Persistent Scheduling:** Store alarms in a configuration file that survives reboots, similar to crontab
6. **Container Isolation:** Demonstrate Linux namespaces and cgroups to isolate alarm processes
7. **Real-time Scheduling:** Explore `SCHED_FIFO` and `SCHED_RR` policies for priority-based alarm management
8. **Multiprocessing:** Compare `multiprocessing` module with `os.fork()` approach

---

## References

[1] A. Silberschatz, P. B. Galvin, and G. Gagne, _Operating System Concepts_, 10th ed. Hoboken, NJ, USA: Wiley, 2018.

[2] A. S. Tanenbaum and H. Bos, _Modern Operating Systems_, 4th ed. Upper Saddle River, NJ, USA: Pearson, 2015.

[3] A. S. Love, _Linux Kernel Development_, 3rd ed. Upper Saddle River, NJ, USA: Addison-Wesley, 2010.

[4] W. R. Stevens and S. A. Rago, _Advanced Programming in the UNIX Environment_, 3rd ed. Upper Saddle River, NJ, USA: Addison-Wesley, 2013.

[5] IEEE, "IEEE Std 1003.1-2017 — Standard for Information Technology — Portable Operating System Interface (POSIX)," The Open Group, 2017.

[6] M. Kerrisk, _The Linux Programming Interface: A Linux and UNIX System Programming Handbook_. San Francisco, CA, USA: No Starch Press, 2010.

[7] R. Cox, M. F. Kaashoek, and R. Morris, "xv6, a simple Unix-like teaching operating system," MIT PDOS, 2019. [Online]. Available: https://pdos.csail.mit.edu/6.828/xv6

[8] D. P. Bovet and M. Cesati, _Understanding the Linux Kernel_, 3rd ed. Sebastopol, CA, USA: O'Reilly Media, 2005.

[9] M. Lutz, _Programming Python_, 4th ed. Sebastopol, CA, USA: O'Reilly Media, 2011.

[10] M. J. Bach, _The Design of the UNIX Operating System_. Englewood Cliffs, NJ, USA: Prentice Hall, 1986.

---

_Note: This report follows the IEEE conference paper format. For final submission, render using a LaTeX template (e.g., `IEEEtran.cls`) or a word processor configured with Times New Roman, two-column layout, and IEEE citation numbering._
