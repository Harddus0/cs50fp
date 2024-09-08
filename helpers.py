import sqlite3
from flask import g, session, redirect, url_for
from functools import wraps

# Function to get a database connection
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect("database.db")
        g.db.row_factory = sqlite3.Row  # Enable dictionary-style access to rows
    return g.db

# Function to close the database connection after each request
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Decorator to require login for certain routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function
