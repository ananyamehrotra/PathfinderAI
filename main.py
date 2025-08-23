import os

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
import plotly.express as px
import pytz
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from pymongo import MongoClient
import pandas as pd
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from datetime import datetime, timedelta
from bson import ObjectId
from flask_dance.contrib.google import make_google_blueprint, google

# Load environment variables first
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# FIXED: Proper Google OAuth blueprint configuration
google_bp = make_google_blueprint(
    client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
    scope=["openid", "email", "profile"]
)

app.register_blueprint(google_bp, url_prefix="/login")

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
    client.admin.command('ping')
    print("MongoDB connection successful.")
except Exception as e:
    print(f"Could not connect to MongoDB: {e}")
    db = None
    users_collection = None
    activities_collection = None

bcrypt = Bcrypt(app)


# Debug route to check redirect URI
@app.route('/debug-oauth')
def debug_oauth():
    redirect_uri = url_for('google.authorized', _external=True)
    return f"""
    <h3>Debug OAuth Info:</h3>
    <p><strong>Redirect URI:</strong> {redirect_uri}</p>
    <p><strong>Client ID:</strong> {os.getenv('GOOGLE_OAUTH_CLIENT_ID')}</p>
    <p>Add this exact redirect URI to your Google Cloud Console!</p>
    """


# FIXED: Proper Google OAuth route
@app.route("/auth/google")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    try:
        resp = google.get("/oauth2/v2/userinfo")
        if not resp.ok:
            flash("Failed to fetch user info from Google.", "error")
            return redirect(url_for("login"))

        user_info = resp.json()
        email = user_info.get("email")
        name = user_info.get("name", "Google User")

        if not email:
            flash("Failed to get email from Google.", "error")
            return redirect(url_for("login"))

        # Check if user exists in database
        user = users_collection.find_one({"email": email})

        if not user:
            # Register new Google user automatically
            user_data = {
                "username": name,
                "email": email,
                "password": None,
                "auth_provider": "google",
                "created_at": datetime.utcnow()
            }
            result = users_collection.insert_one(user_data)
            user = users_collection.find_one({"_id": result.inserted_id})

        # Set session properly
        session["user_id"] = str(user["_id"])
        session["username"] = user["username"]
        session.permanent = True

        flash("Successfully logged in with Google!", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        print(f"Google OAuth error: {e}")
        flash("An error occurred during Google login.", "error")
        return redirect(url_for("login"))


@app.route('/')
def home():
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
            'password': hashed_password
        })
        user = users_collection.find_one({'email': email})
        session['user_id'] = str(user['_id'])
        session['username'] = username
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

    user_id = session['user_id']

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

    return render_template('dashboard.html', username=session['username'], subject_collection=user_subjects,
                           stats=stats)


# Keep all your other routes the same...
# (I'm keeping the rest of your routes unchanged to save space)

@app.route('/study_session/<subject_name>')
def study_session(subject_name):
    if 'user_id' not in session:
        flash('Please log in to start a session.', 'warning')
        return redirect(url_for('login'))

    local_today = datetime.now()
    week_start = local_today - timedelta(days=local_today.weekday())

    doc = sessions_collection.find_one({
        "user_id": ObjectId(session['user_id']),
        "subject_name": subject_name,
        "week_start": week_start.date().isoformat()
    })

    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    if not doc:
        time_spent = [0] * 7
    else:
        time_spent = [doc.get(day, 0) for day in days]

    chart_data = [t / 60 for t in time_spent]

    return render_template(
        'study_session.html',
        subject_name=subject_name,
        chart_data=chart_data,
        days=days
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

    local_today = datetime.now()
    today_str = local_today.strftime("%a").lower()
    week_start = local_today - timedelta(days=local_today.weekday())

    subject = subjects_collection.find_one({
        "owner_id": session['user_id'],
        "subject": subject_name.lower()
    })
    if not subject:
        return jsonify({'status': 'error', 'message': 'Subject not found'}), 404

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
            "thu": 0, "fri": 0, "sat": 0, "sun": 0
        }
        sessions_collection.insert_one(weekly_doc)

    sessions_collection.update_one(
        {
            "user_id": ObjectId(session['user_id']),
            "subject_id": subject['_id'],
            "week_start": week_start.date().isoformat()
        },
        {"$inc": {today_str: int(duration_seconds)}}
    )

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
    time_str = request.form['time']
    priority = request.form.get('priority')
    category = request.form.get('category')
    description = request.form.get('description')

    hours, minutes = map(int, time_str.split(':'))
    total_minutes = hours * 60 + minutes

    subject_data = {
        'owner_id': session['user_id'],
        'subject': subject,
        'marks': marks,
        'time_spent': total_minutes,
        'priority': priority,
        'category': category,
        'description': description,
        'created_at': datetime.utcnow()
    }

    subjects_collection.insert_one(subject_data)
    flash('Subject added successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/update', methods=['POST'])
def update_subject():
    if 'user_id' not in session:
        return "Unauthorized", 401

    subject = request.form['subject'].lower()
    new_marks = int(request.form['marks'])
    new_time = int(request.form['time_spent'])
    new_priority = request.form.get('priority')
    new_category = request.form.get('category')

    subjects_collection.update_one(
        {"subject": subject, "owner_id": session['user_id']},
        {"$set": {"marks": new_marks, "time_spent": new_time}}
    )
    return "Success", 200


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


@app.route('/delete', methods=['POST'])
def delete():
    if 'user_id' not in session:
        return "Unauthorized", 401

    subject = request.form['subject'].lower()

    subjects_collection.delete_one({
        "subject": subject,
        "owner_id": session['user_id']
    })
    user_subjects = list(subjects_collection.find({'owner_id': session['user_id']}))
    return render_template('dashboard.html', username=session['username'], subject_collection=user_subjects)


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
            color_discrete_sequence=['#8A784E']
        )
        fig1.update_traces(textposition="outside")
        fig1.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#3B3B1A',
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