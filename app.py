from flask import Flask, render_template, redirect, url_for, request, jsonify, flash, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import cv2
import av
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = 'joel_app'  # Ganti dengan kunci rahasia Anda

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# In-memory user storage (replace with database in production)
users = {}

# User model
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Login manager
@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

# Mock URL RTSP (replace this with a local video file for testing if needed)
url = "rtsp://admin:qwerty123@192.168.0.230:554/user=admin&password=qwerty123&channel=1&stream=0.sdp?"

# In-memory storage for scheduler data
scheduler_data = {
    "start_time": None,
    "end_time": None
}

# In-memory storage for lock state
lock_state = 1

# Mock data for testing purposes
sensor_states = {
    "pm25_state": str(random.randint(0, 1)),
    "rcwl_state": str(random.randint(0, 1)),
    "lock_state": str(lock_state)
}

@app.route('/')
# @login_required
def index():
    return render_template('routes/dashboard/index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = next((u for u in users.values() if u.username == username), None)
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('routes/index.html')

@app.route('/logout')
# @login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/sensor_data')
# @login_required
def sensor_data():
    global sensor_states, lock_state
    now = datetime.now().isoformat()
    data = [
        {"created_at": now, "name": "pm25_state", "value": sensor_states["pm25_state"]},
        {"created_at": now, "name": "rcwl_state", "value": sensor_states["rcwl_state"]},
        {"created_at": now, "name": "lock_state", "value": str(lock_state)}
    ]
    return jsonify(data)

@app.route('/toggle_lock_state', methods=['POST'])
# @login_required
def toggle_lock_state():
    global lock_state
    lock_state = 1 - lock_state  # Toggle the lock state
    sensor_states["lock_state"] = str(lock_state)
    return jsonify({"message": "Lock state toggled successfully", "lock_state": lock_state})

@app.route('/scheduler', methods=['GET', 'POST'])
# @login_required
def scheduler():
    if request.method == 'POST':
        # Get the start and end times from the request
        start_time = request.json.get('start_time')
        end_time = request.json.get('end_time')

        # Update the scheduler data
        scheduler_data['start_time'] = start_time
        scheduler_data['end_time'] = end_time

        return jsonify({"message": "Scheduler updated successfully"}), 200

    # Return the current scheduler data
    return jsonify(scheduler_data), 200

def generate_frames():
    try:
        container = av.open(url)
        tonemap = cv2.createTonemapDrago(1.0, 0.7)
    except av.error.InvalidDataError as e:
        print(f"Failed to open stream: {e}")
        return

    while True:
        try:
            for frame in container.decode(video=0):
                # Convert frame to numpy array in RGB format
                image_rgb = frame.to_ndarray(format='rgb24')
                image_rgb = cv2.resize(image_rgb, (320, 240))

                # Convert RGB image to HDR (float32) format
                image_hdr = image_rgb.astype('float32') / 255.0

                # Apply tone mapping to convert HDR to LDR
                image_ldr = tonemap.process(image_hdr)

                # Normalize to 8-bit image for display
                image_ldr_8bit = cv2.normalize(image_ldr, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8UC3)

                # Convert back to BGR for OpenCV display
                image_bgr = cv2.cvtColor(image_ldr_8bit, cv2.COLOR_RGB2BGR)

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
# @login_required
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# API endpoint to receive sensor data from ESP32

@app.route('/api/sensor', methods=['GET', 'POST'])
def api_sensor(cc):
    global sensor_states
    if request.method == 'POST':
        data = request.json
        sensor_name = data.get('name')
        sensor_value = data.get('value')
        print(sensor_name)
        print(sensor_value)
        if sensor_name in sensor_states:
            sensor_states[sensor_name] = sensor_value

            return jsonify({"message": "Sensor state updated successfully"}), 200
        else:
            return jsonify({"message": "Invalid sensor name"}), 400
    else:
        return jsonify(sensor_states), 200

# API endpoint to get and set the lock state
@app.route('/api/lock_state', methods=['GET', 'POST'])
def api_lock_state():
    global lock_state
    if request.method == 'POST':
        data = request.json
        lock_state = int(data.get('lock_state'))
        sensor_states["lock_state"] = str(lock_state)
        return jsonify({"message": "Lock state updated successfully", "lock_state": lock_state}), 200
    else:
        return jsonify({"lock_state": lock_state}), 200

@app.route('/api/scheduler', methods=['GET', 'POST'])
def schedulerApi():
    if request.method == 'POST':
        # Get the start and end times from the request
        start_time = request.json.get('start_time')
        end_time = request.json.get('end_time')

        # Update the scheduler data
        scheduler_data['start_time'] = start_time
        scheduler_data['end_time'] = end_time

        return jsonify({"message": "Scheduler updated successfully"}), 200

    elif request.method == 'GET':
        # Get current time
        now = datetime.now()

        # Parse the end_time from scheduler_data
        end_time = datetime.fromisoformat(scheduler_data['end_time']) if scheduler_data['end_time'] else now

        # Determine if the current time is past the end_time
        state = "overdue" if now > end_time else "underdue"
        scheduler_data_with_state = scheduler_data.copy()
        scheduler_data_with_state["state"] = state

        return jsonify(scheduler_data_with_state), 200

# API endpoint to get and post alerts
@app.route('/api/alerts', methods=['GET', 'POST'])
def alerts_api():
    global alerts
    if request.method == 'POST':
        # Get alert data from the request
        alert = request.json
        alerts.append(alert)
        return jsonify({"message": "Alert added successfully"}), 200

    # Return the list of alerts
    return jsonify(alerts), 200

# Register route for new users (for testing purposes, you might want to limit this in a real application)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        print(request.form)
        username = request.form['username']
        password = request.form['password']
        if username in [u.username for u in users.values()]:
            flash('Username already exists')
        else:
            user_id = str(len(users) + 1)
            users[user_id] = User(user_id, username, password)
            flash('User registered successfully')
            return redirect(url_for('login'))
    return render_template('routes/register.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
