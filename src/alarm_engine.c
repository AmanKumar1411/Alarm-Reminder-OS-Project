/*
 * alarm_engine.c — Modular Alarm & Reminder Engine
 *
 * A command-line C program demonstrating core OS concepts:
 *   fork(), exec(), waitpid(), sleep(), signals (SIGCHLD),
 *   time(), mktime(), difftime(), setenv("TZ"), tzset(),
 *   access(), execlp(), system()
 *
 * Usage:
 *   ./alarm_engine worldclock
 *   ./alarm_engine alarm "YYYY-MM-DD HH:MM" "message" "sound"
 *   ./alarm_engine sounds
 *
 * Compile:
 *   make            (or: gcc src/alarm_engine.c -o alarm_engine)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <signal.h>
#include <sys/wait.h>

#include "../include/alarm_engine.h"

/* ================================================================
 *  WORLD CLOCK — Timezone handling via setenv("TZ") + tzset()
 * ================================================================ */

typedef struct {
    const char *tz;      /* IANA timezone identifier */
    const char *label;   /* Human-readable city name */
} timezone_entry_t;

static const timezone_entry_t TIMEZONES[] = {
    { "Asia/Kolkata",     "India (IST)"     },
    { "America/New_York", "New York (EST)"  },
    { "Europe/London",    "London (GMT)"    },
    { "Asia/Tokyo",       "Tokyo (JST)"     },
};
static const int NUM_TZ = sizeof(TIMEZONES) / sizeof(TIMEZONES[0]);

void get_world_clock_json(void) {
    time_t now = time(NULL);   /* OS system call: get current UNIX timestamp */

    printf("[\n");
    for (int i = 0; i < NUM_TZ; i++) {
        /*
         * OS Concept: setenv("TZ", ...) + tzset()
         * Modifies the process-level environment to switch the timezone
         * that localtime() uses, without affecting other processes.
         */
        setenv("TZ", TIMEZONES[i].tz, 1);
        tzset();

        struct tm *local = localtime(&now);  /* Convert to local time in new TZ */

        char time_str[9];   /* "HH:MM:SS" */
        char date_str[32];  /* "Weekday, Mon DD, YYYY" */
        strftime(time_str, sizeof(time_str), "%H:%M:%S", local);
        strftime(date_str, sizeof(date_str), "%A, %b %d, %Y", local);

        /* Compute UTC offset in hours */
        long utc_off = local->tm_gmtoff;
        int off_h = (int)(utc_off / 3600);
        int off_m = abs((int)((utc_off % 3600) / 60));
        char offset_str[16];
        snprintf(offset_str, sizeof(offset_str), "UTC%+d:%02d", off_h, off_m);

        printf("  {\"tz\":\"%s\", \"label\":\"%s\", \"time\":\"%s\", \"date\":\"%s\", \"offset\":\"%s\"}%s\n",
               TIMEZONES[i].tz, TIMEZONES[i].label,
               time_str, date_str, offset_str,
               (i < NUM_TZ - 1) ? "," : "");
    }
    printf("]\n");
    fflush(stdout);

    /* Restore default timezone */
    unsetenv("TZ");
    tzset();
}

/* ================================================================
 *  SOUND PLAYBACK — Cross-platform with OS-level file access checks
 * ================================================================ */

typedef struct {
    const char *name;
    const char *macos_file;   /* macOS system sound path */
    const char *description;
} sound_entry_t;

static const sound_entry_t SOUNDS[] = {
    { "glass",     "/System/Library/Sounds/Glass.aiff",     "Glass chime"      },
    { "ping",      "/System/Library/Sounds/Ping.aiff",      "Ping notification" },
    { "hero",      "/System/Library/Sounds/Hero.aiff",      "Hero fanfare"     },
    { "purr",      "/System/Library/Sounds/Purr.aiff",      "Gentle purr"      },
    { "submarine", "/System/Library/Sounds/Submarine.aiff", "Submarine sonar"  },
    { "basso",     "/System/Library/Sounds/Basso.aiff",     "Deep bass tone"   },
    { "funk",      "/System/Library/Sounds/Funk.aiff",      "Funky alert"      },
    { "pop",       "/System/Library/Sounds/Pop.aiff",       "Pop sound"        },
};
static const int NUM_SOUNDS = sizeof(SOUNDS) / sizeof(SOUNDS[0]);

void play_sound(const char *sound_name) {
    fprintf(stderr, "[ALARM ENGINE] play_sound(\"%s\") — PID %d\n", sound_name, getpid());

    /* Find the named sound */
    const char *filepath = NULL;
    for (int i = 0; i < NUM_SOUNDS; i++) {
        if (strcmp(sound_name, SOUNDS[i].name) == 0) {
            filepath = SOUNDS[i].macos_file;
            break;
        }
    }

    /*
     * Strategy 1: macOS — use afplay with system sound file
     * OS Concept: access() — check file existence at kernel level
     * OS Concept: execlp() — replace process image (exec family)
     */
    if (filepath != NULL && access(filepath, F_OK) == 0) {
        fprintf(stderr, "[ALARM ENGINE] Playing via afplay: %s\n", filepath);

        /* Fork a child to play sound so we can also speak the message */
        pid_t spid = fork();
        if (spid == 0) {
            execlp("afplay", "afplay", filepath, (char *)NULL);
            _exit(1);  /* exec failed */
        }
        if (spid > 0) {
            waitpid(spid, NULL, 0);  /* Wait for sound to finish */
        }
        return;
    }

    /*
     * Strategy 2: Linux — try paplay (PulseAudio) or aplay (ALSA)
     * OS Concept: access() to check if binaries exist in standard paths
     */
    if (access("/usr/bin/paplay", X_OK) == 0) {
        fprintf(stderr, "[ALARM ENGINE] Playing via paplay (Linux PulseAudio)\n");
        pid_t spid = fork();
        if (spid == 0) {
            /* Try common Linux notification sound path */
            execlp("paplay", "paplay",
                   "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
                   (char *)NULL);
            _exit(1);
        }
        if (spid > 0) waitpid(spid, NULL, 0);
        return;
    }

    if (access("/usr/bin/aplay", X_OK) == 0) {
        fprintf(stderr, "[ALARM ENGINE] Playing via aplay (Linux ALSA)\n");
        pid_t spid = fork();
        if (spid == 0) {
            execlp("aplay", "aplay",
                   "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
                   (char *)NULL);
            _exit(1);
        }
        if (spid > 0) waitpid(spid, NULL, 0);
        return;
    }

    /*
     * Strategy 3: Fallback — terminal beep
     * OS Concept: printf("\a") sends BEL character to terminal
     */
    fprintf(stderr, "[ALARM ENGINE] Fallback: terminal beep (\\a)\n");
    for (int i = 0; i < 3; i++) {
        printf("\a");
        fflush(stdout);
        usleep(500000);  /* 0.5 second between beeps */
    }
}

void list_sounds_json(void) {
    printf("[\n");
    for (int i = 0; i < NUM_SOUNDS; i++) {
        /* Check if the sound file actually exists on this system */
        int available = (access(SOUNDS[i].macos_file, F_OK) == 0);
        printf("  {\"name\":\"%s\", \"description\":\"%s\", \"available\":%s}%s\n",
               SOUNDS[i].name, SOUNDS[i].description,
               available ? "true" : "false",
               (i < NUM_SOUNDS - 1) ? "," : "");
    }
    printf("]\n");
    fflush(stdout);
}

/* ================================================================
 *  ALARM SCHEDULING — Calendar-based with fork(), mktime(), difftime()
 * ================================================================ */

void schedule_alarm(const char *datetime, const char *message, const char *sound) {
    fprintf(stderr, "[ALARM ENGINE] schedule_alarm() — Parent PID %d\n", getpid());

    /* ── Parse datetime string "YYYY-MM-DD HH:MM" into struct tm ── */
    struct tm target_tm;
    memset(&target_tm, 0, sizeof(target_tm));

    if (sscanf(datetime, "%d-%d-%d %d:%d",
               &target_tm.tm_year, &target_tm.tm_mon, &target_tm.tm_mday,
               &target_tm.tm_hour, &target_tm.tm_min) != 5) {
        printf("{\"status\":\"error\", \"message\":\"Invalid datetime format. Use YYYY-MM-DD HH:MM\"}\n");
        fflush(stdout);
        return;
    }

    /* struct tm uses year since 1900 and months 0-11 */
    target_tm.tm_year -= 1900;
    target_tm.tm_mon  -= 1;
    target_tm.tm_sec   = 0;
    target_tm.tm_isdst = -1;  /* Let the OS determine DST */

    /*
     * OS Concept: mktime()
     * Converts broken-down local time (struct tm) → UNIX timestamp (time_t).
     * The kernel's timezone data determines how local time maps to UTC.
     */
    time_t target_time = mktime(&target_tm);
    if (target_time == (time_t)-1) {
        printf("{\"status\":\"error\", \"message\":\"Failed to convert datetime to timestamp\"}\n");
        fflush(stdout);
        return;
    }

    /*
     * OS Concept: time()
     * System call to get the current UNIX timestamp from the kernel.
     */
    time_t now = time(NULL);

    /*
     * OS Concept: difftime()
     * Computes the difference between two time_t values in seconds.
     */
    double delay_secs = difftime(target_time, now);

    /* Safety: reject past times */
    if (delay_secs <= 0) {
        printf("{\"status\":\"error\", \"message\":\"Cannot set alarm in the past (%.0f seconds ago)\"}\n",
               -delay_secs);
        fflush(stdout);
        return;
    }

    unsigned int delay = (unsigned int)delay_secs;
    fprintf(stderr, "[ALARM ENGINE] Alarm in %u seconds (%.1f minutes)\n", delay, delay_secs / 60.0);

    /*
     * OS Concept: SIGCHLD + SA_NOCLDWAIT
     * Prevents zombie processes by telling the kernel to auto-reap
     * child processes when they exit.
     */
    struct sigaction sa;
    sa.sa_handler = SIG_DFL;
    sa.sa_flags = SA_NOCLDWAIT;   /* Prevent zombie child processes */
    sigemptyset(&sa.sa_mask);
    sigaction(SIGCHLD, &sa, NULL);

    /*
     * OS Concept: fork()
     * Creates a new child process. The child inherits the parent's
     * address space (copy-on-write). The child sleeps and then fires
     * the alarm, while the parent returns immediately.
     */
    pid_t pid = fork();

    if (pid < 0) {
        perror("[ALARM ENGINE] fork() failed");
        printf("{\"status\":\"error\", \"message\":\"Failed to create alarm process\"}\n");
        fflush(stdout);
        return;
    }

    if (pid == 0) {
        /* ── CHILD PROCESS ────────────────────────────────── */
        fprintf(stderr, "[ALARM ENGINE] Child PID %d — sleeping %u seconds...\n",
                getpid(), delay);

        /*
         * OS Concept: sleep()
         * Puts the process into a sleeping state. The kernel's process
         * scheduler suspends this process and resumes it after the
         * specified number of seconds, using timer interrupts.
         */
        sleep(delay);

        /* Alarm fires! */
        fprintf(stderr, "\n[ALARM ENGINE] ⏰ ALARM FIRED! PID %d\n", getpid());
        fprintf(stderr, "[ALARM ENGINE] Message: %s\n", message);

        /* Play the selected sound */
        play_sound(sound);

        /* Use macOS say command to speak the message */
        char say_cmd[512];
        snprintf(say_cmd, sizeof(say_cmd), "say 'Alarm: %s'", message);
        system(say_cmd);

        _exit(0);   /* Child process exits cleanly */
    }

    /* ── PARENT PROCESS ────────────────────────────────── */
    /* Parent returns immediately — child runs in background */
    fprintf(stderr, "[ALARM ENGINE] Parent PID %d — alarm child spawned as PID %d\n",
            getpid(), pid);

    char formatted_time[64];
    struct tm *ft = localtime(&target_time);
    strftime(formatted_time, sizeof(formatted_time), "%Y-%m-%d %H:%M", ft);

    printf("{\"status\":\"success\", \"message\":\"Alarm scheduled\", "
           "\"target\":\"%s\", \"delay_seconds\":%u, "
           "\"child_pid\":%d, \"sound\":\"%s\", \"alarm_message\":\"%s\"}\n",
           formatted_time, delay, pid, sound, message);
    fflush(stdout);
}

/* ================================================================
 *  MAIN — CLI dispatcher
 * ================================================================ */

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr,
            "Alarm & Reminder Engine — OS Concepts Demo\n"
            "\n"
            "Usage:\n"
            "  %s worldclock                              Show world clock (4 timezones)\n"
            "  %s alarm \"YYYY-MM-DD HH:MM\" \"msg\" \"sound\"  Schedule a calendar alarm\n"
            "  %s sounds                                  List available sounds\n"
            "  %s test-sound <name>                       Play a sound immediately (for testing)\n",
            argv[0], argv[0], argv[0], argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "worldclock") == 0) {
        get_world_clock_json();
    }
    else if (strcmp(argv[1], "alarm") == 0) {
        if (argc < 5) {
            fprintf(stderr, "Usage: %s alarm \"YYYY-MM-DD HH:MM\" \"message\" \"sound\"\n", argv[0]);
            printf("{\"status\":\"error\", \"message\":\"Missing arguments. Need: datetime, message, sound\"}\n");
            return 1;
        }
        schedule_alarm(argv[2], argv[3], argv[4]);
    }
    else if (strcmp(argv[1], "sounds") == 0) {
        list_sounds_json();
    }
    else if (strcmp(argv[1], "test-sound") == 0) {
        /*
         * CLI test mode — plays a named sound immediately via the OS.
         * Useful for verifying backend sound works independently of
         * the browser/frontend. Separates OS audio from browser audio.
         */
        const char *name = (argc >= 3) ? argv[2] : "glass";
        fprintf(stderr, "[TEST] Playing sound '%s' via OS...\n", name);
        play_sound(name);
        fprintf(stderr, "[TEST] Done.\n");
    }
    else if (strcmp(argv[1], "cancel") == 0) {
        /*
         * CANCEL ALARM — kills a background alarm process
         * Usage: ./alarm_engine cancel <PID>
         * OS Concept: kill() system call sends a signal to a process.
         */
        if (argc < 3) {
            fprintf(stderr, "Usage: %s cancel <PID>\n", argv[0]);
            printf("{\"status\":\"error\", \"message\":\"Missing PID\"}\n");
            return 1;
        }
        pid_t pid = atoi(argv[2]);
        if (pid <= 0) {
            printf("{\"status\":\"error\", \"message\":\"Invalid PID\"}\n");
            return 1;
        }

        /*
         * OS Concept: kill(pid, 0)
         * Sends signal 0 (null signal) to check if process exists
         * and we have permission to send signals to it.
         */
        if (kill(pid, 0) == -1) {
            perror("[ALARM ENGINE] check PID failed");
            printf("{\"status\":\"error\", \"message\":\"Process %d not found or access denied\"}\n", pid);
            return 1;
        }

        /*
         * OS Concept: kill(pid, SIGTERM)
         * Sends termination signal to the process.
         */
        if (kill(pid, SIGTERM) == 0) {
            fprintf(stderr, "[ALARM ENGINE] Killed PID %d\n", pid);
            printf("{\"status\":\"success\", \"message\":\"Process %d cancelled\"}\n", pid);
        } else {
            perror("[ALARM ENGINE] kill failed");
            printf("{\"status\":\"error\", \"message\":\"Failed to kill process %d\"}\n", pid);
            return 1;
        }
    }
    else {
        fprintf(stderr, "Unknown command: %s\n", argv[1]);
        return 1;
    }

    return 0;
}
