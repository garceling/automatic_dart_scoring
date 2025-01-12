#!/bin/bash

VENV_PATH="/home/grace/Desktop/automatic_dart_scoring/venv"

if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
    export PYTHONPATH="/home/grace/Desktop/automatic_dart_scoring"

    # Print success messages
    echo "Virtual environment activated."
    echo "PYTHONPATH set to: $PYTHONPATH"

else
    echo "Error: Virtual environment not found "
    exit 1
fi
