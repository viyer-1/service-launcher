#!/usr/bin/env python3
"""
Test shell command handling after fix
"""

import sys
sys.path.insert(0, '.')

print("Testing shell command handling...")
print("="*60)

# Test the actual function from script_runner
try:
    from script_runner import sanitize_command

    # Test 1: Shell command with &&
    print("\n[Test 1] Shell command with &&")
    cmd = sanitize_command("sudo apt update && sudo apt upgrade -y", {})
    print(f"Command: {cmd}")
    assert cmd == ['stdbuf', '-oL', '-eL', 'bash', '-c', 'sudo apt update && sudo apt upgrade -y'], f"Expected stdbuf + bash -c wrapper, got {cmd}"
    print("✓ PASS: Shell operators wrapped with stdbuf + bash -c")

    # Test 2: Shell command with pipes
    print("\n[Test 2] Shell command with pipe")
    cmd = sanitize_command("ps aux | grep python", {})
    print(f"Command: {cmd}")
    assert cmd == ['stdbuf', '-oL', '-eL', 'bash', '-c', 'ps aux | grep python'], f"Expected stdbuf + bash -c wrapper, got {cmd}"
    print("✓ PASS: Pipe wrapped with stdbuf + bash -c")

    # Test 3: Simple command without shell operators
    print("\n[Test 3] Simple command (no shell operators)")
    cmd = sanitize_command("python3 script.py", {"--arg": "value"})
    print(f"Command: {cmd}")
    assert 'bash' not in cmd, f"Should NOT use bash -c for simple commands, got {cmd}"
    assert cmd == ['python3', 'script.py', '--arg', 'value'], f"Unexpected format: {cmd}"
    print("✓ PASS: Simple commands don't use bash -c")

    # Test 4: Command with shell operators AND parameters
    print("\n[Test 4] Shell command with parameters")
    cmd = sanitize_command("echo test && echo", {"": "hello"})
    print(f"Command: {cmd}")
    assert cmd == ['stdbuf', '-oL', '-eL', 'bash', '-c', 'echo test && echo "hello"'], f"Expected stdbuf + bash -c with params, got {cmd}"
    print("✓ PASS: Shell command with parameters works")

    print("\n" + "="*60)
    print("ALL SHELL COMMAND TESTS PASSED ✓")
    print("="*60)

except ImportError as e:
    print(f"✗ FAIL: Could not import script_runner: {e}")
    print("This is expected if dependencies aren't installed.")
    sys.exit(1)
except Exception as e:
    print(f"✗ FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
