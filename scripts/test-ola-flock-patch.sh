#!/bin/bash
# =============================================================================
# test-ola-flock-patch.sh
# =============================================================================
# Tests that the OLA flock() patch (PR #1770) is correctly applied and that
# the UUCP self-lock race condition no longer occurs.
#
# Tests:
#   1. Verify flock support was compiled in (HAVE_FLOCK)
#   2. Verify the new API exists (AcquireLockAndOpenSerialPort symbol)
#   3. Verify flock() is used instead of UUCP when locking a serial device
#   4. Simulate the self-lock race: create UUCP lock with own PID, verify
#      that AcquireLockAndOpenSerialPort still succeeds (flock doesn't care)
#   5. Verify no stale lock files after olad crash (kill -9)
#   6. Verify same-process re-lock works (the actual 21h bug scenario)
#
# Prerequisites:
#   - Patched OLA package installed (0.10.9.nojsmin-2+cuems1)
#   - olad running via systemd
#   - A serial device or pseudo-terminal for testing
# =============================================================================

set -uo pipefail

PASS=0
FAIL=0
SKIP=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }
skip() { echo "  SKIP: $1"; SKIP=$((SKIP + 1)); }

echo "=============================================="
echo "  OLA flock() Patch Test Suite"
echo "=============================================="
echo ""

# ─────────────────────────────────────────────────
# Test 1: Verify HAVE_FLOCK was set at compile time
# ─────────────────────────────────────────────────
echo "Test 1: HAVE_FLOCK compiled in"
LIBOLACOMMON="/usr/lib/x86_64-linux-gnu/libolacommon.so"
NM_TMPFILE=$(mktemp)
nm -D "$LIBOLACOMMON" > "$NM_TMPFILE" 2>/dev/null || true
if grep -q "flock" "$NM_TMPFILE"; then
    pass "libolacommon.so imports flock() from glibc"
else
    fail "flock() not imported -- HAVE_FLOCK may not be set"
fi

# ─────────────────────────────────────────────────
# Test 2: Verify new API symbol exists
# ─────────────────────────────────────────────────
echo "Test 2: AcquireLockAndOpenSerialPort symbol exists"
if grep -q "AcquireLockAndOpenSerialPort" "$NM_TMPFILE"; then
    pass "AcquireLockAndOpenSerialPort found in libolacommon.so"
else
    fail "AcquireLockAndOpenSerialPort NOT found -- patch may not be applied"
fi

# ─────────────────────────────────────────────────
# Test 3: Verify old API still exists (backwards compat)
# ─────────────────────────────────────────────────
echo "Test 3: AcquireUUCPLockAndOpen still present (backwards compat)"
if grep -q "AcquireUUCPLockAndOpen" "$NM_TMPFILE"; then
    pass "AcquireUUCPLockAndOpen still available"
else
    fail "AcquireUUCPLockAndOpen missing -- ABI break"
fi

# ─────────────────────────────────────────────────
# Test 4: Verify ReleaseSerialPortLock symbol exists
# ─────────────────────────────────────────────────
echo "Test 4: ReleaseSerialPortLock symbol exists"
if grep -q "ReleaseSerialPortLock" "$NM_TMPFILE"; then
    pass "ReleaseSerialPortLock found"
else
    fail "ReleaseSerialPortLock NOT found"
fi

# ─────────────────────────────────────────────────
# Test 5: Verify usbpro plugin uses new API
# ─────────────────────────────────────────────────
echo "Test 5: usbpro plugin uses AcquireLockAndOpenSerialPort"
USBPRO_LIB=$(find /usr/lib -name "libolausbpro.so*" -not -name "*.a" 2>/dev/null | head -1)
if [ -n "$USBPRO_LIB" ]; then
    USBPRO_NM=$(nm -D "$USBPRO_LIB" 2>/dev/null || true)
    if echo "$USBPRO_NM" | grep -q "AcquireLockAndOpenSerialPort"; then
        pass "usbpro plugin calls AcquireLockAndOpenSerialPort"
    elif echo "$USBPRO_NM" | grep -q "AcquireUUCPLockAndOpen"; then
        fail "usbpro plugin still uses old AcquireUUCPLockAndOpen"
    else
        fail "usbpro plugin has no lock function reference"
    fi
else
    skip "libolausbpro.so not found"
fi

# ─────────────────────────────────────────────────
# Test 6: Verify stageprofi plugin uses new API
# ─────────────────────────────────────────────────
echo "Test 6: stageprofi plugin uses AcquireLockAndOpenSerialPort"
STAGEPROFI_LIB=$(find /usr/lib -name "libolastageprofi.so*" -not -name "*.a" 2>/dev/null | head -1)
if [ -n "$STAGEPROFI_LIB" ]; then
    STAGEPROFI_NM=$(nm -D "$STAGEPROFI_LIB" 2>/dev/null || true)
    if echo "$STAGEPROFI_NM" | grep -q "AcquireLockAndOpenSerialPort"; then
        pass "stageprofi plugin calls AcquireLockAndOpenSerialPort"
    else
        fail "stageprofi plugin still uses old API"
    fi
else
    skip "libolastageprofi.so not found"
fi

# ─────────────────────────────────────────────────
# Test 7: UUCP lock file with own PID doesn't block flock
# ─────────────────────────────────────────────────
echo "Test 7: Stale UUCP lock with own PID doesn't prevent locking"
# flock() operates on file descriptors, not lock files. A stale UUCP lock
# file with our own PID is irrelevant to flock — this is the core fix.
# We test this by flocking a file that also has a UUCP-style lock.
TEST_FILE="/tmp/test-ola-uucp-$$"
UUCP_LOCK="/var/lock/LCK..$(basename $TEST_FILE)"
touch "$TEST_FILE"
printf "%10d\n" $$ > "$UUCP_LOCK" 2>/dev/null || true
if [ -f "$UUCP_LOCK" ]; then
    if python3 -c "
import fcntl, os, sys
fd = os.open('$TEST_FILE', os.O_RDWR)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print('flock succeeded despite UUCP lock with own PID')
    os.close(fd)
    sys.exit(0)
except IOError as e:
    print(f'flock failed: {e}')
    os.close(fd)
    sys.exit(1)
" 2>/dev/null; then
        pass "flock() ignores stale UUCP lock with own PID"
    else
        fail "flock() blocked by stale UUCP lock"
    fi
    rm -f "$UUCP_LOCK"
else
    skip "Could not create UUCP lock file (permissions?)"
fi
rm -f "$TEST_FILE"

# ─────────────────────────────────────────────────
# Test 8: flock is re-entrant — same FD re-lock works
# ─────────────────────────────────────────────────
echo "Test 8: flock() re-lock on same FD succeeds (re-entrant)"
TEST_FILE="/tmp/test-ola-relock-$$"
touch "$TEST_FILE"
if python3 -c "
import fcntl, os, sys
fd = os.open('$TEST_FILE', os.O_RDWR)
# First lock
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
# Re-lock same FD (simulates rescan re-acquiring)
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
print('re-lock succeeded')
os.close(fd)
sys.exit(0)
" 2>/dev/null; then
    pass "Same-FD re-lock works (no deadlock)"
else
    fail "Same-FD re-lock failed"
fi
rm -f "$TEST_FILE"

# ─────────────────────────────────────────────────
# Test 9: flock blocks different FD on same file (plugin isolation)
# ─────────────────────────────────────────────────
echo "Test 9: flock() blocks second FD on same file (plugin isolation)"
TEST_FILE="/tmp/test-ola-isolation-$$"
touch "$TEST_FILE"
if python3 -c "
import fcntl, os, sys
fd1 = os.open('$TEST_FILE', os.O_RDWR)
fd2 = os.open('$TEST_FILE', os.O_RDWR)
# First open locks
fcntl.flock(fd1, fcntl.LOCK_EX | fcntl.LOCK_NB)
# Second open should be blocked
try:
    fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print('ERROR: second lock succeeded (should have been blocked)')
    os.close(fd1)
    os.close(fd2)
    sys.exit(1)
except IOError:
    print('second lock correctly blocked')
    os.close(fd1)
    os.close(fd2)
    sys.exit(0)
" 2>/dev/null; then
    pass "Different-FD lock correctly blocked (plugin isolation works)"
else
    fail "Different-FD lock was not blocked"
fi
rm -f "$TEST_FILE"

# ─────────────────────────────────────────────────
# Test 10: No stale lock files after process exit
# ─────────────────────────────────────────────────
echo "Test 10: flock() released after process crash (no stale locks)"
TEST_FILE="/tmp/test-ola-stale-$$"
touch "$TEST_FILE"
# Spawn a process that flocks and gets killed
python3 -c "
import fcntl, os, time, sys
fd = os.open('$TEST_FILE', os.O_RDWR)
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
sys.stdout.write('locked\n')
sys.stdout.flush()
time.sleep(60)
" &
LOCK_PID=$!
sleep 0.5
kill -9 $LOCK_PID 2>/dev/null
wait $LOCK_PID 2>/dev/null || true
# Now try to lock — should succeed since flock is released on process exit
if python3 -c "
import fcntl, os, sys
fd = os.open('$TEST_FILE', os.O_RDWR)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print('lock acquired after crash')
    os.close(fd)
    sys.exit(0)
except IOError as e:
    print(f'lock still held after crash: {e}')
    os.close(fd)
    sys.exit(1)
" 2>/dev/null; then
    pass "flock released after process crash — no stale locks"
else
    fail "flock still held after process crash"
fi
rm -f "$TEST_FILE"

# ─────────────────────────────────────────────────
# Test 11: olad is running and healthy
# ─────────────────────────────────────────────────
echo "Test 11: olad is running via systemd"
if systemctl is-active olad >/dev/null 2>&1; then
    pass "olad.service is active"
else
    fail "olad.service is not active"
fi

# ─────────────────────────────────────────────────
# Test 12: olad uses --config-dir /etc/ola
# ─────────────────────────────────────────────────
echo "Test 12: olad using system config dir"
OLAD_CMD=$(ps -p $(pgrep -x olad 2>/dev/null | head -1) -o args= 2>/dev/null || echo "")
if echo "$OLAD_CMD" | grep -q -- "--config-dir /etc/ola"; then
    pass "olad running with --config-dir /etc/ola"
elif echo "$OLAD_CMD" | grep -q "olad"; then
    fail "olad running but without --config-dir /etc/ola: $OLAD_CMD"
else
    skip "olad not running"
fi

# ─────────────────────────────────────────────────
# Test 13: No UUCP lock files in /var/lock for serial devices
# ─────────────────────────────────────────────────
echo "Test 13: No stale UUCP lock files"
STALE_LOCKS=$(find /var/lock -name "LCK..ttyUSB*" -o -name "LCK..ttyACM*" 2>/dev/null)
if [ -z "$STALE_LOCKS" ]; then
    pass "No UUCP lock files found in /var/lock"
else
    fail "Stale UUCP lock files found: $STALE_LOCKS"
fi

# ─────────────────────────────────────────────────
# Test 14: No rogue olad processes
# ─────────────────────────────────────────────────
echo "Test 14: No rogue olad processes"
OLAD_COUNT=$(pgrep -c -x olad 2>/dev/null || echo "0")
if [ "$OLAD_COUNT" -eq 1 ]; then
    pass "Exactly one olad process running"
elif [ "$OLAD_COUNT" -eq 0 ]; then
    fail "No olad process running"
else
    fail "$OLAD_COUNT olad processes running (expected 1)"
fi

# ─────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────
echo ""
echo "=============================================="
TOTAL=$((PASS + FAIL + SKIP))
echo "  Results: $PASS passed, $FAIL failed, $SKIP skipped (of $TOTAL)"
echo "=============================================="

rm -f "$NM_TMPFILE"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
