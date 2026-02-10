from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Collection, TaskList

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-change-this'  # TODO: change this to something more secure
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///taskmanager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set up database
db.init_app(app)

# Set up login manager for user authentication
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # redirect here if not logged in

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables if they don't exist
with app.app_context():
    db.create_all()


# ========== ROUTES ==========

@app.route('/')
def home():
    # Redirect to dashboard if logged in, otherwise go to login
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, just go to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    errors = {}
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Try to find the user
        user = User.query.filter_by(username=username).first()
        
        if not user:
            errors['username'] = 'Username not found'
        elif not user.check_password(password):
            errors['password'] = 'Incorrect password'
        else:
            # Login successful
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
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            errors['username'] = 'Username already exists'
        
        # Make sure passwords match
        if password != confirm_password:
            errors['confirm-password'] = 'Passwords do not match'
        
        # Create the user if no errors
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
    # Get all collections for current user, newest first
    collections = Collection.query.filter_by(user_id=current_user.user_id).order_by(Collection.created_at.desc()).all()
    return render_template('dashboard.html', username=current_user.username, collections=collections)


# ========== COLLECTION ROUTES ==========

@app.route('/collection/create', methods=['POST'])
@login_required
def create_collection():
    collection_name = request.form.get('collection_name')
    description = request.form.get('description')
    
    if not collection_name:
        flash('Collection name is required!', 'error')
        return redirect(url_for('dashboard'))
    
    # Create new collection
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
    
    # Security check - make sure user owns this
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
    
    # Make sure user owns this collection
    if collection.user_id != current_user.user_id:
        flash('You do not have permission to view this collection.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get all task lists for this collection
    task_lists = TaskList.query.filter_by(collection_id=collection_id).order_by(TaskList.created_at.desc()).all()
    
    return render_template('collection.html', collection=collection, task_lists=task_lists)


# ========== TASK LIST ROUTES ==========

@app.route('/collection/<int:collection_id>/create_list', methods=['POST'])
@login_required
def create_task_list(collection_id):
    collection = Collection.query.get_or_404(collection_id)
    
    # Check user owns the collection
    if collection.user_id != current_user.user_id:
        flash('You do not have permission to modify this collection.', 'error')
        return redirect(url_for('dashboard'))
    
    list_name = request.form.get('list_name')
    description = request.form.get('description')
    
    if not list_name:
        flash('Task list name is required!', 'error')
        return redirect(url_for('view_collection', collection_id=collection_id))
    
    # Create the task list
    new_task_list = TaskList(
        collection_id=collection_id,
        list_name=list_name,
        description=description
    )
    
    db.session.add(new_task_list)
    db.session.commit()
    
    flash('Task list created successfully!', 'success')
    return redirect(url_for('view_collection', collection_id=collection_id))


@app.route('/tasklist/delete/<int:task_list_id>', methods=['POST'])
@login_required
def delete_task_list(task_list_id):
    task_list = TaskList.query.get_or_404(task_list_id)
    collection = Collection.query.get(task_list.collection_id)
    
    # Security check
    if collection.user_id != current_user.user_id:
        flash('You do not have permission to delete this task list.', 'error')
        return redirect(url_for('dashboard'))
    
    collection_id = task_list.collection_id
    db.session.delete(task_list)
    db.session.commit()
    
    flash('Task list deleted successfully!', 'success')
    return redirect(url_for('view_collection', collection_id=collection_id))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)