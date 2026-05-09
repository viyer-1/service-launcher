#!/usr/bin/env python3
"""
Test script to identify bugs in the script runner
"""

import subprocess
import sys
import os

# Add current directory to path
sys.path.insert(0, '.')

from script_runner import sanitize_command

def test_sanitize_command():
    """Test the sanitize_command function for bugs"""
    
    print("Testing sanitize_command function...")
    
    # Test 1: Normal command with parameters
    try:
        cmd = sanitize_command("echo hello", {"world": "test"})
        print(f"✓ Test 1 passed: {cmd}")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
    
    # Test 2: Command with positional argument (empty name)
    try:
        cmd = sanitize_command("echo", {"": "hello world"})
        print(f"✓ Test 2 passed: {cmd}")
        print(f"  Command would be: {' '.join(cmd)}")
        # This will create: ['echo', '', 'hello world']
        # Which becomes: echo '' 'hello world'
        # This is problematic!
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
    
    # Test 3: Command injection attempt
    try:
        cmd = sanitize_command("echo", {"test": "hello; rm -rf /"})
        print(f"✗ Test 3 failed: Should have blocked command injection")
    except ValueError as e:
        print(f"✓ Test 3 passed: Correctly blocked command injection: {e}")
    except Exception as e:
        print(f"✗ Test 3 failed with unexpected error: {e}")
    
    # Test 4: Multiple parameters including positional
    try:
        cmd = sanitize_command("script.py", {"--input": "file.txt", "": "output.txt"})
        print(f"✓ Test 4 passed: {cmd}")
        print(f"  Command would be: {' '.join(cmd)}")
    except Exception as e:
        print(f"✗ Test 4 failed: {e}")

def test_parameter_validation():
    """Test parameter validation logic"""
    
    print("\nTesting parameter validation logic...")
    
    # Simulate the validation logic from script_runner.py
    script = {
        'parameters': [
            {'name': '--required', 'required': True},
            {'name': '', 'required': True}  # Positional required parameter
        ]
    }
    
    # Test with missing required parameter
    params = {'--required': 'value'}  # Missing positional parameter
    
    for param in script['parameters']:
        if param.get('required', False) and param['name'] not in params:
            print(f"✗ Validation would fail for parameter '{param['name']}'")
            print(f"  This is problematic for positional arguments with empty names!")
        else:
            print(f"✓ Parameter '{param['name']}' validation passed")

def test_command_execution():
    """Test actual command execution with problematic cases"""
    
    print("\nTesting command execution...")
    
    # Test what happens when we have empty string in command
    try:
        result = subprocess.run(['echo', '', 'hello'], capture_output=True, text=True)
        print(f"✓ Command with empty string executed: {result.stdout.strip()}")
        print(f"  Return code: {result.returncode}")
    except Exception as e:
        print(f"✗ Command execution failed: {e}")

if __name__ == '__main__':
    test_sanitize_command()
    test_parameter_validation()
    test_command_execution()
    
    print("\n" + "="*50)
    print("BUG SUMMARY:")
    print("1. Positional arguments (empty name) create empty strings in command list")
    print("2. Parameter validation fails for required positional arguments")
    print("3. Empty strings in command lists may cause unexpected behavior")
    print("="*50)