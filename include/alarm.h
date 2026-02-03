#ifndef ALARM_H
#define ALARM_H

#include <signal.h>

/* Function declarations */
void create_alarm_process(int seconds, char *message);
void alarm_handler(int sig);

#endif
