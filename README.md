# 🚀 PathfinderAI - Stage 1

A learning companion designed to help students and developers organize, track, and improve their learning journey. This project starts as a simple study tracker and will evolve into a full-fledged AI-powered study assistant.

---

## ✅ Core Features (Stage 1)

* **Secure User Authentication:** Users can register, log in, and log out. Passwords are fully hashed and secured.
* **Session Management:** The app remembers users while they are logged in.
* **Subject Management (CRUD):** Users can create, update, and delete their study subjects.
* **Progress Tracking:** Marks and time spent can be logged for each subject.
* **Performance Dashboard:** Visual charts show a user's performance and time allocation across subjects.
* **Activity Logging:** Key user actions are logged in the database.

---

## ⚙️ Technology Stack

* **Backend:** Python (Flask)
* **Database:** MongoDB (via MongoDB Atlas)
* **Frontend:** HTML, CSS, JavaScript
* **Data Visualization:** Plotly & Pandas
* **Security:** Flask-Bcrypt for password hashing

---

## How We Built Stage 1: Our Approach

We built Stage 1 by focusing on a solid foundation, following a "backend-first" approach to ensure the core logic was working before building out the full user interface.

### 1. Setting the Foundation (The Backend)
We started by setting up a **Flask** web server. The first critical step was establishing a reliable connection to our **MongoDB Atlas** database. We chose to use the `PyMongo` library directly for a robust and modern connection, wrapping the initial connection logic in a `try...except` block to gracefully handle any potential database outages.

### 2. Building the Front Door (User Authentication)
With the database connected, we built the user authentication system. This involved:
* **Creating Routes:** We defined Flask routes for `/register`, `/login`, and `/logout`.
* **Handling Forms:** The register and login routes were built to handle `POST` requests, taking the user's details from the HTML form.
* **Securing Passwords:** We implemented **Bcrypt** to one-way hash all user passwords before storing them in the `users` collection. This ensures we never store plain-text passwords, a critical security practice.

### 3. Adding the Core Functionality (Subject Management)
Once a user could log in, we built the main feature of the app.
* **CRUD Operations:** We created routes (`/add`, `/update`, `/delete`) and functions that allow a logged-in user to Create, Read, Update, and Delete subjects.
* **Session-Based Logic:** Every action is tied to the logged-in user. We use the `user_id` stored in the Flask **session** to ensure users can only see and manage their own subjects.
* **Activity Logging:** We also created an `activities` collection to log key events, like a user viewing their dashboard, by linking the action to their `user_id`.

### 4. Making it Visual (Frontend & Charts)
Finally, with all the backend logic in place, we created the frontend.
* **HTML Templates:** We built several HTML pages (`dashboard.html`, `login.html`, etc.) using the Jinja2 templating engine to dynamically display user-specific data.
* **Data Visualization:** To give users immediate feedback, we used **Plotly** and **Pandas** to read their subject data from the database and generate simple, effective charts for the performance and time-tracking pages.