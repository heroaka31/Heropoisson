"""
FishMarket Platform - app.py
Flask web application for a multi-seller fish marketplace.
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///fishmarket.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────

class User(db.Model):
    """Base user table; role: 'admin' | 'seller' | 'customer'"""
    __tablename__ = "users"

    id           = db.Column(db.Integer, primary_key=True)
    email        = db.Column(db.String(120), unique=True, nullable=False)
    password_hash= db.Column(db.String(256), nullable=False)
    role         = db.Column(db.String(20), nullable=False, default="customer")  # admin / seller / customer
    full_name    = db.Column(db.String(120), nullable=False)
    phone        = db.Column(db.String(30))           # PII – admin-only
    address      = db.Column(db.String(255))          # PII – admin-only
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    is_active    = db.Column(db.Boolean, default=True)

    shop   = db.relationship("Shop",  back_populates="seller", uselist=False)
    orders = db.relationship("Order", back_populates="customer")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Shop(db.Model):
    """A fish shop owned by one seller."""
    __tablename__ = "shops"

    id          = db.Column(db.Integer, primary_key=True)
    seller_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    name        = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    location    = db.Column(db.String(255), nullable=False)
    city        = db.Column(db.String(80))
    logo_url    = db.Column(db.String(255))
    is_open     = db.Column(db.Boolean, default=True)   # shop open/closed toggle
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    seller  = db.relationship("User",  back_populates="shop")
    fishes  = db.relationship("Fish",  back_populates="shop", cascade="all, delete-orphan")
    orders  = db.relationship("Order", back_populates="shop")


class Fish(db.Model):
    """A fish listing inside a shop."""
    __tablename__ = "fishes"

    id           = db.Column(db.Integer, primary_key=True)
    shop_id      = db.Column(db.Integer, db.ForeignKey("shops.id"), nullable=False)
    name         = db.Column(db.String(120), nullable=False)
    species      = db.Column(db.String(120))
    description  = db.Column(db.Text)
    price_per_kg = db.Column(db.Float, nullable=False)
    stock_kg     = db.Column(db.Float, default=0.0)     # 0 = out of stock
    is_orderable = db.Column(db.Boolean, default=True)  # seller decides if ordering is open
    image_url    = db.Column(db.String(255))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    shop        = db.relationship("Shop",      back_populates="fishes")
    order_items = db.relationship("OrderItem", back_populates="fish")

    @property
    def available(self):
        return self.is_orderable and self.stock_kg > 0 and self.shop.is_open


class Order(db.Model):
    """An order placed by a customer at a specific shop."""
    __tablename__ = "orders"

    id          = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    shop_id     = db.Column(db.Integer, db.ForeignKey("shops.id"),  nullable=False)
    status      = db.Column(db.String(30), default="pending")  # pending / confirmed / ready / delivered / cancelled
    note        = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("User",      back_populates="orders")
    shop     = db.relationship("Shop",      back_populates="orders")
    items    = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    @property
    def total(self):
        return sum(i.quantity_kg * i.unit_price for i in self.items)


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey("orders.id"),  nullable=False)
    fish_id    = db.Column(db.Integer, db.ForeignKey("fishes.id"),   nullable=False)
    quantity_kg= db.Column(db.Float,   nullable=False)
    unit_price = db.Column(db.Float,   nullable=False)   # snapshot at order time

    order = db.relationship("Order", back_populates="items")
    fish  = db.relationship("Fish",  back_populates="order_items")


# ─────────────────────────────────────────────
# DECORATORS
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in.", "warning")
                return redirect(url_for("login"))
            user = db.session.get(User, session["user_id"])
            if not user or user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def current_user():
    if "user_id" in session:
        return db.session.get(User, session["user_id"])
    return None


# ─────────────────────────────────────────────
# PUBLIC ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    shops = Shop.query.filter_by(is_open=True).all()
    fishes = Fish.query.join(Shop).filter(Shop.is_open == True).order_by(Fish.created_at.desc()).limit(12).all()
    return render_template("index.html", shops=shops, fishes=fishes, user=current_user())


@app.route("/shops")
def shops():
    city = request.args.get("city", "").strip()
    q    = request.args.get("q", "").strip()
    query = Shop.query
    if city:
        query = query.filter(Shop.city.ilike(f"%{city}%"))
    if q:
        query = query.filter(Shop.name.ilike(f"%{q}%"))
    shops = query.order_by(Shop.name).all()
    cities = [r[0] for r in db.session.query(Shop.city).distinct().filter(Shop.city != None).all()]
    return render_template("shops.html", shops=shops, cities=cities, user=current_user())


@app.route("/shop/<int:shop_id>")
def shop_detail(shop_id):
    shop   = Shop.query.get_or_404(shop_id)
    fishes = Fish.query.filter_by(shop_id=shop_id).order_by(Fish.name).all()
    return render_template("shop_detail.html", shop=shop, fishes=fishes, user=current_user())


@app.route("/fish/<int:fish_id>")
def fish_detail(fish_id):
    fish = Fish.query.get_or_404(fish_id)
    return render_template("fish_detail.html", fish=fish, user=current_user())


# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role      = request.form.get("role", "customer")
        if role not in ("seller", "customer"):
            role = "customer"
        email     = request.form["email"].strip().lower()
        full_name = request.form["full_name"].strip()
        phone     = request.form.get("phone", "").strip()
        address   = request.form.get("address", "").strip()
        password  = request.form["password"]

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        user = User(email=email, full_name=full_name, phone=phone, address=address, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        session["role"]    = user.role
        flash("Welcome to FishMarket!", "success")
        if role == "seller":
            return redirect(url_for("seller_dashboard"))
        return redirect(url_for("index"))

    return render_template("register.html", user=None)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"].strip().lower()
        password = request.form["password"]
        user     = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))
        if not user.is_active:
            flash("Account suspended. Contact support.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        session["role"]    = user.role
        flash(f"Welcome back, {user.full_name}!", "success")

        if user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        if user.role == "seller":
            return redirect(url_for("seller_dashboard"))
        return redirect(url_for("index"))

    return render_template("login.html", user=None)


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))


# ─────────────────────────────────────────────
# SELLER ROUTES
# ─────────────────────────────────────────────

@app.route("/seller/dashboard")
@role_required("seller")
def seller_dashboard():
    user = current_user()
    shop = user.shop
    return render_template("seller/dashboard.html", user=user, shop=shop)


@app.route("/seller/shop/create", methods=["GET", "POST"])
@role_required("seller")
def seller_create_shop():
    user = current_user()
    if user.shop:
        return redirect(url_for("seller_dashboard"))
    if request.method == "POST":
        shop = Shop(
            seller_id  = user.id,
            name       = request.form["name"].strip(),
            description= request.form.get("description", "").strip(),
            location   = request.form["location"].strip(),
            city       = request.form.get("city", "").strip(),
            logo_url   = request.form.get("logo_url", "").strip() or None,
        )
        db.session.add(shop)
        db.session.commit()
        flash("Shop created!", "success")
        return redirect(url_for("seller_dashboard"))
    return render_template("seller/shop_form.html", user=user, shop=None)


@app.route("/seller/shop/edit", methods=["GET", "POST"])
@role_required("seller")
def seller_edit_shop():
    user = current_user()
    shop = user.shop
    if not shop:
        return redirect(url_for("seller_create_shop"))
    if request.method == "POST":
        shop.name        = request.form["name"].strip()
        shop.description = request.form.get("description", "").strip()
        shop.location    = request.form["location"].strip()
        shop.city        = request.form.get("city", "").strip()
        shop.logo_url    = request.form.get("logo_url", "").strip() or None
        shop.is_open     = "is_open" in request.form
        db.session.commit()
        flash("Shop updated.", "success")
        return redirect(url_for("seller_dashboard"))
    return render_template("seller/shop_form.html", user=user, shop=shop)


@app.route("/seller/fish/add", methods=["GET", "POST"])
@role_required("seller")
def seller_add_fish():
    user = current_user()
    if not user.shop:
        flash("Create your shop first.", "warning")
        return redirect(url_for("seller_create_shop"))
    if request.method == "POST":
        fish = Fish(
            shop_id      = user.shop.id,
            name         = request.form["name"].strip(),
            species      = request.form.get("species", "").strip(),
            description  = request.form.get("description", "").strip(),
            price_per_kg = float(request.form["price_per_kg"]),
            stock_kg     = float(request.form.get("stock_kg", 0)),
            is_orderable = "is_orderable" in request.form,
            image_url    = request.form.get("image_url", "").strip() or None,
        )
        db.session.add(fish)
        db.session.commit()
        flash(f"{fish.name} added!", "success")
        return redirect(url_for("seller_dashboard"))
    return render_template("seller/fish_form.html", user=user, fish=None)


@app.route("/seller/fish/<int:fish_id>/edit", methods=["GET", "POST"])
@role_required("seller")
def seller_edit_fish(fish_id):
    user = current_user()
    fish = Fish.query.get_or_404(fish_id)
    if fish.shop.seller_id != user.id:
        abort(403)
    if request.method == "POST":
        fish.name         = request.form["name"].strip()
        fish.species      = request.form.get("species", "").strip()
        fish.description  = request.form.get("description", "").strip()
        fish.price_per_kg = float(request.form["price_per_kg"])
        fish.stock_kg     = float(request.form.get("stock_kg", 0))
        fish.is_orderable = "is_orderable" in request.form
        fish.image_url    = request.form.get("image_url", "").strip() or None
        db.session.commit()
        flash("Fish listing updated.", "success")
        return redirect(url_for("seller_dashboard"))
    return render_template("seller/fish_form.html", user=user, fish=fish)


@app.route("/seller/fish/<int:fish_id>/delete", methods=["POST"])
@role_required("seller")
def seller_delete_fish(fish_id):
    user = current_user()
    fish = Fish.query.get_or_404(fish_id)
    if fish.shop.seller_id != user.id:
        abort(403)
    db.session.delete(fish)
    db.session.commit()
    flash("Listing removed.", "info")
    return redirect(url_for("seller_dashboard"))


@app.route("/seller/orders")
@role_required("seller")
def seller_orders():
    user   = current_user()
    shop   = user.shop
    if not shop:
        return redirect(url_for("seller_create_shop"))
    orders = Order.query.filter_by(shop_id=shop.id).order_by(Order.created_at.desc()).all()
    return render_template("seller/orders.html", user=user, shop=shop, orders=orders)


@app.route("/seller/orders/<int:order_id>/status", methods=["POST"])
@role_required("seller")
def seller_update_order(order_id):
    user  = current_user()
    order = Order.query.get_or_404(order_id)
    if order.shop.seller_id != user.id:
        abort(403)
    new_status = request.form.get("status")
    allowed = {"pending", "confirmed", "ready", "delivered", "cancelled"}
    if new_status in allowed:
        order.status = new_status
        db.session.commit()
        flash(f"Order #{order.id} marked as {new_status}.", "success")
    return redirect(url_for("seller_orders"))


# ─────────────────────────────────────────────
# CUSTOMER ROUTES
# ─────────────────────────────────────────────

@app.route("/order/<int:fish_id>", methods=["GET", "POST"])
@role_required("customer")
def place_order(fish_id):
    fish = Fish.query.get_or_404(fish_id)
    user = current_user()

    if not fish.available:
        flash("This fish is not available for ordering right now.", "warning")
        return redirect(url_for("shop_detail", shop_id=fish.shop_id))

    if request.method == "POST":
        qty = float(request.form.get("quantity_kg", 0))
        if qty <= 0:
            flash("Please enter a valid quantity.", "danger")
            return redirect(url_for("place_order", fish_id=fish_id))
        if qty > fish.stock_kg:
            flash(f"Only {fish.stock_kg} kg in stock.", "warning")
            return redirect(url_for("place_order", fish_id=fish_id))

        # Reuse open pending order for same shop, or create new
        order = Order.query.filter_by(customer_id=user.id, shop_id=fish.shop_id, status="pending").first()
        if not order:
            order = Order(customer_id=user.id, shop_id=fish.shop_id, note=request.form.get("note", ""))
            db.session.add(order)
            db.session.flush()

        item = OrderItem(order_id=order.id, fish_id=fish.id, quantity_kg=qty, unit_price=fish.price_per_kg)
        fish.stock_kg -= qty
        db.session.add(item)
        db.session.commit()
        flash("Order placed successfully!", "success")
        return redirect(url_for("my_orders"))

    return render_template("customer/order_form.html", fish=fish, user=user)


@app.route("/my-orders")
@role_required("customer")
def my_orders():
    user   = current_user()
    orders = Order.query.filter_by(customer_id=user.id).order_by(Order.created_at.desc()).all()
    return render_template("customer/my_orders.html", user=user, orders=orders)


@app.route("/my-orders/<int:order_id>/cancel", methods=["POST"])
@role_required("customer")
def cancel_order(order_id):
    user  = current_user()
    order = Order.query.get_or_404(order_id)
    if order.customer_id != user.id:
        abort(403)
    if order.status not in ("pending",):
        flash("Only pending orders can be cancelled.", "warning")
        return redirect(url_for("my_orders"))
    # Restore stock
    for item in order.items:
        item.fish.stock_kg += item.quantity_kg
    order.status = "cancelled"
    db.session.commit()
    flash("Order cancelled and stock restored.", "info")
    return redirect(url_for("my_orders"))


# ─────────────────────────────────────────────
# ADMIN ROUTES (PII access)
# ─────────────────────────────────────────────

@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    user_count  = User.query.count()
    shop_count  = Shop.query.count()
    order_count = Order.query.count()
    return render_template("admin/dashboard.html", user=current_user(),
                           user_count=user_count, shop_count=shop_count, order_count=order_count)


@app.route("/admin/users")
@role_required("admin")
def admin_users():
    role   = request.args.get("role", "")
    q      = request.args.get("q", "").strip()
    query  = User.query
    if role:
        query = query.filter_by(role=role)
    if q:
        query = query.filter(
            (User.full_name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )
    users = query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", user=current_user(), users=users, role=role, q=q)


@app.route("/admin/users/<int:uid>/toggle", methods=["POST"])
@role_required("admin")
def admin_toggle_user(uid):
    u = User.query.get_or_404(uid)
    if u.role == "admin":
        flash("Cannot deactivate another admin.", "danger")
    else:
        u.is_active = not u.is_active
        db.session.commit()
        flash(f"User {'activated' if u.is_active else 'deactivated'}.", "info")
    return redirect(url_for("admin_users"))


@app.route("/admin/shops")
@role_required("admin")
def admin_shops():
    shops = Shop.query.order_by(Shop.created_at.desc()).all()
    return render_template("admin/shops.html", user=current_user(), shops=shops)


@app.route("/admin/orders")
@role_required("admin")
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", user=current_user(), orders=orders)


# ─────────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────────

@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html", user=current_user()), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html", user=current_user()), 404


# ─────────────────────────────────────────────
# INIT DB + SEED
# ─────────────────────────────────────────────

def seed_data():
    """Create a default admin and sample data if DB is empty."""
    if User.query.first():
        return

    admin = User(email="admin@fishmarket.com", full_name="Platform Admin",
                 phone="+237600000000", address="HQ, Yaoundé", role="admin")
    admin.set_password("admin1234")
    db.session.add(admin)

    seller = User(email="seller@example.com", full_name="Jean Poisson",
                  phone="+237612345678", address="Marché Central, Douala", role="seller")
    seller.set_password("seller1234")
    db.session.add(seller)

    customer = User(email="customer@example.com", full_name="Marie Ngo",
                    phone="+237698765432", address="Bastos, Yaoundé", role="customer")
    customer.set_password("customer1234")
    db.session.add(customer)
    db.session.flush()

    shop = Shop(seller_id=seller.id, name="Poissonnerie Centrale", city="Douala",
                location="Marché Central, Akwa, Douala",
                description="Fresh Atlantic and river fish every morning.",
                is_open=True)
    db.session.add(shop)
    db.session.flush()

    fishes = [
        Fish(shop_id=shop.id, name="Tilapia", species="Oreochromis niloticus",
             description="Farm-raised, very fresh.", price_per_kg=2500, stock_kg=50,
             is_orderable=True),
        Fish(shop_id=shop.id, name="Capitaine (Nile Perch)", species="Lates niloticus",
             description="Wild-caught from the river.", price_per_kg=4000, stock_kg=20,
             is_orderable=True),
        Fish(shop_id=shop.id, name="Mackerel (Congélé)", species="Scomber scombrus",
             description="Frozen Atlantic mackerel.", price_per_kg=1800, stock_kg=0,
             is_orderable=False),
    ]
    db.session.add_all(fishes)
    db.session.commit()
    print("✅  Seed data created.")
    print("   Admin:    admin@fishmarket.com / admin1234")
    print("   Seller:   seller@example.com   / seller1234")
    print("   Customer: customer@example.com / customer1234")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True)
