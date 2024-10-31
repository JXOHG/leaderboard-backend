from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import os
from flask_cors import CORS
from io import StringIO
import json

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'public'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# JSON file paths
USER_DATA_FILE = 'public/users.json'
STEPS_FILE = 'public/steps.json'

# Helper function to merge manual and submit csv files
def combine_and_replace_csv():
    if os.path.isfile("public/manual.csv"):
        submit_df = pd.read_csv("public/submit.csv", usecols=["Name", "Total Steps", "Avg Daily Steps"])
        manual_df = pd.read_csv("public/manual.csv", usecols=["Name", "Total Steps", "Avg Daily Steps"])
    else:
        print("Manual.csv does not exist. No further operations")
        return

    combined_df = pd.concat([submit_df, manual_df], ignore_index=True)
    combined_df = combined_df.groupby('Name').agg(
        {'Total Steps': 'sum', 'Avg Daily Steps': 'sum'}
    ).reset_index()

    combined_df = combined_df.sort_values(by="Total Steps", ascending=False)

    # Delete anyone with negative number steps
    combined_df = combined_df[combined_df['Total Steps'] >= 0]

    # Update total steps in JSON file
    total_steps = combined_df['Total Steps'].sum()
    with open(STEPS_FILE, 'w') as f:
        json.dump({"current_steps": total_steps}, f)

    # Replace the existing 'main.csv' with the combined data
    combined_df.to_csv("public/main.csv", index=False)
    print("Files combined successfully, and 'main.csv' has been replaced.")

def load_users():
    try:
        with open(USER_DATA_FILE) as f:
            return json.load(f)
    except:
        print('Failed to open user data')
        return {}

def save_users(username, password):
    try:
        data = load_users()
        data[username] = password
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(e)
        print('Failed to save user data')

# Handles csv file upload
@app.route("/csv", methods=['POST'])
def csv():
    if request.method == 'POST':
        f = request.files['file']
        data_filename = secure_filename(f.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], data_filename)
        f.save(file_path)
        os.rename(file_path, os.path.join(app.config['UPLOAD_FOLDER'], 'temp.csv'))

        try:
            df = pd.read_csv("public/temp.csv")
            if set(['Name', 'Total Steps', "Avg Daily Steps"]).issubset(df.columns):
                df = df[["Name", "Total Steps", "Avg Daily Steps"]]
                df = df.sort_values(by="Total Steps", ascending=False)
                df.to_csv("public/submit.csv", index=False)

                combine_and_replace_csv()
                os.remove("public/temp.csv")
            else:
                os.remove("public/temp.csv")
                return jsonify({"message": "wrong csv file"}), 400
        except:
            if os.path.isfile('public/temp.csv'):
                os.remove("public/temp.csv")
        return jsonify({"message": "File uploaded successfully"}), 200
    return jsonify({"message": "File did not upload successfully"}), 400

@app.route("/manual", methods=['POST'])
def manual():
    if request.method == 'POST':
        csvStr = request.data.decode('utf-8')
        csvStr = StringIO(csvStr)
        df = pd.read_csv(csvStr, sep=",", header=0)

        if set(['name', 'steps']).issubset(df.columns):
            df = df[["name", "steps"]]
            df.rename(columns={'steps': 'Total Steps', 'name': 'Name', 'averageSteps': 'Avg Daily Steps'}, inplace=True)

            if os.path.isfile("public/manual.csv"):
                df.to_csv("public/manual.csv", mode='a', header=False, index=False)
            else:
                df.to_csv("public/manual.csv", index=False)

            combine_and_replace_csv()
        return jsonify({"message": "CSV received and processed"}), 200
    return jsonify({"message": "fail"}), 400

@app.route("/login", methods=['POST'])
def login():
    if request.method == 'POST':
        users = load_users()
        uname = request.json["username"]
        pw = request.json["password"]

        if uname in users and check_password_hash(users[uname], pw):
            return jsonify({'message': 'Successful login!'}), 200
        else:
            return jsonify({"message": 'Login failed!'}), 400

@app.route("/changepw", methods=['POST'])
def changepw():
    if request.method == 'POST':
        users = load_users()
        userpass = request.data.decode('utf-8').split()
        uname = userpass[0]
        pw = userpass[1]

        hashed_pw = generate_password_hash(pw)
        try:
            save_users(uname, hashed_pw)
        except:
            return jsonify({"message": "Failed to load users"}), 400
        return jsonify({"message": "Password updated!"}), 200

# New route to get and set the current steps
@app.route("/current_steps", methods=['GET'])
def curSteps():
    if request.method == 'GET':
        if os.path.isfile(STEPS_FILE):
            with open(STEPS_FILE, 'r') as f:
                data = json.load(f)
                return jsonify({"current_steps": data.get("current_steps", 0)}), 200
        return jsonify({"current_steps": 0}), 200  # Default steps if file doesn't exist

# New route to get and set the step goal
@app.route("/step_goal", methods=['GET', 'POST'])
def stepGoal():
    if request.method == 'GET':
        if os.path.isfile(STEPS_FILE):
            with open(STEPS_FILE, 'r') as f:
                data = json.load(f)
                return jsonify({"step_goal": data.get("step_goal", 10000)}), 200  # Default goal if file doesn't exist

    if request.method == 'POST':
        new_step_goal = request.json.get('step_goal')
        if new_step_goal is not None:
            with open(STEPS_FILE, 'r') as f:
                data = json.load(f)
            data['step_goal'] = new_step_goal
            with open(STEPS_FILE, 'w') as f:
                json.dump(data, f)
            return jsonify({"message": "Step goal updated successfully."}), 200
        return jsonify({"message": "Invalid step goal value."}), 400

# New route to get and set the goal
@app.route("/goal", methods=['GET', 'POST'])
def goal():
    if request.method == 'GET':
        if os.path.isfile(STEPS_FILE):
            with open(STEPS_FILE, 'r') as f:
                data = json.load(f)
                return jsonify({"goal": data.get("goal", 1000)}), 200  # Default goal if file doesn't exist

    if request.method == 'POST':
        new_goal = request.json.get('goal')
        if new_goal is not None:
            with open(STEPS_FILE, 'r') as f:
                data = json.load(f)
            data['goal'] = new_goal
            with open(STEPS_FILE, 'w') as f:
                json.dump(data, f)
            return jsonify({"message": "Goal updated successfully."}), 200
        return jsonify({"message": "Invalid goal value."}), 400

# New route to get and set the current value raised
@app.route("/current_value", methods=['GET', 'POST'])
def current_value():
    if request.method == 'GET':
        if os.path.isfile(STEPS_FILE):
            with open(STEPS_FILE, 'r') as f:
                data = json.load(f)
                return jsonify({"current_value": data.get("current_value", 0)}), 200
        return jsonify({"current_value": 0}), 200  # Default value if file doesn't exist

    if request.method == 'POST':
        new_value = request.json.get('current_value')
        if new_value is not None:
            with open(STEPS_FILE, 'r') as f:
                data = json.load(f)
            data['current_value'] = new_value
            with open(STEPS_FILE, 'w') as f:
                json.dump(data, f)
            return jsonify({"message": "Current value updated successfully."}), 200
        return jsonify({"message": "Invalid value."}), 400

if __name__ == '__main__':
    app.run(port=5000)