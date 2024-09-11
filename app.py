from helpers import get_db, close_db, login_required, get_user_projects, get_project_locations, get_project_wbs
from flask import Flask, flash, redirect, render_template, request, session, url_for, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = "your_secret_key"

app.teardown_appcontext(close_db)

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

    
@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "POST":
        cur = get_db().cursor()

        # Check for missing username or password
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            flash("Username is required", "error")
            return render_template("login.html")
        if not password:
            flash("Password is required", "error")
            return render_template("login.html")

        # Fetch user from the database
        rows = cur.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            flash("Invalid username or password", "error")
            return render_template("login.html")

        # Store user ID in session to log them in
        session["user_id"] = rows[0]["id"]
        cur.close()
        # flash("You are logged in","success")
        return redirect("/")

    # GET method
    return render_template("login.html")


@app.route("/project", methods=["GET", "POST"])
@login_required
def project():
    
    if request.method == "POST":
        cur = get_db().cursor()

        selected_project = request.form.get("selected_project")
        
        if selected_project:
            session["project_id"] = cur.execute(
                "SELECT id FROM projects WHERE user_id = ? AND name = ?",
                (session.get("user_id"), selected_project)
            ).fetchone()[0]
            return render_template("index.html", selected_project=selected_project)

        project = request.form.get("project")

        if not project:
            flash("Project name required", "error")
            return render_template("project.html")

        cur.execute("INSERT INTO projects (user_id, name) VALUES (?, ?)", (session.get("user_id"), project))

        g.db.commit()
        cur.close()

        flash("Project successfully created!","success")
        return render_template("project.html", projects=get_user_projects())

    return render_template("project.html", projects=get_user_projects())


@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()

    if request.method == "POST":
        cur = get_db().cursor()
        
        # Check for missing username or password
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            flash("Username is required", "error")
            return render_template("register.html")
        elif not password:
            flash("Password is required", "error")
            return render_template("register.html")

        # Ensure confirmation password exists and is identical to the password
        elif not confirmation or password != confirmation:
            flash("Confirmation password is required", "error")
            return render_template("register.html")

        # Attempt to add username, if it already exists, returns an apology
        try:
            cur.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            (username, generate_password_hash(password))
            )   

            g.db.commit()
            cur.close()

        except:
            flash("Username already exists", "error")
            return render_template("register.html")


        # Redirect user to home page for login once registration completes
        # flash("Registration successful","success")
        return redirect("/login")

    # GET method
    return render_template("register.html")
    

@app.route("/location", methods=["GET", "POST"])
@login_required  # Protect this route so only logged-in users can access it
def location():
    
    cur = get_db().cursor()

    if request.method == "POST":
        
        project_id = session.get("project_id")
        location = request.form.get("location")
        above = request.form.get("above")
      
        if not location:
            flash("location required", "error")
            return render_template("location.html", location_table=get_project_locations())

        try:
            cur.execute("INSERT INTO lbs (project_id, location, above) VALUES (?, ?, ?)", (project_id, location, above))
            g.db.commit()
        except:
            flash("try again", "error")
            return render_template("location.html", location_table=get_project_locations())

        return render_template("location.html", location_table=get_project_locations())

    return render_template("location.html", location_table=get_project_locations())


@app.route("/task", methods=["GET", "POST"])
@login_required  # Protect this route so only logged-in users can access it
def task():

    if request.method == "POST":
        cur = get_db().cursor()

        project_id = session.get("project_id")
        task_name = request.form.get("task")
        duration = request.form.get("duration")
        predecessors = request.form.getlist("predecessor")

        if not task or not duration:
            flash("Please fill in the required fields", "error")
            return render_template("task.html", wbs_table=get_project_wbs())
    
        cur.execute(
            "INSERT INTO wbs (project_id, task, duration, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
        (project_id, task_name, duration, None, None)
        )
        
        # Get the inserted task's ID
        task_id = cur.lastrowid

        # Insert into wbs_predecessors if predecessors were selected
        for predecessor_id in predecessors:
            cur.execute(
                "INSERT INTO wbs_predecessors (task_id, predecessor_id) VALUES (?, ?)",
                (task_id, predecessor_id)
            )
        g.db.commit()

        flash("Task added successfully!", "success")
        return render_template("task.html",wbs_table=get_project_wbs())
    
    return render_template("task.html",wbs_table=get_project_wbs())

        






@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
