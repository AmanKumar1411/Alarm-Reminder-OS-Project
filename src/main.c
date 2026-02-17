#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <signal.h>
#include "../include/alarm.h"

int main() {
    int seconds;
    char message[100];

    printf("Enter time (in seconds): ");
    scanf("%d", &seconds);

    printf("Enter reminder message: ");
    scanf(" %[^\n]", message);

    create_alarm_process(seconds, message);

    printf("Alarm set successfully!\n");

    // Parent waits so child can run
    while (1) {
        pause();
    }

    return 0;
}
void alarm_handler(int sig) {
    printf("\a");
    exit(0);
}

void create_alarm_process(int seconds, char *message) {
    pid_t pid = fork();

    if (pid == 0) {
        sleep(seconds);
        // Use macOS native sound and speech
        printf("ALARM: %s\n", message);
        fflush(stdout); // Ensure message prints before sound starts
        
        // Play system sound and speak the message
        // Using system() is simple for this use case
        system("afplay /System/Library/Sounds/Glass.aiff");
        
        char command[256];
        snprintf(command, sizeof(command), "say 'Alarm for %s'", message);
        system(command);
        
        exit(0);
    }
}