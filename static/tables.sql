CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    username TEXT NOT NULL,
    hash TEXT NOT NULL,
    UNIQUE (username)
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    user_id INTEGER NOT NULL,
    start_date DATE,
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

CREATE TABLE wbs (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    display_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    task TEXT NOT NULL,
    duration FLOAT,  
    start_time DATE,  
    end_time DATE,  
    ES DATE,
    EF DATE,
    LS DATE,
    LF DATE,
    slack FLOAT,
    critical TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE (project_id, task)
);

CREATE TABLE wbs_predecessors (
    task_id INTEGER NOT NULL,
    predecessor_id INTEGER,
    PRIMARY KEY (task_id, predecessor_id),
    FOREIGN KEY (task_id) REFERENCES wbs(id) ON DELETE CASCADE,
    FOREIGN KEY (predecessor_id) REFERENCES wbs(id) ON DELETE CASCADE
);

-- For calculated for each location, this table must be created and the calcule_dates function updated
CREATE TABLE wbs_lbs (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    wbs_id INTEGER NOT NULL,
    lbs_id INTEGER NOT NULL,
    start_time DATE,
    end_time DATE,
    FOREIGN KEY (wbs_id) REFERENCES wbs(id) ON DELETE CASCADE,
    FOREIGN KEY (lbs_id) REFERENCES lbs(id) ON DELETE CASCADE,
    UNIQUE (wbs_id, lbs_id)
);