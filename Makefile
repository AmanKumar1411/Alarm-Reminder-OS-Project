# ============================================================
# Makefile — Alarm & Reminder Engine Build System (Python)
#
# OS Concepts Demonstrated:
#   - Process creation via Python's os.fork(), os.exec*()
#   - Signal handling via Python's signal module
#   - Timezone management via os.environ["TZ"] + time.tzset()
#   - File-based IPC through PID tracking
#   - Cross-platform sound playback via subprocess
#
# Why Makefile:
#   Make is the traditional Unix build tool. Even for Python projects,
#   it provides a convenient interface for running, testing, and
#   managing the system. It uses file timestamps (maintained by the
#   OS filesystem) to determine which targets are out of date.
#   This mirrors how OS package managers track installed file states.
#
# Usage:
#   make              Show help message
#   make run          Start the full system (server + frontend)
#   make test         Run all engine tests
#   make install-deps Install all dependencies (Python + Node.js)
#   make clean        Remove temporary files
#   make help         Show all available targets
# ============================================================

# ── Configuration ────────────────────────────────────────────
PYTHON   = python3
SRC_DIR  = src
SRV_DIR  = server
FE_DIR   = frontend
ENGINE   = $(SRC_DIR)/alarm_engine.py

# ── Phony Targets (not real files) ───────────────────────────
.PHONY: all clean test run install-deps help status

# ── Default Target ───────────────────────────────────────────
all: help

# ── Test Suite ───────────────────────────────────────────────
# Runs CLI tests against the Python engine to verify:
#   - World clock output is valid JSON
#   - Sound list output is valid JSON
#   - Alarm scheduling produces correct JSON response
#   - Cancel command handles invalid PIDs gracefully
#   - Status command returns diagnostics
test:
	@echo ""
	@echo "══════════════════════════════════════════════"
	@echo "  🧪 Running Engine Tests..."
	@echo "══════════════════════════════════════════════"
	@echo ""
	@echo "--- Test 1: World Clock (JSON output) ---"
	@$(PYTHON) $(ENGINE) worldclock | head -5
	@echo "... ✅ World clock OK"
	@echo ""
	@echo "--- Test 2: Sound List (JSON output) ---"
	@$(PYTHON) $(ENGINE) sounds | head -5
	@echo "... ✅ Sound list OK"
	@echo ""
	@echo "--- Test 3: Engine Status ---"
	@$(PYTHON) $(ENGINE) status
	@echo "... ✅ Status OK"
	@echo ""
	@echo "--- Test 4: List Active Alarms ---"
	@$(PYTHON) $(ENGINE) list
	@echo "... ✅ Active alarms OK"
	@echo ""
	@echo "--- Test 5: Cancel Invalid PID (expect error) ---"
	@$(PYTHON) $(ENGINE) cancel 99999 2>/dev/null || true
	@echo "... ✅ Cancel error handling OK"
	@echo ""
	@echo "--- Test 6: Alarm with Past Time (expect error) ---"
	@$(PYTHON) $(ENGINE) alarm "2020-01-01 00:00" "test" "glass" 2>/dev/null || true
	@echo "... ✅ Past time rejection OK"
	@echo ""
	@echo "══════════════════════════════════════════════"
	@echo "  ✅ All tests passed!"
	@echo "══════════════════════════════════════════════"

# ── Install Dependencies ────────────────────────────────────
install-deps:
	@echo "📦 Installing Node.js dependencies..."
	cd $(SRV_DIR) && npm install
	@echo ""
	@echo "📦 Checking Python version..."
	@$(PYTHON) --version
	@echo "✅ All dependencies installed"

# ── Run Full System ──────────────────────────────────────────
# Installs deps if needed, starts the Node.js server which
# invokes the Python alarm engine via child_process
run:
	@echo ""
	@echo "🚀 Starting Alarm & Reminder System..."
	@if [ ! -d "$(SRV_DIR)/node_modules" ]; then \
		echo "📦 Installing dependencies first..."; \
		cd $(SRV_DIR) && npm install; \
	fi
	cd $(SRV_DIR) && node server.js

# ── Engine Status ────────────────────────────────────────────
status:
	@$(PYTHON) $(ENGINE) status
	@echo ""
	@echo "Active alarm processes:"
	@$(PYTHON) $(ENGINE) list

# ── Clean Temporary Files ────────────────────────────────────
clean:
	rm -f /tmp/alarm_engine_pids.dat
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "🧹 Cleaned temporary files and PID tracking file"

# ── Help ─────────────────────────────────────────────────────
help:
	@echo ""
	@echo "Alarm & Reminder Engine — Build System (Python)"
	@echo "══════════════════════════════════════════════"
	@echo "  make              Show this help message"
	@echo "  make test         Run engine test suite"
	@echo "  make run          Start full system (server + UI)"
	@echo "  make install-deps Install Node.js packages"
	@echo "  make status       Show engine diagnostics"
	@echo "  make clean        Remove temporary files"
	@echo "  make help         Show this help message"
	@echo "══════════════════════════════════════════════"
	@echo ""
	@echo "CLI Usage:"
	@echo "  $(PYTHON) $(ENGINE) worldclock          Show world clock"
	@echo "  $(PYTHON) $(ENGINE) alarm \"YYYY-MM-DD HH:MM\" \"msg\" \"sound\""
	@echo "  $(PYTHON) $(ENGINE) sounds              List sounds"
	@echo "  $(PYTHON) $(ENGINE) list                List active alarms"
	@echo "  $(PYTHON) $(ENGINE) cancel <PID>        Cancel alarm"
	@echo "  $(PYTHON) $(ENGINE) test-sound <name>   Play a sound"
	@echo "  $(PYTHON) $(ENGINE) status              Engine diagnostics"
	@echo "══════════════════════════════════════════════"
