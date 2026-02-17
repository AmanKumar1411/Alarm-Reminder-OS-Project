# Makefile — Alarm & Reminder Engine
# Demonstrates OS-level compilation and linking

CC       = gcc
CFLAGS   = -Wall -Wextra -std=c11
SRC      = src/alarm_engine.c
TARGET   = alarm_engine

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC) include/alarm_engine.h
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)
	@echo "✅ Built $(TARGET) successfully"

clean:
	rm -f $(TARGET)
	@echo "🧹 Cleaned build artifacts"
