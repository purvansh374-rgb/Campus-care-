# CampusCare — College Complaint Management System

Beginner-friendly BCA project using Flask, SQLite, HTML, CSS and Jinja templates.

## Features
- Student registration and login with hashed passwords
- Submit complaints with category, location and description
- Unique complaint reference IDs
- Student dashboard, filters and status tracking
- Admin dashboard with counts and search/filter
- Admin can change status and add a response
- SQLite persistence and responsive layout

## Run on Windows
1. Extract this ZIP.
2. Open Command Prompt inside the extracted `campuscare_project` folder.
3. Run these commands one at a time:

   py -m venv .venv
   .venv\\Scripts\\activate
   py -m pip install -r requirements.txt
   py app.py

4. Open http://127.0.0.1:5000

## Demo admin login
Email: admin@campuscare.local
Password: Admin@12345

The database and demo admin are created automatically on first run. Use this account only for a local demo. Before public deployment, change the secret key and admin password, disable debug mode, and add CSRF protection.

## Demo steps
1. Register a student account.
2. Log in as the student and submit a complaint.
3. Note its generated reference ID.
4. Log out, then log in using the demo admin account.
5. Open the complaint, change its status and write a response.
6. Log back in as the student and see the update.

## Database
`users`: id, name, email, password_hash, role, created_at
`complaints`: id, code, user_id, title, category, location, description, status, response, created_at, updated_at

## Viva summary
Flask handles HTTP routes and server-side validation. SQLite stores persistent data. Passwords are hashed, sessions track login, and role-based route checks protect admin pages. The app demonstrates CRUD operations, authentication, relational data and responsive UI.
