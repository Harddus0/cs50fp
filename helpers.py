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

# Fetch all projects for the logged-in user
def get_user_projects():
    cur = get_db().cursor()
    user_id = session.get("user_id")
    projects = cur.execute("SELECT name FROM projects WHERE user_id = ?", (user_id,)).fetchall()
    cur.close()

    # Return project names as a list
    return [project["name"] for project in projects]

# Fetch all locations for the selected project
def get_project_locations():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    locations = cur.execute("SELECT id, display_id, location FROM lbs WHERE project_id = ? ORDER BY id DESC", (project_id,)).fetchall()
    cur.close()
    
    # Return locations as a list of dictionaries
    return locations

# Fetch Work Breakdown Structure for selected project
def get_project_wbs():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    wbs_table = cur.execute(
        """
        SELECT wbs.id, wbs.display_id, wbs.task, wbs.duration,
        GROUP_CONCAT(wbs_predecessors.predecessor_id) AS predecessors
        FROM wbs
        LEFT JOIN wbs_predecessors ON wbs.id = wbs_predecessors.task_id
        WHERE wbs.project_id = ?
        GROUP BY wbs.display_id, wbs.task, wbs.duration
        ORDER BY wbs.display_id DESC
        """,
        (project_id,)
    ).fetchall()
    cur.close()
    
    # Return the WBS as a list of dictionaries
    return wbs_table