from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
import bcrypt
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'voting_system'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# Helper functions
def get_db_connection():
    return mysql.connection.cursor()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(hashed_password, user_password):
    return bcrypt.checkpw(user_password.encode('utf-8'), hashed_password.encode('utf-8'))

# Routes
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = get_db_connection()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        
        if user and check_password(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('profile'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        full_name = request.form['full_name']
        voter_id = request.form['voter_id']
        
        hashed_password = hash_password(password)
        
        try:
            cur = get_db_connection()
            cur.execute(
                "INSERT INTO users (username, password, email, full_name, voter_id) VALUES (%s, %s, %s, %s, %s)",
                (username, hashed_password, email, full_name, voter_id)
            )
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('login'))
        except Exception as e:
            return render_template('signup.html', error=str(e))
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    cur = get_db_connection()
    
    # Get user info
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    
    # Check if user has voted
    cur.execute("SELECT COUNT(*) as count FROM votes WHERE user_id = %s", (user_id,))
    vote_count = cur.fetchone()['count']
    has_voted = vote_count > 0
    
    cur.close()
    
    return render_template('profile.html', user=user, has_voted=has_voted)

@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Check if user has already voted
    cur = get_db_connection()
    cur.execute("SELECT COUNT(*) as count FROM votes WHERE user_id = %s", (user_id,))
    vote_count = cur.fetchone()['count']
    if vote_count > 0:
        return redirect(url_for('profile'))
    
    if request.method == 'POST':
        # Process the vote
        votes = request.get_json()
        
        try:
            cur = get_db_connection()
            for position_id, candidate_id in votes.items():
                cur.execute(
                    "INSERT INTO votes (user_id, candidate_id, position_id) VALUES (%s, %s, %s)",
                    (user_id, candidate_id, position_id)
                )
            
            # Mark user as voted
            cur.execute("UPDATE users SET has_voted = TRUE WHERE id = %s", (user_id,))
            mysql.connection.commit()
            cur.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    # GET request - show voting page
    cur.execute("SELECT * FROM positions")
    positions = cur.fetchall()
    
    candidates_by_position = {}
    for position in positions:
        cur.execute("""
            SELECT c.*, p.title as position_title 
            FROM candidates c 
            JOIN positions p ON c.position_id = p.id 
            WHERE c.position_id = %s
        """, (position['id'],))
        candidates = cur.fetchall()
        candidates_by_position[position['id']] = {
            'position': position,
            'candidates': candidates
        }
    
    cur.close()
    return render_template('vote.html', positions=candidates_by_position)

@app.route('/results')
def results():
    cur = get_db_connection()
    
    # Get all positions
    cur.execute("SELECT * FROM positions")
    positions = cur.fetchall()
    
    results = {}
    for position in positions:
        cur.execute("""
            SELECT c.name, c.party, COUNT(v.id) as vote_count
            FROM candidates c
            LEFT JOIN votes v ON c.id = v.candidate_id
            WHERE c.position_id = %s
            GROUP BY c.id
            ORDER BY vote_count DESC
        """, (position['id'],))
        candidates = cur.fetchall()
        results[position['id']] = {
            'position': position,
            'candidates': candidates
        }
    
    cur.close()
    return render_template('results.html', results=results)

if __name__ == '__main__':
    app.run(debug=True)