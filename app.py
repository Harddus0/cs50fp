from helpers import get_db, close_db, login_required, get_user_projects, get_project_locations, get_project_wbs, calculate_lob, calculate_date_cpm, calculate_lob_total, check_requirements, has_locations, has_tasks, get_mermaid
from flask import Flask, flash, redirect, render_template, request, session, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import re

app = Flask(__name__)
app.secret_key = "your_secret_key"

app.teardown_appcontext(close_db)

@app.route("/")
def index():
    selected_project = request.form.get("selected_project")
    user_id = session.get("user_id")
    
    if user_id:
        return render_template("index.html", selected_project=selected_project)
    else:
        return redirect("/login")
    
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


@app.route("/create-project", methods=["GET", "POST"])
@login_required
def create_project():

    if request.method == "POST":
        cur = get_db().cursor()

        project = request.form.get("project")
        start_date = request.form.get("start_date")

        if not project:
            flash("Project name required", "error")
            return render_template("create-project.html")
        
        if not start_date:
            flash("Project Start Date required", "error")
            return render_template("create-project.html")

        cur.execute("INSERT INTO projects (user_id, name, start_date) VALUES (?, ?, ?)", (session.get("user_id"), project, start_date))

        g.db.commit()
        cur.close()

        return render_template("select-project.html", projects=get_user_projects())
    
    return render_template("create-project.html")


@app.route("/select-project", methods=["GET", "POST"])
@login_required
def select_project():
    
    if request.method == "POST":
        cur = get_db().cursor()

        selected_project = request.form.get("selected_project")
        
        if selected_project:
            session["project_id"] = cur.execute(
                "SELECT id FROM projects WHERE user_id = ? AND name = ?",
                (session.get("user_id"), selected_project)
            ).fetchone()[0]
            flash("Project successfully created!","success")
            return render_template("index.html", selected_project=selected_project)
        else:
            flash("Select a project to proceed","error")
            return render_template("select-project.html", projects=get_user_projects())

    return render_template("select-project.html", projects=get_user_projects())


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
@login_required
def location():
    cur = get_db().cursor()
    project_id = session.get("project_id")

    if request.method == "POST":
        # Check if the button for 'add next location' is clicked
        add_next = request.form.get("add_next")
        location = request.form.get("location")
        delete_id = request.form.get("id")

        # Handle deletion
        if delete_id:
            cur.execute("DELETE FROM lbs WHERE id = ?", (delete_id,))
            g.db.commit()
            flash("Successfully deleted", "success")
            return render_template("location.html", lbs_table=get_project_locations())

        # If "Add Next Location" button is clicked
        if add_next:
            last_location = cur.execute("SELECT location FROM lbs WHERE project_id = ? ORDER BY display_id DESC LIMIT 1", (project_id,)).fetchone()
            last_location = last_location[0] if last_location else "Floor 0"

            # Extract number and increment
            
            match = re.match(r"(\D*)(\d+)$", last_location)
            if match:
                prefix, number = match.groups()
                next_location = f"{prefix}{int(number) + 1}"
            else:
                next_location = "Floor 1"

            # Insert new location
            max_id = cur.execute("SELECT IFNULL(MAX(display_id), 0) FROM lbs WHERE project_id = ?", (project_id,)).fetchone()[0]
            cur.execute("INSERT INTO lbs (display_id, project_id, location) VALUES (?, ?, ?)", (max_id + 1, project_id, next_location))
            g.db.commit()

            return render_template("location.html", lbs_table=get_project_locations())

        # Handle standard location input (not auto-increment)
        if location:
            max_id = cur.execute("SELECT IFNULL(MAX(display_id), 0) FROM lbs WHERE project_id = ?", (project_id,)).fetchone()[0]
            cur.execute("INSERT INTO lbs (display_id, project_id, location) VALUES (?, ?, ?)", (max_id + 1, project_id, location))
            g.db.commit()
            return render_template("location.html", lbs_table=get_project_locations())

        flash("Location required", "error")
        return render_template("location.html", lbs_table=get_project_locations())

    return render_template("location.html", lbs_table=get_project_locations())



@app.route("/task", methods=["GET", "POST"])
@login_required  # Protect this route so only logged-in users can access it
def task():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    
    if request.method == "POST":

        task_name = request.form.get("task")
        delete_id = request.form.get("id")
        predecessors = request.form.getlist("predecessor")  

        if delete_id:
            flash("Task successfully deleted", "success")
            cur.execute("DELETE FROM wbs WHERE id = ?", (delete_id,))
            cur.execute("DELETE FROM wbs_predecessors WHERE task_id = ?", (delete_id,))
            g.db.commit()

            ready = True
            mermaid_code = get_mermaid()

            return render_template("task.html", wbs_table=get_project_wbs(), mermaid_code=mermaid_code, ready=ready)

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

        ready = True
        mermaid_code = get_mermaid()
        flash("Task added successfully!", "success")

        return render_template("task.html", wbs_table=get_project_wbs(), mermaid_code=mermaid_code, ready=ready)
    
    task_count = cur.execute("SELECT COUNT(*) FROM wbs WHERE project_id = ?", (project_id,)).fetchone()[0]

    if task_count > 0:
        ready = True
        mermaid_code = get_mermaid()
    else:
        ready = False
        mermaid_code = ""

    return render_template("task.html", wbs_table=get_project_wbs(), mermaid_code=mermaid_code, ready=ready)


@app.route("/wbs")
@login_required
@check_requirements(has_tasks)
def wbs():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    calculate_date_cpm()

    data_wbs = cur.execute(
        """
        SELECT wbs.task, wbs.duration, wbs.ES, wbs.EF, wbs.LS, wbs.LF, wbs.slack, wbs.critical,
        GROUP_CONCAT(wbs_predecessors.predecessor_id) AS predecessors
        FROM wbs
        LEFT JOIN wbs_predecessors ON wbs.id = wbs_predecessors.task_id
        WHERE wbs.project_id = ?
        GROUP BY wbs.id
        ORDER BY wbs.display_id DESC
        """,
        (project_id,)
    ).fetchall()
    cur.close()
    return render_template("wbs.html", data_wbs=data_wbs)


@app.route("/gantt-data")
@login_required
def gantt_data():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    calculate_date_cpm()

    data_wbs = cur.execute(
        """
        SELECT wbs.display_id, wbs.task, wbs.duration, wbs.ES, wbs.EF, wbs.critical,
        GROUP_CONCAT(wbs_predecessors.predecessor_id) AS predecessors
        FROM wbs
        LEFT JOIN wbs_predecessors ON wbs.id = wbs_predecessors.task_id
        WHERE wbs.project_id = ?
        GROUP BY wbs.id
        ORDER BY wbs.display_id DESC 
        """,
        (project_id,)
    ).fetchall()

    # If data is empty, print for debugging
    if not data_wbs:
        print("No data returned for project:", project_id)

    gantt_data = []
    for row in data_wbs:
        gantt_data.append({
            "id": row["display_id"],
            "task": row["task"],
            "predecessors": row["predecessors"],
            "duration": row["duration"],
            "ES": row["ES"],
            "EF": row["EF"],
            "critical": row["critical"]
        })
    
    return jsonify(gantt_data)
    


@app.route("/gantt")
@check_requirements(has_tasks)
@login_required
def gantt():
    return render_template("gantt.html")


@app.route("/gantt-total-data")
@login_required
def gantt_total_data():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    calculate_date_cpm()
    calculate_lob()

    data_wbs = cur.execute(
        """
        SELECT wbs.task, wbs.duration, wbs_lbs.start_time, wbs_lbs.end_time, lbs.location
        FROM wbs_lbs
        JOIN wbs ON wbs.id = wbs_lbs.wbs_id
        JOIN lbs ON lbs.id = wbs_lbs.lbs_id
        WHERE wbs.project_id = ?
        ORDER BY wbs.display_id DESC, lbs.display_id DESC
        """,
        (project_id,)
    ).fetchall()

    # If data is empty, print for debugging
    if not data_wbs:
        print("No data returned for project:", project_id)

    gantt_data = []
    for row in data_wbs:
        gantt_data.append({
            "task": row["task"]+" "+row["location"],
            "duration": row["duration"],
            "start_time": row["start_time"],
            "end_time": row["end_time"]
        })
    
    return jsonify(gantt_data)


@app.route('/gantt-total')
@login_required
@check_requirements(has_locations)
@check_requirements(has_tasks)
def gantt_total():
    return render_template('gantt-total.html')


@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)



@app.route("/lob-data")
@login_required
def lob_data():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    calculate_date_cpm()
    calculate_lob_total()

    data_wbs = cur.execute(
        """
        SELECT task, start_time, end_time
        FROM wbs
        WHERE project_id = ? AND critical = 1
        """, 
        (project_id,)
    ).fetchall()

    total_locations = cur.execute(
        """
        SELECT COUNT(DISTINCT display_id) as location_total
        FROM lbs
        WHERE project_id = ?
        """, 
        (project_id,)
    ).fetchone()[0]
    
    # If data is empty, print for debugging
    if not data_wbs:
        print("No data returned for project:", project_id)

    lob_data = []
    for row in data_wbs:
        lob_data.append({
            "task": row["task"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "location": total_locations,
        })
    
    return jsonify(lob_data)


@app.route('/lob')
@login_required
@check_requirements(has_locations)
@check_requirements(has_tasks)
def lob():
    return render_template('lob.html')


