# Hardplan: Construction Project Management Tool

Hardplan is a web-based application for managing construction projects using scheduling algorithms like the Critical Path Method (CPM) and Line of Balance (LOB). Built with Flask, Python, and SQLite3, it allows users to create Gantt charts and Line of Balance visualizations for better project management.

## Features
> Project creation: Define tasks and locations for detailed project breakdown.
> Task management: Add durations and dependencies between tasks.
> Scheduling algorithms: Automatically calculate start and end times for tasks using CPM and LOB.
> Gantt Charts: Visualize project schedules by location or across all locations.
> Line of Balance: Analyze task progress across multiple locations in the project.
> Interactive Visualizations: Visualize task relationships using Mermaid.js and schedule data with Plotly.js.

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Harddus0/cs50fp.git
```

2. Navigate to the project directory:
`cd cs50fp`

3. Create virtual enviroment:
`python3 -m venv venv`
`source venv/bin/activate`  # For Windows: venv\Scripts\activate

4. Install dependencies
`pip install -r requirements.txt`

5. Run the application:
`flask run`


## Usage

1. After running the application, navigate to `http://127.0.0.1:5000` in your browser.
2. Register for an account or log in if you already have one.
3. Create a new project, add tasks and locations, and visualize the project schedules using the built-in Gantt and Line of Balance charts.


## project structure
```
cs50fp/ 
    ├── static/             # Static files (CSS, JS, etc.)
    ├── templates/          # HTML files
    ├── app.py              # Main application
    ├── helpers.py          # Utility functions and scheduling algorithms
    ├── database.db         # SQLite3 database 
    ├── requirements.txt    # Dependencies 
    └── README.md           # Project README
```

### Routes Overview

| Route             | Description                                                               |
|-------------------|---------------------------------------------------------------------------|
| `/index`          | Homepage                                                                  |
| `/login`          | Handles user login                                                        |
| `/register`       | Handles user registration                                                 |
| `/create-project` | Create a new project                                                      |
| `/select-project` | Displays a list of the user’s projects                                    |
| `/location`       | Add and display project locations                                         |
| `/task`           | Add and display project tasks, with a task flowchart                      |
| `/gantt`          | Visualize a Gantt Chart for the typical floor                             |
| `/gantt-total`    | Visualize a Gantt Chart for all locations                                 |
| `/lob`            | Visualize a Line of Balance                                               |


### SQL Tables Overview

| Table              | Description                                                              |
|--------------------|--------------------------------------------------------------------------|
| `users`            | Stores user credentials                                                  |
| `projects`         | Stores project details                                                   |
| `lbs`              | Stores project locations                                                 |
| `wbs`              | Stores project tasks and scheduling details                              |
| `wbs_predecessors` | Handles multiple task predecessors                                       |
| `wbs_lbs`          | Links tasks (WBS) to locations (LBS)                                     |

## helpers.py functions

- **Database Management**:
    - `get_db()` and `close_db()`: Handle database connections.

- **User Authentication and Input Requirements**:
    - `login_required()` and `check_requirements()`: Ensure routes are protected by user login and necessary project inputs.

- **Scheduling Algorithms**:
    - `calculate_date_cpm()`: Calculates CPM attributes for project tasks.
    - `calculate_lob()` and `calculate_lob_total()`: Apply LOB for tasks across multiple locations.
    - [See detailed explanation](#scheduling-algorithms-analysis)

- **Data Visualization**:
    - `get_mermaid()`: Converts task data into a flowchart format using Mermaid.js.
    - `gantt-data` and `lob-data`: Fetch data for Gantt charts and Line of Balance using Plotly.js.


## app.py Overview

- **index**: Homepage.
- **login and register**: Handle user login and registration.
- **create-project**: Requires start date input to create a project and initiate scheduling algorithms.
- **select-project**: Displays a list of the user’s projects.
- **location**: Receives and manages project locations input, allowing for adding and deleting locations.
- **task**: Manages task input, including task name, duration, and predecessors, and generates flowcharts with Mermaid.js.
- **wbs**: Displays full CPM results for the project.
- **gantt-data**: Provides task data for Gantt chart visualization (by location).
- **gantt-total-data**: Provides task and location data for Gantt chart visualization across all locations.
- **lob-data**: Provides Line of Balance data for visualization.


## HTML Templates Overview

- **layout and layout2**: Define standard page layouts. layout includes a sidebar for core navigation, while layout2 is a simpler layout for pages like login and registration.
- **login, register, create-project, select-project**: Pages for user input and project creation.
- **location**: Displays and updates a table of project locations, allowing for deletion of the most recent entry.
- **task**: Displays and updates a table of project tasks, including task flowcharts for better visualization.
- **wbs**: Displays full results from the CPM algorithm.
- **gantt and gantt-total**: Fetch data to display Gantt charts for individual and multiple locations, respectively.
- **lob**: Fetches Line of Balance data to display a Line of Balance chart.


## Scheduling Algorithms Analysis

### Critical Path Method (CPM)

The `calculate_date_cpm()` function implements the CPM algorithm, which calculates task start and end dates. The algorithm works by performing a forward pass through the tasks to calculate the "Earliest Start" (ES) and "Earliest Finish" (EF), followed by a backward pass to calculate the "Latest Start" (LS) and "Latest Finish" (LF). 

**Design Decisions:**
- **Topological Sort** was initially considered for efficiency but a simpler while loop was used instead, iterating through the tasks until all attributes were calculated.
- **Slack** and **Critical Tasks**: Once both passes are complete, the slack (the difference between earliest and latest start times) is computed, determining whether a task is critical (i.e., it has zero slack and no flexibility in its schedule).

### Line of Balance (LOB)

The `calculate_lob()` function is used to handle task scheduling across multiple locations. This algorithm operates with two nested loops: one for tasks and another for locations.
The `calculate_lob_total()` does a global calculation is made to assess the start and finish of tasks across all locations, instead of individual locations.

**Design Decisions:**
- **Task and Location Iteration**: The LOB algorithm calculates the start and end times of each task in each location. A comparison is made between task durations and their predecessors, determining whether to perform a forward or backward pass (i.e., calculating from the first to the last location or vice versa).
