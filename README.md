# Alarm & Reminder System ⏰

An Operating Systems mini-project demonstrating **process management**, **scheduling**, **timezone handling**, and **system calls** — with a C backend engine, Node.js bridge server, and a modern web frontend.

## Architecture

```
┌──────────────────────┐       HTTP        ┌────────────────────┐     fork/exec     ┌──────────────────┐
│   Frontend (Browser) │ ◄──────────────► │  Node.js Server    │ ◄──────────────► │  C Alarm Engine  │
│   HTML / CSS / JS    │   GET/POST /api   │  Express :3000     │  child_process    │  alarm_engine    │
│   - World Clock Tab  │                   │  - Static files    │                   │  - worldclock    │
│   - Alarms Tab       │                   │  - /api/worldclock │                   │  - alarm         │
│   - Reminders Tab    │                   │  - /api/alarm      │                   │  - sounds        │
└──────────────────────┘                   │  - /api/sounds     │                   └──────┬───────────┘
                                           └────────────────────┘                          │
                                                                                    OS Kernel
                                                                              fork() sleep() waitpid()
                                                                              setenv("TZ") tzset()
                                                                              mktime() difftime()
                                                                              execlp() access()
```

## OS Concepts Demonstrated

| Concept | System Call / API | Where Used |
|---------|------------------|------------|
| Process Creation | `fork()` | Alarm scheduling — child process sleeps then fires alarm |
| Process Replacement | `execlp()` | Sound playback — replaces child process with `afplay` |
| Zombie Prevention | `SA_NOCLDWAIT` + `SIGCHLD` | Parent prevents zombie processes after child exits |
| Process Waiting | `waitpid()` | Sound playback waits for afplay to finish |
| Time Management | `time()`, `localtime()` | Getting current UNIX timestamp from kernel |
| Timezone Handling | `setenv("TZ")`, `tzset()` | World clock switches process timezone for each query |
| Calendar Conversion | `mktime()` | Converts `struct tm` (date/time) → UNIX timestamp |
| Time Difference | `difftime()` | Calculates seconds until alarm should fire |
| File Access Check | `access()` | Checks if sound files exist before playing |
| Sleep Scheduling | `sleep()` | Child process suspended by kernel scheduler |
| Terminal I/O | `printf("\a")` | Fallback beep when no sound system available |
| System Command | `system()` | macOS `say` command for text-to-speech |

## Features

1. **World Clock** — Displays time in 4 timezones (India, New York, London, Tokyo) using OS-level `setenv("TZ")` + `tzset()`
2. **Calendar Reminders** — Set alarms by date & time, converted to UNIX timestamps via `mktime()` / `difftime()`
3. **Multiple Sounds** — Choose from 8 macOS system sounds, with Linux and terminal beep fallbacks
4. **Frontend ↔ Backend** — Real HTTP API integration; frontend sends requests, backend spawns C processes

## Project Structure

```
os_alarm_system/
├── Makefile                    # Build the C engine
├── alarm_engine                # Compiled binary (after make)
├── include/
│   ├── alarm.h                 # Original header (preserved)
│   └── alarm_engine.h          # New modular engine header
├── src/
│   ├── main.c                  # Original alarm (preserved)
│   └── alarm_engine.c          # New modular C engine
├── server/
│   ├── package.json            # Node.js dependencies
│   └── server.js               # Express bridge server
└── frontend/
    ├── index.html              # UI with 3 tabs
    ├── script.js               # API integration logic
    └── styles.css              # Premium dark theme
```

## How to Run

### 1. Build the C Engine
```bash
cd /path/to/os_alarm_system
make
```

### 2. Test the C Engine (CLI)
```bash
# World clock — prints timezone JSON
./alarm_engine worldclock

# List available sounds
./alarm_engine sounds

# Schedule an alarm (replace with a future time)
./alarm_engine alarm "2026-02-14 18:00" "Team meeting" "glass"
```

### 3. Start the Server
```bash
cd server
npm install      # First time only
npm start        # Starts on http://localhost:3000
```

### 4. Open the Frontend
Open **http://localhost:3000** in your browser.

- **World Clock tab** → Live timezone data from the C engine
- **Add Alarm** → Schedules via backend with `fork()` + `sleep()`
- **Add Reminder** → Same backend scheduling with sound selection

---
*Created as an Operating Systems Mini Project — demonstrating process management, scheduling, system calls, and background execution.*
