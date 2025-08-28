import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
import plotly.express as px
import pytz
import requests
import secrets
import json
from urllib.parse import urlencode
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from pymongo import MongoClient
import pandas as pd
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from datetime import datetime, timedelta
from bson import ObjectId
from werkzeug.utils import secure_filename
from flask import send_from_directory

# Load environment variables first
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'pptx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')


GOOGLE_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid_configuration"

# MongoDB setup (keeping your existing setup)
MONGO_URI = os.environ.get('url')
utc_now = datetime.utcnow()
local_tz = pytz.timezone("Asia/Kolkata")
local_now = utc_now.replace(tzinfo=pytz.utc).astimezone(local_tz)

try:
    client = MongoClient(MONGO_URI)
    db = client.get_database('pathfinderDB')
    users_collection = db.users
    subjects_collection = db.subjects
    activities_collection = db.activities
    goals_collection = db.goals
    sessions_collection = db.sessions
    reminders_collection = db.reminders
    files_collection = db.files
    client.admin.command('ping')
    print("MongoDB connection successful.")
except Exception as e:
    print(f"Could not connect to MongoDB: {e}")
    db = None
    users_collection = None
    subjects_collection = None
    activities_collection = None
    goals_collection = None
    sessions_collection = None
    reminders_collection = None
    files_collection = None

bcrypt = Bcrypt(app)

def get_google_provider_cfg():
    """Get Google's OAuth configuration"""
    try:
        response = requests.get(GOOGLE_DISCOVERY_URL)
        return response.json()
    except:
        # Fallback configuration
        return {
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/auth",
            "token_endpoint": "https://oauth2.googleapis.com/token",
            "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo"
        }

@app.route('/')
def home():
    return redirect(url_for('login'))

# Debug route to check OAuth configuration
@app.route('/debug-oauth')
def debug_oauth():
    redirect_uri = 'http://127.0.0.1:5000/auth/callback'  # Fixed
    return f"""
    <h2>OAuth Debug Info</h2>
    <p><strong>Redirect URI:</strong> {redirect_uri}</p>
    <p><strong>Client ID:</strong> {GOOGLE_CLIENT_ID}</p>
    <p><strong>Add this exact redirect URI to your Google Cloud Console!</strong></p>
    <hr>
    <p>In Google Cloud Console:</p>
    <ol>
        <li>Go to APIs & Services → Credentials</li>
        <li>Click your OAuth 2.0 Client ID</li>
        <li>Add this redirect URI: <strong>{redirect_uri}</strong></li>
        <li>Save changes</li>
    </ol>
    """

@app.route('/auth/google')
def google_login():
    """Initiate Google OAuth flow"""
    try:
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        session['oauth_state'] = state

        # Get Google's configuration
        google_provider_cfg = get_google_provider_cfg()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]

        # FIXED: Force 127.0.0.1 in redirect URI to match Google Console
        redirect_uri = 'http://127.0.0.1:5000/auth/callback'

        # Prepare the authorization URL
        params = {
            'client_id': GOOGLE_CLIENT_ID,
            'redirect_uri': redirect_uri,
            'scope': 'openid email profile',
            'response_type': 'code',
            'state': state,
            'access_type': 'offline',
            'prompt': 'consent'
        }

        authorization_url = authorization_endpoint + '?' + urlencode(params)
        print(f"Redirecting to: {authorization_url}")

        return redirect(authorization_url)

    except Exception as e:
        print(f"Error in google_login: {e}")
        flash("Error initiating Google login", "error")
        return redirect(url_for('login'))

@app.route('/auth/callback')
def callback():
    """Handle Google OAuth callback"""
    try:
        print("=== OAuth Callback Started ===")

        # Verify state parameter
        if request.args.get('state') != session.get('oauth_state'):
            print("State mismatch!")
            flash("Invalid state parameter", "error")
            return redirect(url_for('login'))

        # Get authorization code
        code = request.args.get('code')
        if not code:
            print("No authorization code received")
            flash("Authorization failed", "error")
            return redirect(url_for('login'))

        print(f"Authorization code received: {code[:20]}...")

        # Get Google's configuration
        google_provider_cfg = get_google_provider_cfg()
        token_endpoint = google_provider_cfg["token_endpoint"]

        # FIXED: Use same redirect URI format as in authorization
        redirect_uri = 'http://127.0.0.1:5000/auth/callback'

        # Exchange code for tokens
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        }

        print("Exchanging code for tokens...")
        token_response = requests.post(token_endpoint, data=token_data)

        if not token_response.ok:
            print(f"Token exchange failed: {token_response.text}")
            flash("Failed to exchange authorization code", "error")
            return redirect(url_for('login'))

        tokens = token_response.json()
        print("Tokens received successfully")

        # Get user info
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        headers = {'Authorization': f'Bearer {tokens["access_token"]}'}

        print("Fetching user info...")
        user_response = requests.get(userinfo_endpoint, headers=headers)

        if not user_response.ok:
            print(f"Failed to get user info: {user_response.text}")
            flash("Failed to get user information", "error")
            return redirect(url_for('login'))

        user_info = user_response.json()
        print(f"User info received: {user_info}")

        email = user_info.get('email')
        name = user_info.get('name', 'Google User')

        if not email:
            print("No email in user info")
            flash("Failed to get email from Google", "error")
            return redirect(url_for('login'))

        # Check if user exists in database
        user = users_collection.find_one({"email": email})

        if not user:
            # Register new Google user
            user_data = {
                "username": name,
                "email": email,
                "password": None,
                "auth_provider": "google",
                "created_at": datetime.utcnow()
            }
            result = users_collection.insert_one(user_data)
            user = users_collection.find_one({"_id": result.inserted_id})
            print(f"New user created: {email}")
        else:
            print(f"Existing user found: {email}")

        # Set session
        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        session.permanent = True

        # Clean up OAuth state
        session.pop('oauth_state', None)

        print(f"Login successful for: {name}")
        flash(f"Successfully logged in as {name}!", "success")
        return redirect(url_for('dashboard'))

    except Exception as e:
        print(f"=== OAuth Callback Error ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print("=== End Error ===")

        session.pop('oauth_state', None)
        flash("An error occurred during Google login", "error")
        return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if users_collection is None:
            flash("Database not connected. Please check server logs.", "error")
            return redirect(url_for('register'))

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = users_collection.find_one({'email': email})
        if existing_user:
            flash('Email already registered!', 'error')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        users_collection.insert_one({
            'username': username,
            'email': email,
            'password': hashed_password,
            'auth_provider': 'local',
            'created_at': datetime.utcnow()
        })

        flash('Registration successful! Login with the new ID', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if users_collection is None:
            flash("Database not connected. Please check server logs.", "error")
            return redirect(url_for('login'))

        email = request.form.get('email')
        password = request.form.get('password')

        user = users_collection.find_one({'email': email})
        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check your email and password.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))

    user_id_obj = ObjectId(session['user_id'])

    if activities_collection is not None:
        activities_collection.insert_one({
            'user_id': session['user_id'],
            'action': 'viewed_dashboard',
            'timestamp': datetime.utcnow()
        })
        user_subjects = list(subjects_collection.find({'owner_id': session['user_id']}))

        stats = {
            "daily": {"total": 0, "completed": 0},
            "weekly": {"total": 0, "completed": 0},
            "monthly": {"total": 0, "completed": 0}
        }

        todos = goals_collection.find({"user_id": session['user_id']})
        for todo in todos:
            period = todo.get("goal_period")
            completed = todo.get("completion_status", False)

            if period in stats:
                stats[period]["total"] += 1
                if completed:
                    stats[period]["completed"] += 1

        time_goals = list(goals_collection.find({
            'user_id': user_id_obj,
            'goal_type': 'time',
            'status': 'active'
        }))

        for goal in time_goals:
            subject = subjects_collection.find_one({'_id': goal.get('subject_id')})
            if subject:
                goal['subject_name'] = subject.get('subject', 'Unknown Subject')

        user_subjects = list(subjects_collection.find({'owner_id': session['user_id']}))

        for subject in user_subjects:
            subject_id_obj = subject['_id']
            subject['files'] = list(files_collection.find({'subject_id': subject_id_obj}))


        return render_template('dashboard.html',
                               username=session['username'],
                               subject_collection=user_subjects,
                               stats=stats,
                               time_goals=time_goals)


@app.route('/study_session/<subject_name>')
def study_session(subject_name):
    if 'user_id' not in session:
        flash('Please log in to start a session.', 'warning')
        return redirect(url_for('login'))

    local_today = datetime.now()
    week_start = local_today - timedelta(days=local_today.weekday())

    # Get session doc
    doc = sessions_collection.find_one({
        "user_id": ObjectId(session['user_id']),
        "subject_name": subject_name,
        "week_start": week_start.date().isoformat()
    })

    # Get the subject
    subject = subjects_collection.find_one({
        "owner_id": session['user_id'],
        "subject": subject_name.lower()
    })

    # Attach files for this subject
    if subject:
        original_subject_id = subject['_id']
        subject['_id'] = str(subject['_id'])
        subject['name'] = subject['subject']  # For template compatibility

        # Find files using original ObjectId
        files = list(files_collection.find({'subject_id': original_subject_id}))

        # Convert file ObjectIds to strings for template use
        for file in files:
            file['_id'] = str(file['_id'])
            if 'subject_id' in file:
                file['subject_id'] = str(file['subject_id'])

        subject['files'] = files
    else:
        subject = {"name": subject_name, "files": []}

    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    if not doc:
        time_spent = [0] * 7
        productive_hours = {}
    else:
        time_spent = [doc.get(day, 0) for day in days]
        productive_hours = doc.get("productive_hours", {})

    chart_data = [t / 60 for t in time_spent]

    return render_template(
        "study_session.html",
        subject=subject,
        subject_name=subject_name,
        chart_data=chart_data,
        days=days,
        productive_hours=productive_hours
    )


@app.route('/log_session', methods=['POST'])
def log_session():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    data = request.get_json()
    subject_name = data.get('subject_name')
    duration_seconds = data.get('duration_seconds')

    if not subject_name or duration_seconds is None:
        return jsonify({'status': 'error', 'message': 'Missing required data'}), 400

    duration_seconds = int(duration_seconds)
    local_today = datetime.now()
    today_str = local_today.strftime("%a").lower()
    week_start = local_today - timedelta(days=local_today.weekday())

    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=duration_seconds)

    # Productive hours calculation
    current = start_time
    remaining = duration_seconds
    updates = {}

    while current < end_time and remaining > 0:
        hour_key = str(current.hour).zfill(2)
        seconds_left_in_hour = (60 - current.minute) * 60 - current.second
        seconds_to_add = min(remaining, seconds_left_in_hour)
        updates[f"productive_hours.{hour_key}"] = updates.get(f"productive_hours.{hour_key}", 0) + (
                    seconds_to_add // 60)
        remaining -= seconds_to_add
        current += timedelta(seconds=seconds_to_add)

    # Find subject
    subject = subjects_collection.find_one({
        "owner_id": session['user_id'],
        "subject": subject_name.lower()
    })

    if not subject:
        return jsonify({'status': 'error', 'message': 'Subject not found'}), 404

    # Get or create weekly doc
    weekly_doc = sessions_collection.find_one({
        "user_id": ObjectId(session['user_id']),
        "subject_id": subject['_id'],
        "week_start": week_start.date().isoformat()
    })

    if not weekly_doc:
        weekly_doc = {
            "user_id": ObjectId(session['user_id']),
            "subject_id": subject['_id'],
            "subject_name": subject_name,
            "week_start": week_start.date().isoformat(),
            "mon": 0, "tue": 0, "wed": 0,
            "thu": 0, "fri": 0, "sat": 0, "sun": 0,
            "productive_hours": {str(h).zfill(2): 0 for h in range(24)},
            'created_at': datetime.utcnow()
        }
        sessions_collection.insert_one(weekly_doc)

    # Update study time + productive hours
    sessions_collection.update_one(
        {
            "user_id": ObjectId(session['user_id']),
            "subject_id": subject['_id'],
            "week_start": week_start.date().isoformat()
        },
        {
            "$inc": {
                today_str: duration_seconds // 60,
                **updates
            }
        }
    )

    now = datetime.utcnow()
    duration_minutes = int(duration_seconds) / 60

    # Update time-based goals
    goals_collection.update_one(
        {
            'user_id': ObjectId(session['user_id']),
            'subject_id': subject['_id'],
            'goal_type': 'time',
            'status': 'active',
            'start_date': {'$lte': now},
            'end_date': {'$gte': now}
        },
        {
            '$inc': {'current_duration_minutes': duration_minutes}
        })

    return jsonify({'status': 'success', 'message': f'Session logged to {today_str} successfully!'})


@app.route('/add_form')
def add_form():
    return render_template('add.html')


@app.route('/add', methods=['POST'])
def add_subject():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    subject = request.form['subject'].lower()
    marks = int(request.form['marks'])
    priority = request.form.get('priority')
    category = request.form.get('category')
    description = request.form.get('description')

    subject_data = {
        'owner_id': session['user_id'],
        'subject': subject,
        'marks': marks,
        'priority': priority,
        'category': category,
        'description': description,
        'created_at': datetime.utcnow()
    }

    subjects_collection.insert_one(subject_data)
    flash('Subject added successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/update', methods=['POST'])
def update():
    if 'user_id' not in session:
        return "Unauthorized", 401

    subject = request.form['subject'].lower()
    new_marks = int(request.form['marks'])
    new_priority = request.form.get('priority')
    new_category = request.form.get('category')

    subjects_collection.update_one(
        {"subject": subject, "owner_id": session['user_id']},
        {"$set": {"marks": new_marks, "priority": new_priority,"category":new_category}}
    )
    return "Success", 200


@app.route('/delete', methods=['POST'])
def delete():
    if 'user_id' not in session:
        return "Unauthorized", 401

    subject = request.form['subject'].lower()


    result = subjects_collection.delete_one({
            "subject": subject,
            "owner_id": session['user_id']
        })

    return "Success", 200


@app.route('/upload/<subject_id>', methods=['POST'])
def upload_file(subject_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('dashboard'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        user_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], session['user_id'])
        os.makedirs(user_upload_folder, exist_ok=True)
        file_path = os.path.join(user_upload_folder, filename)
        file.save(file_path)

        # --- THIS IS THE NEW PART ---
        # 1. Find the subject document to get its name
        subject_doc = subjects_collection.find_one({'_id': ObjectId(subject_id)})
        subject_name = subject_doc.get('subject', 'Unknown Subject') if subject_doc else 'Unknown Subject'

        # 2. Save the file's metadata, now including the subject_name
        files_collection.insert_one({
            'user_id': ObjectId(session['user_id']),
            'subject_id': ObjectId(subject_id),
            'subject_name': subject_name,  # <-- The new field you wanted
            'original_filename': file.filename,
            'secure_filename': filename,
            'file_path': file_path,
            'file_type': file.mimetype,
            'upload_date': datetime.utcnow()
        })
        # ---------------------------


        # Check if request came from study session
        if request.form.get('source') == 'study_session':
            return redirect(url_for('study_session', subject_name=subject_name))
    else:
        flash('File type not allowed.', 'danger')

    return redirect(url_for('dashboard'))


@app.route('/download/<file_id>')
def download_file(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file_doc = files_collection.find_one({'_id': ObjectId(file_id), 'user_id': ObjectId(session['user_id'])})
    if not file_doc:
        return "File not found or access denied.", 404

    # The directory is the user's specific upload folder
    directory = os.path.join(app.config['UPLOAD_FOLDER'], session['user_id'])

    # Use send_from_directory for security
    return send_from_directory(directory=directory, path=file_doc['secure_filename'], as_attachment=False)


# Add this new route to main.py
@app.route('/view_file/<file_id>')
def view_file(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Find the file metadata in the database
    file_doc = files_collection.find_one({
        '_id': ObjectId(file_id),
        'user_id': ObjectId(session['user_id'])
    })

    if not file_doc:
        # Check if request came from study session
        if request.args.get('source') == 'study_session':
            # Need to have file_doc before using it - redirect to dashboard if file not found
            return redirect(url_for('dashboard'))
        return redirect(url_for('dashboard'))

    # Get the directory where the user's files are stored
    directory = os.path.join(app.config['UPLOAD_FOLDER'], session['user_id'])

    # Serve the file for inline viewing (the browser will try to open it)
    return send_from_directory(
        directory=directory,
        path=file_doc['secure_filename'],
        as_attachment=False
    )


@app.route('/delete_file/<file_id>', methods=['POST'])
def delete_file(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file_doc = files_collection.find_one({'_id': ObjectId(file_id), 'user_id': ObjectId(session['user_id'])})
    if file_doc:
        # Delete the physical file from the server
        try:
            os.remove(file_doc['file_path'])
        except OSError as e:
            print(f"Error deleting file {file_doc['file_path']}: {e}")
            flash('Error deleting file from server.', 'danger')

        # Delete the metadata from the database
        files_collection.delete_one({'_id': ObjectId(file_id)})

        # Check if request came from study session
        if request.form.get('source') == 'study_session':
            return redirect(url_for('study_session', subject_name=file_doc.get('subject_name', 'Unknown')))
    else:
        flash('File not found or you do not have permission to delete it.', 'danger')

    return redirect(url_for('dashboard'))

@app.route("/reminders", methods=["GET", "POST"])
def reminders():
    user_id = session["user_id"]

    if request.method == "GET":
        today = datetime.now().strftime('%Y-%m-%d')

        reminders_collection.delete_many({
            "user_id": user_id,
            "date": {"$lt": today}
        })

        data = list(reminders_collection.find(
            {"user_id": user_id},
            {"_id": 0}
        ))
        return jsonify(data)

    if request.method == "POST":
        title = request.json.get("title")
        date = request.json.get("date")

        if not title or not date:
            return jsonify({"success": False})

        reminders_collection.insert_one({
            "user_id": user_id,
            "title": title,
            "date": date
        })
        return jsonify({"success": True})


@app.route('/time')
def time():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    subjects = list(sessions_collection.find({"user_id": ObjectId(session['user_id'])}))

    if not subjects:
        chart2 = "<p>No subjects found. Please add some subjects first.</p>"
        max_subject = None
        min_subject = None
    else:
        df = pd.DataFrame(subjects)
        weekday_cols = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        df["time_spent"] = df[weekday_cols].sum(axis=1)
        df_grouped = df.groupby("subject_name", as_index=False)["time_spent"].sum()
        df_grouped["time_hours"] = df_grouped["time_spent"] / 3600

        fig2 = px.bar(df_grouped,
                      x="subject_name",
                      y="time_hours",
                      title="Total Study Time by Subject (hrs)",
                      text="time_hours",
                      color_discrete_sequence=["#6B8E23"])

        chart2 = fig2.to_html(full_html=False, include_plotlyjs='cdn')

        max_row = df_grouped.loc[df_grouped["time_spent"].idxmax()]
        min_row = df_grouped.loc[df_grouped["time_spent"].idxmin()]

        max_subject = {
            "name": max_row["subject_name"],
            "hours": round(max_row["time_spent"] / 3600, 1)
        }
        min_subject = {
            "name": min_row["subject_name"],
            "hours": round(min_row["time_spent"] / 3600, 1)
        }

    return render_template("time.html",
                           chart2=chart2,
                           max_subject=max_subject,
                           min_subject=min_subject,
                           subjects=subjects)
@app.route('/history')
def study_history():
    """Displays a complete history of all past study sessions."""
    if 'user_id' not in session:
        flash('Please log in to view your history.', 'warning')
        return redirect(url_for('login'))

    # Find all sessions for the current user and sort them by end_time (newest first)
    user_sessions = list(sessions_collection.find(
        {'user_id': ObjectId(session['user_id'])}
    ).sort('end_time', -1))

    return render_template('history.html', sessions=user_sessions)

@app.route('/add_goal_form')
def add_goal_form():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Fetch user's subjects to show in the dropdown
    subjects = list(subjects_collection.find({'owner_id': session['user_id']}))
    return render_template('add_goal.html', subjects=subjects)

# In main.py
@app.route('/add_goal', methods=['POST'])
def add_goal():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    subject_id = request.form.get('subject_id')
    target_duration = float(request.form.get('target_duration')) # Assuming hours for now
    period = request.form.get('period')

    # Calculate start and end dates for the goal
    today = datetime.utcnow()
    if period == 'weekly':
        start_date = today - timedelta(days=today.weekday()) # Monday
        end_date = start_date + timedelta(days=6) # Sunday
    else: # monthly
        start_date = today.replace(day=1)
        # Find the last day of the month
        next_month = start_date.replace(day=28) + timedelta(days=4)
        end_date = next_month - timedelta(days=next_month.day)

    goal_data = {
        'user_id': ObjectId(session['user_id']),
        'subject_id': ObjectId(subject_id),
        'goal_type': 'time',
        'target_duration_minutes': target_duration * 60, # Convert hours to minutes
        'current_duration_minutes': 0,
        'start_date': start_date.replace(hour=0, minute=0, second=0),
        'end_date': end_date.replace(hour=23, minute=59, second=59),
        'status': 'active'
    }

    goals_collection.insert_one(goal_data)
    flash('New time-based goal has been set!', 'success')
    return redirect(url_for('dashboard'))



@app.route("/todo_stats")
@app.route("/todo_stats")
def todo_stats():
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    user_id = session.get("user_id")

    stats = {
        "daily": {"total": 0, "completed": 0},
        "weekly": {"total": 0, "completed": 0},
        "monthly": {"total": 0, "completed": 0}
    }

    todos = goals_collection.find({"user_id": user_id})

    for todo in todos:
        period = todo.get("goal_period")
        completed = todo.get("completion_status", False)

        if period in stats:
            stats[period]["total"] += 1
            if completed:
                stats[period]["completed"] += 1

    return jsonify(stats)


@app.route('/todo')
def get_todos():
    if 'user_id' not in session:
        return {"todos": []}

    today = datetime.utcnow()

    expired_goals = list(goals_collection.find({
        "user_id": session['user_id'],
        "deadline": {"$lt": today},
        "completion_status": False
    }))

    if expired_goals:
        expired_goal_ids = [g["_id"] for g in expired_goals]
        goals_collection.delete_many({
            "user_id": session['user_id'],
            "_id": {"$in": expired_goal_ids}
        })

    cleanup_time = today - timedelta(days=1)
    goals_collection.delete_many({
        "user_id": session['user_id'],
        "deadline": {"$lt": cleanup_time},
        "completion_status": True
    })

    todos = list(goals_collection.find(
        {"user_id": session['user_id']},
        {
            "task": 1,
            "_id": 1,
            "completion_status": 1,
            "goal_period": 1,
            "created_at": 1,
            "deadline": 1
        }
    ))

    for todo in todos:
        todo["_id"] = str(todo["_id"])
        todo["completion_status"] = todo.get("completion_status", False)
        todo["goal_period"] = todo.get("goal_period", "no-period")

    return jsonify({"todos": todos})


@app.route("/todo/add", methods=["POST"])
def add_todo():
    user_id = session.get("user_id")
    task = request.json.get("task")
    goal_period = request.json.get("goal_period")

    if not task:
        return jsonify({"error": "Task cannot be empty"}), 400

    if not goal_period:
        return jsonify({"error": "Goal period is required"}), 400

    today = datetime.utcnow()
    if goal_period == "daily":
        deadline = today + timedelta(days=1)
    elif goal_period == "weekly":
        deadline = today + timedelta(weeks=1)
    elif goal_period == "monthly":
        deadline = today + timedelta(days=30)
    else:
        deadline = today + timedelta(days=1)

    new_goal = {
        "user_id": user_id,
        "task": task,
        "goal_type": "task",
        "current_progress": 0,
        "goal_period": goal_period,
        "deadline": deadline,
        "completion_status": False,
        "created_at": datetime.utcnow()
    }

    result = goals_collection.insert_one(new_goal)

    if result.inserted_id:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to add task"}), 500


@app.route("/todo/done", methods=["POST"])
def mark_todo_done():
    user_id = session.get("user_id")
    todo_id = request.json.get("id")

    if not todo_id:
        return jsonify({"error": "Todo ID is required"}), 400

    try:
        todo = goals_collection.find_one({"_id": ObjectId(todo_id), "user_id": user_id})
        if not todo:
            return jsonify({"error": "Todo not found"}), 404

        new_status = not todo.get("completion_status", False)
        progress = 1 if new_status else 0

        result = goals_collection.update_one(
            {"_id": ObjectId(todo_id), "user_id": user_id},
            {"$set": {
                "completion_status": new_status,
                "current_progress": progress
            }}
        )

        if result.modified_count > 0:
            return jsonify({"success": True, "completion_status": new_status})
        else:
            return jsonify({"error": "Failed to update todo"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/todo/check-deadlines", methods=["GET"])
def check_deadlines():
    if 'user_id' not in session:
        return jsonify({"expiredTasks": []})

    today = datetime.utcnow()

    expired_tasks = list(goals_collection.find({
        "user_id": session['user_id'],
        "deadline": {"$lt": today},
        "completion_status": False
    }, {"task": 1, "_id": 1}))

    if expired_tasks:
        expired_goal_ids = [task["_id"] for task in expired_tasks]
        goals_collection.delete_many({
            "user_id": session['user_id'],
            "_id": {"$in": expired_goal_ids}
        })

        for task in expired_tasks:
            task["_id"] = str(task["_id"])

    return jsonify({"expiredTasks": expired_tasks})





@app.route('/performance')
def performance():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    subjects = list(subjects_collection.find(
        {"owner_id": user_id},
        {"_id": 0, "subject": 1, "marks": 1, "time_spent": 1}
    ))

    if not subjects:
        chart1 = "<p>No subjects found. Please add some subjects first.</p>"
    else:
        subject_names = [s['subject'].title() for s in subjects]
        marks = [s['marks'] for s in subjects]

        df = pd.DataFrame({
            'Subject': subject_names,
            'Marks': marks
        })

        fig1 = px.bar(
            df,
            x='Subject',
            y='Marks',
            title="Subject-wise Performance",
            text='Marks',
            color_discrete_sequence=['#7E6363']
        )
        fig1.update_traces(textposition="outside")
        fig1.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#7E6363',
            xaxis_title="Subject",
            yaxis_title="Marks (%)"
        )
        chart1 = fig1.to_html(full_html=False, include_plotlyjs='cdn')

    return render_template("performance.html", chart1=chart1, subjects=subjects)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)