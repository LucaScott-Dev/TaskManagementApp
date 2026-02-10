from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Collection

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///taskmanager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables
with app.app_context():
    db.create_all()

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
        
        # Validation
        if User.query.filter_by(username=username).first():
            errors['username'] = 'Username already exists'
        
        if password != confirm_password:
            errors['confirm-password'] = 'Passwords do not match'
        
        # If no errors, create user
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
    # Get all collections for the current user
    collections = Collection.query.filter_by(user_id=current_user.user_id).order_by(Collection.created_at.desc()).all()
    return render_template('dashboard.html', username=current_user.username, collections=collections)

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
    
    # Make sure the user owns this collection
    if collection.user_id != current_user.user_id:
        flash('You do not have permission to delete this collection.', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(collection)
    db.session.commit()
    
    flash('Collection deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)