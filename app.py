from helpers import get_db, close_db, login_required, get_user_projects, get_project_locations, get_project_wbs, calculate_lob, calculate_date_cpm
from flask import Flask, flash, redirect, render_template, request, session, url_for, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = "your_secret_key"

app.teardown_appcontext(close_db)

@app.route("/")
def index():
    selected_project = request.form.get("selected_project")
    return render_template("index.html", selected_project=selected_project)

    
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
        start_date = request.form.get("start_date")

        if not project:
            flash("Project name required", "error")
            return render_template("project.html", projects=get_user_projects())
        
        if not start_date:
            flash("Project Start Date required", "error")
            return render_template("project.html", projects=get_user_projects())

        cur.execute("INSERT INTO projects (user_id, name, start_date) VALUES (?, ?, ?)", (session.get("user_id"), project, start_date))

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
        delete_id = request.form.get("id")

        if delete_id:
            flash("Successfully deleted", "success")
            cur.execute("DELETE FROM lbs WHERE id = ?", (delete_id,))
            g.db.commit()
            return render_template("location.html", lbs_table=get_project_locations())

        if not location:
            flash("location required", "error")
            return render_template("location.html", lbs_table=get_project_locations())
        
        max_id = cur.execute("SELECT IFNULL(MAX(display_id),0) FROM lbs WHERE project_id = ?", (project_id,)).fetchone()[0]

        try:
            cur.execute("INSERT INTO lbs (display_id, project_id, location) VALUES (?, ?, ?)", (max_id + 1, project_id, location))
            g.db.commit()
        except:
            flash("Please fill in the required fields", "error")
            return render_template("location.html", lbs_table=get_project_locations())

        return render_template("location.html", lbs_table=get_project_locations())

    return render_template("location.html", lbs_table=get_project_locations())


@app.route("/task", methods=["GET", "POST"])
@login_required  # Protect this route so only logged-in users can access it
def task():

    if request.method == "POST":
        cur = get_db().cursor()

        project_id = session.get("project_id")
        task_name = request.form.get("task")
        delete_id = request.form.get("id")
        predecessors = request.form.getlist("predecessor")  
        


        if delete_id:
            flash("Successfully deleted", "success")
            cur.execute("DELETE FROM wbs WHERE id = ?", (delete_id,))
            cur.execute("DELETE FROM wbs_predecessors WHERE task_id = ?", (delete_id,))
            g.db.commit()
            return render_template("task.html", wbs_table=get_project_wbs())

        try:
            duration = float(request.form.get("duration"))
        except:
            flash("Please fill in the required fields", "error")
            return render_template("task.html", wbs_table=get_project_wbs())

        if not task or not duration:
            flash("Please fill in the required fields", "error")
            return render_template("task.html", wbs_table=get_project_wbs())
    

        max_id = cur.execute("SELECT IFNULL(MAX(display_id),0) FROM wbs WHERE project_id = ?", (project_id,)).fetchone()[0]

        try:
            cur.execute(
                "INSERT INTO wbs (display_id, project_id, task, duration, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?)",
            (max_id + 1, project_id, task_name, duration, None, None)
            )
        except:
            flash("Insert an unique task", "error")
            return render_template("task.html", wbs_table=get_project_wbs())
        
        # Get the inserted task's ID
        task_id = cur.lastrowid

        # Insert into wbs_predecessors only if predecessors were selected (not "None")
        for predecessor_id in predecessors:
            if predecessor_id != "":  # Only insert if a predecessor is selected
                cur.execute(
                    "INSERT INTO wbs_predecessors (task_id, predecessor_id) VALUES (?, ?)",
                    (task_id, predecessor_id)
                )
        g.db.commit()

        flash("Task added successfully!", "success")
        return render_template("task.html",wbs_table=get_project_wbs())
    
    return render_template("task.html",wbs_table=get_project_wbs())


@app.route("/lob-data")
def lob_data():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    
    data = cur.execute(
        """
        SELECT wbs.task, wbs.start_time, wbs.end_time, lbs.location, lbs.display_id
        FROM wbs
        JOIN lbs ON wbs.project_id = lbs.project_id
        WHERE wbs.project_id = ?
        """, 
        (project_id,)
    ).fetchall()
    
    # If data is empty, print for debugging
    if not data:
        print("No data returned for project:", project_id)
    
    lob_data = []
    for row in data:
        lob_data.append({
            "task": row["task"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "location": row["location"],
            "location_order": row["display_id"]
        })
    
    return jsonify(lob_data)


@app.route('/lob')
def lob():
    calculate_lob()
    return render_template('lob.html')


@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
