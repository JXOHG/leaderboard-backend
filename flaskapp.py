from flask import Flask, request, jsonify, send_from_directory
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

# Helper function to merge manual and submit csv files
def combine_and_replace_csv():
    if os.path.isfile("public/manual.csv"):
        submit_df = pd.read_csv("public/submit.csv", usecols=["Name", "Total Steps", "Avg Daily Steps"])
        manual_df = pd.read_csv("public/manual.csv", usecols=["Name", "Total Steps", "Avg Daily Steps"])
    else:
        print("Manual.csv does not exist. No further operations")
        return

    # Combine the two DataFrames
    combined_df = pd.concat([submit_df, manual_df], ignore_index=True)
    combined_df = combined_df.groupby('Name').agg({'Total Steps': 'sum', 'Avg Daily Steps': 'sum'}).reset_index()
    combined_df = combined_df.sort_values(by="Total Steps", axis=0, ascending=False)

    # Remove negative Total Steps
    combined_df['Total Steps'] = combined_df['Total Steps'].astype('int')
    combined_df = combined_df[combined_df['Total Steps'] >= 0]
    combined_df['Total Steps'] = combined_df['Total Steps'].astype('str')

    # Record total steps in current_steps.txt
    total_steps = combined_df['Total Steps'].sum()
    with open('public/current_steps.txt', 'w') as f:
        f.write(str(total_steps))

    # Replace existing main.csv with combined data
    combined_df.to_csv("public/main.csv", index=False)
    print("Files combined successfully, and 'main.csv' has been replaced.")

def load_users():
    try:
        with open('users.json') as f:
            data = json.load(f)
            return data
    except:
        print('Failed to open data')

def save_users(username, password):
    try:
        with open('users.json') as f:
            data = json.load(f)
            data[username] = password
        with open('users.json', 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(e)
        print('Failed to save data')

# Handles CSV file upload
@app.route("/csv", methods=['POST'])
def csv_upload():
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
                df = df.sort_values(by="Total Steps", axis=0, ascending=False)
                df.to_csv("public/submit.csv", index=False)

                # Merges manual.csv with submit.csv
                combine_and_replace_csv()
                os.remove("public/temp.csv")
            else:
                os.remove("public/temp.csv")
                return jsonify({"message": "Wrong CSV file"}), 400
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
            df = df[["name", "steps", "averageSteps"]]
            df.rename(columns={'steps': 'Total Steps', 'name': 'Name', 'averageSteps': 'Avg Daily Steps'}, inplace=True)

            if os.path.isfile("public/manual.csv"):
                df.to_csv("public/manual.csv", mode='a', header=False, index=False)
            else:
                df.to_csv("public/manual.csv", index=False)

            manual_df = pd.read_csv("public/manual.csv")
            manual_df = manual_df.sort_values(by="Total Steps", ascending=False)
            manual_df.to_csv("public/manual.csv", index=False)

            combine_and_replace_csv()
        return jsonify({"message": "CSV received and processed"}), 200
    return jsonify({"message": "Failed"}), 400

@app.route("/login", methods=['POST'])
def login():
    if request.method == 'POST':
        try:
            users = load_users()
        except:
            return jsonify({"message": "Failed to load user data"}), 400
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
        uname, pw = userpass[0], userpass[1]
        hashed_pw = generate_password_hash(pw)

        try:
            save_users(uname, hashed_pw)
        except:
            return jsonify({"message": "Failed to load users"}), 400
        return jsonify({"message": "Password updated!"}), 200

CURRENT_STEP_FILE = 'public/current_steps.txt'

# New route to get current steps
@app.route("/current_steps", methods=['GET'])
def curSteps():
    if request.method == 'GET':
        if os.path.isfile(CURRENT_STEP_FILE):
            with open(CURRENT_STEP_FILE, 'r') as f:
                current_steps = f.read().strip()
                return jsonify({"current_steps": int(current_steps)}), 200
        else:
            return jsonify({"current_steps": 0}), 200

STEP_GOAL_FILE = 'public/step_goal.txt'

# New route to get and set the step goal
@app.route("/step_goal", methods=['GET', 'POST'])
def stepGoal():
    if request.method == 'GET':
        if os.path.isfile(STEP_GOAL_FILE):
            with open(STEP_GOAL_FILE, 'r') as f:
                step_goal = f.read().strip()
                return jsonify({"step_goal": int(step_goal)}), 200
    
    if request.method == 'POST':
        new_step_goal = request.json.get('step_goal')
        if new_step_goal is not None:
            with open(STEP_GOAL_FILE, 'w') as f:
                f.write(str(new_step_goal))
            return jsonify({"message": "Step goal updated successfully."}), 200
        return jsonify({"message": "Invalid step goal value."}), 400

GOAL_FILE = 'public/goal.txt'

# New route to get and set the goal
@app.route("/goal", methods=['GET', 'POST'])
def goal():
    if request.method == 'GET':
        if os.path.isfile(GOAL_FILE):
            with open(GOAL_FILE, 'r') as f:
                current_goal = f.read().strip()
                return jsonify({"goal": int(current_goal)}), 200
        else:
            return jsonify({"goal": 1000}), 200

    if request.method == 'POST':
        new_goal = request.json.get('goal')
        if new_goal is not None:
            with open(GOAL_FILE, 'w') as f:
                f.write(str(new_goal))
            return jsonify({"message": "Goal updated successfully."}), 200
        return jsonify({"message": "Invalid goal value."}), 400

CURRENT_VALUE_FILE = 'public/current_value.txt'

# New route to get and set the current value raised
@app.route("/current_value", methods=['GET', 'POST'])
def current_value():
    if request.method == 'GET':
        if os.path.isfile(CURRENT_VALUE_FILE):
            with open(CURRENT_VALUE_FILE, 'r') as f:
                current_value = f.read().strip()
                return jsonify({"current_value": int(current_value)}), 200
        else:
            return jsonify({"current_value": 0}), 200

    if request.method == 'POST':
        new_value = request.json.get('current_value')
        if new_value is not None:
            with open(CURRENT_VALUE_FILE, 'w') as f:
                f.write(str(new_value))
            return jsonify({"message": "Current value updated successfully."}), 200
        return jsonify({"message": "Invalid value."}), 400

# New route to serve the main.csv file
@app.route("/public/main.csv", methods=['GET'])
def get_csv():
    return send_from_directory(app.config['UPLOAD_FOLDER'], 'main.csv')

if __name__ == '__main__':
    app.run(port=5000)
