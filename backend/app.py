from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    time_entries = db.relationship('TimeEntry', backref='user', lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)
    subtasks = db.relationship('Task', backref=db.backref('parent', remote_side=[id]))
    time_entries = db.relationship('TimeEntry', backref='task', lazy=True)

class TimeEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)

# Routes
@app.route('/api/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{"id": user.id, "code": user.code, "name": user.name} for user in users])

@app.route('/api/users/<code>', methods=['GET'])
def get_user_by_code(code):
    user = User.query.filter_by(code=code).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"id": user.id, "code": user.code, "name": user.name})

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    new_user = User(code=data['code'], name=data['name'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"id": new_user.id, "code": new_user.code, "name": new_user.name}), 201

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    # Get only top-level tasks
    tasks = Task.query.filter_by(parent_id=None).all()
    result = []
    for task in tasks:
        task_data = {"id": task.id, "name": task.name}
        subtasks = []
        for subtask in task.subtasks:
            subtasks.append({"id": subtask.id, "name": subtask.name})
        task_data["subtasks"] = subtasks
        result.append(task_data)
    return jsonify(result)

@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.json
    parent_id = data.get('parent_id')
    new_task = Task(name=data['name'], parent_id=parent_id)
    db.session.add(new_task)
    db.session.commit()
    return jsonify({"id": new_task.id, "name": new_task.name, "parent_id": new_task.parent_id}), 201

@app.route('/api/time-entries', methods=['GET'])
def get_active_entries():
    active_entries = TimeEntry.query.filter_by(end_time=None).all()
    result = []
    for entry in active_entries:
        user = User.query.get(entry.user_id)
        task = Task.query.get(entry.task_id)
        parent_task = None
        if task.parent_id:
            parent_task = Task.query.get(task.parent_id)
            
        result.append({
            "id": entry.id,
            "user": {"id": user.id, "name": user.name},
            "task": {
                "id": task.id, 
                "name": task.name,
                "parent": {"id": parent_task.id, "name": parent_task.name} if parent_task else None
            },
            "start_time": entry.start_time.isoformat()
        })
    return jsonify(result)

@app.route('/api/time-entries', methods=['POST'])
def start_time_entry():
    data = request.json
    user_id = data['user_id']
    task_id = data['task_id']
    
    # End any active entries for this user
    active_entries = TimeEntry.query.filter_by(user_id=user_id, end_time=None).all()
    for entry in active_entries:
        entry.end_time = datetime.utcnow()
    
    # Check if there's a recent entry for the same task to continue
    recent_entry = TimeEntry.query.filter_by(
        user_id=user_id, 
        task_id=task_id
    ).order_by(TimeEntry.start_time.desc()).first()
    
    # If it's the same task and was active in the last hour, continue it
    if recent_entry and recent_entry.end_time and (datetime.utcnow() - recent_entry.end_time).total_seconds() < 3600:
        # Continue the task
        new_entry = TimeEntry(user_id=user_id, task_id=task_id)
    else:
        # Start a new task
        new_entry = TimeEntry(user_id=user_id, task_id=task_id)
    
    db.session.add(new_entry)
    db.session.commit()
    
    return jsonify({
        "id": new_entry.id,
        "user_id": new_entry.user_id,
        "task_id": new_entry.task_id,
        "start_time": new_entry.start_time.isoformat()
    }), 201

@app.route('/api/time-entries/<int:entry_id>', methods=['PUT'])
def end_time_entry(entry_id):
    entry = TimeEntry.query.get_or_404(entry_id)
    entry.end_time = datetime.utcnow()
    db.session.commit()
    return jsonify({
        "id": entry.id,
        "user_id": entry.user_id,
        "task_id": entry.task_id,
        "start_time": entry.start_time.isoformat(),
        "end_time": entry.end_time.isoformat()
    })

@app.route('/api/initialize', methods=['POST'])
def initialize_data():
    # Create main tasks
    main_tasks = [
        "PRZYJĘCIE DOSTAWY", 
        "KOMPLETACJA", 
        "PAKOWANIE", 
        "ZWROTY", 
        "JAKOŚĆ", 
        "CZYNNOŚCI DODATKOWE",
        "SPECJALIŚCI",
        "PRZERWA"
    ]
    
    task_mapping = {}
    
    for task_name in main_tasks:
        task = Task(name=task_name)
        db.session.add(task)
        db.session.commit()
        task_mapping[task_name] = task.id
    
    # Create subtasks
    subtasks = {
        "PRZYJĘCIE DOSTAWY": ["wiszące", "koszule", "karton", "buty"],
        "KOMPLETACJA": ["grupówka", "jednorazy", "`002", "`030", "zagranica"],
        "PAKOWANIE": ["pakowanie www"],
        "ZWROTY": ["zwroty002", "zwroty zagranica", "zwroty www", "lokowanie zwrotów"],
        "JAKOŚĆ": ["kontrola jakości", "kontrola zagranica", "czyszczenie lokacji", "defekty", "przemieszczenia"],
        "CZYNNOŚCI DODATKOWE": ["przeklejanie cen", "wywieszanie na wieszaki", "przemieszczenia", "pomoc biuro", "porządki", "targi/ eventy", "transport", "inne"]
    }
    
    for parent_name, sub_tasks in subtasks.items():
        parent_id = task_mapping.get(parent_name)
        if parent_id:
            for subtask_name in sub_tasks:
                subtask = Task(name=subtask_name, parent_id=parent_id)
                db.session.add(subtask)
    
    # Add sample users
    sample_users = [
        {"code": "EMP001", "name": "Jan Kowalski"},
        {"code": "EMP002", "name": "Anna Nowak"},
        {"code": "EMP003", "name": "Piotr Wiśniewski"}
    ]
    
    for user_data in sample_users:
        user = User(code=user_data["code"], name=user_data["name"])
        db.session.add(user)
    
    db.session.commit()
    return jsonify({"message": "Database initialized successfully"}), 201

# Create database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)