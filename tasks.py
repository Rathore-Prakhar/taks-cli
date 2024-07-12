import sqlite3
from datetime import datetime, timedelta
from InquirerPy import prompt
import time
from colorama import Fore, Style, init
import matplotlib.pyplot as plt
from collections import defaultdict
from pync import Notifier
import json
import csv
import threading

DB_FILE = 'tasks.db'
init(autoreset=True)

def send_notification(task_name, due_time):
    Notifier.notify(f'Task "{task_name}" is due at {due_time}', title='Task Reminder')

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            due_date TEXT NOT NULL,
            due_time TEXT NOT NULL,
            priority TEXT NOT NULL,
            tags TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            repeatable INTEGER NOT NULL DEFAULT 0,
            repeat_interval TEXT,
            completed_dates TEXT
        )
    ''')
    conn.commit()
    conn.close()

def check_upcoming_tasks():
    while True:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            current_time = datetime.now()
            reminder_time = current_time + timedelta(minutes=30)
            cursor.execute('''
                SELECT name, due_date, due_time
                FROM tasks
                WHERE completed = 0 AND datetime(due_date || " " || due_time) BETWEEN ? AND ?
            ''', (current_time.strftime("%Y-%m-%d %H:%M"), reminder_time.strftime("%Y-%m-%d %H:%M")))
            upcoming_tasks = cursor.fetchall()
            conn.close()

            for task in upcoming_tasks:
                task_name = task[0]
                due_datetime = f"{task[1]} {task[2]}"
                send_notification(task_name, due_datetime)

            time.sleep(120)  # check every 2 mins
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")

def validate_date(date_text):
    try:
        date = datetime.strptime(date_text, "%Y-%m-%d")
        if date.date() < datetime.now().date():
            return False
        return True
    except ValueError:
        return False

def validate_time(hour, minute, period, date):
    try:
        if 1 <= int(hour) <= 12 and 0 <= int(minute) <= 59:
            task_datetime = datetime.strptime(f"{date} {hour}:{minute} {period}", "%Y-%m-%d %I:%M %p")
            if task_datetime < datetime.now():
                return False
            return True
        else:
            return False
    except ValueError:
        return False

def add_task():
    current_datetime = datetime.now()
    current_date = current_datetime.strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT tags FROM tasks')
    all_tags = set()
    for row in cursor.fetchall():
        all_tags.update(filter(None, row[0].split(',')))

    all_tags = list(all_tags)

    conn.close()

    questions = [
        {'type': 'input', 'name': 'name', 'message': 'Enter the task name:'},
        {'type': 'input', 'name': 'description', 'message': 'Enter the task description:'},
        {'type': 'input', 'name': 'due_date', 'message': f'Enter the due date (YYYY-MM-DD) or leave blank (current: {current_date}):', 'default': current_date},
        {'type': 'input', 'name': 'due_hour', 'message': 'Enter the due hour (1-12) or leave blank:', 'default': '12'},
        {'type': 'input', 'name': 'due_minute', 'message': 'Enter the due minute (00-59) or leave blank:', 'default': '00'},
        {'type': 'list', 'name': 'due_period', 'message': 'Select AM/PM:', 'choices': ['AM', 'PM']},
        {'type': 'list', 'name': 'priority', 'message': 'Select task priority:', 'choices': ['Low', 'Medium', 'High']},
        {'type': 'checkbox', 'name': 'tags', 'message': 'Select tags or create new (press tab to select and press tab again to deselect):', 'choices': all_tags + ["Create new tag", "No tag"]},
        {'type': 'confirm', 'name': 'repeatable', 'message': 'Is the task repeatable?', 'default': False},
        {'type': 'list', 'name': 'repeat_interval', 'message': 'Select repeat interval:', 'choices': ['Daily', 'Weekly'], 'when': lambda answers: answers['repeatable']}
    ]
    answers = prompt(questions)

    selected_tags = []
    if "No tag" not in answers['tags']:
        create_new = "Create new tag" in answers['tags']
        for tag in answers['tags']:
            if tag != "Create new tag":
                selected_tags.append(tag)
        
        while create_new:
            new_tag_question = [
                {'type': 'input', 'name': 'new_tag', 'message': 'Enter the new tag:'}
            ]
            new_tag_answer = prompt(new_tag_question)
            if new_tag_answer['new_tag']:
                selected_tags.append(new_tag_answer['new_tag'])
                create_another_question = [
                    {'type': 'confirm', 'name': 'create_another', 'message': 'Create another tag?', 'default': False}
                ]
                create_another = prompt(create_another_question)['create_another']
                if not create_another:
                    create_new = False
            else:
                create_new = False

    if not validate_date(answers['due_date']):
        print("Invalid date format or date is in the past. Please use YYYY-MM-DD.")
        return

    if not validate_time(answers['due_hour'], answers['due_minute'], answers['due_period'], answers['due_date']):
        print("Invalid time format or time is in the past.")
        return

    due_hour = int(answers['due_hour'])
    due_minute = int(answers['due_minute'])
    due_time = format_time(due_hour, due_minute, answers['due_period'])
    tags = ",".join(selected_tags) if selected_tags else ""

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (name, description, due_date, due_time, priority, tags, repeatable, repeat_interval, completed_dates)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (answers['name'], answers['description'], answers['due_date'], due_time, answers['priority'], tags, int(answers['repeatable']), answers.get('repeat_interval', None), ""))
        conn.commit()
        conn.close()
        print(f'Task "{answers["name"]}" added.')
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

def complete_task():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM tasks WHERE completed = 0')
        tasks = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        return

    if not tasks:
        print("No tasks to complete.")
        return

    task_choices = [{'name': task[1], 'value': task[0]} for task in tasks]
    questions = [{'type': 'checkbox', 'name': 'tasks', 'message': 'Select tasks to complete:', 'choices': task_choices}]
    answers = prompt(questions)
    selected_task_ids = answers['tasks']

    if not selected_task_ids:
        print("No tasks selected.")
        return

    completion_datetime = datetime.now().strftime("%Y-%m-%d %I:%M %p")

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        for task_id in selected_task_ids:
            cursor.execute('SELECT completed_dates, repeatable, repeat_interval, due_date, name FROM tasks WHERE id = ?', (task_id,))
            task = cursor.fetchone()
            completed_dates = task[0] + ("," if task[0] else "") + completion_datetime
            repeatable = task[1]
            repeat_interval = task[2]
            due_date = task[3]
            task_name = task[4]

            cursor.execute('''
                UPDATE tasks
                SET completed = 1, completed_dates = ?
                WHERE id = ?
            ''', (completed_dates, task_id))

            if repeatable and repeat_interval:
                next_due_date = datetime.strptime(due_date, "%Y-%m-%d")
                if repeat_interval == 'Daily':
                    next_due_date += timedelta(days=1)
                elif repeat_interval == 'Weekly':
                    next_due_date += timedelta(days=7)
                next_due_date_str = next_due_date.strftime("%Y-%m-%d")
                cursor.execute('''
                    INSERT INTO tasks (name, description, due_date, due_time, priority, tags, repeatable, repeat_interval, completed_dates)
                    SELECT name, description, ?, due_time, priority, tags, repeatable, repeat_interval, ""
                    FROM tasks WHERE id = ?
                ''', (next_due_date_str, task_id))

        conn.commit()
        conn.close()
        print("Selected tasks completed.")
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

def list_tasks():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute('SELECT DISTINCT tags FROM tasks')
        all_tags = set()
        for row in cursor.fetchall():
            all_tags.update(filter(None, row[0].split(',')))

        all_tags = list(all_tags)
        if not all_tags:
            all_tags.append("No tags")

        questions = [
            {'type': 'list', 'name': 'filter_priority', 'message': 'Filter by priority:', 'choices': ['All', 'Low', 'Medium', 'High'], 'default': 'All'},
            {'type': 'checkbox', 'name': 'filter_tags', 'message': 'Filter by tags (select multiple):', 'choices': all_tags}
        ]
        answers = prompt(questions)
        filter_priority = answers['filter_priority'] if answers['filter_priority'] != 'All' else None
        filter_tags = answers['filter_tags']

        query = 'SELECT name, due_date, due_time, priority, tags FROM tasks WHERE completed = 0'
        params = []

        if filter_priority:
            query += ' AND priority = ?'
            params.append(filter_priority)
        if filter_tags:
            tag_conditions = []
            for tag in filter_tags:
                if tag == "No tags":
                    tag_conditions.append('tags IS NULL OR tags = ""')
                else:
                    tag_conditions.append('tags LIKE ?')
                    params.append(f"%{tag}%")
            query += ' AND (' + ' OR '.join(tag_conditions) + ')'

        cursor.execute(query, params)
        pending_tasks = cursor.fetchall()

        cursor.execute('SELECT name, completed_dates FROM tasks WHERE completed = 1')
        completed_tasks = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        return

    def get_color(priority):
        if priority == 'High':
            return Fore.RED
        elif priority == 'Medium':
            return Fore.YELLOW
        elif priority == 'Low':
            return Fore.GREEN
        return Style.RESET_ALL

    print("Pending Tasks:")
    for task in pending_tasks:
        due_date_str = f" (Due: {task[1]} {task[2]})" if task[1] and task[2] else ""
        task_color = get_color(task[3])
        print(f"{task_color} - {task[0]}{due_date_str} [Priority: {task[3]}] [Tags: {task[4]}]")

    print("\nCompleted Tasks:")
    for task in completed_tasks:
        completed_dates_str = task[1]
        print(f" - {task[0]} (Completed on: {completed_dates_str})")

def stats():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM tasks')
        total_tasks = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM tasks WHERE completed = 1')
        completed_tasks = cursor.fetchone()[0]

        print(f'Total tasks: {total_tasks}')
        print(f'Completed tasks: {completed_tasks}')

        cursor.execute('SELECT name, due_date, due_time, completed_dates FROM tasks WHERE completed = 1')
        completed_tasks_data = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        return

    late_tasks_count = 0
    current_datetime = datetime.now()
    for task in completed_tasks_data:
        due_datetime = datetime.strptime(f"{task[1]} {task[2]}", "%Y-%m-%d %H:%M")
        completed_dates = task[3].split(', ')
        for completion_date in completed_dates:
            completion_datetime = datetime.strptime(completion_date, "%Y-%m-%d %I:%M %p")
            if completion_datetime > due_datetime:
                late_tasks_count += 1
                print(f"Task '{task[0]}' was completed late. Due date was {task[1]} {task[2]}.")
                break
    print(f'Total late tasks: {late_tasks_count}')

def cleanup_completed_tasks():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tasks WHERE completed = 1')
        conn.commit()
        conn.close()
        print("All completed tasks have been removed.")
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

def format_time(hour, minute, period):
    if period == "PM" and hour != 12:
        hour += 12
    elif period == "AM" and hour == 12:
        hour = 0
    return f"{hour:02}:{minute:02}"

def generate_completion_graph():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT completed_dates FROM tasks WHERE completed = 1')
        completed_dates = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        return

    date_counts = defaultdict(int)
    for dates in completed_dates:
        for date_str in dates[0].split(','):
            date = datetime.strptime(date_str.strip(), "%Y-%m-%d %I:%M %p").date()
            date_counts[date] += 1

    dates = sorted(date_counts.keys())
    counts = [date_counts[date] for date in dates]

    plt.figure(figsize=(12, 6))
    plt.bar(dates, counts)
    plt.title('Tasks Completed per Day')
    plt.xlabel('Date')
    plt.ylabel('Number of Tasks Completed')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

def edit_task():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM tasks WHERE completed = 0')
        tasks = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        return

    if not tasks:
        print("No tasks to edit.")
        return

    task_choices = [f"{task[0]}: {task[1]}" for task in tasks]
    questions = [{'type': 'list', 'name': 'task', 'message': 'Select the task to edit:', 'choices': task_choices}]
    answer = prompt(questions)
    task_id = int(answer['task'].split(':')[0])

    edit_questions = [
        {'type': 'input', 'name': 'name', 'message': 'Enter new task name (leave blank to keep current):'},
        {'type': 'input', 'name': 'due_date', 'message': 'Enter new due date (YYYY-MM-DD) (leave blank to keep current):'},
        {'type': 'input', 'name': 'due_time', 'message': 'Enter new due time (HH:MM) (leave blank to keep current):'},
        {'type': 'list', 'name': 'priority', 'message': 'Select new priority:', 'choices': ['Low', 'Medium', 'High', 'Keep current']},
    ]
    edit_answers = prompt(edit_questions)

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        update_fields = []
        params = []
        if edit_answers['name']:
            update_fields.append('name = ?')
            params.append(edit_answers['name'])
        if edit_answers['due_date']:
            update_fields.append('due_date = ?')
            params.append(edit_answers['due_date'])
        if edit_answers['due_time']:
            update_fields.append('due_time = ?')
            params.append(edit_answers['due_time'])
        if edit_answers['priority'] != 'Keep current':
            update_fields.append('priority = ?')
            params.append(edit_answers['priority'])
        
        if update_fields:
            query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?"
            params.append(task_id)
            cursor.execute(query, params)
            conn.commit()
            print("Task updated successfully.")
        else:
            print("No changes were made to the task.")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

def view_today_tasks():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT name, due_time, priority FROM tasks WHERE due_date = ? AND completed = 0', (today,))
        tasks = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        return

    if not tasks:
        print("No tasks due today.")
        return

    print("Tasks due today:")
    for task in tasks:
        print(f" - {task[0]} (Due: {task[1]}) [Priority: {task[2]}]")

def search_tasks():
    questions = [
        {'type': 'input', 'name': 'keyword', 'message': 'Enter keyword to search in task name or description:'},
        {'type': 'input', 'name': 'tag', 'message': 'Enter tag to search or leave blank:'},
        {'type': 'confirm', 'name': 'include_completed', 'message': 'Include completed tasks?', 'default': False},
    ]
    answers = prompt(questions)
    keyword = answers['keyword']
    tag = answers['tag']
    include_completed = answers['include_completed']

    query = '''
        SELECT id, name, description, due_date, due_time, priority, tags, completed
        FROM tasks
        WHERE (name LIKE ? OR description LIKE ?)
    '''
    params = [f'%{keyword}%', f'%{keyword}%']

    if tag:
        query += ' AND tags LIKE ?'
        params.append(f'%{tag}%')

    if not include_completed:
        query += ' AND completed = 0'

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        return

    if not results:
        print("No tasks found.")
    else:
        for task in results:
            status = "Completed" if task[7] else "Pending"
            print(f"ID: {task[0]}, Name: {task[1]}, Description: {task[2]}, Due: {task[3]} {task[4]}, Priority: {task[5]}, Tags: {task[6]}, Status: {status}")

def generate_completion_graph():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT completed_dates FROM tasks WHERE completed = 1')
        completed_dates = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        return

    date_counts = defaultdict(int)
    for dates in completed_dates:
        for date_str in dates[0].split(','):
            date = datetime.strptime(date_str.strip(), "%Y-%m-%d %I:%M %p")
            date_counts[date] += 1

    range_options = [
        'Today',
        'This Week',
        'This Month',
        'This Year',
        'Custom Date Range'
    ]

    range_question = [{'type': 'list', 'name': 'range', 'message': 'Select date range:', 'choices': range_options}]
    range_answer = prompt(range_question)['range']

    now = datetime.now()

    if range_answer == 'Today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        label_format = "%H:00"
        increment = timedelta(hours=1)
        title = 'Tasks Completed Today (by hour)'
    elif range_answer == 'This Week':
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)
        label_format = "%a"
        increment = timedelta(days=1)
        title = 'Tasks Completed This Week'
    elif range_answer == 'This Month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = (start_date + timedelta(days=32)).replace(day=1)
        label_format = "%d"
        increment = timedelta(days=1)
        title = 'Tasks Completed This Month'
    elif range_answer == 'This Year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date.replace(year=start_date.year + 1)
        label_format = "%b"
        increment = timedelta(days=30)
        title = 'Tasks Completed This Year'
    else:
        custom_range_questions = [
            {'type': 'input', 'name': 'start_date', 'message': 'Enter start date (YYYY-MM-DD):'},
            {'type': 'input', 'name': 'end_date', 'message': 'Enter end date (YYYY-MM-DD):'}
        ]
        custom_range = prompt(custom_range_questions)
        start_date = datetime.strptime(custom_range['start_date'], "%Y-%m-%d")
        end_date = datetime.strptime(custom_range['end_date'], "%Y-%m-%d") + timedelta(days=1)
        
        if (end_date - start_date).days <= 7:
            label_format = "%a"
            increment = timedelta(days=1)
        elif (end_date - start_date).days <= 31:
            label_format = "%d"
            increment = timedelta(days=1)
        else:
            label_format = "%b"
            increment = timedelta(days=30)
        
        title = f'Tasks Completed from {start_date.date()} to {end_date.date() - timedelta(days=1)}'

    graph_data = []
    current_date = start_date
    while current_date < end_date:
        count = sum(1 for d in date_counts if current_date <= d < current_date + increment)
        graph_data.append((current_date, count))
        current_date += increment

    max_count = max(count for _, count in graph_data) if graph_data else 0
    
    print(title)
    print('-' * 50)
    
    graph_height = 10
    for i in range(graph_height, 0, -1):
        row = ""
        for _, count in graph_data:
            if count >= (i / graph_height) * max_count:
                row += "█"
            else:
                row += " "
        print(f"{row} {i * max_count // graph_height:2d}")
    x_axis = "".join(date.strftime(label_format)[0] for date, _ in graph_data)
    print(x_axis)
    print('-' * 50)
    for date, _ in graph_data:
        print(f"{date.strftime(label_format):>3}", end=" ")
    print()
    print('-' * 50)
    for _, count in graph_data:
        print(f"{count:3d}", end=" ")
    print()

def settings():
    current_settings = load_settings()
    
    all_menu_items = [
        'Add a task',
        'Complete a task',
        'Edit a task',
        'List all tasks',
        'View tasks due today',
        'Search tasks',
        'Show task statistics',
        'Generate completion graph',
        'Remove completed tasks',
        'Export tasks',
        'Import tasks'
    ]
    
    setting_questions = [
        {
            'type': 'checkbox',
            'name': 'menu_items',
            'message': 'Toggle menu items to display:',
            'choices': [
                {
                    'name': item,
                    'value': item,
                    'checked': item in current_settings['menu_items']
                } for item in all_menu_items
            ]
        }
    ]
    
    new_settings = prompt(setting_questions)
    save_settings(new_settings)
    print("Settings updated successfully.")

def export_tasks():
    questions = [
        {'type': 'list', 'name': 'format', 'message': 'Select export format:', 'choices': ['CSV', 'JSON']}
    ]
    answers = prompt(questions)
    export_format = answers['format']

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT name, description, due_date, due_time, priority, tags, completed, repeatable, repeat_interval, completed_dates FROM tasks')
    tasks = cursor.fetchall()
    conn.close()

    if export_format == 'CSV':
        with open('tasks_export.csv', 'w', newline='') as csvfile:
            fieldnames = ['Name', 'Description', 'Due Date', 'Due Time', 'Priority', 'Tags', 'Completed', 'Repeatable', 'Repeat Interval', 'Completed Dates']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for task in tasks:
                writer.writerow({
                    'Name': task[0],
                    'Description': task[1],
                    'Due Date': task[2],
                    'Due Time': task[3],
                    'Priority': task[4],
                    'Tags': task[5],
                    'Completed': task[6],
                    'Repeatable': task[7],
                    'Repeat Interval': task[8],
                    'Completed Dates': task[9]
                })
    elif export_format == 'JSON':
        with open('tasks_export.json', 'w') as jsonfile:
            task_list = []
            for task in tasks:
                task_list.append({
                    'Name': task[0],
                    'Description': task[1],
                    'Due Date': task[2],
                    'Due Time': task[3],
                    'Priority': task[4],
                    'Tags': task[5],
                    'Completed': task[6],
                    'Repeatable': task[7],
                    'Repeat Interval': task[8],
                    'Completed Dates': task[9]
                })
            json.dump(task_list, jsonfile, indent=4)
    print(f'Tasks exported to tasks_export.{export_format.lower()}.')

def import_tasks():
    filename = input("Enter the filename to import tasks from (e.g., tasks.csv): ")
    try:
        with open(filename, 'r') as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            for row in reader:
                cursor.execute('''
                    INSERT INTO tasks (name, due_date, due_time, priority, tags, completed, repeatable, repeat_interval, completed_dates)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (row[1], row[2], row[3], row[4], row[5], int(row[6]), int(row[7]), row[8], row[9]))
            
            conn.commit()
            conn.close()
            print(f"Tasks imported successfully from {filename}")
    except FileNotFoundError:
        print(f"File {filename} not found.")
    except csv.Error as e:
        print(f"Error reading CSV file: {e}")
    except sqlite3.Error as e:
        print(f"Error inserting data into database: {e}")

def get_default_menu_items():
    return [
        'Add a task',
        'Complete a task',
        'Edit a task',
        'List all tasks',
        'View tasks due today',
        'Search tasks',
        'Show task statistics',
        'Generate completion graph',
        'Remove completed tasks',
        'Export tasks',
        'Import tasks'
    ]

def load_settings():
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
            if 'menu_items' not in settings:
                settings['menu_items'] = get_default_menu_items()
            return settings
    except FileNotFoundError:
        return {'menu_items': get_default_menu_items()}

def save_settings(settings):
    with open('settings.json', 'w') as f:
        json.dump(settings, f, indent=2)

def main():
    init_db()
    while True:
        current_settings = load_settings()
        menu_items = current_settings['menu_items'] + ['Settings', 'Exit']
        
        questions = [
            {'type': 'list', 'name': 'choice', 'message': 'Task Reminder CLI Tool', 'choices': menu_items}
        ]
        choice = prompt(questions)['choice']
        
        if choice == 'Add a task':
            add_task()
        elif choice == 'Complete a task':
            complete_task()
        elif choice == 'Edit a task':
            edit_task()
        elif choice == 'List all tasks':
            list_tasks()
        elif choice == 'View tasks due today':
            view_today_tasks()
        elif choice == 'Search tasks':
            search_tasks()
        elif choice == 'Show task statistics':
            stats()
        elif choice == 'Generate completion graph':
            generate_completion_graph()
        elif choice == 'Remove completed tasks':
            cleanup_completed_tasks()
        elif choice == 'Export tasks':
            export_tasks()
        elif choice == 'Import tasks':
            import_tasks()
        elif choice == 'Settings':
            settings()
        elif choice == 'Exit':
            break
        time.sleep(2)

notification_thread = threading.Thread(target=check_upcoming_tasks, daemon=True)
notification_thread.start()

if __name__ == '__main__':
    try:
        init_db()
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted. Exiting.")
