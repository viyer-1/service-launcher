#!/bin/bash
LINES=${1:-20}
FILE=${2:-/var/log/syslog}
if [ ! -f "$FILE" ]; then
    echo "Error: File $FILE not found."
    exit 1
fi
echo "Showing last $LINES lines of $FILE:"
tail -n "$LINES" "$FILE"
