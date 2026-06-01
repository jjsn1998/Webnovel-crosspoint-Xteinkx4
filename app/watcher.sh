#!/bin/bash

INPUT_DIR="/input"
PROCESSING_DIR="/processing"
IMPORTED_HTML_DIR="/imported-html"
FAILED_DIR="/failed"
CALIBRE_INGEST_DIR="/calibre-ingest"
LOG_FILE="/logs/watcher.log"

mkdir -p "$INPUT_DIR" "$PROCESSING_DIR" "$IMPORTED_HTML_DIR" "$FAILED_DIR" "$CALIBRE_INGEST_DIR" "/logs"

echo "==== Webnovel EPUB watcher started: $(date) ====" >> "$LOG_FILE"

while true; do
  shopt -s nullglob

  for FILE in "$INPUT_DIR"/*.html "$INPUT_DIR"/*.htm; do
    BASENAME="$(basename "$FILE")"
    WORKING_FILE="$PROCESSING_DIR/$BASENAME"

    echo "Found file: $BASENAME at $(date)" >> "$LOG_FILE"

    mv "$FILE" "$WORKING_FILE"

    python /work/html_to_epub.py "$WORKING_FILE" \
      --output "$CALIBRE_INGEST_DIR" \
      --author "pirateaba" \
      --chunk-size 3500 >> "$LOG_FILE" 2>&1

    if [ $? -eq 0 ]; then
      mv "$WORKING_FILE" "$IMPORTED_HTML_DIR/$BASENAME"
      echo "Converted successfully: $BASENAME" >> "$LOG_FILE"
    else
      mv "$WORKING_FILE" "$FAILED_DIR/$BASENAME"
      echo "FAILED: $BASENAME" >> "$LOG_FILE"
    fi
  done

  sleep 30
done
