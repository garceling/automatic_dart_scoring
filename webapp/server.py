from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from app_calibration import *
import sqlite3
import hashlib
import random
from datetime import datetime
import time
from contextlib import contextmanager
import threading
import time
import os

CV_DB_PATH = os.path.join('/home/lawrence/Desktop/Grace_Github_pi/automatic_dart_scoring/simulation', 'cv_data.db') #path is for lawrence's pi

# Initialize Flask app and SocketIO
app = Flask(__name__)

# Set secret key for flask sessions 
app.config['SECRET_KEY'] = 'banana'  # Replace with a secure key

# Socket.IO event handlers
socketio = SocketIO(app, cors_allowed_origins="*")

app.register_blueprint(calibration_bp)

# pass in the websocket for the calibartion
register_socketio_events(socketio)


cv_active_games = {}  # Dict to track CV mode status for games {game_id: last_processed_id}
cv_polling_thread = None
cv_polling_active = False

@contextmanager
def get_db_connection_with_retry(max_attempts=5, db_path='dartboard.db'):
    conn = None
    attempts = 0
    while attempts < max_attempts:
        try:
            conn = sqlite3.connect(db_path, timeout=20)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.close()
            break
        except sqlite3.OperationalError as e:
            attempts += 1
            if attempts == max_attempts:
                print(f"Failed to connect after {max_attempts} attempts")
                raise
            print(f"Database locked, attempt {attempts} of {max_attempts}. Retrying...")
            time.sleep(0.5)
            if conn:
                conn.close()


def cv_polling_loop():
    """Background thread to poll CV database for new throws"""
    print("CV polling loop started") # Debug: Loop start
    global cv_polling_active
    
    while cv_polling_active:
        try:
            # Only poll if there are games using CV mode
            if cv_active_games:
                print(f"Checking throws for {len(cv_active_games)} active games") # Debug: Active games
                for game_id, last_id in list(cv_active_games.items()):  # Use list to avoid runtime modification issues
                    new_throws = check_cv_throws(game_id, last_id)
                    
                    if new_throws:
                        print(f"Found {len(new_throws)} new throws for game {game_id}") # Debug: New throws
                        # Update game's last processed ID
                        cv_active_games[game_id] = new_throws[-1]['id']
                        
                        # Send each throw to all players in the game
                        #Tweaked emit to use same code as manual throw. Basically the socketio emitting wasn't working with the cv_dart_detected emit to the html, so instead we're just gonna trick the script into thinking we are doing a manual throw (which works) but the manual throw info is from our cv writer
                        for throw in new_throws:
                            print(f"Sending throw to game {game_id}: score={throw['score']}, multiplier={throw['multiplier']}") # Debug: Throw emit
                            socketio.emit('throw_dart', {
                                'manual' : True,
                                'score': throw['score'],
                                'multiplier': throw['multiplier']
                            }, room=f"game_{game_id}")
                
        except Exception as e:
            print(f"Error in CV polling loop: {e}")
            
        time.sleep(0.5)  # Poll every 500ms


# Hashing passwords securely
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Game-related functions
def simulate_dart_throw():
    # Simulate a realistic dart throw with weighted probabilities
    throw_types = [
        ('single', 0.65),  # 65% chance of single
        ('double', 0.15),  # 15% chance of double
        ('triple', 0.15),  # 15% chance of triple
        ('bull', 0.05)     # 5% chance of bull
    ]
    
    # Select throw type based on probabilities
    throw_type = random.choices([t[0] for t in throw_types], 
                              weights=[t[1] for t in throw_types])[0]
    
    if throw_type == 'bull':
        # 25 or 50 (double bull)
        score = random.choices([25, 50], weights=[0.7, 0.3])[0]
        multiplier = 1
        bull_flag = True
    else:
        # Normal board numbers 1-20
        base_score = random.randint(1, 20)
        multiplier = {'single': 1, 'double': 2, 'triple': 3}[throw_type]
        score = base_score * multiplier
        bull_flag = False
    
    return score, multiplier, bull_flag

def get_current_round(game_id, player_id):
    with get_db_connection_with_retry() as conn:
        cursor = conn.cursor()
        
        # Get the latest round that's not a bust
        cursor.execute('''
            SELECT * FROM GameRounds 
            WHERE game_id = ? AND player_id = ?
            AND is_bust = 0
            ORDER BY round_number DESC LIMIT 1
        ''', (game_id, player_id))
        current_round = cursor.fetchone()
        
        if not current_round or (
            current_round['throw1_score'] is not None and
            current_round['throw2_score'] is not None and
            current_round['throw3_score'] is not None
        ):
            # Calculate next round number
            cursor.execute('''
                SELECT COALESCE(MAX(round_number), 0) + 1 as next_round
                FROM GameRounds
                WHERE game_id = ? AND player_id = ?
            ''', (game_id, player_id))
            next_round_num = cursor.fetchone()['next_round']
            
            # Create new round
            cursor.execute('''
                INSERT INTO GameRounds (game_id, player_id, round_number)
                VALUES (?, ?, ?)
            ''', (game_id, player_id, next_round_num))
            conn.commit()
            return cursor.lastrowid, 1  # New round, first throw
        
        # Determine which throw we're on
        throw_number = 1
        if current_round['throw1_score'] is not None:
            throw_number = 2
            if current_round['throw2_score'] is not None:
                throw_number = 3
        
        return current_round['id'], throw_number

def cleanup_player_rooms(player_id, conn):
    """Remove player from all waiting rooms and clean up empty rooms"""
    cursor = conn.cursor()
    
    # Get all rooms the player is in
    cursor.execute('''
        SELECT r.id, r.created_by, r.room_status,
               COUNT(gp.player_id) as player_count
        FROM GameRooms r
        JOIN GamePlayers gp ON gp.game_id = r.id
        WHERE gp.player_id = ?
        GROUP BY r.id
    ''', (player_id,))
    rooms = cursor.fetchall()
    
    for room in rooms:
        # If this is the last player or player is host
        if room['player_count'] <= 1 or room['created_by'] == player_id:
            cursor.execute('DELETE FROM GamePlayers WHERE game_id = ?', (room['id'],))
            cursor.execute('DELETE FROM GameRooms WHERE id = ?', (room['id'],))
        else:
            # Just remove the player
            cursor.execute('''
                DELETE FROM GamePlayers 
                WHERE game_id = ? AND player_id = ?
            ''', (room['id'], player_id))
            
            # Update room player count
            cursor.execute('''
                UPDATE GameRooms 
                SET current_players = current_players - 1
                WHERE id = ?
            ''', (room['id'],))


def validate_dart_score(score, multiplier):
    #"""Validate if a dart score is possible"""
    try:
        score = int(score)
        multiplier = int(multiplier)
        
        if multiplier not in [1, 2, 3]:
            return False
            
        # Handle bull scores
        if score == 25 and multiplier <= 2:
            return True
        if score == 50 and multiplier == 2:
            return True
            
        # Regular scores must be 1-20
        return 1 <= score <= 20
            
    except (TypeError, ValueError):
        return False




def update_lobby_state(room_id):
    """Helper function to update lobby state for all players"""
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Get room information
            cursor.execute('''
                SELECT r.*, 
                       (SELECT COUNT(*) FROM GamePlayers WHERE game_id = r.id) as actual_player_count
                FROM GameRooms r 
                WHERE r.id = ?
            ''', (room_id,))
            room = cursor.fetchone()
            
            if not room:
                return
            
            # Update player count if it's incorrect
            if room['current_players'] != room['actual_player_count']:
                cursor.execute('''
                    UPDATE GameRooms 
                    SET current_players = ?
                    WHERE id = ?
                ''', (room['actual_player_count'], room_id))
                room['current_players'] = room['actual_player_count']
            
            # Get player list with correct join conditions
            cursor.execute('''
                SELECT p.id, p.username, 
                       CASE WHEN r.created_by = p.id THEN 1 ELSE 0 END as is_host
                FROM GamePlayers gp
                JOIN Players p ON p.id = gp.player_id
                JOIN GameRooms r ON r.id = ? AND r.id = gp.game_id
                ORDER BY gp.player_position
            ''', (room_id,))
            players = cursor.fetchall()
            
            # Emit updated state to all players in the room
            emit('lobby_update', {
                'name': room['name'],
                'game_type': room['game_type'],
                'double_out_required': bool(room['double_out_required']),
                'current_players': room['current_players'],
                'max_players': room['max_players'],
                'players': [{
                    'id': p['id'],
                    'username': p['username'],
                    'is_host': bool(p['is_host'])
                } for p in players]
            }, room=f"room_{room_id}", broadcast=True)
            
    except sqlite3.Error as e:
        print(f"Error updating lobby state: {e}")
        

#Below are helper functions used in getting CV data
def get_current_game_id():
    """Helper function to get current game ID from room"""
    print("Getting current game ID") # Debug: Function entry
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT g.id as game_id
                FROM Games g
                JOIN GameRooms r ON r.id = g.room_id
                WHERE r.id = ? AND g.game_status = 'in_progress'
            ''', (session['current_room'],))
            
            game = cursor.fetchone()
            print(f"Found game ID: {game['game_id'] if game else None}") # Debug: Query result
            return game['game_id'] if game else None
    except sqlite3.Error as e:
        print(f"Error getting game ID: {e}")
        return None
    

def get_latest_cv_throw_id():
    """Helper function to get the latest throw ID from CV database"""
    try:
        with sqlite3.connect(CV_DB_PATH) as cv_conn:
            cv_conn.row_factory = sqlite3.Row
            cursor = cv_conn.cursor()
            cursor.execute('SELECT MAX(id) as max_id FROM throws')
            result = cursor.fetchone()
            return result['max_id'] if result['max_id'] is not None else 0
    except sqlite3.Error as e:
        print(f"Error getting latest CV throw ID: {e}")
        return 0

def check_cv_throws(game_id, last_id):
    """Helper function to check for new CV throws"""
    print(f"Checking CV throws for game {game_id} after ID {last_id}") # Debug: Function entry
    try:
        with sqlite3.connect(CV_DB_PATH) as cv_conn:
            cv_conn.row_factory = sqlite3.Row
            cursor = cv_conn.cursor()
            
            cursor.execute('''
                SELECT id, score, multiplier 
                FROM throws 
                WHERE id > ? 
                ORDER BY id ASC
            ''', (last_id,))
            
            throws = cursor.fetchall()
            print(f"Found {len(throws)} new throws") # Debug: Query result
            return throws
    except sqlite3.Error as e:
        print(f"Error checking CV throws: {e}")
        return []

# Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email')  # Made email optional
        hashed_password = hash_password(password)
        
        try:
            with get_db_connection_with_retry() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO Players (username, password, email)
                VALUES (?, ?, ?)
                ''', (username, hashed_password, email))
                conn.commit()
                flash('Registration successful!', 'success')
                return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Error: Username already taken.', 'error')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = hash_password(password)
        
        try:
            with get_db_connection_with_retry() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT * FROM Players WHERE username = ? AND password = ?
                ''', (username, hashed_password))
                user = cursor.fetchone()
                
                if user:
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    flash(f'Welcome, {username}!', 'success')
                    return redirect(url_for('index'))
                else:
                    flash('Invalid username or password.', 'error')
        except sqlite3.Error as e:
            flash('An error occurred during login.', 'error')
            print(f"Database error during login: {e}")
            
    return render_template('login.html')

@app.route('/rooms')
def rooms():
    if 'user_id' not in session:
        flash('You must be logged in to view rooms!', 'error')
        return redirect(url_for('login'))
    return render_template('rooms.html')

@app.route('/game')
def game():
    if 'user_id' not in session:
        flash('You must be logged in to play!', 'error')
        return redirect(url_for('login'))
    
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Get active game info
            cursor.execute('''
                SELECT g.*, r.id as room_id, r.game_type, r.double_out_required
                FROM Games g
                JOIN GameRooms r ON r.id = g.room_id
                JOIN GamePlayers gp ON gp.game_id = r.id
                WHERE gp.player_id = ? 
                AND g.game_status = 'in_progress'
                AND r.room_status = 'in_progress'
                ORDER BY g.started_at DESC
                LIMIT 1
            ''', (session['user_id'],))
            
            game_data = cursor.fetchone()
            
            if not game_data:
                flash('No active game found', 'error')
                return redirect(url_for('rooms'))
            
            # Set current_room in session
            session['current_room'] = game_data['room_id']
            
            # Get all players in the game
            cursor.execute('''
                SELECT p.username, gp.current_score, gp.player_position
                FROM GamePlayers gp
                JOIN Players p ON p.id = gp.player_id
                WHERE gp.game_id = ?
                ORDER BY gp.player_position
            ''', (game_data['id'],))
            
            players = cursor.fetchall()
            
            return render_template('game.html', 
                                game_data=game_data,
                                players=players)
            
    except sqlite3.Error as e:
        flash('Error accessing game', 'error')
        return redirect(url_for('rooms'))
            
    except sqlite3.Error as e:
        flash('Error accessing game', 'error')
        return redirect(url_for('rooms'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/lobby/<int:room_id>')
def lobby(room_id):
    if 'user_id' not in session:
        flash('You must be logged in to view the lobby!', 'error')
        return redirect(url_for('login'))
        
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM GameRooms 
                WHERE id = ? AND room_status = 'waiting'
            ''', (room_id,))
            room_data = cursor.fetchone()
            
            if not room_data:
                flash('Room not found or game already started', 'error')
                return redirect(url_for('rooms'))
            
            # Set current_room in session if not already set
            session['current_room'] = room_id
                
            return render_template('lobby.html', room_data=room_data)
            
    except sqlite3.Error as e:
        flash('Error accessing room', 'error')
        return redirect(url_for('rooms'))



@app.route('/create_room', methods=['GET', 'POST'])
def create_room():
    if 'user_id' not in session:
        flash('You must be logged in to create a room!', 'error')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        try:
            with get_db_connection_with_retry() as conn:
                cursor = conn.cursor()
                
                # Create the room
                cursor.execute('''
                    INSERT INTO GameRooms (
                        name, created_by, game_type, double_out_required, 
                        is_private, room_password, current_players
                    ) VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (
                    request.form['name'],
                    session['user_id'],
                    request.form['game_type'],
                    'double_out' in request.form,
                    'is_private' in request.form,
                    request.form.get('room_password'),
                ))
                room_id = cursor.lastrowid
                
                # Add the creator to the room's players
                cursor.execute('''
                    INSERT INTO GamePlayers (game_id, player_id, player_position, current_score)
                    VALUES (?, ?, 0, ?)
                ''', (room_id, session['user_id'], request.form['game_type']))
                
                conn.commit()
                
                # Set current_room in session
                session['current_room'] = room_id
                
                return redirect(url_for('lobby', room_id=room_id))
                
        except sqlite3.Error as e:
            print(f"Database error in create_room: {e}")  # Debug log
            flash('Failed to create room', 'error')
            return redirect(url_for('rooms'))
            
    return render_template('create_room.html')


@socketio.on('connect')
def handle_connect():
    print("Client connected:", request.sid)
    if 'username' in session:
        print(f"User {session['username']} connected")

@socketio.on('get_rooms')
def handle_get_rooms():
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.*, p.username as creator_name,
                       (SELECT COUNT(*) FROM GamePlayers gp 
                        JOIN Games g ON g.id = gp.game_id
                        WHERE g.room_id = r.id) as current_players
                FROM GameRooms r
                JOIN Players p ON r.created_by = p.id
                WHERE r.room_status = 'waiting'
            ''')
            rooms = cursor.fetchall()
            
            room_list = [{
                'id': room['id'],
                'name': room['name'],
                'game_type': room['game_type'],
                'double_out_required': bool(room['double_out_required']),
                'is_private': bool(room['is_private']),
                'current_players': room['current_players'],
                'max_players': room['max_players'],
                'creator': room['creator_name'],
                'room_status': room['room_status']
            } for room in rooms]
            
            emit('rooms_list', {'rooms': room_list})
            
    except sqlite3.Error as e:
        print(f"Database error in get_rooms: {e}")
        emit('error', {'message': 'Failed to fetch rooms'})

@socketio.on('create_room')
def handle_create_room(data):
    if 'user_id' not in session:
        emit('error', {'message': 'You must be logged in to create a room'})
        return
        
    room_name = data.get('name')
    game_type = data.get('game_type', 501)
    double_out = data.get('double_out_required', False)
    is_private = data.get('is_private', False)
    room_password = data.get('room_password') if is_private else None
    
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO GameRooms (name, created_by, game_type, double_out_required, 
                                     is_private, room_password, current_players)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', (room_name, session['user_id'], game_type, double_out, 
                  is_private, room_password))
            room_id = cursor.lastrowid
            
            # Add creator to room
            cursor.execute('''
                INSERT INTO GamePlayers (game_id, player_id, player_position, current_score)
                VALUES (?, ?, 0, ?)
            ''', (room_id, session['user_id'], game_type))
            
            conn.commit()
            
            emit('room_created', {
                'room_id': room_id,
                'redirect_url': f'/lobby/{room_id}'
            })
            
    except sqlite3.Error as e:
        emit('error', {'message': 'Failed to create room'})



@socketio.on('join_room')
def handle_join_room(data):
    if 'user_id' not in session:
        emit('error', {'message': 'You must be logged in to join a room'})
        return
        
    room_id = data.get('room_id')
    password = data.get('password', '')
    
    try:
        with get_db_connection_with_retry() as conn:
            # Clean up any existing room memberships
            cleanup_player_rooms(session['user_id'], conn)
            
            cursor = conn.cursor()
            
            # Get room information
            cursor.execute('''
                SELECT * FROM GameRooms 
                WHERE id = ? AND room_status = 'waiting'
            ''', (room_id,))
            room = cursor.fetchone()
            
            if not room:
                emit('error', {'message': 'Room not found or game already started'})
                return
            
            # Check password for private rooms
            if room['is_private'] and room['room_password'] != password:
                emit('error', {'message': 'Invalid room password'})
                return
            
            # Check if room is full
            if room['current_players'] >= room['max_players']:
                emit('error', {'message': 'Room is full'})
                return
            
            # Add player to room
            cursor.execute('''
                INSERT INTO GamePlayers (game_id, player_id, player_position, current_score)
                VALUES (?, ?, ?, ?)
            ''', (room_id, session['user_id'], room['current_players'], room['game_type']))
            
            # Update room player count
            cursor.execute('''
                UPDATE GameRooms 
                SET current_players = current_players + 1
                WHERE id = ?
            ''', (room_id,))
            
            conn.commit()
            
            # Join the socket room
            join_room(f"room_{room_id}")
            
            # Set current_room in session
            session['current_room'] = room_id
            
            emit('join_success', {
                'room_id': room_id,
                'redirect_url': f'/lobby/{room_id}'
            })
            
    except sqlite3.Error as e:
        print(f"Database error in join_room: {e}")
        emit('error', {'message': 'Failed to join room'})



@socketio.on('start_game')
def handle_start_game(data):
    if 'user_id' not in session or 'current_room' not in session:
        emit('error', {'message': 'Not in a room'})
        return
        
    room_id = session['current_room']
    
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Check if user is room creator
            cursor.execute('''
                SELECT created_by, game_type, double_out_required, current_players 
                FROM GameRooms 
                WHERE id = ? AND room_status = 'waiting'
            ''', (room_id,))
            room = cursor.fetchone()
            
            if not room:
                emit('error', {'message': 'Room not found'})
                return
                
            if room['created_by'] != session['user_id']:
                emit('error', {'message': 'Only room creator can start the game'})
                return
                
            if room['current_players'] < 2:
                emit('error', {'message': 'Need at least 2 players to start'})
                return

            # Create new game
            cursor.execute('''
                INSERT INTO Games (room_id, game_status)
                VALUES (?, 'in_progress')
            ''', (room_id,))
            game_id = cursor.lastrowid

            # Get all players in room
            cursor.execute('''
                SELECT p.id, p.username 
                FROM GamePlayers gp
                JOIN Players p ON p.id = gp.player_id
                WHERE gp.game_id = ?
                ORDER BY gp.player_position
            ''', (room_id,))
            players = cursor.fetchall()

            if not players:
                emit('error', {'message': 'No players found in room'})
                return
            
            # Update room status
            cursor.execute('''
                UPDATE GameRooms 
                SET room_status = 'in_progress'
                WHERE id = ?
            ''', (room_id,))
            
            # Update all players with new game_id and initial score
            for idx, player in enumerate(players):
                cursor.execute('''
                    UPDATE GamePlayers
                    SET current_score = ?
                    WHERE game_id = ? AND player_id = ?
                ''', (room['game_type'], room_id, player['id']))
            
            conn.commit()

            print(f"Starting game with {len(players)} players")
            
            # Notify all players that game is starting
            emit('game_started', {
                'game_id': game_id,
                'players': [{'id': p['id'], 'username': p['username']} for p in players],
                'first_player': players[0]['username'],
                'game_type': room['game_type'],
                'double_out_required': room['double_out_required']
            }, room=f"room_{room_id}")
            
    except sqlite3.Error as e:
        print(f"Database error in start_game: {e}")
        emit('error', {'message': 'Failed to start game'})

@socketio.on('leave_room')
def handle_leave_room():
    if 'current_room' in session:
        room_id = session['current_room']
        
        try:
            with get_db_connection_with_retry() as conn:
                cursor = conn.cursor()
                
                # Update room player count
                cursor.execute('''
                    UPDATE GameRooms 
                    SET current_players = current_players - 1
                    WHERE id = ? AND room_status = 'waiting'
                ''', (room_id,))
                
                leave_room(f"room_{room_id}")
                session.pop('current_room', None)
                
                emit('player_left', {
                    'player': session['username']
                }, room=f"room_{room_id}")
                
                conn.commit()
                
        except sqlite3.Error as e:
            emit('error', {'message': 'Error leaving room'})





@socketio.on('override_throw')
def handle_override_throw(data):
    if 'user_id' not in session:
        emit('error', {'message': 'Not authenticated'})
        return
        
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # First get the active game info
            cursor.execute('''
                SELECT g.id as game_id, g.current_player_position,
                       r.game_type, r.double_out_required, r.id as room_id
                FROM Games g
                JOIN GameRooms r ON r.id = g.room_id
                WHERE r.id = ? 
                AND g.game_status = 'in_progress'
            ''', (session['current_room'],))
            
            game = cursor.fetchone()
            if not game:
                emit('error', {'message': 'No active game found'})
                return

            # Get the last throw with player information and score before throw
            cursor.execute('''
                WITH CurrentRound AS (
                    SELECT * FROM GameRounds 
                    WHERE game_id = ? 
                    AND player_id = ?
                    ORDER BY round_number DESC
                    LIMIT 1
                )
                SELECT gr.*, gp.current_score, gp.player_id,
                       p.username as player_name,
                       CASE 
                           WHEN throw3_score IS NOT NULL THEN 3
                           WHEN throw2_score IS NOT NULL THEN 2
                           WHEN throw1_score IS NOT NULL THEN 1
                           ELSE 0
                       END as last_throw_number,
                       CASE 
                           WHEN throw3_score IS NOT NULL THEN score_before_throw3
                           WHEN throw2_score IS NOT NULL THEN score_before_throw2
                           WHEN throw1_score IS NOT NULL THEN score_before_throw1
                       END as score_before_throw
                FROM CurrentRound gr
                JOIN Games g ON g.id = gr.game_id
                JOIN GamePlayers gp ON gp.game_id = g.room_id AND gp.player_id = gr.player_id
                JOIN Players p ON p.id = gr.player_id
                WHERE gr.game_id = ?
                AND gr.player_id = ?
                AND (gr.throw1_score IS NOT NULL OR gr.throw2_score IS NOT NULL OR gr.throw3_score IS NOT NULL)
            ''', (game['game_id'], session['user_id'], game['game_id'], session['user_id']))
            
            last_throw = cursor.fetchone()
            
            if not last_throw or last_throw['last_throw_number'] == 0:
                emit('error', {'message': 'No throw found to override'})
                return

            # Get the throw being modified
            throw_number = last_throw['last_throw_number']
            original_throw_value = last_throw[f'throw{throw_number}_score']
            score_before_throw = last_throw['score_before_throw']

            # Calculate new score using the score before this throw
            #new_score = score_before_throw - data['score']


            #I might change this approach with a if throw x new_score = last_throw['score_before_throwx'] - data['score']
            scores_this_round = []
            if throw_number >= 1:
                scores_this_round.append(last_throw['throw1_score'] if throw_number != 1 else data['score'])
            if throw_number >= 2:
                scores_this_round.append(last_throw['throw2_score'] if throw_number != 2 else data['score'])
            if throw_number >= 3:
                scores_this_round.append(last_throw['throw3_score'] if throw_number != 3 else data['score'])

            # Calculate new score starting from the score at beginning of round
            new_score = last_throw['score_before_throw1'] - sum(scores_this_round)



            # Check if this would be a valid score
            if new_score < 0 or (game['double_out_required'] and new_score == 1):
                emit('error', {'message': 'Invalid override - would result in bust'})
                return

            # Calculate round total
            #scores_this_round = []
            #if throw_number >= 1:
            #    scores_this_round.append(last_throw['throw1_score'])
            #if throw_number >= 2:
            #    scores_this_round.append(data['score'] if throw_number == 2 else last_throw['throw2_score'])
            #if throw_number >= 3:
            #    scores_this_round.append(data['score'] if throw_number == 3 else last_throw['throw3_score'])
            
            # Replace the overridden score in the total
            #scores_this_round[throw_number - 1] = data['score']
            round_total = sum(scores_this_round)

            # Update the throw
            throw_column = f'throw{throw_number}_score'
            mult_column = f'throw{throw_number}_multiplier'
            cursor.execute(f'''
                UPDATE GameRounds 
                SET {throw_column} = ?, 
                    {mult_column} = ?, 
                    is_bust = 0,
                    round_total = ?
                WHERE id = ?
            ''', (data['score'], data['multiplier'], round_total, last_throw['id']))
            
            # Update player's score
            cursor.execute('''
                UPDATE GamePlayers
                SET current_score = ?
                WHERE game_id = ? AND player_id = ?
            ''', (new_score, game['game_id'], last_throw['player_id']))
            
            # Get all players' current state
            cursor.execute('''
                SELECT p.username, gp.current_score, gp.player_position
                FROM GamePlayers gp
                JOIN Players p ON p.id = gp.player_id
                WHERE gp.game_id = ?
                ORDER BY gp.player_position
            ''', (game['game_id'],))
            players = cursor.fetchall()
            
            # Get complete updated round info
            cursor.execute('''
                SELECT gr.*, p.username as player_name
                FROM GameRounds gr
                JOIN Players p ON p.id = gr.player_id
                WHERE gr.id = ?
            ''', (last_throw['id'],))
            updated_round = cursor.fetchone()
            
            conn.commit()
            
            # Emit game state update to all players
            emit('game_state_update', {
                'throw': {
                    'score': data['score'],
                    'multiplier': data['multiplier'],
                    'is_bust': False
                },
                'players': [{
                    'username': p['username'],
                    'score': p['current_score'],
                    'position': p['player_position']
                } for p in players],
                'round_info': dict(updated_round),
                'current_score': new_score
            }, room=f"game_{game['game_id']}")
            
    except sqlite3.Error as e:
        print(f"Database error in handle_override: {e}")
        emit('error', {'message': 'An error occurred while processing the override'})






@socketio.on('throw_dart')
def handle_throw_dart(data=None):
    print(f"Processing throw_dart event: {data}")
    if 'user_id' not in session:
        emit('error', {'message': 'Not authenticated'})
        return
    
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Modified query to get current game state and last round info
            cursor.execute('''
                SELECT g.*, gp.current_score, gp.player_position as current_position,
                       r.game_type, r.double_out_required, r.id as room_id,
                       COALESCE(
                           (SELECT gr.round_total 
                            FROM GameRounds gr 
                            WHERE gr.game_id = g.id 
                            AND gr.player_id = gp.player_id
                            AND gr.is_bust = 0
                            ORDER BY gr.round_number DESC LIMIT 1), 0
                       ) as last_round_total
                FROM Games g
                JOIN GameRooms r ON r.id = g.room_id
                JOIN GamePlayers gp ON gp.game_id = g.id
                WHERE r.id = ? 
                AND g.game_status = 'in_progress'
                AND gp.player_id = ?
            ''', (session['current_room'], session['user_id']))
            
            game_state = cursor.fetchone()
            
            if not game_state:
                print("No game state found")
                emit('error', {'message': 'No active game found'})
                return
            

            #removed player turn verification so cv get simulate from any turn
            # Verify it's this player's turn
            #if game_state['current_player_position'] != game_state['current_position']:
                #emit('error', {'message': 'Not your turn'})
                #return
            
            print(f"Processing throw for game {game_state['id']}")

            # Handle manual throw if provided
            if data and data.get('manual'):
                base_score = data.get('score')
                multiplier = data.get('multiplier')
                
                # Server-side validation
                if not validate_dart_score(base_score, multiplier):
                    emit('error', {'message': 'Invalid score'})
                    return
                    
                # Handle bull scores specially
                if base_score == 25 or base_score == 50:
                    score = base_score
                    multiplier = 2 if base_score == 50 else 1
                    bull_flag = True
                else:
                    score = base_score * multiplier
                    bull_flag = False
            else:
                # Use existing simulation
                score, multiplier, bull_flag = simulate_dart_throw()
            
            print(f"Throw result: score={score}, multiplier={multiplier}, bull={bull_flag}")
            
            # Get current round information
            round_id, throw_number = get_current_round(game_state['id'], session['user_id'])
            print(f"Current round: {round_id}, throw: {throw_number}")

            # Get the current round's existing throws
            cursor.execute('''
                SELECT *, 
                       COALESCE(throw1_score, 0) + COALESCE(throw2_score, 0) + COALESCE(throw3_score, 0) as current_round_total,
                       score_before_throw1
                FROM GameRounds
                WHERE id = ?
            ''', (round_id,))
            current_round = cursor.fetchone()
            
            # Determine the correct score to use before this throw
            if throw_number == 1:
                score_before_throw = game_state['current_score']
            else:
                # For subsequent throws, use the score after previous throws
                previous_throws_total = 0
                for i in range(1, throw_number):
                    previous_score = current_round[f'throw{i}_score']
                    if previous_score is not None:
                        previous_throws_total += previous_score
                score_before_throw = current_round['score_before_throw1'] - previous_throws_total

            # Record the throw
            throw_column = f'throw{throw_number}_score'
            mult_column = f'throw{throw_number}_multiplier'
            score_before_column = f'score_before_throw{throw_number}'
            
            cursor.execute(f'''
                UPDATE GameRounds 
                SET {throw_column} = ?, 
                    {mult_column} = ?,
                    {score_before_column} = ?
                WHERE id = ?
            ''', (score, multiplier, score_before_throw, round_id))

            # Calculate round total up to this throw
            cursor.execute('''
                SELECT *, 
                       COALESCE(throw1_score, 0) + COALESCE(throw2_score, 0) + COALESCE(throw3_score, 0) as current_round_total
                FROM GameRounds
                WHERE id = ?
            ''', (round_id,))
            round_info = cursor.fetchone()
            round_total = round_info['current_round_total']

            # Calculate potential score from the start of round score
            potential_score = round_info['score_before_throw1'] - round_total

            # Get all players' current state
            cursor.execute('''
                SELECT p.username, gp.current_score, gp.player_position
                FROM GamePlayers gp
                JOIN Players p ON p.id = gp.player_id
                WHERE gp.game_id = ?
                ORDER BY gp.player_position
            ''', (game_state['id'],))
            players = cursor.fetchall()

            # Check for win condition before bust check
            is_win = (potential_score == 0 and 
                     (not game_state['double_out_required'] or multiplier == 2 or bull_flag))

            # Check for bust conditions
            is_bust = (
                potential_score < 0 or
                (game_state['double_out_required'] and potential_score == 1) or
                (game_state['double_out_required'] and potential_score == 0 and not (multiplier == 2 or bull_flag))
            )

            if is_bust:
                print("Bust detected - keeping original score")
                # Mark round as bust and clear throw scores
                cursor.execute('''
                    UPDATE GameRounds
                    SET is_bust = 1,
                        round_total = 0,
                        throw1_score = NULL,
                        throw2_score = NULL,
                        throw3_score = NULL,
                        throw1_multiplier = NULL,
                        throw2_multiplier = NULL,
                        throw3_multiplier = NULL
                    WHERE id = ?
                ''', (round_id,))
                # Keep original score for display
                potential_score = current_round['score_before_throw1']

                # Get updated round info after marking bust
                cursor.execute('''
                    SELECT gr.*, p.username as player_name
                    FROM GameRounds gr
                    JOIN Players p ON p.id = gr.player_id
                    WHERE gr.id = ?
                ''', (round_id,))
                display_round_info = cursor.fetchone()
                print("Bust round info:", dict(display_round_info))

                # Set up for next player
                cursor.execute('''
                    SELECT COUNT(*) as player_count FROM GamePlayers WHERE game_id = ?
                ''', (game_state['id'],))
                player_count = cursor.fetchone()['player_count']
                next_position = (game_state['current_position'] + 1) % player_count
                
                cursor.execute('''
                    UPDATE Games
                    SET current_player_position = ?
                    WHERE id = ?
                ''', (next_position, game_state['id']))

                # Get next player's username
                cursor.execute('''
                    SELECT p.username
                    FROM GamePlayers gp
                    JOIN Players p ON p.id = gp.player_id
                    WHERE gp.game_id = ? AND gp.player_position = ?
                ''', (game_state['id'], next_position))
                next_player = cursor.fetchone()
                next_player_name = next_player['username']

                # Start new round
                cursor.execute('''
                    SELECT COALESCE(MAX(round_number), 0) + 1 as next_round
                    FROM GameRounds
                    WHERE game_id = ? AND player_id = ?
                ''', (game_state['id'], session['user_id']))
                next_round = cursor.fetchone()['next_round']
                
                cursor.execute('''
                    INSERT INTO GameRounds (game_id, player_id, round_number)
                    VALUES (?, ?, ?)
                ''', (game_state['id'], session['user_id'], next_round))

                game_over = False

            elif throw_number == 3 or is_win:
                # Normal round completion or win
                cursor.execute('''
                    UPDATE GamePlayers
                    SET current_score = ?
                    WHERE game_id = ? AND player_id = ?
                ''', (potential_score, game_state['id'], session['user_id']))
                
                # Get round info for display
                cursor.execute('''
                    SELECT gr.*, p.username as player_name
                    FROM GameRounds gr
                    JOIN Players p ON p.id = gr.player_id
                    WHERE gr.id = ?
                ''', (round_id,))
                display_round_info = cursor.fetchone()
                print("Regular round info:", dict(display_round_info))

                if is_win:
                    game_over = True
                    next_player_name = session['username']  # Keep current player as winner
                    
                    # Update game and room status
                    cursor.execute('''
                        UPDATE Games 
                        SET game_status = 'completed'
                        WHERE id = ?
                    ''', (game_state['id'],))
                    
                    cursor.execute('''
                        UPDATE GameRooms
                        SET room_status = 'completed'
                        WHERE id = ?
                    ''', (session['current_room'],))
                else:
                    # Move to next player
                    cursor.execute('''
                        SELECT COUNT(*) as player_count FROM GamePlayers WHERE game_id = ?
                    ''', (game_state['id'],))
                    player_count = cursor.fetchone()['player_count']
                    next_position = (game_state['current_position'] + 1) % player_count
                    
                    cursor.execute('''
                        UPDATE Games
                        SET current_player_position = ?
                        WHERE id = ?
                    ''', (next_position, game_state['id']))

                    # Get next player's username
                    cursor.execute('''
                        SELECT p.username
                        FROM GamePlayers gp
                        JOIN Players p ON p.id = gp.player_id
                        WHERE gp.game_id = ? AND gp.player_position = ?
                    ''', (game_state['id'], next_position))
                    next_player = cursor.fetchone()
                    next_player_name = next_player['username']

                    game_over = False

            else:
                # Middle of round, not a win or bust
                cursor.execute('''
                    SELECT gr.*, p.username as player_name
                    FROM GameRounds gr
                    JOIN Players p ON p.id = gr.player_id
                    WHERE gr.id = ?
                ''', (round_id,))
                display_round_info = cursor.fetchone()
                print("Mid-round info:", dict(display_round_info))
                
                game_over = False
                next_player_name = session['username']  # Stay on current player

            conn.commit()
            
            # Emit game state update to all players
            emit('game_state_update', {
                'game_id': game_state['id'],
                'current_player': next_player_name,
                'throw': {
                    'score': score,
                    'multiplier': multiplier,
                    'is_bust': is_bust
                },
                'players': [{
                    'username': p['username'],
                    'score': p['current_score'],
                    'position': p['player_position']
                } for p in players],
                'round_info': dict(display_round_info),
                'current_score': potential_score,
                'game_over': game_over,
                'winner': session['username'] if game_over else None
            }, broadcast=True, room=f"game_{game_state['id']}")
            
    except sqlite3.Error as e:
        print(f"Database error in handle_throw: {e}")
        emit('error', {'message': 'An error occurred while processing your throw'})



@socketio.on('confirm_win')
def handle_confirm_win(data):
    if 'user_id' not in session:
        emit('error', {'message': 'Not authenticated'})
        return
        
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Get game state
            cursor.execute('''
                SELECT g.*, r.id as room_id
                FROM Games g
                JOIN GameRooms r ON r.id = g.room_id
                WHERE g.id = ? AND g.game_status = 'in_progress'
            ''', (data['game_id'],))
            
            game = cursor.fetchone()
            
            if not game:
                emit('error', {'message': 'Game not found or already completed'})
                return

            # Update player's final score
            cursor.execute('''
                UPDATE GamePlayers
                SET current_score = 0
                WHERE game_id = ? AND player_id = ?
            ''', (game['id'], session['user_id']))

            # Update game and room status
            cursor.execute('''
                UPDATE Games 
                SET game_status = 'completed'
                WHERE id = ?
            ''', (game['id'],))
            
            cursor.execute('''
                UPDATE GameRooms
                SET room_status = 'completed'
                WHERE id = ?
            ''', (game['room_id'],))

            # Get final game state for all players
            cursor.execute('''
                SELECT p.username, gp.current_score, gp.player_position
                FROM GamePlayers gp
                JOIN Players p ON p.id = gp.player_id
                WHERE gp.game_id = ?
                ORDER BY gp.player_position
            ''', (game['id'],))
            players = cursor.fetchall()
            
            conn.commit()

            # Emit final game state to all players
            emit('game_state_update', {
                'game_id': game['id'],
                'throw': data['throw'],
                'players': [{
                    'username': p['username'],
                    'score': p['current_score'],
                    'position': p['player_position']
                } for p in players],
                'current_score': 0,
                'game_over': True,
                'winner': session['username']
            }, room=f"game_{game['id']}")
            
    except sqlite3.Error as e:
        print(f"Database error in confirm_win: {e}")
        emit('error', {'message': 'An error occurred while completing the game'})




@socketio.on('end_game')
def handle_end_game():
    try:
        game_id = get_current_game_id()
        if game_id:
            cv_active_games.pop(game_id, None)
        if 'current_room' not in session:
            return
            
        try:
            with get_db_connection_with_retry() as conn:
                cursor = conn.cursor()
                
                # First check the game status
                cursor.execute('''
                    SELECT game_status
                    FROM Games
                    WHERE room_id = ?
                    ORDER BY id DESC LIMIT 1
                ''', (session['current_room'],))
                
                game = cursor.fetchone()
                
                if game:
                    if game['game_status'] == 'in_progress':
                        # Only mark as abandoned if game was in progress
                        cursor.execute('''
                            UPDATE Games 
                            SET game_status = 'abandoned'
                            WHERE room_id = ? AND game_status = 'in_progress'
                        ''', (session['current_room'],))
                        
                        cursor.execute('''
                            UPDATE GameRooms
                            SET room_status = 'abandoned'
                            WHERE id = ?
                        ''', (session['current_room'],))
                    else:
                        # Game was already completed or abandoned, just clean up
                        cursor.execute('''
                            DELETE FROM GamePlayers
                            WHERE game_id = ?
                        ''', (session['current_room'],))
                        
                        cursor.execute('''
                            DELETE FROM GameRooms
                            WHERE id = ?
                        ''', (session['current_room'],))
                
                conn.commit()
                
                # Notify all players in room
                emit('game_ended', {
                    'message': f"Game ended by {session['username']}"
                }, room=f"room_{session['current_room']}")
                
                session.pop('current_room', None)
                
        except sqlite3.Error as e:
            emit('error', {'message': 'Failed to end game properly'})
    except Exception as e:
        print(f"Error cleaning up CV mode: {e}")


 




@socketio.on('join_lobby')
def handle_join_lobby(data):
    if 'user_id' not in session:
        emit('error', {'message': 'You must be logged in'})
        return
        
    room_id = data.get('room_id')
    # Set current_room in session
    session['current_room'] = room_id
    
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Get room information
            cursor.execute('''
                SELECT * FROM GameRooms 
                WHERE id = ? AND room_status = 'waiting'
            ''', (room_id,))
            room = cursor.fetchone()
            
            if not room:
                emit('error', {'message': 'Room not found or game already started'})
                return
            
            # Join the socket room
            join_room(f"room_{room_id}")
            
            # Get player list
            cursor.execute('''
                SELECT p.id, p.username, 
                       CASE WHEN r.created_by = p.id THEN 1 ELSE 0 END as is_host
                FROM GamePlayers gp
                JOIN Players p ON p.id = gp.player_id
                JOIN GameRooms r ON r.id = ?
                WHERE gp.game_id = r.id
                ORDER BY gp.player_position
            ''', (room_id,))
            players = cursor.fetchall()
            
            # Emit lobby update to all players
            emit('lobby_update', {
                'name': room['name'],
                'game_type': room['game_type'],
                'double_out_required': bool(room['double_out_required']),
                'current_players': room['current_players'],
                'max_players': room['max_players'],
                'players': [{
                    'id': p['id'],
                    'username': p['username'],
                    'is_host': bool(p['is_host'])
                } for p in players]
            }, room=f"room_{room_id}")
            
    except sqlite3.Error as e:
        emit('error', {'message': 'Failed to join lobby'})
        session.pop('current_room', None)  # Remove room from session if error


@socketio.on('kick_player')
def handle_kick_player(data):
    if 'user_id' not in session:
        return
        
    room_id = data.get('room_id')
    player_id = data.get('player_id')
    
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Verify sender is room host
            cursor.execute('''
                SELECT created_by FROM GameRooms 
                WHERE id = ? AND created_by = ?
            ''', (room_id, session['user_id']))
            
            if not cursor.fetchone():
                emit('error', {'message': 'Only the host can kick players'})
                return
            
            # Check if player is actually in the room
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM GamePlayers
                WHERE game_id = ? AND player_id = ?
            ''', (room_id, player_id))
            
            if cursor.fetchone()['count'] == 0:
                emit('error', {'message': 'Player not found in room'})
                return
            
            # Get the player's username for the socket room
            cursor.execute('''
                SELECT username FROM Players WHERE id = ?
            ''', (player_id,))
            player = cursor.fetchone()
            
            # Remove player from room
            cursor.execute('''
                DELETE FROM GamePlayers 
                WHERE game_id = ? AND player_id = ?
            ''', (room_id, player_id))
            
            # Update room player count
            cursor.execute('''
                UPDATE GameRooms 
                SET current_players = (
                    SELECT COUNT(*) 
                    FROM GamePlayers 
                    WHERE game_id = ?
                )
                WHERE id = ?
            ''', (room_id, room_id))
            
            conn.commit()
            
            # Broadcast to everyone in the room that a player was kicked
            emit('player_kicked', {
                'player_id': player_id,
                'username': player['username'],
                'kicked_player_sid': request.sid,  # Include the socket ID
                'room_id': room_id
            }, room=f"room_{room_id}", broadcast=True)
            
            # Update room state for remaining players
            update_lobby_state(room_id)
            
    except sqlite3.Error as e:
        emit('error', {'message': 'Failed to kick player'})


@socketio.on('close_lobby')
def handle_close_lobby(data):
    if 'user_id' not in session:
        return
        
    room_id = data.get('room_id')
    
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Verify sender is room host
            cursor.execute('''
                SELECT created_by FROM GameRooms 
                WHERE id = ? AND created_by = ?
            ''', (room_id, session['user_id']))
            
            if not cursor.fetchone():
                emit('error', {'message': 'Only the host can close the lobby'})
                return
            
            # Delete all players and the room
            cursor.execute('DELETE FROM GamePlayers WHERE game_id = ?', (room_id,))
            cursor.execute('DELETE FROM GameRooms WHERE id = ?', (room_id,))
            
            conn.commit()
            
            # Notify all players in room
            emit('lobby_closed', room=f"room_{room_id}")
            
    except sqlite3.Error as e:
        emit('error', {'message': 'Failed to close lobby'})


@socketio.on('leave_lobby')
def handle_leave_lobby(data):
    if 'user_id' not in session:
        return
        
    room_id = data.get('room_id')
    was_kicked = data.get('was_kicked', False)
    
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Check if player is host
            cursor.execute('''
                SELECT created_by, (SELECT username FROM Players WHERE id = ?) as username 
                FROM GameRooms 
                WHERE id = ?
            ''', (session['user_id'], room_id))
            room = cursor.fetchone()
            
            if not room:
                return
                
            if room['created_by'] == session['user_id']:
                # Host is leaving, close the room
                cursor.execute('DELETE FROM GamePlayers WHERE game_id = ?', (room_id,))
                cursor.execute('DELETE FROM GameRooms WHERE id = ?', (room_id,))
                
                # Notify all players
                emit('lobby_closed', {
                    'message': 'Host has left the lobby'
                }, room=f"room_{room_id}", broadcast=True)
            else:
                # Only update player count if player wasn't already kicked
                if not was_kicked:
                    cursor.execute('''
                        DELETE FROM GamePlayers 
                        WHERE game_id = ? AND player_id = ?
                    ''', (room_id, session['user_id']))
                    
                    cursor.execute('''
                        UPDATE GameRooms 
                        SET current_players = (
                            SELECT COUNT(*) 
                            FROM GamePlayers 
                            WHERE game_id = ?
                        )
                        WHERE id = ?
                    ''', (room_id, room_id))
                    
                    # Notify remaining players that someone left
                    emit('player_left', {
                        'username': room['username'],
                        'room_id': room_id
                    }, room=f"room_{room_id}", broadcast=True)
                
                # Update lobby for remaining players
                update_lobby_state(room_id)
            
            conn.commit()
            
            # Leave socket room
            leave_room(f"room_{room_id}")
            session.pop('current_room', None)
            
    except sqlite3.Error as e:
        emit('error', {'message': 'Failed to leave lobby'})

def update_lobby_state(room_id):
    """Helper function to update lobby state for all players"""
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Get room information
            cursor.execute('''
                SELECT r.*, 
                       (SELECT COUNT(*) FROM GamePlayers WHERE game_id = r.id) as actual_player_count
                FROM GameRooms r 
                WHERE r.id = ?
            ''', (room_id,))
            room = cursor.fetchone()
            
            if not room:
                return
            
            # Update player count if it's incorrect
            if room['current_players'] != room['actual_player_count']:
                cursor.execute('''
                    UPDATE GameRooms 
                    SET current_players = ?
                    WHERE id = ?
                ''', (room['actual_player_count'], room_id))
                room['current_players'] = room['actual_player_count']
            
            # Get player list with correct join conditions
            cursor.execute('''
                SELECT p.id, p.username, 
                       CASE WHEN r.created_by = p.id THEN 1 ELSE 0 END as is_host
                FROM GamePlayers gp
                JOIN Players p ON p.id = gp.player_id
                JOIN GameRooms r ON r.id = ? AND r.id = gp.game_id
                ORDER BY gp.player_position
            ''', (room_id,))
            players = cursor.fetchall()
            
            # Emit updated state to all players
            emit('lobby_update', {
                'name': room['name'],
                'game_type': room['game_type'],
                'double_out_required': bool(room['double_out_required']),
                'current_players': room['current_players'],
                'max_players': room['max_players'],
                'players': [{
                    'id': p['id'],
                    'username': p['username'],
                    'is_host': bool(p['is_host'])
                } for p in players]
            }, room=f"room_{room_id}")
            
    except sqlite3.Error as e:
        print(f"Error updating lobby state: {e}")


@socketio.on('join_game')
def handle_join_game(data=None):
    #print(f"Player {session['username']} joining game room: game_{game['id']}")
    if 'user_id' not in session:
        return
    
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Get game state by finding the most recent active game for this player
            cursor.execute('''
                SELECT g.*, r.id as room_id, r.game_type, r.double_out_required
                FROM Games g
                JOIN GameRooms r ON r.id = g.room_id
                JOIN GamePlayers gp ON gp.game_id = r.id
                WHERE gp.player_id = ? 
                AND g.game_status = 'in_progress'
                AND r.room_status = 'in_progress'
                ORDER BY g.started_at DESC
                LIMIT 1
            ''', (session['user_id'],))
            
            game = cursor.fetchone()
            
            if not game:
                emit('error', {'message': 'Game not found'})
                return

            # Set current_room in session
            session['current_room'] = game['room_id']
            
            # Join both the game and room socket rooms
            join_room(f"game_{game['id']}")
            join_room(f"room_{game['room_id']}")
            
            # Get all players and their scores
            cursor.execute('''
                SELECT p.username, gp.current_score, gp.player_position
                FROM GamePlayers gp
                JOIN Players p ON p.id = gp.player_id
                WHERE gp.game_id = ?
                ORDER BY gp.player_position
            ''', (game['id'],))
            
            players = cursor.fetchall()
            
            if not players:
                emit('error', {'message': 'No players found in game'})
                return

            # Get current player
            cursor.execute('''
                SELECT p.username as current_player
                FROM Players p
                JOIN GamePlayers gp ON gp.player_id = p.id
                WHERE gp.game_id = ? AND gp.player_position = ?
            ''', (game['id'], game['current_player_position']))
            current_player = cursor.fetchone()

            # Get the latest round info if any exists
            cursor.execute('''
                SELECT gr.*, p.username as player_name
                FROM GameRounds gr
                JOIN Players p ON p.id = gr.player_id
                WHERE gr.game_id = ?
                ORDER BY gr.timestamp DESC
                LIMIT 1
            ''', (game['id'],))
            latest_round = cursor.fetchone()
            
            # Send initial game state to all players in the room
            emit('game_state_update', {
                'game_id': game['id'],
                'current_score': next((p['current_score'] for p in players 
                                    if p['username'] == session['username']), None),
                'game_type': game['game_type'],
                'double_out_required': game['double_out_required'],
                'players': [{
                    'username': p['username'],
                    'score': p['current_score'],
                    'position': p['player_position']
                } for p in players],
                'current_player': current_player['current_player'] if current_player else players[0]['username'],
                'round_info': dict(latest_round) if latest_round else None,
                'game_over': False
            }, room=f"game_{game['id']}")
            
    except sqlite3.Error as e:
        print(f"Database error in join_game: {e}")
        emit('error', {'message': 'Failed to join game'})


@socketio.on('toggle_cv_mode')
def handle_toggle_cv_mode(data):
    """Handle toggling CV mode on/off for entire game"""
    print(f"Toggle CV mode called with data: {data}") # Debug: Event handler entry
    global cv_polling_active, cv_polling_thread
    
    try:
        game_id = get_current_game_id()
        if not game_id:
            print("No active game found for CV mode toggle") # Debug: No game
            emit('error', {'message': 'No active game found'})
            return

        is_enabled = data.get('enabled', False)
        print(f"CV mode being set to: {is_enabled} for game {game_id}") # Debug: Toggle state

        if is_enabled:
            # Get latest throw ID and start tracking this game
            last_id = get_latest_cv_throw_id()
            cv_active_games[game_id] = last_id
            
            # Start polling thread if not already running
            if not cv_polling_active:
                print("Starting CV polling thread") # Debug: Thread start
                cv_polling_active = True
                cv_polling_thread = threading.Thread(target=cv_polling_loop)
                cv_polling_thread.daemon = True
                cv_polling_thread.start()
        else:
            # Remove game from tracking
            print(f"Stopping CV mode for game {game_id}") # Debug: Mode stop
            cv_active_games.pop(game_id, None)
            
            # Stop polling if no games are using CV mode
            if not cv_active_games and cv_polling_active:
                print("Stopping CV polling thread") # Debug: Thread stop
                cv_polling_active = False
                if cv_polling_thread:
                    cv_polling_thread.join(timeout=1.0)
                    cv_polling_thread = None
        
        # Notify all players in the game about CV mode status
        print(f"Broadcasting CV mode status to game {game_id}") # Debug: Broadcasting
        emit('cv_mode_status', {
            'enabled': is_enabled,
            'toggled_by': session['username']
        }, room=f"game_{game_id}")
        
    except Exception as e:
        print(f"Error toggling CV mode: {e}")
        emit('error', {'message': 'Failed to toggle CV mode'})



# Run the server
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
