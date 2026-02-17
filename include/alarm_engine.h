/*
 * alarm_engine.h — Modular Alarm & Reminder Engine
 * 
 * OS Concepts demonstrated:
 *   - Process creation: fork(), exec()
 *   - Process synchronization: waitpid(), SIGCHLD, SA_NOCLDWAIT
 *   - Time management: time(), mktime(), difftime(), localtime()
 *   - Timezone handling: setenv("TZ"), tzset()
 *   - Sleep/scheduling: sleep()
 *   - System calls: access(), execlp()
 */

#ifndef ALARM_ENGINE_H
#define ALARM_ENGINE_H

#include <stddef.h>

/* ── World Clock ────────────────────────────────────────────────
 * Queries the OS for current time in multiple timezones using
 * setenv("TZ", ...) + tzset() + localtime().
 * Outputs JSON to stdout.
 */
void get_world_clock_json(void);

/* ── Calendar-Based Alarm Scheduling ────────────────────────────
 * Parses "YYYY-MM-DD HH:MM" into struct tm, converts to UNIX
 * timestamp via mktime(), computes delay via difftime().
 * fork()s a child process that sleep()s and then calls play_sound().
 * Parent prevents zombies with SA_NOCLDWAIT on SIGCHLD.
 *
 * @param datetime  Target time string "YYYY-MM-DD HH:MM"
 * @param message   Reminder message to display
 * @param sound     Sound name (e.g. "glass", "ping", "hero")
 */
void schedule_alarm(const char *datetime, const char *message, const char *sound);

/* ── Cross-Platform Sound ───────────────────────────────────────
 * Plays a named sound using OS-specific tools:
 *   macOS  → afplay /System/Library/Sounds/<name>.aiff
 *   Linux  → aplay / paplay
 *   Fallback → printf("\a") terminal beep
 *
 * @param sound_name  One of: glass, ping, hero, purr, submarine, beep
 */
void play_sound(const char *sound_name);

/* ── Sound List ─────────────────────────────────────────────────
 * Prints available sound options as a JSON array to stdout.
 */
void list_sounds_json(void);

#endif /* ALARM_ENGINE_H */
