import sqlite3
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


def topological_sort(tasks):
    # Build the graph (adjacency list) and in-degree dictionary
    graph = defaultdict(list)
    in_degree = {task["id"]: 0 for task in tasks}

    print("Graph just created:", graph)
    print("in_degree just created:", in_degree)

    # Build the task graph based on predecessors
    for task in tasks:
        for predecessor in task["predecessors"]:
            if predecessor:  # Avoid empty predecessors
                graph[int(predecessor)].append(task["id"])
                in_degree[task["id"]] += 1

    print("Graph after iteration:", graph)
    print("in_degree after iteration:", in_degree)

    # Queue to process tasks with no predecessors (in-degree == 0)
    queue = deque([task["id"] for task in tasks if in_degree[task["id"]] == 0])

    print("queue:", queue)

    sorted_tasks = []

    while queue:
        current_task = queue.popleft()
        sorted_tasks.append(current_task)

        for dependent_task in graph[current_task]:
            in_degree[dependent_task] -= 1
            if in_degree[dependent_task] == 0:
                queue.append(dependent_task)

    print("Sorted Tasks:", sorted_tasks)
    print("All Tasks:", [task["id"] for task in tasks])


    # If sorted_tasks does not include all tasks, there is a cyclic dependency
    if len(sorted_tasks) != len(tasks):
        raise ValueError("Cyclic dependency detected in tasks.")

    # Ensure sorted_tasks includes all tasks (even those with no predecessors)
    sorted_task_ids = [task["id"] for task in tasks]
    for task_id in sorted_task_ids:
        if task_id not in sorted_tasks:
            sorted_tasks.append(task_id)

    return sorted_tasks


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
    
    # Ensure task["id"] is used in topological_sort, not task["display_id"]
    sorted_task_ids = topological_sort([{"id": task["id"], "predecessors": task["predecessors"].split(",") if task["predecessors"] else []} for task in wbs_table])

    for task_id in sorted_task_ids:
        task = next(task for task in wbs_table if task["id"] == task_id)
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



def calculate_dates2():
    cur = get_db().cursor()
    project_id = session.get("project_id")

    # Fetch project start date
    project_start_date =  cur.execute("SELECT start_date FROM projects WHERE id = ?", (project_id,)).fetchone()[0]

    # Get the number of locations
    locations_count = cur.execute("SELECT display_id FROM lbs WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()[0]
    
    # Fetch WBS table with tasks and possible predecessors
    wbs_table = cur.execute(
        """
        SELECT wbs.id, wbs.display_id, wbs.task, wbs.duration, wbs_lbs.start_time, wbs_lbs.end_time,
        GROUP_CONCAT(wbs_predecessors.predecessor_id) AS predecessors
        FROM wbs
        LEFT JOIN wbs_predecessors ON wbs.id = wbs_predecessors.task_id
        JOIN wbs_lbs WHERE wbs.id = wbs_lbs.wbs_id --connects to the empty wbs_lbs table
        WHERE wbs.project_id = ?
        GROUP BY wbs.display_id, wbs.task, wbs.duration
        ORDER BY wbs.display_id
        """,
        (project_id,)
    ).fetchall()

    for task in wbs_table:
        task_id = task["id"]
        predecessors = task["predecessors"]

        for location in locations_count:
            location_id = location

            # set start time as project_start_date for task with no predecessor
            if not predecessors:
                start_time = datetime.strptime(project_start_date,"%Y-%m-%d")
                end_time = start_time + timedelta(days=task["duration"])
                cur.execute("INSERT INTO wbs_lbs (wbs_id, lbs_id, start_time, end_time) VALUES (?, ?, ?, ?)",(task_id, location_id, start_time,end_time,task_id))
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
                    end_time = start_time + timedelta(days=task["duration"])
                else:
                    # Case where predecessor's duration is larger than the current task's duration
                    end_time = datetime.strptime(predecessor_end_time,"%Y-%m-%d %H:%M:%S") + timedelta(days=task["duration"])
                    start_time = end_time - timedelta(days=task["duration"])

            # Update the WBS table with calculated start and end times
            cur.execute(
                "UPDATE wbs SET start_time = ?, end_time = ? WHERE id = ?", 
                (start_time, end_time, task_id)
            )
            get_db().commit()

    
    cur.close()
