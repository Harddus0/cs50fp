import sqlite3
from datetime import timedelta, datetime
from flask import g, session, redirect, url_for, flash
from functools import wraps
from collections import defaultdict, deque

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


def check_requirements(requirement_func):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not requirement_func():  # Call the passed requirement function
                flash("Please complete all required steps before accessing this page.")
                return redirect(url_for("index"))  # Redirect to safe route
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Fetch all projects for the logged-in user
def get_user_projects():
    cur = get_db().cursor()
    user_id = session.get("user_id")
    projects = cur.execute("SELECT name FROM projects WHERE user_id = ?", (user_id,)).fetchall()
    cur.close()

    # Return project names as a list
    return [project["name"] for project in projects]


def has_tasks():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    tasks = cur.execute('SELECT COUNT(*) FROM wbs WHERE project_id = ?', (project_id,)).fetchone()
    return tasks[0] > 0


def has_locations():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    locations = cur.execute('SELECT COUNT(*) FROM lbs WHERE project_id = ?', (project_id,)).fetchone()
    return locations[0] > 0

def get_mermaid():
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

    mermaid_code = 'graph LR\n'
    for task in data_wbs:
        task_id = task['display_id']
        task_name = task['task']
        mermaid_code += f'    {task_id}["{task_name}"]\n'
        predecessors = task["predecessors"].split(",") if task["predecessors"] else []
        for pred in predecessors:
            if pred:
                mermaid_code += f'    {pred} --> {task_id}\n'
    
    return mermaid_code


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


def calculate_date_cpm():
    cur = get_db().cursor()
    project_id = session.get("project_id")

    project_start_date = 0
    
    # Fetch WBS table with tasks and predecessors
    wbs_table = cur.execute(
        """
        SELECT wbs.display_id, wbs.task, wbs.duration, wbs.start_time, wbs.end_time,
        GROUP_CONCAT(wbs_predecessors.predecessor_id) AS predecessors
        FROM wbs
        LEFT JOIN wbs_predecessors ON wbs.id = wbs_predecessors.task_id
        WHERE wbs.project_id = ?
        GROUP BY wbs.id
        ORDER BY wbs.display_id
        """,
        (project_id,)
    ).fetchall()

    # Convert fetched table rows into a list of dictionaries
    tasks = []
    successors = defaultdict(list)  # Dictionary to track successors
    for row in wbs_table:
        task = {
            "id": row["display_id"],
            "duration": row["duration"],
            "predecessors": row["predecessors"].split(",") if row["predecessors"] else [],
            "ES": None,  # Earliest Start
            "EF": None,  # Earliest Finish
            "LS": float('inf'),  # Latest Start (initialize to "infinity")
            "LF": float('inf'),  # Latest Finish (initialize to "infinity")
            "Slack": float('inf'),  # Total Slack
            "Critical": False,  # Whether the task is on the critical path
            "successors": []  # Successors will be added later
        }
        tasks.append(task)

        # Populate the successors dictionary
        for predecessor_id in task["predecessors"]:
            if predecessor_id:
                successors[int(predecessor_id)].append(task["id"])

    # Add successors to each task
    for task in tasks:
        task["successors"] = successors[task["id"]]
    # Dictionary for easy lookup by task id
    task_dict = {task["id"]: task for task in tasks}

    # Gets the number of changes necessary inside while loop
    num = len(tasks)

    # Forward Pass: Calculate ES and EF
    def forward_pass():
        i = 0
        while i < num:
            for task in tasks:

                if not task["predecessors"]:  # If no predecessors, start at project_start_date
                    if task["ES"] is None:
                        task["ES"] = project_start_date
                        task["EF"] = task["ES"] + task["duration"]
                        i += 1
                else:
                    max_ef = 0
                    ready = True
                    for predecessor_id in task["predecessors"]:
                        pred = task_dict.get(int(predecessor_id))
                        if pred and pred["EF"] is not None:
                            max_ef = max(max_ef, pred["EF"])
                        else:
                            ready = False
                    if ready and task["ES"] is None:  # Only update if all predecessors are calculated
                        task["ES"] = max_ef
                        task["EF"] = task["ES"] + task["duration"]
                        i += 1


    # Backward Pass: Calculate LS and LF
    def backward_pass():
        project_duration = 0 
        for task in tasks: 
            project_duration = max(project_duration, task["EF"])
        
        i = 0
        while i < num:
            for task in reversed(tasks):
                if not task["successors"]:  # Tasks without successors get their LF from project_duration
                    if task["LF"] == float('inf'):
                        task["LF"] = project_duration
                        task["LS"] = task["LF"] - task["duration"]
                        i += 1
                else:
                    min_ls = float('inf')
                    ready = True
                    for successor_id in task["successors"]:
                        succ = task_dict.get(int(successor_id))
                        if succ and succ["LS"] != float('inf'):
                            min_ls = min(min_ls, succ["LS"])
                        else:
                            ready = False
                    if ready and task["LF"] == float('inf'):  # Only update if all successors are calculated
                        task["LF"] = min_ls
                        task["LS"] = task["LF"] - task["duration"]
                        i += 1

    # Run Forward Pass to calculate ES and EF
    forward_pass()

    # Run Backward Pass to calculate LS and LF
    backward_pass()


    # Calculate Total Slack and mark critical tasks
    for task in tasks:
        task["Slack"] = task["LS"] - task["ES"]
        if task["Slack"] == 0:
            task["Critical"] = True

    # Fetch project start date
    project_start_date_string = cur.execute("SELECT start_date FROM projects WHERE id = ?", (project_id,)).fetchone()[0]

    # Convert project_start_date from string to datetime object
    project_start_datetime = datetime.strptime(project_start_date_string, "%Y-%m-%d")

    # Convert float values (representing days from project start) to SQL DATE format
    for task in tasks:
        if task["ES"] is not None:
            task["ES"] = project_start_datetime + timedelta(days=task["ES"])
        if task["EF"] is not None:
            task["EF"] = project_start_datetime + timedelta(days=task["EF"])
        if task["LS"] != float('inf'):
            task["LS"] = project_start_datetime + timedelta(days=task["LS"])
        if task["LF"] != float('inf'):
            task["LF"] = project_start_datetime + timedelta(days=task["LF"])
    
    for task in tasks:
        cur.execute(
            """
            UPDATE wbs
            SET ES = ?, EF = ?, LS = ?, LF = ?, slack = ?, critical = ?
            WHERE display_id = ? AND project_id = ? 
            """,
            (
                task["ES"].strftime("%Y-%m-%d") if task["ES"] is not None else None,
                task["EF"].strftime("%Y-%m-%d") if task["EF"] is not None else None,
                task["LS"].strftime("%Y-%m-%d") if task["LS"] != float('inf') else None,
                task["LF"].strftime("%Y-%m-%d") if task["LF"] != float('inf') else None,
                task["Slack"],
                task["Critical"],
                task["id"],
                project_id
            )
        )
    g.db.commit()
    
    cur.close()

    # Print verification
    # for task in tasks:
    #     print(f"Task {task['id']}: ES={task['ES']}, EF={task['EF']}, LS={task['LS']}, LF={task['LF']}, Slack={task['Slack']}, Critical={task['Critical']}")
    


def calculate_lob():
    cur = get_db().cursor()
    project_id = session.get("project_id")
    project_start_time = 0  # Use the actual project start time here
    
    # Fetch WBS table with critical tasks and predecessors
    wbs_table = cur.execute(
        """
        SELECT id, wbs.display_id, wbs.task, wbs.duration, wbs.critical,
        GROUP_CONCAT(wbs_predecessors.predecessor_id) AS predecessors
        FROM wbs
        LEFT JOIN wbs_predecessors ON wbs.id = wbs_predecessors.task_id
        WHERE wbs.project_id = ? AND critical = 1
        GROUP BY wbs.id
        ORDER BY wbs.ES
        """,
        (project_id,)
    ).fetchall()
    
    # Fetch LBS table (locations)
    locations = cur.execute(
        """
        SELECT id, location FROM lbs
        WHERE project_id = ?
        ORDER BY display_id
        """,
        (project_id,)
    ).fetchall()
    
    # Initialize tasks with location data
    tasks = []
    task_dict = {} # Create a lookup dictionary for tasks
    for row in wbs_table:
        task = {
            "id": row["id"],
            "display_id": row["display_id"],
            "duration": row["duration"],
            "predecessors": row["predecessors"].split(",") if row["predecessors"] else [],
            "critical": row["critical"],
            "locations": [
                {"location_id": loc["id"], "start_time": None, "end_time": None} for loc in locations
            ]
        }
        tasks.append(task)
        task_dict[task["display_id"]] = task  # Map task by its id for easy lookup
        

    first_end = 0
    last_end = 0

    # Forward and Backward passes through each task and each location
    for task in tasks:
        temp = 0
        
        # Calculate max predecessor duration
        max_pred_dur = 0
        for predecessor_id in task["predecessors"]:
            predecessor_id = int(predecessor_id)  # Ensure it's an integer
            predecessor = task_dict.get(predecessor_id)  # Look up the predecessor task
            try:
                if predecessor["critical"] == "1":
                    max_pred_dur = max(max_pred_dur, predecessor["duration"])
            except TypeError:
                pass
        # max_pred_dur = max((task_dict[int(pred_id)]["duration"] for pred_id in task["predecessors"]), default=0)

        # Check if it's first task or if task is longer than predecessor
        if not task["predecessors"] or task["duration"] > max_pred_dur:
        
            # Forward pass: calculate start_time and end_time per location
            for loc in task["locations"]:
                if temp == 0:  # First location
                    if first_end == 0:
                        loc["start_time"] = project_start_time
                    else:
                        loc["start_time"] = first_end
                    loc["end_time"] = loc["start_time"] + task["duration"]
                    temp = loc["end_time"]
                    first_end = loc["end_time"] # Update first_end for the next task
                else:
                    loc["start_time"] = temp
                    loc["end_time"] = loc["start_time"] + task["duration"]
                    temp = loc["end_time"]
                last_end = loc["end_time"] # Update last_end for the backward pass

            temp = 0 # Reset temp for backward pass

        else:
            # Backward pass: calculate start_time and end_time in reverse order
            for loc in reversed(task["locations"]):
                if temp == 0:  # Last location
                    loc["start_time"] = last_end
                    loc["end_time"] = loc["start_time"] + task["duration"]
                    temp = loc["start_time"]
                    last_end = loc["end_time"] # Update last_end for the next backward pass
                else:
                    loc["end_time"] = temp
                    loc["start_time"] = loc["end_time"] - task["duration"]
                    temp = loc["start_time"]
                first_end = loc["end_time"] # Update first_end for forward pass

    # Fetch project start date
    project_start_date_string = cur.execute("SELECT start_date FROM projects WHERE id = ?", (project_id,)).fetchone()[0]

    # Convert project_start_date from string to datetime object
    project_start_datetime = datetime.strptime(project_start_date_string, "%Y-%m-%d")

    # Convert float values (representing days from project start) to SQL DATE format
    for task in tasks:
        for loc in task["locations"]:
            loc["start_time"] = project_start_datetime + timedelta(days=loc["start_time"])
            loc["end_time"] = project_start_datetime + timedelta(days=loc["end_time"])

    # Insert the task-location timing into wbs_lbs table
    for task in tasks:
        for loc in task["locations"]:
            cur.execute(
                """
                INSERT INTO wbs_lbs (wbs_id, lbs_id, start_time, end_time)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(wbs_id, lbs_id) DO UPDATE SET
                start_time = excluded.start_time,
                end_time = excluded.end_time
                """,
                (   
                    task["id"],
                    loc["location_id"],
                    loc["start_time"].strftime("%Y-%m-%d"),
                    loc["end_time"].strftime("%Y-%m-%d")
                )
            )
    get_db().commit()


def calculate_lob_total():
    cur = get_db().cursor()
    project_id = session.get("project_id")

    # Fetch project start date
    project_start_date_str = cur.execute("SELECT start_date FROM projects WHERE id = ?", (project_id,)).fetchone()[0]
    project_start_date = datetime.strptime(project_start_date_str, "%Y-%m-%d")

    # Get the number of locations
    locations_count = cur.execute("SELECT display_id FROM lbs WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()[0]

    # Fetch WBS table with tasks and possible predecessors
    wbs_table = cur.execute(
        """
        SELECT wbs.id, wbs.display_id, wbs.task, wbs.duration, wbs.start_time, wbs.end_time, wbs.critical,
        GROUP_CONCAT(wbs_predecessors.predecessor_id) AS predecessors
        FROM wbs
        LEFT JOIN wbs_predecessors ON wbs.id = wbs_predecessors.task_id
        WHERE wbs.project_id = ?
        GROUP BY wbs.id
        ORDER BY wbs.display_id
        """,
        (project_id,)
    ).fetchall()

    # Convert to list of dictionaries for processing
    sorted_tasks = [
        {
            "id": row["id"],
            "display_id": row["display_id"],
            "task": row["task"],
            "duration": row["duration"],
            "predecessors": row["predecessors"].split(",") if row["predecessors"] else [],
            "start_time": None,
            "end_time": None,
            "critical": row["critical"]
        }
        for row in wbs_table
    ]

    # Convert list of tasks to a dictionary for quick lookup
    task_dict = {task["display_id"]: task for task in sorted_tasks}

    for task in sorted_tasks:
        predecessors = task["predecessors"]

        # Set start time as project_start_date for tasks with no predecessors
        if not predecessors:
            task["start_time"] = project_start_date
            task["end_time"] = task["start_time"] + timedelta(days=task["duration"] * (locations_count - 1))
        else:
            # get task predecessor of highest duration, extracting both the highest duration (max_dur) and the predecessor end_date
            max_pred_dur = 0
            max_pred_end = project_start_date
            max_pred_start = project_start_date

            for predecessor_id in predecessors:

                predecessor_id = int(predecessor_id)  # Ensure it's an integer
                predecessor = task_dict.get(predecessor_id)  # Look up the predecessor task

                if predecessor["critical"] == "0":
                    continue

                if predecessor["end_time"]:
                    max_pred_end = max(max_pred_end, predecessor["end_time"])
                if predecessor["start_time"]:
                    max_pred_start = max(max_pred_start, predecessor["start_time"])
                max_pred_dur = max(max_pred_dur, predecessor["duration"])

            # Use Line of Balance logic to calculate dates
            if max_pred_dur <= task["duration"]:
                # Case where predecessor's duration is smaller or equal to current task's duration
                task["start_time"] = max_pred_start + timedelta(days=max_pred_dur)
                task["end_time"] = task["start_time"] + timedelta(days=task["duration"] * (locations_count - 1))
            else:
                # Case where predecessor's duration is larger than the current task's duration
                task["end_time"] = max_pred_end + timedelta(days=max_pred_dur)
                task["start_time"] = task["end_time"] - timedelta(days=task["duration"] * (locations_count - 1))

    for task in sorted_tasks:
        # Update the WBS table with calculated start and end times
        cur.execute(
            "UPDATE wbs SET start_time = ?, end_time = ? WHERE id = ?", 
            (task["start_time"].strftime("%Y-%m-%d %H:%M:%S"), task["end_time"].strftime("%Y-%m-%d %H:%M:%S"), task["id"])
        )
        get_db().commit()

    cur.close()
