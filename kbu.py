from flask import Flask, render_template, request, redirect, jsonify, url_for, session
import json
import os
from dotenv import load_dotenv
import time
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("PaulKey")  # Replace with a strong secret key for session management

# Paths for the JSON files
USER_DATA_FILE = "data/users.json"
BIO_DATA_FILE = "data/bio.json"
MESSAGE_DATA_FILE = "data/messages.json"
UPLOAD_FOLDER = 'static/uploads'
BACKGROUND_UPLOAD_FOLDER = 'static/backuploads'

# Ensure necessary folders and files exist
for folder in [UPLOAD_FOLDER, BACKGROUND_UPLOAD_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

for file_path in [USER_DATA_FILE, BIO_DATA_FILE, MESSAGE_DATA_FILE]:
    if not os.path.exists(file_path) or os.stat(file_path).st_size == 0:
        with open(file_path, "w") as file:
            json.dump([], file, indent=4) if "messages" in file_path else json.dump({}, file, indent=4)

# Utility functions to read/write JSON files
def read_users_from_file():
    try:
        with open(USER_DATA_FILE, "r") as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_users_to_file(users):
    with open(USER_DATA_FILE, "w") as file:
        json.dump(users, file, indent=4)

def read_bio_from_file():
    try:
        with open(BIO_DATA_FILE, "r") as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_bio_to_file(bios):
    with open(BIO_DATA_FILE, "w") as file:
        json.dump(bios, file, indent=4)

def read_messages_from_file():
    try:
        with open(MESSAGE_DATA_FILE, "r") as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_messages_to_file(messages):
    with open(MESSAGE_DATA_FILE, "w") as file:
        json.dump(messages, file, indent=4)

def generate_user_id(users):
    if users:
        last_user_id = max(int(uid) for uid in users.keys())
        return f"{last_user_id + 1:05d}"
    return "00001"

# Utility function to save files
def save_file(file, folder_path):
    filename = secure_filename(file.filename)
    file_path = os.path.join(folder_path, filename)
    file.save(file_path)
    return filename

# Routes
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

        users = read_users_from_file()

        if any(user["email"] == email for user in users.values()):
            return "This email is already registered. Please use a different email."

        user_id = generate_user_id(users)
        users[user_id] = {
            "username": username,
            "email": email,
            "line_id": line_id,
            "dob": dob,
            "member_no": user_id
        }

        save_users_to_file(users)

        session['member_no'] = user_id
        session['username'] = username

        return redirect('/')

    return render_template("register.html")

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        member_no = request.form.get("member_no", "").strip()

        users = read_users_from_file()

        for user_id, user_data in users.items():
            if user_data.get("email") == email and user_data.get("member_no") == member_no:
                session['member_no'] = user_data["member_no"]
                session['username'] = user_data["username"]
                return redirect('/')

        return "Invalid credentials. Please try again."
    return render_template("login.html")

@app.route('/profile/<user_id>', methods=["GET", "POST"])
def profile(user_id):
    users = read_users_from_file()
    bios = read_bio_from_file()

    if user_id not in users:
        return "User not found!", 404

    user_data = users[user_id]

    if request.method == "POST":
        # Profile Picture Upload
        if "profile_picture" in request.files:
            profile_picture = request.files["profile_picture"]
            if profile_picture:
                filename = save_file(profile_picture, UPLOAD_FOLDER)
                user_data["profile_picture"] = url_for('static', filename=f'uploads/{filename}')
                users[user_id] = user_data
                save_users_to_file(users)

        # Background Picture Upload
        if "background_picture" in request.files:
            background_picture = request.files["background_picture"]
            if background_picture:
                filename = save_file(background_picture, BACKGROUND_UPLOAD_FOLDER)
                user_data["profile_background"] = filename  # Save filename in user data
                users[user_id] = user_data
                save_users_to_file(users)

        # Bio Update
        bio = request.form.get("bio", "").strip()
        if bio:
            bios[user_id] = bio
            save_bio_to_file(bios)

        return redirect(f'/profile/{user_id}')

    # Default profile picture and background
    profile_picture = user_data.get("profile_picture", url_for('static', filename="uploads/default-avatar.jpg"))
    profile_background = user_data.get("profile_background", "profileback.jpg")
    user_bio = bios.get(user_id, "")

    return render_template("profile.html", user_data=user_data, user_bio=user_bio,
                           profile_picture=profile_picture, profile_background=profile_background)

@app.route('/get-member-no', methods=["GET"])
def get_member_no():
    email = request.args.get("email", "").strip()
    users = read_users_from_file()

    for user_id, user_data in users.items():
        if user_data.get("email") == email:
            return jsonify({"member_no": user_data["member_no"]})

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
        return redirect('/login')  # Redirect to login if not logged in

    username = session.get('username', 'Guest')
    messages = read_messages_from_file()

    if request.method == "POST":
        message_text = request.form.get("message", "").strip()
        if message_text:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            message_data = {"username": username, "message": message_text, "timestamp": timestamp}
            messages.append(message_data)
            save_messages_to_file(messages)

        return redirect('/chat')  # Redirect to avoid form resubmission

    return render_template('chat.html', username=username, messages=messages)

if __name__ == "__main__":
    app.run(debug=True)
