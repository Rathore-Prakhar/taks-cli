import sqlite3
from datetime import datetime, timedelta
from InquirerPy import prompt
import time
from colorama import Fore, Style, init

DB_FILE = 'tasks.db'
init(autoreset=True)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
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
        {'type': 'input', 'name': 'due_date', 'message': f'Enter the due date (YYYY-MM-DD) or leave blank (current: {current_date}):', 'default': current_date},
        {'type': 'input', 'name': 'due_hour', 'message': 'Enter the due hour (1-12) or leave blank:', 'default': '12'},
        {'type': 'input', 'name': 'due_minute', 'message': 'Enter the due minute (00-59) or leave blank:', 'default': '00'},
        {'type': 'list', 'name': 'due_period', 'message': 'Select AM/PM:', 'choices': ['AM', 'PM']},
        {'type': 'list', 'name': 'priority', 'message': 'Select task priority:', 'choices': ['Low', 'Medium', 'High']},
        {'type': 'checkbox', 'name': 'tags', 'message': 'Select tags (multiple allowed) or create new:', 'choices': all_tags + ["Create new tag"] + ["No tag"]},
        {'type': 'confirm', 'name': 'repeatable', 'message': 'Is the task repeatable?', 'default': False},
        {'type': 'list', 'name': 'repeat_interval', 'message': 'Select repeat interval:', 'choices': ['Daily', 'Weekly'], 'when': lambda answers: answers['repeatable']}
    ]
    answers = prompt(questions)

    if "Create new tag" in answers['tags']:
        new_tag_question = [
            {'type': 'input', 'name': 'new_tag', 'message': 'Enter the new tag:'}
        ]
        new_tag_answer = prompt(new_tag_question)
        answers['tags'].remove("Create new tag")
        answers['tags'].append(new_tag_answer['new_tag'])

    if not validate_date(answers['due_date']):
        print("Invalid date format or date is in the past. Please use YYYY-MM-DD.")
        return

    if not validate_time(answers['due_hour'], answers['due_minute'], answers['due_period'], answers['due_date']):
        print("Invalid time format or time is in the past.")
        return

    due_hour = int(answers['due_hour'])
    due_minute = int(answers['due_minute'])
    due_time = format_time(due_hour, due_minute, answers['due_period'])
    tags = ",".join(answers['tags'])

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (name, due_date, due_time, priority, tags, repeatable, repeat_interval, completed_dates)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (answers['name'], answers['due_date'], due_time, answers['priority'], tags, int(answers['repeatable']), answers.get('repeat_interval', None), ""))
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

    task_choices = [task[1] for task in tasks]
    questions = [{'type': 'list', 'name': 'name', 'message': 'Select the task to complete:', 'choices': task_choices}]
    answers = prompt(questions)
    task_name = answers['name']
    completion_datetime = datetime.now().strftime("%Y-%m-%d %I:%M %p")

    for task in tasks:
        if task[1] == task_name:
            task_id = task[0]
            break

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT completed_dates, repeatable, repeat_interval, due_date FROM tasks WHERE id = ?', (task_id,))
        task = cursor.fetchone()
        completed_dates = task[0] + ("," if task[0] else "") + completion_datetime
        repeatable = task[1]
        repeat_interval = task[2]
        due_date = task[3]

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
                INSERT INTO tasks (name, due_date, due_time, priority, tags, repeatable, repeat_interval, completed_dates)
                SELECT name, ?, due_time, priority, tags, repeatable, repeat_interval, ""
                FROM tasks WHERE id = ?
            ''', (next_due_date_str, task_id))

        conn.commit()
        conn.close()
        print(f'Task "{task_name}" marked as completed.')
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

def main():
    init_db()
    while True:
        questions = [
            {'type': 'list', 'name': 'choice', 'message': 'Task Reminder CLI Tool', 'choices': ['Add a task', 'Complete a task', 'List all tasks', 'Show task statistics', 'Remove completed tasks', 'Exit']}
        ]
        choice = prompt(questions)['choice']
        
        if choice == 'Add a task':
            add_task()
        elif choice == 'Complete a task':
            complete_task()
        elif choice == 'List all tasks':
            list_tasks()
        elif choice == 'Show task statistics':
            stats()
        elif choice == 'Remove completed tasks':
            cleanup_completed_tasks()
        elif choice == 'Exit':
            break
        time.sleep(2)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted. Exiting.")
