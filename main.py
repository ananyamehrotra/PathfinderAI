import os
import plotly.express as px
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from pymongo.results import InsertOneResult
import flask_bcrypt
import pandas as pd
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
MONGO_URI = os.getenv('MONGO_URI')

try:
    client = MongoClient(MONGO_URI)
    db = client.get_database('pathfinderDB')
    users_collection = db.users
    subjects_collection=db.subjects
    activities_collection = db.activities

    client.admin.command('ping')
    print("MongoDB connection successful.")

except Exception as e:
    print(f"Could not connect to MongoDB: {e}")
    db = None
    users_collection = None
    activities_collection = None

bcrypt = Bcrypt(app)


@app.route('/')
def home():
    """Renders the home page, which can be the login or register page."""
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if request.method == 'POST':
        if users_collection is None:
            flash("Database not connected. Please check server logs.", "danger")
            return redirect(url_for('register'))

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = users_collection.find_one({'email': email})

        if existing_user:
            flash('Email already registered!', 'danger')
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
        flash('Registration successful!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        if users_collection is None:
            flash("Database not connected. Please check server logs.", "danger")
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
            flash('Login failed. Check your email and password.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    """Displays the user's dashboard, a protected route."""
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))

    if activities_collection is not None:
        activities_collection.insert_one({
            'user_id': session['user_id'],
            'action': 'viewed_dashboard',
            'timestamp': datetime.utcnow()
        })
        user_subjects = list(subjects_collection.find({'owner_id': session['user_id']}))
    return render_template('dashboard.html', username=session['username'],subject_collection=user_subjects )



@app.route('/add_form')
def add_form():
    return render_template('add.html')

@app.route('/add', methods=['POST'])
def add_subject():
    subject = request.form['subject'].lower()
    marks = int(request.form['marks'])
    time_spent =(request.form['time']).split(":")
    time=int(time_spent[0])*60 +int(time_spent[1])
    subject_data = {
        'owner_id': session['user_id'],
        'subject': subject,
        'marks': marks,
        'time_spent': time,
        'created_at': datetime.utcnow()
    }

    # Insert into MongoDB
    subjects_collection.insert_one(subject_data)
    user_subjects = list(subjects_collection.find({'owner_id': session['user_id']}))

    flash('Subject added successfully!', 'success')
    return render_template('dashboard.html',username=session['username'],subject_collection=user_subjects )

@app.route('/update', methods=['POST'])
def update_subject():
    if 'user_id' not in session:
        return "Unauthorized", 401

    subject = request.form['subject'].lower()
    new_marks = int(request.form['marks'])
    new_time = int(request.form['time_spent'])

    subjects_collection.update_one(
        {"subject": subject, "owner_id": session['user_id']},
        {"$set": {"marks": new_marks, "time_spent": new_time}}
    )
    user_subjects = list(subjects_collection.find({'owner_id': session['user_id']}))
    return render_template('dashboard.html', username=session['username'], subject_collection=user_subjects)



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


@app.route('/time')
def time():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    subjects = list(subjects_collection.find(
        {"owner_id": user_id},
        {"_id": 0, "subject": 1, "marks": 1, "time_spent": 1}
    ))



    if not subjects:
        chart2 = "<p>No subjects found. Please add some subjects first.</p>"
    else:
        subject_names = [s['subject'].title() for s in subjects]
        time_hours = [s['time_spent'] / 60 for s in subjects]

        df = pd.DataFrame({
            'Subject': subject_names,
            'Time': time_hours
        })

        fig2 = px.line(
            df,
            x='Subject',
            y='Time',
            title="Time Spent on Each Subject",
            text='Time',
            color_discrete_sequence=['#8A784E']
        )
        fig2.update_traces(textposition="top center", line=dict(width=4))
        fig2.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#3B3B1A',
            xaxis_title="Subject",
            yaxis_title="Time (hours)"
        )
        chart2 = fig2.to_html(full_html=False, include_plotlyjs='cdn')

    return render_template("time.html", chart2=chart2, subjects=subjects)


@app.route('/logout')
def logout():
    """Logs the user out."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)