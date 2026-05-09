#!/bin/bash
TARGET=${1:-8.8.8.8}
echo "Checking connectivity to $TARGET..."
ping -c 4 "$TARGET"
