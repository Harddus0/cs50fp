
tasks = []
locations = []
predecessor = []
project_start_time = 0

temp = 0
for task in tasks:
    
    # Check if it's first task or if task is longer than predecessor
    if predecessor or task["duration"] > predecessor["duration"]:
        
        # Forward Pass
        for location in locations:
            if temp == 0:
                task["start_time"] = temp
                task["end_time"] = task["start_time"] + task["duration"]
                temp = task["end_time"]
                first_end = task["end_time"]
            else:
                task["start_time"] = project_start_time
                task["end_time"] = task["start_time"] + task["duration"]
                temp = task["end_time"]
        last_end = task["end_time"]
        temp = 0

            
    else:
        # Backwards pass
        for location in reversed(locations):
            if temp == 0:
                task["start_time"] = last_end
                task["end_time"] = task["start_time"] + task["duration"]
                temp = task["start_time"]
                last_end = task["end_time"]
            else:
                task["end_time"] = temp
                task["start_time"] = task["end_time"] - task["duration"]
                temp = task["start_time"]
        first_end = task["end_time"]