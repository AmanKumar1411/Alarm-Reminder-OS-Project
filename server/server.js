/**
 * server.js — Node.js Bridge Server for Alarm & Reminder System
 *
 * This server bridges the HTML/CSS/JS frontend with the C alarm engine.
 * It demonstrates how a higher-level process manager can invoke
 * OS-level C programs using child_process (which internally uses
 * fork() + exec() system calls).
 *
 * OS Concepts demonstrated at this layer:
 *   - Process spawning via child_process.execFile / spawn
 *   - Detached background processes (daemon-like)
 *   - Process unreferencing (allows parent to exit independently)
 *   - Inter-process communication via stdout pipes
 */

const express = require('express');
const cors = require('cors');
const path = require('path');
const { execFile, spawn } = require('child_process');

const app = express();
const PORT = 3000;

/* Path to the compiled C alarm engine binary */
const ENGINE_PATH = path.resolve(__dirname, '..', 'alarm_engine');

app.use(cors());
app.use(express.json());

/* Serve the frontend as static files */
app.use(express.static(path.resolve(__dirname, '..', 'frontend')));

/* ================================================================
 *  GET /api/worldclock — World Clock
 *
 *  Invokes: ./alarm_engine worldclock
 *  The C engine uses setenv("TZ") + tzset() + localtime() to
 *  query the OS for time in multiple timezones.
 *  Returns JSON array of timezone data.
 * ================================================================ */
app.get('/api/worldclock', (req, res) => {
    execFile(ENGINE_PATH, ['worldclock'], { timeout: 5000 }, (error, stdout, stderr) => {
        if (stderr) {
            console.log('[Server] Engine log:', stderr.trim());
        }
        if (error) {
            console.error('[Server] worldclock error:', error.message);
            return res.status(500).json({ error: 'Failed to get world clock data' });
        }
        try {
            const data = JSON.parse(stdout);
            res.json(data);
        } catch (parseErr) {
            console.error('[Server] JSON parse error:', parseErr.message);
            res.status(500).json({ error: 'Invalid response from engine' });
        }
    });
});

/* ================================================================
 *  GET /api/sounds — List Available Sounds
 *
 *  Invokes: ./alarm_engine sounds
 *  The C engine uses access() to check file existence at OS level.
 *  Returns JSON array of sound options.
 * ================================================================ */
app.get('/api/sounds', (req, res) => {
    execFile(ENGINE_PATH, ['sounds'], { timeout: 5000 }, (error, stdout, stderr) => {
        if (stderr) {
            console.log('[Server] Engine log:', stderr.trim());
        }
        if (error) {
            console.error('[Server] sounds error:', error.message);
            return res.status(500).json({ error: 'Failed to get sounds list' });
        }
        try {
            const data = JSON.parse(stdout);
            res.json(data);
        } catch (parseErr) {
            res.status(500).json({ error: 'Invalid response from engine' });
        }
    });
});

/* ================================================================
 *  POST /api/alarm — Schedule a Calendar-Based Alarm
 *
 *  Body: { datetime: "YYYY-MM-DD HH:MM", message: "...", sound: "glass" }
 *
 *  Invokes: ./alarm_engine alarm "datetime" "message" "sound"
 *
 *  The C engine uses:
 *    - mktime() to convert to UNIX timestamp
 *    - difftime() to compute delay
 *    - fork() to create a background child process
 *    - sleep() for the child to wait
 *    - play_sound() with afplay/aplay/beep
 *    - SA_NOCLDWAIT on SIGCHLD to prevent zombies
 *
 *  The Node spawn is detached + unref'd so the alarm process
 *  runs independently even if the server restarts.
 * ================================================================ */
app.post('/api/alarm', (req, res) => {
    const { datetime, message, sound } = req.body;

    if (!datetime || !message) {
        return res.status(400).json({
            status: 'error',
            message: 'Missing required fields: datetime, message'
        });
    }

    const soundChoice = sound || 'glass';

    console.log(`[Server] Scheduling alarm: "${datetime}" msg="${message}" sound="${soundChoice}"`);

    /*
     * We use execFile first to get the immediate JSON response from
     * the engine (success/error). The C engine itself fork()s a child
     * that runs in the background, so the execFile returns quickly.
     */
    execFile(ENGINE_PATH, ['alarm', datetime, message, soundChoice],
        { timeout: 10000 },
        (error, stdout, stderr) => {
            if (stderr) {
                console.log('[Server] Engine log:', stderr.trim());
            }
            if (error) {
                console.error('[Server] alarm error:', error.message);
                return res.status(500).json({
                    status: 'error',
                    message: 'Failed to schedule alarm'
                });
            }
            try {
                const result = JSON.parse(stdout);
                console.log('[Server] Alarm result:', result);
                res.json(result);
            } catch (parseErr) {
                /* If parsing fails, return the raw output */
                res.json({ status: 'success', raw: stdout.trim() });
            }
        }
    );
});

/* ================================================================
 *  POST /api/cancel — Cancel a Scheduled Alarm Process
 *
 *  Body: { pid: <number> }
 *
 *  Invokes: ./alarm_engine cancel <PID>
 *  OS Concept: kills the specific child process using SIGTERM.
 * ================================================================ */
app.post('/api/cancel', (req, res) => {
    const { pid } = req.body;

    if (!pid) {
        return res.status(400).json({
            status: 'error',
            message: 'Missing required field: pid'
        });
    }

    console.log(`[Server] Cancelling alarm process PID ${pid}...`);

    execFile(ENGINE_PATH, ['cancel', String(pid)],
        { timeout: 5000 },
        (error, stdout, stderr) => {
            if (stderr) console.log('[Server] Engine log:', stderr.trim());
            
            if (error) {
                console.error('[Server] cancel error:', error.message);
                // Even if it fails (e.g. process already gone), we might want to tell frontend it's "done"
                return res.status(500).json({ status: 'error', message: 'Failed to cancel process' });
            }
            
            try {
                const result = JSON.parse(stdout);
                res.json(result);
            } catch (parseErr) {
                res.json({ status: 'success', raw: stdout.trim() });
            }
        }
    );
});

/* ================================================================
 *  GET /api/status — Server Health Check
 * ================================================================ */
app.get('/api/status', (req, res) => {
    const fs = require('fs');
    const engineExists = fs.existsSync(ENGINE_PATH);

    res.json({
        server: 'running',
        engine: engineExists ? 'available' : 'not found',
        enginePath: ENGINE_PATH,
        pid: process.pid,
        uptime: Math.floor(process.uptime()),
        platform: process.platform
    });
});

/* ================================================================
 *  Fallback — Serve index.html for SPA-like behavior
 * ================================================================ */
app.get('*', (req, res) => {
    res.sendFile(path.resolve(__dirname, '..', 'frontend', 'index.html'));
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

    /* Verify the C engine binary exists */
    const fs = require('fs');
    if (!fs.existsSync(ENGINE_PATH)) {
        console.warn('\n⚠️  WARNING: alarm_engine binary not found!');
        console.warn('   Run "make" in the project root to build it.\n');
    } else {
        console.log('✅ C alarm engine binary detected\n');
    }
});
