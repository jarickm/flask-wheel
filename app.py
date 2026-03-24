from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import random
import datetime

app = Flask(__name__)
app.secret_key = 'cci_workspace_ultra_secret'

# DATABASE CONNECTION
app.config[
    'SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://postgres.tqjvwfikswvppeyopvdg:3srdUc8IFDiUkbJu@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres'
db = SQLAlchemy(app)

# --- AUTH ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class WheelAdmin(UserMixin, db.Model):
    __tablename__ = 'wheel_admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))


@login_manager.user_loader
def load_user(user_id):
    return WheelAdmin.query.get(int(user_id))


# --- MODELS ---
class WheelGuest(db.Model):
    __tablename__ = 'wheel_guests'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    company = db.Column(db.String(100)) # NEW
    phone = db.Column(db.String(20))    # NEW
    details = db.Column(db.String(200)) # Department/Position
    is_active = db.Column(db.Boolean, default=True)



class WheelPrize(db.Model):
    __tablename__ = 'wheel_prizes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    icon = db.Column(db.String(10))
    weight = db.Column(db.Integer, default=25)


class WheelHistory(db.Model):
    __tablename__ = 'wheel_history'
    id = db.Column(db.Integer, primary_key=True)
    guest_name = db.Column(db.String(100))
    prize_name = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now)


# --- ROUTES ---

@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = WheelAdmin.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid Access Credentials')
    return render_template('login.html')


@app.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    msg = None
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        if WheelAdmin.query.filter_by(username=username).first():
            msg = "User already exists"
        else:
            db.session.add(WheelAdmin(username=username, password=password))
            db.session.commit()
            flash("Admin Account Activated")
            return redirect(url_for('login'))
    return render_template('register_admin.html', message=msg)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- API DATA ---
@app.route('/get_state')
@login_required
def get_state():
    # We now fetch full objects to show more info in the dashboard
    guests = WheelGuest.query.filter_by(is_active=True).all()
    prizes = WheelPrize.query.all()
    hist = WheelHistory.query.order_by(WheelHistory.id.desc()).all()

    return jsonify({
        "participants_full": [
            {"name": g.name, "company": g.company, "phone": g.phone, "dept": g.details}
            for g in guests
        ],
        "participants": [g.name for g in guests],  # Kept for the wheel logic
        "prizes": [{"id": p.id, "name": p.name, "icon": p.icon, "weight": p.weight} for p in prizes],
        "history": [{"name": h.guest_name, "prize": h.prize_name, "time": h.timestamp.strftime("%I:%M %p")} for h in
                    hist],
        "stats": {"total_guests": len(guests), "total_prizes": len(prizes), "total_winners": len(hist)}
    })


@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        company = request.form.get('company', '').strip()
        phone = request.form.get('phone', '').strip()
        details = request.form.get('details', '').strip()

        if WheelGuest.query.filter_by(name=name).first():
            msg = "This name is already registered!"
        elif name:
            new_guest = WheelGuest(name=name, company=company, phone=phone, details=details)
            db.session.add(new_guest)
            db.session.commit()
            return render_template('register_success.html', name=name)
    return render_template('register.html', message=msg)

@app.route('/add_prize', methods=['POST'])
@login_required
def add_prize():
    data = request.json
    db.session.add(WheelPrize(name=data['name'], icon=data.get('icon', '🎁')))
    db.session.commit()
    return jsonify({"success": True})


@app.route('/clear_data', methods=['POST'])
@login_required
def clear_data():
    target = request.json.get('target')
    if target == 'participants':
        WheelGuest.query.delete()
    elif target == 'prizes':
        WheelPrize.query.delete()
    elif target == 'history':
        WheelHistory.query.delete()
    db.session.commit()
    return jsonify({"success": True})


@app.route('/spin', methods=['POST'])
@login_required
def spin():
    active_g = WheelGuest.query.filter_by(is_active=True).all()
    prizes = WheelPrize.query.all()
    if not active_g or not prizes: return jsonify({"error": "No Data"}), 400

    win_p = random.choices(prizes, weights=[p.weight for p in prizes], k=1)[0]
    win_g = random.choice(active_g)

    db.session.add(WheelHistory(guest_name=win_g.name, prize_name=win_p.name))
    win_g.is_active = False
    db.session.commit()

    idx = next(i for i, p in enumerate(prizes) if p.id == win_p.id)
    return jsonify({"winner": win_g.name, "prize": {"name": win_p.name, "icon": win_p.icon}, "prizeIndex": idx})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)