#!/usr/bin/env python3
"""
Example script for testing Service Launcher
This script demonstrates how parameters are passed and output is streamed
"""

import sys
import time
import argparse

def main():
    parser = argparse.ArgumentParser(description='Example script with parameters')
    parser.add_argument('--name', type=str, default='World', help='Name to greet')
    parser.add_argument('--count', type=int, default=5, help='Number of times to greet')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between greetings (seconds)')
    
    args = parser.parse_args()
    
    print(f"Starting example script...")
    print(f"Parameters received:")
    print(f"  - name: {args.name}")
    print(f"  - count: {args.count}")
    print(f"  - delay: {args.delay}")
    print("-" * 50)
    
    for i in range(1, args.count + 1):
        print(f"[{i}/{args.count}] Hello, {args.name}!")
        sys.stdout.flush()  # Important: flush output for real-time streaming
        time.sleep(args.delay)
    
    print("-" * 50)
    print("Script completed successfully!")

if __name__ == '__main__':
    main()
