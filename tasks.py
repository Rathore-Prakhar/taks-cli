import sqlite3
from datetime import datetime, timedelta
from InquirerPy import prompt
import time


DB_FILE = 'tasks.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            due_date TEXT NOT NULL,
            due_time TEXT NOT NULL,
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
        datetime.strptime(date_text, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def validate_time(hour, minute):
    try:
        if 1 <= int(hour) <= 12 and 0 <= int(minute) <= 59:
            return True
        else:
            return False
    except ValueError:
        return False

def add_task():
    current_datetime = datetime.now()
    current_date = current_datetime.strftime("%Y-%m-%d")

    questions = [
        {'type': 'input', 'name': 'name', 'message': 'Enter the task name:'},
        {'type': 'input', 'name': 'due_date', 'message': f'Enter the due date (YYYY-MM-DD) or leave blank (current: {current_date}):', 'default': current_date},
        {'type': 'input', 'name': 'due_hour', 'message': 'Enter the due hour (1-12) or leave blank:', 'default': '12'},
        {'type': 'input', 'name': 'due_minute', 'message': 'Enter the due minute (00-59) or leave blank:', 'default': '00'},
        {'type': 'list', 'name': 'due_period', 'message': 'Select AM/PM:', 'choices': ['AM', 'PM']},
        {'type': 'confirm', 'name': 'repeatable', 'message': 'Is the task repeatable?', 'default': False},
        {'type': 'list', 'name': 'repeat_interval', 'message': 'Select repeat interval:', 'choices': ['Daily', 'Weekly'], 'when': lambda answers: answers['repeatable']}
    ]
    answers = prompt(questions)
    
    if not validate_date(answers['due_date']):
        print("Invalid date format. Please use YYYY-MM-DD.")

        return
    
    if not validate_time(answers['due_hour'], answers['due_minute']):
        print("Invalid time format.")
        return

    due_hour = int(answers['due_hour'])
    due_minute = int(answers['due_minute'])
    due_time = format_time(due_hour, due_minute, answers['due_period'])

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (name, due_date, due_time, repeatable, repeat_interval, completed_dates)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (answers['name'], answers['due_date'], due_time, int(answers['repeatable']), answers.get('repeat_interval', None), ""))
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
                INSERT INTO tasks (name, due_date, due_time, repeatable, repeat_interval, completed_dates)
                SELECT name, ?, due_time, repeatable, repeat_interval, ""
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
        cursor.execute('SELECT name, due_date, due_time FROM tasks WHERE completed = 0')
        pending_tasks = cursor.fetchall()
        cursor.execute('SELECT name, completed_dates FROM tasks WHERE completed = 1')
        completed_tasks = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        return

    print("Pending Tasks:")
    for task in pending_tasks:
        due_date_str = f" (Due: {task[1]} {task[2]})" if task[1] and task[2] else ""
        print(f" - {task[0]}{due_date_str}")

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
    main()
