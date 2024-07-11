from flask import Flask, render_template, redirect, url_for, request, jsonify, flash, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import cv2
import av
from datetime import datetime
import random

from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'joel_app'  # Ganti dengan kunci rahasia Anda
url = "rtsp://admin:qwerty123@192.168.0.230:554/user=admin&password=qwerty123&channel=1&stream=0.sdp?"

# Konfigurasi database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:@192.168.5.1/joelapp'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(256), unique=True, nullable=False)
    username = db.Column(db.String(256), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def __init__(self, nama, username, password):
        self.nama = nama
        self.username = username
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now, nullable=False)
    status = db.Column(db.String(150), nullable=False)

    def __init__(self, status):
        self.status = status

class SchedulerData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)

class SensorState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pm25_state = db.Column(db.Boolean, nullable=False)
    rcwl_state = db.Column(db.Boolean, nullable=False)
    lock_state = db.Column(db.Boolean, nullable=False)

    def __init__(self, pm25_state=False, rcwl_state=False, lock_state=False):
        self.pm25_state = pm25_state
        self.rcwl_state = rcwl_state
        self.lock_state = lock_state

# Buat semua tabel
with app.app_context():
    db.create_all()



# Login manager
@login_manager.user_loader
def load_user(user_id):
    with app.app_context():
        return db.session.get(User, int(user_id))


# Mock URL RTSP (replace this with a local video file for testing if needed)


@app.route('/')
@login_required
def index():
    return render_template('routes/dashboard/index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('routes/index.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/sensor_data')
@login_required
def sensor_data():
    sensor_data = SensorState.query.order_by(SensorState.id.desc()).first()
    if not sensor_data:
        sensor_data = SensorState(pm25_state=False, rcwl_state=False, lock_state=False)
        db.session.add(sensor_data)
        db.session.commit()
    now = datetime.now().isoformat()
    data = [
        {"created_at": now, "name": "pm25_state", "value": str(int(sensor_data.pm25_state))},
        {"created_at": now, "name": "rcwl_state", "value": str(int(sensor_data.rcwl_state))},
        {"created_at": now, "name": "lock_state", "value": str(int(sensor_data.lock_state))}
    ]
    return jsonify(data)

@app.route('/toggle_lock_state', methods=['POST'])
@login_required
def toggle_lock_state():
    sensor_data = SensorState.query.order_by(SensorState.id.desc()).first()
    if sensor_data:
        sensor_data.lock_state = not sensor_data.lock_state
        db.session.commit()
        new_alert = Alert(status="State Lock Change Detected")
        db.session.add(new_alert)
        db.session.commit()

        return jsonify({"message": "Lock state toggled successfully", "lock_state": sensor_data.lock_state})


    return jsonify({"message": "No sensor data found"}), 404


@app.route('/scheduler', methods=['GET', 'POST'])
@login_required
def scheduler():
    if request.method == 'POST':

        start_time =  datetime.strptime(request.json.get('start_time'),  '%H:%M').time()
        end_time =  datetime.strptime(request.json.get('end_time'),  '%H:%M').time()

        print(start_time, end_time)
        scheduler_data = SchedulerData.query.first()
        if not scheduler_data:
            scheduler_data = SchedulerData()
            db.session.add(scheduler_data)
        scheduler_data.start_time = start_time
        scheduler_data.end_time = end_time
        db.session.commit()
        return jsonify({"message": "Scheduler updated successfully"}), 200

    scheduler_data = SchedulerData.query.first()
    return jsonify({
        "start_time": scheduler_data.start_time,
        "end_time": scheduler_data.end_time
    }), 200
def generate_frames():
    try:
        container = av.open(url, options={'pixel_format': 'rgb24'})
        tonemap = cv2.createTonemapDrago(1.0, 0.7)
    except av.error.InvalidDataError as e:
        print(f"Failed to open stream: {e}")
        return

    while True:
        try:
            for frame in container.decode(video=0):
                # Convert frame to numpy array in RGB format
                image_rgb = frame.to_ndarray(format='rgb24')
                #image_rgb = frame.to_rgb().to_ndarray()
                image_rgb = cv2.resize(image_rgb, (320, 240))

                # Convert RGB image to HDR (float32) format
                image_hdr = image_rgb.astype('float32') / 255.0

                # Apply tone mapping to convert HDR to LDR
                image_ldr = tonemap.process(image_hdr)

                # Normalize to 8-bit image for display
                image_ldr_8bit = cv2.normalize(image_ldr, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8UC3)

                # Convert back to BGR for OpenCV display
                image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

                # Encode the frame in JPEG format
                ret, buffer = cv2.imencode('.jpg', image_bgr)
                frame = buffer.tobytes()

                # Yield the frame in a byte format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        except av.AVError as e:
            print(f"Error reading frame: {e}")
            continue  # Continue attempting to read frames

@app.route('/video_feed')
@login_required
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# API endpoint to receive sensor data from ESP32

@app.route('/api/sensor', methods=['GET', 'POST'])
def api_sensor():
    if request.method == 'POST':
        data = request.json
        sensor_name = data.get('name')
        sensor_value = data.get('value')

        sensor_data = SensorState.query.first()
        if not sensor_data:
            sensor_data = SensorState()
            db.session.add(sensor_data)
            db.session.commit()

        if sensor_name in ['pm25_state', 'rcwl_state', 'lock_state']:
            if sensor_name == 'pm25_state':
                sensor_data.pm25_state = bool(int(sensor_value))
                if bool(int(sensor_value)):
                    new_alert = Alert(status="Smoke Detected")
                    db.session.add(new_alert)
            elif sensor_name == 'rcwl_state':
                sensor_data.rcwl_state = bool(int(sensor_value))
                if bool(int(sensor_value)):
                    new_alert = Alert(status="Motion Detected")
                    db.session.add(new_alert)
            elif sensor_name == 'lock_state':
                sensor_data.lock_state = bool(int(sensor_value))
                if bool(int(sensor_value)):
                    new_alert = Alert(status="State Lock Change Detected")
                    db.session.add(new_alert)

            db.session.commit()
            return jsonify({"message": "Sensor state updated successfully"}), 200
        else:
            return jsonify({"message": "Invalid sensor name"}), 400
    else:
        sensor_data = SensorState.query.first()
        if not sensor_data:
            sensor_data = SensorState()
            db.session.add(sensor_data)
            db.session.commit()

        return jsonify({
            "pm25_state": str(int(sensor_data.pm25_state)),
            "rcwl_state": str(int(sensor_data.rcwl_state)),
            "lock_state": str(int(sensor_data.lock_state))
        }), 200


# API endpoint to get and set the lock state
@app.route('/api/lock_state', methods=['GET', 'POST'])
def api_lock_state():
    if request.method == 'POST':
        data = request.json
        lock_state = bool(int(data.get('lock_state')))

        sensor_data = SensorState.query.first()
        if not sensor_data:
            sensor_data = SensorState(lock_state=lock_state)
            db.session.add(sensor_data)

            new_alert = Alert(status="State Lock Change Detected")
            db.session.add(new_alert)
        else:
            sensor_data.lock_state = lock_state

        db.session.commit()
        return jsonify({"message": "Lock state updated successfully", "lock_state": lock_state}), 200
    else:
        sensor_data = SensorState.query.order_by(SensorState.id.desc()).first()
        print(sensor_data)
        if not sensor_data:
            return jsonify({"message": "No sensor data found", "lock_state": 0}), 404

        return jsonify({"lock_state": sensor_data.lock_state}), 200


@app.route('/api/scheduler', methods=['GET', 'POST'])
def schedulerApi():
    if request.method == 'POST':
        start_time = request.json.get('start_time')
        end_time = request.json.get('end_time')

        scheduler_data = SchedulerData.query.first()
        if not scheduler_data:
            scheduler_data = SchedulerData(start_time=start_time, end_time=end_time)
            db.session.add(scheduler_data)
        else:
            scheduler_data.start_time = start_time
            scheduler_data.end_time = end_time

        db.session.commit()
        return jsonify({"message": "Scheduler updated successfully"}), 200

    elif request.method == 'GET':
        scheduler_data = SchedulerData.query.first()
        if not scheduler_data:
            return jsonify({"message": "No scheduler data found"}), 404

        now = datetime.now()
        end_time = scheduler_data.end_time if scheduler_data.end_time else now
        state = "overdue" if now > end_time else "underdue"

        return jsonify({
            "start_time": scheduler_data.start_time,
            "end_time": scheduler_data.end_time,
            "state": state
        }), 200


# API endpoint to get and post alerts
@app.route('/api/alerts', methods=['GET', 'POST'])
def alerts_api():
    if request.method == 'POST':
        alert_data = request.json
        new_alert = Alert(status=alert_data['status'])
        db.session.add(new_alert)
        db.session.commit()
        return jsonify({"message": "Alert added successfully"}), 200

    alerts = Alert.query.order_by(Alert.id.desc()).all()
    return jsonify([{
        "id": alert.id,
        "timestamp": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "status": alert.status
    } for alert in alerts]), 200


# Register route for new users (for testing purposes, you might want to limit this in a real application)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nama = request.form['nama']
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
        else:
            new_user = User(nama=nama,username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('User registered successfully')
            return redirect(url_for('login'))
    return render_template('routes/register.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
