import sqlite3
import time
from datetime import timedelta, datetime
from flask import g, session, redirect, url_for
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

    # Print verification
    for task in tasks:
        print(f"Task {task['id']}: ES={task['ES']}, EF={task['EF']}, LS={task['LS']}, LF={task['LF']}, Slack={task['Slack']}, Critical={task['Critical']}")

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
                task["slack"],
                task["critical"],
                task["id"],
                project_id
            )
        )
    g.db.commit()

    # Print verification
    for task in tasks:
        print(f"Task {task['id']}: ES={task['ES']}, EF={task['EF']}, LS={task['LS']}, LF={task['LF']}, Slack={task['Slack']}, Critical={task['Critical']}")


def calculate_date_cpm2():
    cur = get_db().cursor()
    project_id = session.get("project_id")

    # Fetch project start date
    project_start_date =  cur.execute("SELECT start_date FROM projects WHERE id = ?", (project_id,)).fetchone()[0]

    # Fetch WBS table with tasks and predecessors
    wbs_table = cur.execute(
        """
        SELECT wbs.id, wbs.display_id, wbs.task, wbs.duration, wbs.start_time, wbs.end_time,
        GROUP_CONCAT(wbs_predecessors.predecessor_id) AS predecessors
        FROM wbs
        LEFT JOIN wbs_predecessors ON wbs.id = wbs_predecessors.task_id
        WHERE wbs.project_id = ?
        GROUP BY wbs.id
        ORDER BY wbs.display_id
        """,
        (project_id,)
    ).fetchall()

    # initialization
    tasks = []
    for row, i in enumerate(wbs_table):
        tasks[i]["id"] = row["id"]
        tasks[i]["duration"] = row["duration"]
        tasks[i]["predecessors"] = row["predecessors"]
        tasks[i]["ES"] = 0
        tasks[i]["EF"] = 0
        tasks[i]["LS"] = 65536 # infinite
        tasks[i]["LF"] = 65536 # infinite
        tasks[i]["Slack"] = 65536 # infinite
        tasks[i]["Critical"] = False # for now
    
    # Perform Forward Pass (Earliest Start/Finish Calculation)
    while True:
        for task, i in enumerate(tasks):
            task["predecessors"]
            
            if not predecessor:
                tasks[i]["ES"] = project_start_date
            else:
                predecessor_ES = 0
                for predecessor in tasks[i]["predecessors"]:
                    if predecessor_ES > tasks[predecessor]["ES"]:
                        predecessor_ES = tasks[predecessor]["ES"]
                task[i]["ES"] = predecessor_ES

            tasks[i]["EF"] = tasks[i]["ES"] + tasks[i]["duration"]



    """ 
    Atributes each task has:
    id = task["id"]
    duration = task["duration"]
    # calculated from earliest task to latest task:
        Early Start (ES) = latest EF of the task's predecessor (equals to project_start_date if no predecessor)
        Early Finish (EF) = EF + duration
    # calculated from latest task to earliest:
        Late Start (LS) = LF - duration
        Late Finish (LF) = earliest LS of the task's successors
    Total Slack = LS - ES or LF - EF
    Critical bool = true if total slack == 0

    1. Fetch all tasks from the database
    - For each task, initialize ES, EF, LS, LF, Slack, Critical
    
    2. Perform Forward Pass (Earliest Start/Finish Calculation)
        For each task in topological order:
            if task has no predecessors:
                ES = project_start_date
                EF = ES + task_duration
            else:
                ES = max(EF of all predecessors)
                EF = ES + task_duration

    3. Perform Backward Pass (Latest Start/Finish Calculation)
        For each task in reverse topological order:
            if task has no successors:
                LF = project_end_date or EF of the last task
                LS = LF - task_duration
            else:
                LF = min(LS of all successors)
                LS = LF - task_duration

    4. Calculate Slack for each task
        For each task:
            Slack = LS - ES or LF - EF
            if Slack == 0:
                mark task as Critical (belongs to Critical Path)

    5. Output or update the database with:
        - Early Start (ES), Early Finish (EF)
        - Late Start (LS), Late Finish (LF)
        - Slack, Critical status
        - The critical path (sequence of tasks with zero slack)
    """


    


    cur.close()

    

def calculate_dates():
    cur = get_db().cursor()
    project_id = session.get("project_id")

    # Fetch project start date
    project_start_date =  cur.execute("SELECT start_date FROM projects WHERE id = ?", (project_id,)).fetchone()[0]

    # Get the number of locations
    locations_count = cur.execute("SELECT display_id FROM lbs WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()[0]
    
    # Fetch WBS table with tasks and possible predecessors
    wbs_table = cur.execute(
        """
        SELECT wbs.id, wbs.display_id, wbs.task, wbs.duration, wbs.start_time, wbs.end_time,
        GROUP_CONCAT(wbs_predecessors.predecessor_id) AS predecessors
        FROM wbs
        LEFT JOIN wbs_predecessors ON wbs.id = wbs_predecessors.task_id
        WHERE wbs.project_id = ?
        GROUP BY wbs.id
        ORDER BY wbs.display_id
        """,
        (project_id,)
    ).fetchall()
    
    for task in wbs_table:
        task_id = task["id"]
        predecessors = task["predecessors"]

        # set start time as project_start_date for first iteration
        if not predecessors:
            start_time = datetime.strptime(project_start_date,"%Y-%m-%d")
            end_time = start_time + timedelta(days=task["duration"] * locations_count)
            cur.execute("UPDATE wbs SET start_time = ?, end_time = ? WHERE id = ?", (start_time,end_time,task_id))
            g.db.commit()
        else:
            # get task predecessor of highest duration, extracting both the highest duration (max_dur) and the predecessor end_date
            predecessor_durations = cur.execute(
                """
                SELECT wbs.duration, wbs.start_time, wbs.end_time
                FROM wbs
                JOIN wbs_predecessors ON wbs.id = wbs_predecessors.task_id
                WHERE wbs.project_id = ? AND wbs.id = ?
                """,
            (project_id,task_id)
            ).fetchall()

            predecessor_max_duration = 0
            for row in predecessor_durations:
                if predecessor_max_duration < row["duration"]:
                    predecessor_end_time = row["end_time"]
                    predecessor_max_duration = row["duration"]

            # Use Line of Balance logic to calculate dates
            if predecessor_max_duration <= task["duration"]:
                # Case where predecessor's duration is smaller or equal to current task's duration
                start_time = datetime.strptime(predecessor_end_time,"%Y-%m-%d %H:%M:%S")
                end_time = start_time + timedelta(days=task["duration"] * locations_count)
            else:
                # Case where predecessor's duration is larger than the current task's duration
                end_time = datetime.strptime(predecessor_end_time,"%Y-%m-%d %H:%M:%S") + timedelta(days=task["duration"])
                start_time = end_time - timedelta(days=task["duration"] * (locations_count - 1))

        # Update the WBS table with calculated start and end times
        cur.execute(
            "UPDATE wbs SET start_time = ?, end_time = ? WHERE id = ?", 
            (start_time, end_time, task_id)
        )
        get_db().commit()

    
    cur.close()