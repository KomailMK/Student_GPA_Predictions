import os
import random
import smtplib
import hashlib
from email.message import EmailMessage

import joblib
import numpy as np
import pandas as pd
import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError
from flask import Flask, request, render_template, redirect, url_for, session, flash

# Force reload of .env file
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your_secret_key")

FEATURE_COLUMNS = [
    'attendance',
    'study_hours',
    'past_cgpa',
    'quiz_performance',
    'class_participation'
]


def clean_env(key, default=""):
    """Read an environment variable and strip inline comments and surrounding quotes."""
    val = os.environ.get(key, default) or default
    val = str(val).split('#')[0].strip().strip('"').strip("'")
    return val


def get_db_connection(include_db=True):
    """Create and return a MySQL connection using configuration from environment variables."""
    host = clean_env("MYSQL_HOST", "localhost")
    port = int(clean_env("MYSQL_PORT", "3306"))
    user = clean_env("MYSQL_USER", "root")
    password = clean_env("MYSQL_PASSWORD", "")
    db_name = clean_env("MYSQL_DB", "gpa_predictor")

    conn_params = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "charset": "utf8mb4",
        "autocommit": True,
        "cursorclass": pymysql.cursors.DictCursor
    }
    if include_db:
        conn_params["database"] = db_name

    return pymysql.connect(**conn_params)


def init_db():
    """Ensure the MySQL database and users table exist, and perform one-time migration if legacy users.txt exists."""
    db_name = clean_env("MYSQL_DB", "gpa_predictor")
    try:
        # Step 1: Ensure database exists
        conn_server = get_db_connection(include_db=False)
        with conn_server.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn_server.close()

        # Step 2: Ensure users table exists
        conn_db = get_db_connection(include_db=True)
        with conn_db.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    hashed_name VARCHAR(64) NOT NULL,
                    hashed_email VARCHAR(64) NOT NULL UNIQUE,
                    hashed_password VARCHAR(64) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_hashed_email (hashed_email),
                    INDEX idx_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)

            # Step 3: Optional one-time migration if legacy users.txt exists
            if os.path.exists('users.txt'):
                try:
                    with open('users.txt', 'r') as f:
                        for line in f:
                            parts = [p.strip() for p in line.strip().split(',') if p.strip()]
                            if len(parts) >= 3:
                                h_name, h_email, h_pwd = parts[0], parts[1], parts[2]
                                cur.execute("""
                                    INSERT IGNORE INTO users (name, email, hashed_name, hashed_email, hashed_password)
                                    VALUES (%s, %s, %s, %s, %s)
                                """, ('Legacy User', 'legacy@user.local', h_name, h_email, h_pwd))
                except Exception as mig_err:
                    print(f"Notice: legacy users.txt migration skipped ({mig_err}).")

        conn_db.close()
        print("MySQL database and 'users' table verified successfully.")
    except Exception as e:
        print(f"Warning: Could not initialize MySQL database ({e}). Please verify MySQL is running and .env credentials are correct.")


# Initialize MySQL database on startup
init_db()


def load_or_repair_model():
    """Load the GPA model and patch/retrain if a scikit-learn version mismatch occurs."""
    model_path = 'models/final_gpa_model.pkl'
    loaded_model = joblib.load(model_path)

    if hasattr(loaded_model, 'named_steps') and 'imputer' in loaded_model.named_steps:
        imputer = loaded_model.named_steps['imputer']
        if not hasattr(imputer, '_fill_dtype'):
            imputer._fill_dtype = getattr(imputer, '_fit_dtype', np.dtype('float64'))

    try:
        test_df = pd.DataFrame([[80.0, 10.0, 3.0, 75.0, 7.0]], columns=FEATURE_COLUMNS)
        loaded_model.predict(test_df)
        return loaded_model
    except Exception as e:
        print(f"Pickle version mismatch detected ({e}). Rebuilding model for current sklearn version...")
        from sklearn.pipeline import Pipeline
        from sklearn.impute import SimpleImputer
        from sklearn.preprocessing import MinMaxScaler
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import train_test_split

        data = pd.read_csv('others/student_performance_data.csv')
        for col in FEATURE_COLUMNS + ['final_gpa']:
            data[col] = data[col].fillna(data[col].mean())

        X = data[FEATURE_COLUMNS]
        y = data['final_gpa']
        X_train, _, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=42)

        pipeline = Pipeline([
            ('imputer', SimpleImputer(strategy='mean')),
            ('scaler', MinMaxScaler()),
            ('model', RandomForestRegressor(n_estimators=120, max_depth=16, min_samples_leaf=2, random_state=42))
        ])
        pipeline.fit(X_train, y_train)
        os.makedirs('models', exist_ok=True)
        joblib.dump(pipeline, model_path)
        return pipeline


model = load_or_repair_model()


def hash_data(data):
    return hashlib.sha256(data.encode()).hexdigest()


def is_email_registered(email):
    """Check if the email (plain text, exact hash, or lowercase hash) is registered in the MySQL database."""
    exact_hash = hash_data(email)
    normalized_hash = hash_data(email.strip().lower())
    clean_email = email.strip()

    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT id FROM users
                    WHERE hashed_email = %s OR hashed_email = %s OR email = %s
                    LIMIT 1
                """
                cursor.execute(sql, (exact_hash, normalized_hash, clean_email))
                return cursor.fetchone() is not None
        finally:
            conn.close()
    except Exception as e:
        print(f"Database error in is_email_registered: {e}")
        return False


def send_email(email, code, name=None, password=None):
    """Send 6-digit verification code via SMTP and return (success_bool, error_msg)."""
    sender_email = clean_env("SENDER_EMAIL")
    sender_password = clean_env("SENDER_PASSWORD")
    smtp_server = clean_env("SMTP_SERVER", "smtp.gmail.com")
    port = 587

    if not sender_email or not sender_password:
        err = "SENDER_EMAIL or SENDER_PASSWORD is empty in your .env file."
        print("Error sending email:", err)
        return False, err

    user_name = name if name is not None else request.form.get('name', 'User')
    user_password = password if password is not None else request.form.get('password', '')

    try:
        msg = EmailMessage()
        msg["Subject"] = "Verify Your Email"
        msg["From"] = f"Multi Factor Authentication <{sender_email}>"
        msg["To"] = email
        msg.set_content(f"""Hi {user_name}!
        You Recently Tried to Sign Up on GPA Predictor.
        Your verification code is: {code}.
        You can use this code to get your email verified

        Your Account Credentials are:
        Email: {email}
        Password: {user_password}

        Note: Kindly save these credentials for future use. You won't be able to login if you lost/forgotten your password.""")

        with smtplib.SMTP(smtp_server, port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        print(f"Verification code {code} sent to {email}")
        return True, None
    except Exception as e:
        print("Error sending email:", e)
        return False, str(e)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        password = request.form['password']

        # 1. Block already-verified emails in MySQL database
        if is_email_registered(email):
            flash("This email is already in use. Please use a different email.", "danger")
            return redirect(url_for('signup'))

        # 2. Validate email syntax (skip DNS lookup so local network issues don't block signup)
        try:
            validate_email(email, check_deliverability=False)
        except EmailNotValidError as e:
            flash(str(e), 'error')
            return redirect(url_for('signup'))

        # 3. Generate verification code and send email BEFORE saving user
        code = str(random.randint(100000, 999999))
        sent_ok, error_msg = send_email(email, code, name=name, password=password)

        if not sent_ok:
            flash(f"Could not send verification email: {error_msg}", "danger")
            return redirect(url_for('signup'))

        # 4. Store user in session temporarily until they verify the code on /verify
        session['email'] = email
        session['code'] = code
        session['pending_user'] = {
            'raw_name': name,
            'raw_email': email,
            'raw_password': password,
            'hashed_name': hash_data(name),
            'hashed_email': hash_data(email),
            'hashed_password': hash_data(password)
        }

        flash("Verification code sent! Please check your inbox.", "success")
        return redirect(url_for('verify_code'))

    return render_template('email_input.html')


@app.route('/verify', methods=['GET', 'POST'])
def verify_code():
    if 'pending_user' not in session or 'code' not in session:
        flash("Please sign up first to receive a verification code.", "danger")
        return redirect(url_for('signup'))

    if request.method == 'POST':
        user_code = request.form.get('code', '').strip()
        if user_code == session.get('code'):
            pending = session.get('pending_user')

            # Save user to MySQL users table ONLY AFTER successful email verification
            if pending and not is_email_registered(pending['raw_email']):
                try:
                    conn = get_db_connection()
                    try:
                        with conn.cursor() as cursor:
                            sql = """
                                INSERT INTO users (name, email, hashed_name, hashed_email, hashed_password)
                                VALUES (%s, %s, %s, %s, %s)
                            """
                            cursor.execute(sql, (
                                pending['raw_name'],
                                pending['raw_email'],
                                pending['hashed_name'],
                                pending['hashed_email'],
                                pending['hashed_password']
                            ))
                    finally:
                        conn.close()
                except Exception as db_err:
                    print(f"Database error saving verified user: {db_err}")
                    flash("Failed to save account to database. Please try again.", "danger")
                    return redirect(url_for('verify_code'))

            session.pop('code', None)
            session.pop('pending_user', None)
            flash("Email verified and account created! Please sign in.", "success")
            return redirect(url_for('signin'))
        else:
            flash('Invalid verification code. Please try again.', 'error')

    return render_template('verify_code.html')


@app.route('/resend', methods=['POST'])
def resend_code():
    pending = session.get('pending_user')
    if not pending:
        flash("Session expired. Please sign up again.", "danger")
        return redirect(url_for('signup'))

    new_code = str(random.randint(100000, 999999))
    sent_ok, error_msg = send_email(
        pending['raw_email'],
        new_code,
        name=pending['raw_name'],
        password=pending['raw_password']
    )
    if sent_ok:
        session['code'] = new_code
        flash("A new verification code has been sent to your email.", "success")
    else:
        flash(f"Failed to resend code: {error_msg}", "danger")

    return redirect(url_for('verify_code'))


@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']

        hashed_email_exact = hash_data(email)
        hashed_email_lower = hash_data(email.lower())
        hashed_password = hash_data(password)

        try:
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT id, name, email FROM users
                        WHERE (hashed_email = %s OR hashed_email = %s OR email = %s)
                          AND hashed_password = %s
                        LIMIT 1
                    """
                    cursor.execute(sql, (hashed_email_exact, hashed_email_lower, email, hashed_password))
                    user = cursor.fetchone()
                    if user:
                        session['email'] = email
                        session['authenticated'] = True
                        flash("Login successful!", "success")
                        return redirect(url_for('index'))
            finally:
                conn.close()
        except Exception as db_err:
            print(f"Database error during signin: {db_err}")
            flash("Database error during sign in. Please verify database connection.", "danger")
            return redirect(url_for('signin'))

        flash("Incorrect email or password (or email not yet verified).", "danger")
        return redirect(url_for('signin'))
    return render_template('signin.html')


@app.route('/logout')
def logout():
    session.pop('email', None)
    session.pop('authenticated', None)
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('signin'))


@app.route('/index', methods=['GET', 'POST'])
def index():
    if not session.get('authenticated'):
        flash("Please sign in to access this page.", "danger")
        return redirect(url_for('signin'))

    predicted_gpa = None
    if request.method == 'POST':
        try:
            attendance = float(request.form['attendance'])
            study_hours = float(request.form['study-hours'])
            previous_cgpa = float(request.form['previous-cgpa'])
            quizzes_performance = float(request.form['quizzes-performance'])
            class_participation = float(request.form['class-participation'])

            print(f"Form data received: Attendance={attendance}, Study Hours={study_hours}, "
                  f"Previous CGPA={previous_cgpa}, Quizzes Performance={quizzes_performance}, "
                  f"Class Participation={class_participation}")

            features_df = pd.DataFrame(
                [[attendance, study_hours, previous_cgpa, quizzes_performance, class_participation]],
                columns=FEATURE_COLUMNS
            )
            prediction = model.predict(features_df)
            predicted_gpa = float(np.clip(prediction[0], 0, 4))
            predicted_gpa = round(predicted_gpa, 2)
            print(f"Predicted GPA: {predicted_gpa}")
        except Exception as e:
            flash(f"Error during prediction: {e}", "danger")
            print(f"Error occurred: {e}")

    return render_template('index.html', predicted_gpa=predicted_gpa)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
