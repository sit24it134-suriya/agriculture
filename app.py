from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'farmersmarketsecret')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Configure application logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
app.logger.setLevel(getattr(logging, log_level, logging.INFO))

# Always log to stdout (works on Render, Heroku, etc.)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(getattr(logging, log_level, logging.INFO))
stream_handler.setFormatter(log_formatter)
app.logger.addHandler(stream_handler)

# Also log to file locally if the logs directory is writable
try:
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(os.path.join(log_dir, 'app.log'), maxBytes=1024 * 1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(getattr(logging, log_level, logging.INFO))
    file_handler.setFormatter(log_formatter)
    app.logger.addHandler(file_handler)
except OSError:
    pass  # Skip file logging on read-only filesystems (cloud environments)

app.logger.info('Starting Farmers Market app with log level %s', log_level)

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='customer')
    approved = db.Column(db.Boolean, nullable=False, default=True)
    cart_items = db.relationship('Cart', backref='user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    image_url = db.Column(db.String(300), nullable=False)
    approved = db.Column(db.Boolean, nullable=False, default=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    product = db.relationship('Product')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(80), nullable=False, default='Pending')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.before_request
def log_request_info():
    current_user = get_current_user()
    app.logger.info('Request %s %s from %s user=%s', request.method, request.path, request.remote_addr, current_user.email if current_user else 'anonymous')


def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


def is_farmer(user):
    return user is not None and user.role == 'farmer'


def is_master(user):
    return user is not None and user.role == 'master'

@app.route('/')
def home():
    products = Product.query.filter_by(approved=True).order_by(Product.id.desc()).limit(6).all()
    categories = [category[0] for category in db.session.query(Product.category).filter(Product.approved == True).distinct()]
    return render_template('index.html', products=products, categories=categories, user=get_current_user())

@app.route('/products')
def products_page():
    categories = [category[0] for category in db.session.query(Product.category).filter(Product.approved == True).distinct()]
    return render_template('products.html', categories=categories, user=get_current_user())

@app.route('/product/<int:product_id>')
def product_details(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.approved and not (get_current_user() and (is_master(get_current_user()) or get_current_user().id == product.farmer_id)):
        return redirect(url_for('products_page'))
    return render_template('product_details.html', product=product, user=get_current_user())

@app.route('/cart')
def cart_page():
    user = get_current_user()
    if not user:
        flash('Please login to view your cart.', 'warning')
        return redirect(url_for('login'))
    return render_template('cart.html', user=user)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    user = get_current_user()
    if not user:
        flash('Please login to checkout.', 'warning')
        return redirect(url_for('login'))

    cart_items = Cart.query.filter_by(user_id=user.id).all()
    if not cart_items:
        flash('Your cart is empty. Add items before checkout.', 'warning')
        return redirect(url_for('cart_page'))

    if request.method == 'POST':
        shipping_address = request.form.get('shipping_address', '').strip()
        payment_method = request.form.get('payment_method', 'Credit Card')

        if not shipping_address:
            flash('Enter a shipping address to place your order.', 'danger')
            return redirect(url_for('checkout'))

        total = 0.0
        for item in cart_items:
            total += item.quantity * item.product.price

        order = Order(user_id=user.id, total=total, status='Processing')
        db.session.add(order)
        db.session.flush()

        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.product.price,
            )
            db.session.add(order_item)

        Cart.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        app.logger.info('Order placed: order_id=%s user=%s total=%.2f items=%s', order.id, user.email, total, len(cart_items))

        flash('Order placed successfully! Thank you for your purchase.', 'success')
        return redirect(url_for('order_confirmation', order_id=order.id))

    items = []
    total = 0.0
    for item in cart_items:
        subtotal = item.quantity * item.product.price
        total += subtotal
        items.append({
            'name': item.product.name,
            'price': item.product.price,
            'quantity': item.quantity,
            'subtotal': subtotal,
        })

    return render_template('checkout.html', user=user, items=items, total=total)

@app.route('/order-confirmation/<int:order_id>')
def order_confirmation(order_id):
    user = get_current_user()
    if not user:
        flash('Please login to view your order.', 'warning')
        return redirect(url_for('login'))
    order = Order.query.get_or_404(order_id)
    if order.user_id != user.id and not is_master(user):
        flash('You do not have permission to view that order.', 'danger')
        return redirect(url_for('home'))
    return render_template('order_confirmation.html', user=user, order=order)

@app.route('/orders')
def orders_page():
    user = get_current_user()
    if not user:
        flash('Please login to view orders.', 'warning')
        return redirect(url_for('login'))

    if is_master(user):
        orders = Order.query.order_by(Order.created_at.desc()).all()
    else:
        orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', user=user, orders=orders)

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    user = get_current_user()
    if not is_master(user):
        flash('Admin access only.', 'danger')
        return redirect(url_for('home'))

    pending_farmers = User.query.filter_by(role='farmer', approved=False).all()
    pending_products = Product.query.filter_by(approved=False).all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_dashboard.html', user=user, pending_farmers=pending_farmers, pending_products=pending_products, orders=orders)

@app.route('/admin/approve-farmer', methods=['POST'])
def approve_farmer():
    user = get_current_user()
    if not is_master(user):
        return redirect(url_for('home'))
    farmer_id = request.form.get('farmer_id')
    farmer = User.query.get(farmer_id)
    if farmer and farmer.role == 'farmer':
        farmer.approved = True
        db.session.commit()
        app.logger.info('Farmer approved: user_id=%s email=%s by admin=%s', farmer.id, farmer.email, user.email)
        flash('Farmer approved successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve-product', methods=['POST'])
def approve_product():
    user = get_current_user()
    if not is_master(user):
        return redirect(url_for('home'))
    product_id = request.form.get('product_id')
    product = Product.query.get(product_id)
    if product:
        product.approved = True
        db.session.commit()
        app.logger.info('Product approved: product_id=%s name=%s by admin=%s', product.id, product.name, user.email)
        flash('Product approved successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-order-status', methods=['POST'])
def update_order_status():
    user = get_current_user()
    if not is_master(user):
        return redirect(url_for('home'))
    order_id = request.form.get('order_id')
    status = request.form.get('status')
    order = Order.query.get(order_id)
    if order:
        order.status = status
        db.session.commit()
        app.logger.info('Order status updated: order_id=%s status=%s by admin=%s', order.id, status, user.email)
        flash('Order status updated.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/add-product', methods=['GET', 'POST'])
def add_product():
    user = get_current_user()
    if not is_farmer(user):
        flash('Only farmers may add new products.', 'warning')
        return redirect(url_for('login'))

    if not user.approved:
        flash('Your farmer account is pending approval. You cannot add products yet.', 'warning')
        return redirect(url_for('products_page'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '').strip()
        category = request.form.get('category', '').strip()
        image_url = request.form.get('image_url', '').strip()

        if not name or not description or not price or not category or not image_url:
            app.logger.warning('Add product submission missing fields by user=%s', user.email)
            flash('Please complete all product fields.', 'danger')
            return redirect(url_for('add_product'))

        try:
            price_value = float(price)
        except ValueError:
            app.logger.warning('Add product submission invalid price by user=%s price=%s', user.email, price)
            flash('Please enter a valid numeric price.', 'danger')
            return redirect(url_for('add_product'))

        product = Product(
            name=name,
            description=description,
            price=price_value,
            category=category,
            image_url=image_url,
            farmer_id=user.id,
            approved=False,
        )
        db.session.add(product)
        db.session.commit()
        app.logger.info('Product submitted for approval: product=%s farmer=%s', product.name, user.email)
        flash('Product submitted for approval. Master will review and approve it shortly.', 'success')
        return redirect(url_for('products_page'))

    return render_template('add_product.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            app.logger.warning('Failed login attempt for email=%s from %s', email, request.remote_addr)
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['user_role'] = user.role
        app.logger.info('User logged in: %s role=%s', email, user.role)
        flash(f'Welcome back, {user.name}!', 'success')
        return redirect(url_for('home'))
    return render_template('login.html', user=get_current_user())

@app.route('/signup', methods=['POST'])
def signup():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    role = request.form.get('role', 'customer')

    if not name or not email or not password:
        app.logger.warning('Signup attempt with incomplete fields from %s', request.remote_addr)
        flash('Please complete all fields.', 'danger')
        return redirect(url_for('login'))
    if User.query.filter_by(email=email).first():
        app.logger.warning('Signup attempt with existing email: %s', email)
        flash('Email already exists. Please log in.', 'warning')
        return redirect(url_for('login'))

    hashed_password = generate_password_hash(password)
    approved = True
    if role == 'farmer':
        approved = False

    user = User(name=name, email=email, password=hashed_password, role=role, approved=approved)
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    session['user_name'] = user.name
    session['user_role'] = user.role
    app.logger.info('New user registered: %s role=%s', email, role)
    if role == 'farmer':
        flash('Farmer registration submitted. Awaiting master approval.', 'info')
    else:
        flash('Account created successfully. Welcome to the marketplace!', 'success')
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    current_user = get_current_user()
    if current_user:
        app.logger.info('User logged out: %s', current_user.email)
    else:
        app.logger.info('Logout called without active session')
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    user = get_current_user()
    if not user:
        app.logger.warning('Unauthorized add-to-cart attempt from %s', request.remote_addr)
        return jsonify({'success': False, 'message': 'Please login to add items to cart.'}), 401

    product_id = request.json.get('product_id') if request.is_json else request.form.get('product_id')
    quantity = int(request.json.get('quantity', 1) if request.is_json else request.form.get('quantity', 1))
    product = Product.query.get(product_id)
    if not product:
        app.logger.warning('Invalid add-to-cart product_id=%s by user=%s', product_id, user.email)
        return jsonify({'success': False, 'message': 'Product not found.'}), 404

    cart_item = Cart.query.filter_by(user_id=user.id, product_id=product.id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = Cart(user_id=user.id, product_id=product.id, quantity=quantity)
        db.session.add(cart_item)
    db.session.commit()
    app.logger.info('Added to cart: user=%s product=%s quantity=%s', user.email, product.name, quantity)
    return jsonify({'success': True, 'message': f'Added {product.name} to cart.'})

@app.route('/api/products')
def api_products():
    user = get_current_user()
    if is_master(user):
        products = Product.query.all()
    else:
        products = Product.query.filter_by(approved=True).all()
    result = []
    for product in products:
        result.append({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': product.price,
            'category': product.category,
            'image_url': product.image_url,
            'farmer_id': product.farmer_id,
            'approved': product.approved,
        })
    return jsonify(result)

@app.route('/api/cart')
def api_cart():
    user = get_current_user()
    if not user:
        return jsonify({'items': [], 'total': 0.0})
    items = []
    total = 0.0
    cart_items = Cart.query.filter_by(user_id=user.id).all()
    for item in cart_items:
        product = item.product
        subtotal = item.quantity * product.price
        total += subtotal
        items.append({
            'cart_id': item.id,
            'product_id': product.id,
            'name': product.name,
            'price': product.price,
            'image_url': product.image_url,
            'quantity': item.quantity,
            'subtotal': subtotal,
        })
    return jsonify({'items': items, 'total': total})

@app.route('/api/remove-cart-item', methods=['POST'])
def remove_cart_item():
    user = get_current_user()
    if not user:
        return jsonify({'success': False}), 401
    cart_id = request.json.get('cart_id')
    cart_item = Cart.query.filter_by(id=cart_id, user_id=user.id).first()
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/update-cart-quantity', methods=['POST'])
def update_cart_quantity():
    user = get_current_user()
    if not user:
        return jsonify({'success': False}), 401
    cart_id = request.json.get('cart_id')
    quantity = int(request.json.get('quantity', 1))
    cart_item = Cart.query.filter_by(id=cart_id, user_id=user.id).first()
    if cart_item:
        if quantity <= 0:
            db.session.delete(cart_item)
        else:
            cart_item.quantity = quantity
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

@app.route('/api/featured-products')
def api_featured_products():
    products = Product.query.order_by(Product.id.desc()).limit(6).all()
    result = []
    for product in products:
        result.append({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': product.price,
            'category': product.category,
            'image_url': product.image_url,
        })
    return jsonify(result)

@app.cli.command('initdb')
def initdb_command():
    init_db()
    print('Initialized the database.')

def init_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
        if not User.query.filter_by(email='farmer1@example.com').first():
            master = User(name='Master Admin', email='admin@example.com', password=generate_password_hash('admin123'), role='master', approved=True)
            farmer = User(name='Maya Farm', email='farmer1@example.com', password=generate_password_hash('farm123'), role='farmer', approved=True)
            customer = User(name='Asha Customer', email='customer@example.com', password=generate_password_hash('shop123'), role='customer', approved=True)
            db.session.add(master)
            db.session.add(farmer)
            db.session.add(customer)
            db.session.commit()
            sample_products = [
                Product(name='Organic Tomatoes', description='Freshly harvested red tomatoes grown with minimal pesticides.', price=3.49, category='Vegetables', image_url='https://images.unsplash.com/photo-1567306226416-28f0efdc88ce?auto=format&fit=crop&w=800&q=80', farmer_id=farmer.id),
                Product(name='Mango Honey', description='Naturally sweet honey from our orchard-friendly bees.', price=10.99, category='Honey', image_url='https://img.freepik.com/free-psd/delicious-mango-studio_23-2151843107.jpg?semt=ais_incoming&w=740&q=80', farmer_id=farmer.id),
                Product(name='Millet Flour', description='Stone-ground millet flour perfect for healthy baking.', price=6.25, category='Grains', image_url='https://images.unsplash.com/photo-1528825871115-3581a5387919?auto=format&fit=crop&w=800&q=80', farmer_id=farmer.id),
                Product(name='Leafy Spinach', description='Tender spinach leaves packed with vitamins and flavor.', price=2.79, category='Vegetables', image_url='https://images.unsplash.com/photo-1518972559570-5c2a5993e241?auto=format&fit=crop&w=800&q=80', farmer_id=farmer.id),
                Product(name='Fresh Corn', description='Sweet corn harvested today, great for grilling or salads.', price=4.50, category='Vegetables', image_url='https://images.unsplash.com/photo-1506806732259-39c2d0268443?auto=format&fit=crop&w=800&q=80', farmer_id=farmer.id),
                Product(name='Herbal Tea Mix', description='A calming blend of mint and chamomile from our farm.', price=8.10, category='Beverages', image_url='https://images.unsplash.com/photo-1501022546376-5f2d8a7c0883?auto=format&fit=crop&w=800&q=80', farmer_id=farmer.id),
            ]
            for product in sample_products:
                db.session.add(product)
            db.session.commit()

if __name__ == '__main__':
    if not os.path.exists('database.db'):
        init_db()
    app.run(debug=True)