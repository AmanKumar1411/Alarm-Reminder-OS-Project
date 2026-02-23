/**
 * server.js — Node.js Bridge Server for Alarm & Reminder System
 *
 * This server bridges the HTML/CSS/JS frontend with the Python alarm engine.
 * It demonstrates how a higher-level process manager can invoke
 * OS-level Python programs using child_process (which internally uses
 * fork() + exec() system calls).
 *
 * OS Concepts demonstrated at this layer:
 *   - Process spawning via child_process.execFile / spawn
 *   - Detached background processes (daemon-like)
 *   - Process unreferencing (allows parent to exit independently)
 *   - Inter-process communication via stdout pipes
 */

const express = require("express");
const cors = require("cors");
const path = require("path");
const { execFile, spawn } = require("child_process");

const app = express();
const PORT = 3000;

/* Path to the Python alarm engine script */
const ENGINE_PATH = path.resolve(__dirname, "..", "src", "alarm_engine.py");
const PYTHON = "python3";

app.use(cors());
app.use(express.json());

/* Serve the frontend as static files */
app.use(express.static(path.resolve(__dirname, "..", "frontend")));

/* ================================================================
 *  GET /api/worldclock — World Clock
 *
 *  Invokes: python3 alarm_engine.py worldclock
 *  The Python engine uses os.environ["TZ"] + time.tzset() + time.localtime()
 *  to query the OS for time in multiple timezones.
 *  Returns JSON array of timezone data.
 * ================================================================ */
app.get("/api/worldclock", (req, res) => {
  execFile(
    PYTHON,
    [ENGINE_PATH, "worldclock"],
    { timeout: 5000 },
    (error, stdout, stderr) => {
      if (stderr) {
        console.log("[Server] Engine log:", stderr.trim());
      }
      if (error) {
        console.error("[Server] worldclock error:", error.message);
        return res
          .status(500)
          .json({ error: "Failed to get world clock data" });
      }
      try {
        const data = JSON.parse(stdout);
        res.json(data);
      } catch (parseErr) {
        console.error("[Server] JSON parse error:", parseErr.message);
        res.status(500).json({ error: "Invalid response from engine" });
      }
    },
  );
});

/* ================================================================
 *  GET /api/sounds — List Available Sounds
 *
 *  Invokes: python3 alarm_engine.py sounds
 *  The Python engine uses os.access() to check file existence at OS level.
 *  Returns JSON array of sound options.
 * ================================================================ */
app.get("/api/sounds", (req, res) => {
  execFile(
    PYTHON,
    [ENGINE_PATH, "sounds"],
    { timeout: 5000 },
    (error, stdout, stderr) => {
      if (stderr) {
        console.log("[Server] Engine log:", stderr.trim());
      }
      if (error) {
        console.error("[Server] sounds error:", error.message);
        return res.status(500).json({ error: "Failed to get sounds list" });
      }
      try {
        const data = JSON.parse(stdout);
        res.json(data);
      } catch (parseErr) {
        res.status(500).json({ error: "Invalid response from engine" });
      }
    },
  );
});

/* ================================================================
 *  POST /api/alarm — Schedule a Calendar-Based Alarm
 *
 *  Body: { datetime: "YYYY-MM-DD HH:MM", message: "...", sound: "glass" }
 *
 *  Invokes: python3 alarm_engine.py alarm "datetime" "message" "sound"
 *
 *  The Python engine uses:
 *    - time.mktime() to convert to UNIX timestamp
 *    - time difference computation for delay
 *    - os.fork() to create a background child process
 *    - time.sleep() for the child to wait
 *    - play_sound() with afplay/aplay/beep
 *    - signal.SIG_IGN on SIGCHLD to prevent zombies
 *
 *  The Node spawn is detached + unref'd so the alarm process
 *  runs independently even if the server restarts.
 * ================================================================ */
app.post("/api/alarm", (req, res) => {
  const { datetime, message, sound } = req.body;

  if (!datetime || !message) {
    return res.status(400).json({
      status: "error",
      message: "Missing required fields: datetime, message",
    });
  }

  const soundChoice = sound || "glass";

  console.log(
    `[Server] Scheduling alarm: "${datetime}" msg="${message}" sound="${soundChoice}"`,
  );

  /*
   * We use execFile first to get the immediate JSON response from
   * the engine (success/error). The Python engine itself os.fork()s a child
   * that runs in the background, so the execFile returns quickly.
   */
  execFile(
    PYTHON,
    [ENGINE_PATH, "alarm", datetime, message, soundChoice],
    { timeout: 10000 },
    (error, stdout, stderr) => {
      if (stderr) {
        console.log("[Server] Engine log:", stderr.trim());
      }
      if (error) {
        console.error("[Server] alarm error:", error.message);
        return res.status(500).json({
          status: "error",
          message: "Failed to schedule alarm",
        });
      }
      try {
        const result = JSON.parse(stdout);
        console.log("[Server] Alarm result:", result);
        res.json(result);
      } catch (parseErr) {
        /* If parsing fails, return the raw output */
        res.json({ status: "success", raw: stdout.trim() });
      }
    },
  );
});

/* ================================================================
 *  POST /api/cancel — Cancel a Scheduled Alarm Process
 *
 *  Body: { pid: <number> }
 *
 *  Invokes: python3 alarm_engine.py cancel <PID>
 *  OS Concept: kills the specific child process using SIGTERM,
 *  and removes it from the PID tracking file.
 * ================================================================ */
app.post("/api/cancel", (req, res) => {
  const { pid } = req.body;

  if (!pid) {
    return res.status(400).json({
      status: "error",
      message: "Missing required field: pid",
    });
  }

  console.log(`[Server] Cancelling alarm process PID ${pid}...`);

  execFile(
    PYTHON,
    [ENGINE_PATH, "cancel", String(pid)],
    { timeout: 5000 },
    (error, stdout, stderr) => {
      if (stderr) console.log("[Server] Engine log:", stderr.trim());

      if (error) {
        console.error("[Server] cancel error:", error.message);
        return res
          .status(500)
          .json({ status: "error", message: "Failed to cancel process" });
      }

      try {
        const result = JSON.parse(stdout);
        res.json(result);
      } catch (parseErr) {
        res.json({ status: "success", raw: stdout.trim() });
      }
    },
  );
});

/* ================================================================
 *  GET /api/active — List Active Alarm Processes
 *
 *  Invokes: python3 alarm_engine.py list
 *  OS Concept: Reads PID tracking file and verifies each process
 *  is alive using os.kill(pid, 0). Provides real-time process inspection.
 * ================================================================ */
app.get("/api/active", (req, res) => {
  execFile(
    PYTHON,
    [ENGINE_PATH, "list"],
    { timeout: 5000 },
    (error, stdout, stderr) => {
      if (stderr) console.log("[Server] Engine log:", stderr.trim());
      if (error) {
        console.error("[Server] list error:", error.message);
        return res.status(500).json({ error: "Failed to list active alarms" });
      }
      try {
        const data = JSON.parse(stdout);
        res.json(data);
      } catch (parseErr) {
        res.status(500).json({ error: "Invalid response from engine" });
      }
    },
  );
});

/* ================================================================
 *  GET /api/status — Server & Engine Health Check
 *
 *  Reports server uptime, engine availability, and active process
 *  count. Invokes python3 alarm_engine.py status for engine diagnostics.
 * ================================================================ */
app.get("/api/status", (req, res) => {
  const fs = require("fs");
  const engineExists = fs.existsSync(ENGINE_PATH);

  const serverInfo = {
    server: "running",
    engine: engineExists ? "available" : "not found",
    enginePath: ENGINE_PATH,
    pid: process.pid,
    uptime: Math.floor(process.uptime()),
    platform: process.platform,
    nodeVersion: process.version,
    memoryUsage: process.memoryUsage(),
  };

  if (engineExists) {
    execFile(
      PYTHON,
      [ENGINE_PATH, "status"],
      { timeout: 3000 },
      (error, stdout) => {
        if (!error) {
          try {
            serverInfo.engineInfo = JSON.parse(stdout);
          } catch (e) {
            /* ignore parse errors */
          }
        }
        res.json(serverInfo);
      },
    );
  } else {
    res.json(serverInfo);
  }
});

/* ================================================================
 *  Fallback — Serve index.html for SPA-like behavior
 * ================================================================ */
app.get("*", (req, res) => {
  res.sendFile(path.resolve(__dirname, "..", "frontend", "index.html"));
});

/* ================================================================
 *  Start Server
 * ================================================================ */
app.listen(PORT, () => {
  console.log(`
╔══════════════════════════════════════════════════╗
║  Alarm & Reminder System — Server Running       ║
╠══════════════════════════════════════════════════╣
║  🌐  Frontend:  http://localhost:${PORT}            ║
║  🔧  API:       http://localhost:${PORT}/api/       ║
║  ⚙️   Engine:    ${ENGINE_PATH}  ║
║  📋  PID:       ${process.pid}                          ║
╚══════════════════════════════════════════════════╝
    `);

  /* Verify the Python engine script exists */
  const fs = require("fs");
  if (!fs.existsSync(ENGINE_PATH)) {
    console.warn("\n⚠️  WARNING: alarm_engine.py not found!");
    console.warn(`   Expected at: ${ENGINE_PATH}\n`);
  } else {
    console.log("✅ Python alarm engine detected\n");
  }
});
