from flask import Flask, render_template
from flask_socketio import SocketIO
from darts_cv_simulation import *

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Instantiate the DartDetection class
dart_detection = DartDetection(socketio)

@app.route('/')
def index():
    """Serve the index.html file from the templates folder."""
    return render_template("index.html")

@socketio.on('start_game')
def handle_start_game():
    """Starts the CV loop."""
    dart_detection.initialize()
    dart_detection.start()
    socketio.emit('game_status', {'message': 'Game started'})

@socketio.on('stop_game')
def handle_stop_game():
    """Stops the CV loop."""
    dart_detection.stop()
    socketio.emit('game_status', {'message': 'Game stopped'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
