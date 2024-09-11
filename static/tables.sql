CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    username TEXT NOT NULL,
    hash TEXT NOT NULL,
    UNIQUE (username)
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    creation_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE lbs (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    display_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    location TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE (project_id, location)  -- Ensures that each location is unique within a project
);

-- wbs join attempt
CREATE TABLE wbs (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    display_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    task TEXT NOT NULL,
    duration FLOAT,  -- Number of days for the task execution
    start_time TIMESTAMP,  -- Calculated in backend, defaults to project start date
    end_time TIMESTAMP,  -- Calculated using CPM logic
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    UNIQUE (project_id, task)
);

CREATE TABLE wbs_predecessors (
    task_id INTEGER NOT NULL,
    predecessor_id INTEGER NOT NULL,
    PRIMARY KEY (task_id, predecessor_id),
    FOREIGN KEY (task_id) REFERENCES wbs(id) ON DELETE CASCADE,
    FOREIGN KEY (predecessor_id) REFERENCES wbs(id) ON DELETE CASCADE
);
-- wbs join attempt








CREATE TABLE wbs (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    display_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    predecessor INTEGER,  -- Can be NULL if no predecessor
    name TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    FOREIGN KEY (predecessor) REFERENCES wbs(id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE wbs_lbs (
    wbs_id INTEGER NOT NULL,
    lbs_id INTEGER NOT NULL,
    PRIMARY KEY (wbs_id, lbs_id),
    FOREIGN KEY (wbs_id) REFERENCES wbs(id) ON DELETE CASCADE,
    FOREIGN KEY (lbs_id) REFERENCES lbs(id) ON DELETE CASCADE
);

CREATE TABLE resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    name TEXT NOT NULL,  -- Name of the resource (e.g., labor, material)
    type TEXT NOT NULL   -- Type of resource (e.g., human, material)
);

CREATE TABLE wbs_resources (
    wbs_id INTEGER NOT NULL,
    resource_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,  -- Quantity of the resource required
    PRIMARY KEY (wbs_id, resource_id),
    FOREIGN KEY (wbs_id) REFERENCES wbs(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
);
