#!/bin/bash

VENV_PATH="/home/lawrence/Desktop/Grace_Github_pi/g_cap_venv"

if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
    export PYTHONPATH="/home/lawrence/Desktop/Grace_Github_pi/automatic_dart_scoring"

    # Print success messages
    echo "Virtual environment activated."
    echo "PYTHONPATH set to: $PYTHONPATH"

else
    echo "Error: Virtual environment not found "
    exit 1
fi
