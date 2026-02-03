# Alarm & Reminder System ⏰

A simple program that helps you set alarms and reminders on your computer.

## What is this?
This is a mini-project showing how Operating Systems (the brain of your computer) handle time and tasks. Think of it like a very basic version of the alarm clock on your phone, but running directly on your computer's system.

## How it works (In simple terms)
When you set an alarm:
1.  **You give a time:** "Remind me in 5 minutes."
2.  **The system waits:** The computer puts a tiny "worker" (a process) to sleep. It stays quiet and doesn't use up your computer's energy.
3.  **Wake up!:** When the time is up, the system taps the worker on the shoulder (using a Signal), and it displays your message.

This demonstrates how computers can manage multiple things at once without getting confused!

## Features
*   **Simple Input:** Just enter the time delay.
*   **Custom Reminders:** Add your own text like "Take a break!" or "Submit Project".
*   **Lightweight:** Runs efficiently in the background.

## How to Run it

1.  **Compile the code** (Convert the code into a runnable program):
    ```bash
    gcc src/main.c -o alarm
    ```

2.  **Start the alarm:**
    ```bash
    ./alarm
    ```

3.  **Follow the instructions:** Enter the duration and your message when asked.

---
*Created as an Operating Systems Mini Project*
