#!/bin/bash

VENV_PATH="/home/benji/dartboard_env"

if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
    export PYTHONPATH="/home/benji/dartboard_env/automatic_dart_scoring/webapp"

    # Print success messages
    echo "Virtual environment activated."
    echo "PYTHONPATH set to: $PYTHONPATH"

else
    echo "Error: Virtual environment not found "
    exit 1
fi
