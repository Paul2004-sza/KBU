from flask import Flask, render_template, request, redirect, jsonify, url_for, session
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("PaulKey")

DB_CONFIG = {
    'host': os.getenv('db_host'),
    'user': os.getenv('db_user'),
    'password': os.getenv('db_password'),
    'database': os.getenv('db_name')
}

UPLOAD_FOLDER = 'static/uploads'
BACKGROUND_UPLOAD_FOLDER = 'static/backuploads'
MESSAGE_UPLOAD_FOLDER = 'static/messageuploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

class Database:
    @staticmethod
    def get_connection():
        return mysql.connector.connect(**DB_CONFIG)

    @staticmethod
    def query_db(query, args=(), fetchone=False, commit=False):
        conn = Database.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, args)
        if commit:
            conn.commit()
            conn.close()
            return
        result = cursor.fetchone() if fetchone else cursor.fetchall()
        conn.close()
        return result

class User:
    @staticmethod
    def register(username, email, line_id, dob):
        user = Database.query_db("SELECT * FROM users WHERE email = %s", (email,), fetchone=True)
        if user:
            return "This email is already registered. Please use a different email."

        Database.query_db(
            "INSERT INTO users (username, email, line_id, dob) VALUES (%s, %s, %s, %s)",
            (username, email, line_id, dob),
            commit=True
        )

        new_user = Database.query_db("SELECT * FROM users WHERE email = %s", (email,), fetchone=True)
        return new_user

    @staticmethod
    def login(email, member_no):
        user = Database.query_db("SELECT * FROM users WHERE email = %s AND member_no = %s", (email, member_no), fetchone=True)
        return user

    @staticmethod
    def get_user(user_id):
        return Database.query_db("SELECT * FROM users WHERE member_no = %s", (user_id,), fetchone=True)

    @staticmethod
    def update_profile(user_id, profile_picture=None, background_picture=None, bio=None):
        if profile_picture:
            filename = FileHandler.save_file(profile_picture, UPLOAD_FOLDER)
            Database.query_db(
                "UPDATE users SET profile_picture = %s WHERE member_no = %s",
                (url_for('static', filename=f'uploads/{filename}'), user_id),
                commit=True
            )

        if background_picture:
            filename = FileHandler.save_file(background_picture, BACKGROUND_UPLOAD_FOLDER)
            Database.query_db(
                "UPDATE users SET profile_background = %s WHERE member_no = %s",
                (filename, user_id),
                commit=True
            )

        if bio:
            Database.query_db(
                "UPDATE users SET bio = %s WHERE member_no = %s",
                (bio, user_id),
                commit=True
            )

class FileHandler:
    @staticmethod
    def save_file(file, folder_path):
        filename = secure_filename(file.filename)
        file_path = os.path.join(folder_path, filename)
        file.save(file_path)
        return filename

class Message:
    @staticmethod
    def send_message(member_no, username, message_text, profile_picture, image=None, video=None):
        image_filename = FileHandler.save_file(image, MESSAGE_UPLOAD_FOLDER) if image else None
        video_filename = FileHandler.save_file(video, MESSAGE_UPLOAD_FOLDER) if video else None
        timestamp = datetime.utcnow().isoformat()

        Database.query_db(
            "INSERT INTO messages (member_no, username, message, timestamp, profile_picture, image, video) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (member_no, username, message_text, timestamp, profile_picture, image_filename, video_filename),
            commit=True
        )

    @staticmethod
    def get_messages():
        return Database.query_db("SELECT * FROM messages WHERE deleted = 0 ORDER BY timestamp DESC")

    @staticmethod
    def delete_message(timestamp, member_no):
        Database.query_db(
            "UPDATE messages SET deleted = 1 WHERE timestamp = %s AND member_no = %s",
            (timestamp, member_no),
            commit=True
        )

    @staticmethod
    def unsend_message(timestamp, member_no):
        Database.query_db(
            "DELETE FROM messages WHERE timestamp = %s AND member_no = %s",
            (timestamp, member_no),
            commit=True
        )

    @staticmethod
    def reply_message(timestamp, member_no, username, reply_text):
        Database.query_db(
            "INSERT INTO replies (message_timestamp, member_no, username, reply, timestamp) VALUES (%s, %s, %s, %s, %s)",
            (timestamp, member_no, username, reply_text, datetime.utcnow().isoformat()),
            commit=True
        )

    @staticmethod
    def react(message_id, member_no, reaction):
        existing_reaction = Database.query_db(
            "SELECT * FROM reactions WHERE message_timestamp = %s AND member_no = %s",
            (message_id, member_no),
            fetchone=True
        )

        if existing_reaction:
            if existing_reaction['reaction'] == reaction:
                Database.query_db(
                    "DELETE FROM reactions WHERE message_timestamp = %s AND member_no = %s",
                    (message_id, member_no),
                    commit=True
                )
            else:
                Database.query_db(
                    "UPDATE reactions SET reaction = %s WHERE message_timestamp = %s AND member_no = %s",
                    (reaction, message_id, member_no),
                    commit=True
                )
        else:
            Database.query_db(
                "INSERT INTO reactions (message_timestamp, member_no, reaction) VALUES (%s, %s, %s)",
                (message_id, member_no, reaction),
                commit=True
            )

@app.route('/')
def home():
    if 'member_no' in session:
        username = session.get('username', 'Guest')
        return render_template('home.html', logged_in=True, username=username)
    return render_template('home.html', logged_in=False)

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        line_id = request.form.get("line_id", "").strip()
        dob = request.form.get("dob", "").strip()

        new_user = User.register(username, email, line_id, dob)
        if isinstance(new_user, str):
            return new_user

        session['member_no'] = new_user['member_no']
        session['username'] = new_user['username']

        return redirect('/')

    return render_template("register.html")

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        member_no = request.form.get("member_no", "").strip()

        user = User.login(email, member_no)
        if user:
            session['member_no'] = user["member_no"]
            session['username'] = user["username"]
            return redirect('/')

        return "Invalid credentials. Please try again."
    return render_template("login.html")

@app.route('/profile/<user_id>', methods=["GET", "POST"])
def profile(user_id):
    user_data = User.get_user(user_id)
    if not user_data:
        return "User not found!", 404

    if request.method == "POST":
        profile_picture = request.files.get("profile_picture")
        background_picture = request.files.get("background_picture")
        bio = request.form.get("bio", "").strip()

        User.update_profile(user_id, profile_picture, background_picture, bio)
        return redirect(f'/profile/{user_id}')

    profile_picture = user_data.get("profile_picture", url_for('static', filename="uploads/default-avatar.jpg"))
    profile_background = user_data.get("profile_background", "profileback.jpg")
    user_bio = user_data.get("bio", "")

    return render_template("profile.html", user_data=user_data, user_bio=user_bio,
                           profile_picture=profile_picture, profile_background=profile_background)

@app.route('/get-member-no', methods=["GET"])
def get_member_no():
    email = request.args.get("email", "").strip()
    user = Database.query_db("SELECT member_no FROM users WHERE email = %s", (email,), fetchone=True)

    if user:
        return jsonify({"member_no": user["member_no"]})

    return jsonify({"error": "No Member No found for the provided email"}), 404

@app.route('/myprofile')
def myprofile():
    if 'member_no' in session:
        return redirect(url_for('profile', user_id=session['member_no']))
    return redirect('/login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/chat', methods=["GET", "POST"])
def chat():
    if 'member_no' not in session:
        return redirect('/login')

    username = session.get('username', 'Guest')
    user_data = User.get_user(session['member_no'])
    profile_picture = user_data.get("profile_picture", url_for('static', filename="uploads/default-avatar.jpg"))

    if request.method == "POST":
        message_text = request.form.get("message", "").strip()
        image = request.files.get("image")
        video = request.files.get("video")

        Message.send_message(session['member_no'], username, message_text, profile_picture, image, video)
        return redirect('/chat')

    messages = Message.get_messages()
    return render_template('chat.html', username=username, messages=messages, profile_picture=profile_picture)

@app.route('/reply_message/<timestamp>', methods=["POST"])
def reply_message(timestamp):
    if 'member_no' not in session:
        return redirect('/login')

    reply_text = request.form.get("reply", "").strip()
    if not reply_text:
        return redirect('/chat')

    Message.reply_message(timestamp, session['member_no'], session.get('username', 'Guest'), reply_text)
    return redirect('/chat')

@app.route('/delete_message/<timestamp>', methods=["POST"])
def delete_message(timestamp):
    if 'member_no' not in session:
        return redirect('/login')

    Message.delete_message(timestamp, session['member_no'])
    return redirect('/chat')

@app.route('/unsend_message/<timestamp>', methods=["POST"])
def unsend_message(timestamp):
    if 'member_no' not in session:
        return redirect('/login')

    Message.unsend_message(timestamp, session['member_no'])
    return redirect('/chat')

@app.route('/react', methods=["POST"])
def react():
    if 'member_no' not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    message_id = data.get("messageId")
    reaction = data.get("reaction")

    Message.react(message_id, session['member_no'], reaction)
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True)