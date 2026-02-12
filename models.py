from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    # Basic info
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    user_role = db.Column(db.String(20), default='user')  # might add admin later
    
    # Links user to their collections
    collections = db.relationship('Collection', backref='owner', lazy=True, cascade='all, delete-orphan')
    
    # Links user to groups they own
    owned_groups = db.relationship('Group', backref='leader', lazy=True, foreign_keys='Group.leader_id')
    
    # Links user to group memberships
    group_memberships = db.relationship('GroupMember', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        # Hash password instead of storing plain text
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        # Check if password matches the hash
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        # Flask-Login needs this to work properly
        return str(self.user_id)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Collection(db.Model):
    __tablename__ = 'collection'
    
    collection_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    collection_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Each collection can have multiple task lists
    task_lists = db.relationship('TaskList', backref='collection', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Collection {self.collection_name}>'


class TaskList(db.Model):
    __tablename__ = 'task_list'
    
    task_list_id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('collection.collection_id'), nullable=False)
    list_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Each task list can have multiple tasks
    tasks = db.relationship('Task', backref='task_list', lazy=True, cascade='all, delete-orphan')
    
    # Track which groups this task list is shared with
    shared_with_groups = db.relationship('SharedTaskList', backref='task_list', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<TaskList {self.list_name}>'


class Task(db.Model):
    __tablename__ = 'task'
    
    task_id = db.Column(db.Integer, primary_key=True)
    task_list_id = db.Column(db.Integer, db.ForeignKey('task_list.task_list_id'), nullable=False)
    task_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='todo')  # todo, doing, completed
    priority = db.Column(db.String(20))
    due_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    completed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))  # Track who completed it
    
    # Relationship to user who completed it
    completed_by = db.relationship('User', foreign_keys=[completed_by_user_id])
    
    def __repr__(self):
        return f'<Task {self.task_name}>'


class Group(db.Model):
    __tablename__ = 'group'
    
    group_id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    leader_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Group members
    members = db.relationship('GroupMember', backref='group', lazy=True, cascade='all, delete-orphan')
    
    # Shared task lists
    shared_task_lists = db.relationship('SharedTaskList', backref='group', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Group {self.group_name}>'


class GroupMember(db.Model):
    __tablename__ = 'group_member'
    
    membership_id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.group_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # leader, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GroupMember user_id={self.user_id} group_id={self.group_id}>'


class SharedTaskList(db.Model):
    __tablename__ = 'shared_task_list'
    
    share_id = db.Column(db.Integer, primary_key=True)
    task_list_id = db.Column(db.Integer, db.ForeignKey('task_list.task_list_id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.group_id'), nullable=False)
    shared_at = db.Column(db.DateTime, default=datetime.utcnow)
    shared_by_user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    
    # Who shared it
    shared_by = db.relationship('User', foreign_keys=[shared_by_user_id])
    
    def __repr__(self):
        return f'<SharedTaskList task_list_id={self.task_list_id} group_id={self.group_id}>'