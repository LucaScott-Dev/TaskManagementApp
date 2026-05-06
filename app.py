from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Collection, TaskList, Task, Group, GroupMember, SharedTaskList, TaskListAssignment
from datetime import datetime

app = Flask(__name__)

app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///taskmanager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()


def user_has_access_to_task_list(user_id, task_list_id):
    task_list = TaskList.query.get(task_list_id)
    if not task_list:
        return False
    
    collection = Collection.query.get(task_list.collection_id)
    
    if collection.user_id == user_id:
        return True
    
    assigned = GroupMember.query.filter(
        GroupMember.user_id == user_id
    ).join(
        TaskListAssignment, TaskListAssignment.membership_id == GroupMember.membership_id
    ).filter(
        TaskListAssignment.task_list_id == task_list_id
    ).first()
    
    return assigned is not None


# ========== ROUTES ==========

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    errors = {}
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not user:
            errors['username'] = 'Username not found'
        elif not user.check_password(password):
            errors['password'] = 'Incorrect password'
        else:
            login_user(user)
            return redirect(url_for('dashboard'))
    
    return render_template('login.html', errors=errors)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    errors = {}
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm-password')
        
        if User.query.filter_by(username=username).first():
            errors['username'] = 'Username already exists'
        
        if password != confirm_password:
            errors['confirm-password'] = 'Passwords do not match'
        
        if not errors:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html', errors=errors)


@app.route('/dashboard')
@login_required
def dashboard():
    collections = Collection.query.filter_by(user_id=current_user.user_id).order_by(Collection.created_at.desc()).all()
    
    owned_groups = Group.query.filter_by(leader_id=current_user.user_id).all()
    
    member_groups = db.session.query(Group).join(GroupMember).filter(
        GroupMember.user_id == current_user.user_id,
        Group.leader_id != current_user.user_id
    ).all()
    
    all_groups = owned_groups + member_groups
    
    return render_template('dashboard.html', 
                         username=current_user.username, 
                         collections=collections,
                         groups=all_groups)


# ========== COLLECTION ROUTES ==========

@app.route('/collection/create', methods=['POST'])
@login_required
def create_collection():
    collection_name = request.form.get('collection_name')
    description = request.form.get('description')
    
    if not collection_name:
        flash('Collection name is required!', 'error')
        return redirect(url_for('dashboard'))
    
    new_collection = Collection(
        user_id=current_user.user_id,
        collection_name=collection_name,
        description=description
    )
    
    db.session.add(new_collection)
    db.session.commit()
    
    flash('Collection created successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/collection/delete/<int:collection_id>', methods=['POST'])
@login_required
def delete_collection(collection_id):
    collection = Collection.query.get_or_404(collection_id)
    
    if collection.user_id != current_user.user_id:
        flash('You do not have permission to delete this collection.', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(collection)
    db.session.commit()
    
    flash('Collection deleted successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/collection/<int:collection_id>')
@login_required
def view_collection(collection_id):
    collection = Collection.query.get_or_404(collection_id)
    
    if collection.user_id != current_user.user_id:
        flash('You do not have permission to view this collection.', 'error')
        return redirect(url_for('dashboard'))
    
    task_lists = TaskList.query.filter_by(collection_id=collection_id).order_by(TaskList.created_at.desc()).all()
    
    user_groups = db.session.query(Group).join(GroupMember).filter(
        GroupMember.user_id == current_user.user_id
    ).all()
    
    return render_template('collection.html', 
                         collection=collection, 
                         task_lists=task_lists,
                         user_groups=user_groups)


# ========== TASK LIST ROUTES ==========

@app.route('/collection/<int:collection_id>/create_list', methods=['POST'])
@login_required
def create_task_list(collection_id):
    collection = Collection.query.get_or_404(collection_id)
    
    if collection.user_id != current_user.user_id:
        flash('You do not have permission to modify this collection.', 'error')
        return redirect(url_for('dashboard'))
    
    list_name = request.form.get('list_name')
    description = request.form.get('description')
    
    if not list_name:
        flash('Task list name is required!', 'error')
        return redirect(url_for('view_collection', collection_id=collection_id))
    
    new_task_list = TaskList(
        collection_id=collection_id,
        list_name=list_name,
        description=description
    )
    
    db.session.add(new_task_list)
    db.session.commit()
    
    flash('Task list created successfully!', 'success')
    return redirect(url_for('view_collection', collection_id=collection_id))


@app.route('/tasklist/share/<int:task_list_id>', methods=['POST'])
@login_required
def share_task_list(task_list_id):
    task_list = TaskList.query.get_or_404(task_list_id)
    collection = Collection.query.get(task_list.collection_id)
    
    if collection.user_id != current_user.user_id:
        flash('Only the owner can share this task list.', 'error')
        return redirect(url_for('view_collection', collection_id=collection.collection_id))
    
    group_id = request.form.get('group_id')
    
    existing = SharedTaskList.query.filter_by(task_list_id=task_list_id, group_id=group_id).first()
    if existing:
        flash('Task list is already shared with this group!', 'error')
        return redirect(url_for('view_collection', collection_id=collection.collection_id))
    
    share = SharedTaskList(
        task_list_id=task_list_id,
        group_id=group_id,
        shared_by_user_id=current_user.user_id
    )
    
    db.session.add(share)
    db.session.commit()
    
    flash('Task list shared successfully!', 'success')
    return redirect(url_for('view_collection', collection_id=collection.collection_id))


@app.route('/tasklist/unshare/<int:task_list_id>/<int:group_id>', methods=['POST'])
@login_required
def unshare_task_list(task_list_id, group_id):
    task_list = TaskList.query.get_or_404(task_list_id)
    collection = Collection.query.get(task_list.collection_id)
    
    if collection.user_id != current_user.user_id:
        flash('Only the owner can unshare this task list.', 'error')
        return redirect(url_for('dashboard'))
    
    share = SharedTaskList.query.filter_by(task_list_id=task_list_id, group_id=group_id).first()
    if share:
        db.session.delete(share)
        db.session.commit()
        flash('Task list unshared successfully!', 'success')
    
    return redirect(url_for('view_collection', collection_id=collection.collection_id))


@app.route('/tasklist/delete/<int:task_list_id>', methods=['POST'])
@login_required
def delete_task_list(task_list_id):
    task_list = TaskList.query.get_or_404(task_list_id)
    collection = Collection.query.get(task_list.collection_id)
    
    if collection.user_id != current_user.user_id:
        flash('You do not have permission to delete this task list.', 'error')
        return redirect(url_for('dashboard'))
    
    collection_id = task_list.collection_id
    db.session.delete(task_list)
    db.session.commit()
    
    flash('Task list deleted successfully!', 'success')
    return redirect(url_for('view_collection', collection_id=collection_id))


@app.route('/tasklist/<int:task_list_id>')
@login_required
def view_task_list(task_list_id):
    task_list = TaskList.query.get_or_404(task_list_id)
    collection = Collection.query.get(task_list.collection_id)
    
    if not user_has_access_to_task_list(current_user.user_id, task_list_id):
        flash('You do not have permission to view this task list.', 'error')
        return redirect(url_for('dashboard'))
    
    is_owner = (collection.user_id == current_user.user_id)
    
    assigned_to_me = False
    if not is_owner:
        my_membership = GroupMember.query.filter(
            GroupMember.user_id == current_user.user_id
        ).join(
            TaskListAssignment, TaskListAssignment.membership_id == GroupMember.membership_id
        ).filter(
            TaskListAssignment.task_list_id == task_list_id
        ).first()
        assigned_to_me = my_membership is not None
    
    if not is_owner and not assigned_to_me:
        flash('This task list has not been assigned to you.', 'error')
        return redirect(url_for('dashboard'))
    
    todo_tasks = Task.query.filter_by(task_list_id=task_list_id, status='todo').order_by(Task.created_at.desc()).all()
    doing_tasks = Task.query.filter_by(task_list_id=task_list_id, status='doing').order_by(Task.created_at.desc()).all()
    completed_tasks = Task.query.filter_by(task_list_id=task_list_id, status='completed').order_by(Task.completed_at.desc()).all()
    
    return render_template('task_list.html', 
                         task_list=task_list, 
                         collection=collection,
                         todo_tasks=todo_tasks,
                         doing_tasks=doing_tasks,
                         completed_tasks=completed_tasks,
                         is_owner=is_owner,
                         assigned_to_me=assigned_to_me)


# ========== TASK ROUTES ==========

@app.route('/tasklist/<int:task_list_id>/create_task', methods=['POST'])
@login_required
def create_task(task_list_id):
    if not user_has_access_to_task_list(current_user.user_id, task_list_id):
        flash('You do not have permission to add tasks here.', 'error')
        return redirect(url_for('dashboard'))
    
    task_name = request.form.get('task_name')
    description = request.form.get('description')
    
    if not task_name:
        flash('Task name is required!', 'error')
        return redirect(url_for('view_task_list', task_list_id=task_list_id))
    
    new_task = Task(
        task_list_id=task_list_id,
        task_name=task_name,
        description=description,
        status='todo'
    )
    
    db.session.add(new_task)
    db.session.commit()
    
    flash('Task created successfully!', 'success')
    return redirect(url_for('view_task_list', task_list_id=task_list_id))


@app.route('/task/edit/<int:task_id>', methods=['POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if not user_has_access_to_task_list(current_user.user_id, task.task_list_id):
        flash('You do not have permission to edit this task.', 'error')
        return redirect(url_for('dashboard'))
    
    task_name = request.form.get('task_name')
    description = request.form.get('description')
    
    if not task_name:
        flash('Task name is required!', 'error')
        return redirect(url_for('view_task_list', task_list_id=task.task_list_id))
    
    task.task_name = task_name
    task.description = description
    db.session.commit()
    
    flash('Task updated successfully!', 'success')
    return redirect(url_for('view_task_list', task_list_id=task.task_list_id))


@app.route('/task/<int:task_id>/move/<string:status>', methods=['POST'])
@login_required
def move_task(task_id, status):
    task = Task.query.get_or_404(task_id)
    
    if not user_has_access_to_task_list(current_user.user_id, task.task_list_id):
        return jsonify({'error': 'Unauthorized'}), 403
    
    if status not in ['todo', 'doing', 'completed']:
        return jsonify({'error': 'Invalid status'}), 400
    
    task.status = status
    
    if status == 'completed':
        task.completed_at = datetime.utcnow()
        task.completed_by_user_id = current_user.user_id
    else:
        task.completed_at = None
        task.completed_by_user_id = None
    
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/task/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if not user_has_access_to_task_list(current_user.user_id, task.task_list_id):
        flash('You do not have permission to delete this task.', 'error')
        return redirect(url_for('dashboard'))
    
    task_list_id = task.task_list_id
    db.session.delete(task)
    db.session.commit()
    
    flash('Task deleted successfully!', 'success')
    return redirect(url_for('view_task_list', task_list_id=task_list_id))


# ========== GROUP ROUTES ==========

@app.route('/group/create', methods=['POST'])
@login_required
def create_group():
    group_name = request.form.get('group_name')
    description = request.form.get('description')
    
    if not group_name:
        flash('Group name is required!', 'error')
        return redirect(url_for('dashboard'))
    
    new_group = Group(
        group_name=group_name,
        description=description,
        leader_id=current_user.user_id
    )
    
    db.session.add(new_group)
    db.session.commit()
    
    leader_member = GroupMember(
        group_id=new_group.group_id,
        user_id=current_user.user_id,
        role='leader'
    )
    
    db.session.add(leader_member)
    db.session.commit()
    
    flash('Group created successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/group/<int:group_id>')
@login_required
def view_group(group_id):
    group = Group.query.get_or_404(group_id)
    
    is_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.user_id).first()
    if not is_member:
        flash('You are not a member of this group.', 'error')
        return redirect(url_for('dashboard'))
    
    members = db.session.query(User, GroupMember).join(
        GroupMember, User.user_id == GroupMember.user_id
    ).filter(GroupMember.group_id == group_id).all()
    
    is_leader = (group.leader_id == current_user.user_id)
    
    member_ids = [m.user_id for _, m in members]
    available_users = User.query.filter(User.user_id.notin_(member_ids)).all()
    
    shared_task_lists = SharedTaskList.query.filter_by(group_id=group_id).all()
    shared_lists = []
    for share in shared_task_lists:
        task_list = TaskList.query.get(share.task_list_id)
        collection = Collection.query.get(task_list.collection_id)
        shared_by_user = User.query.get(share.shared_by_user_id)
        shared_lists.append((task_list, share, collection, shared_by_user))
    
    member_progress = []
    for user, membership in members:
        assignments = TaskListAssignment.query.filter_by(membership_id=membership.membership_id).all()
        
        if not assignments:
            continue
        
        assigned_lists = []
        total_tasks = 0
        completed_tasks = 0
        
        for assignment in assignments:
            task_list = TaskList.query.get(assignment.task_list_id)
            all_tasks = Task.query.filter_by(task_list_id=task_list.task_list_id).all()
            done = Task.query.filter_by(task_list_id=task_list.task_list_id, status='completed').count()
            total = len(all_tasks)
            
            total_tasks += total
            completed_tasks += done
            
            assigned_lists.append({
                'task_list': task_list,
                'total': total,
                'completed': done,
                'percent': int((done / total * 100) if total > 0 else 0)
            })
        
        overall_percent = int((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0)
        
        member_progress.append({
            'user': user,
            'membership': membership,
            'assigned_lists': assigned_lists,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'overall_percent': overall_percent
        })
    
    assignable_lists = []
    for task_list, share, collection, shared_by_user in shared_lists:
        assignable_lists.append(task_list)
    
    return render_template('group.html', 
                         group=group, 
                         members=members,
                         is_leader=is_leader,
                         available_users=available_users,
                         shared_lists=shared_lists,
                         member_progress=member_progress,
                         assignable_lists=assignable_lists)


@app.route('/group/<int:group_id>/add_member', methods=['POST'])
@login_required
def add_group_member(group_id):
    group = Group.query.get_or_404(group_id)
    
    if group.leader_id != current_user.user_id:
        flash('Only the group leader can add members.', 'error')
        return redirect(url_for('view_group', group_id=group_id))
    
    user_id = request.form.get('user_id')
    
    existing = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    if existing:
        flash('User is already a member!', 'error')
        return redirect(url_for('view_group', group_id=group_id))
    
    new_member = GroupMember(
        group_id=group_id,
        user_id=user_id,
        role='member'
    )
    
    db.session.add(new_member)
    db.session.commit()
    
    flash('Member added successfully!', 'success')
    return redirect(url_for('view_group', group_id=group_id))


@app.route('/group/<int:group_id>/remove_member/<int:user_id>', methods=['POST'])
@login_required
def remove_group_member(group_id, user_id):
    group = Group.query.get_or_404(group_id)
    
    if group.leader_id != current_user.user_id:
        flash('Only the group leader can remove members.', 'error')
        return redirect(url_for('view_group', group_id=group_id))
    
    if user_id == group.leader_id:
        flash('Cannot remove the group leader!', 'error')
        return redirect(url_for('view_group', group_id=group_id))
    
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    if member:
        db.session.delete(member)
        db.session.commit()
        flash('Member removed successfully!', 'success')
    
    return redirect(url_for('view_group', group_id=group_id))


@app.route('/group/<int:group_id>/assign_list', methods=['POST'])
@login_required
def assign_task_list(group_id):
    group = Group.query.get_or_404(group_id)
    
    if group.leader_id != current_user.user_id:
        flash('Only the group leader can assign task lists.', 'error')
        return redirect(url_for('view_group', group_id=group_id))
    
    task_list_id = request.form.get('task_list_id')
    membership_id = request.form.get('membership_id')
    
    existing = TaskListAssignment.query.filter_by(
        task_list_id=task_list_id,
        membership_id=membership_id
    ).first()
    
    if existing:
        flash('This task list is already assigned to that member!', 'error')
        return redirect(url_for('view_group', group_id=group_id))
    
    assignment = TaskListAssignment(
        task_list_id=task_list_id,
        membership_id=membership_id,
        assigned_by_user_id=current_user.user_id
    )
    
    db.session.add(assignment)
    db.session.commit()
    
    flash('Task list assigned successfully!', 'success')
    return redirect(url_for('view_group', group_id=group_id))


@app.route('/group/<int:group_id>/unassign_list/<int:assignment_id>', methods=['POST'])
@login_required
def unassign_task_list(group_id, assignment_id):
    group = Group.query.get_or_404(group_id)
    
    if group.leader_id != current_user.user_id:
        flash('Only the group leader can unassign task lists.', 'error')
        return redirect(url_for('view_group', group_id=group_id))
    
    assignment = TaskListAssignment.query.get_or_404(assignment_id)
    db.session.delete(assignment)
    db.session.commit()
    
    flash('Task list unassigned successfully!', 'success')
    return redirect(url_for('view_group', group_id=group_id))


@app.route('/group/delete/<int:group_id>', methods=['POST'])
@login_required
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    
    if group.leader_id != current_user.user_id:
        flash('Only the group leader can delete the group.', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(group)
    db.session.commit()
    
    flash('Group deleted successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    errors = {}

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_user.check_password(current_password):
            errors['current_password'] = 'Current password is incorrect'

        if len(new_password) < 8:
            errors['new_password'] = 'Password must be at least 8 characters'

        if new_password != confirm_password:
            errors['confirm_password'] = 'Passwords do not match'

        if not errors:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password updated successfully!', 'success')
            return redirect(url_for('profile'))

    return render_template('profile.html', errors=errors)

if __name__ == '__main__':
    app.run(debug=True)