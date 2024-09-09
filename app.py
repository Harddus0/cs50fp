from helpers import get_db, close_db, login_required, get_user_projects
from flask import Flask, flash, redirect, render_template, request, session, url_for, g
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



@app.route("/dashboard")
@login_required  # Protect this route so only logged-in users can access it
def dashboard():
    return render_template("dashboard.html")


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
    

@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
