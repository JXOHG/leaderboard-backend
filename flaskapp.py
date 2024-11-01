from flask import Flask, request, jsonify, send_file
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
@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"message": "Server is active"}), 200

# Helper function to merge manual and submit csv files
def combine_and_replace_csv():
    # Read relevant columns from both CSV files
    if (os.path.isfile("public/manual.csv")):
        submit_df = pd.read_csv("public/submit.csv", usecols=["Name", "Total Steps", "Avg Daily Steps"])
        manual_df = pd.read_csv("public/manual.csv", usecols=["Name", "Total Steps", "Avg Daily Steps"])
    else:
        print("Manual.csv does not exist. No further operations")
        return

    # Combine the two DataFrames
    combined_df = pd.concat([submit_df, manual_df], ignore_index=True)

    combined_df = combined_df.groupby('Name').agg(
            {'Total Steps': 'sum', 'Avg Daily Steps': 'sum'}  # Sum Total Steps and Average Avg Daily Steps
        ).reset_index()
    
    combined_df = combined_df.sort_values(by="Total Steps", axis=0, ascending=False)
    
    # Delete anyone with negative number steps
    combined_df['Total Steps'] = combined_df['Total Steps'].astype('int')
    combined_df = combined_df[combined_df['Total Steps'] >= 0]
    
    # Record the total amount of steps into a current_steps.txt file
    total_steps = combined_df['Total Steps'].sum()
    combined_df['Total Steps'] = combined_df['Total Steps'].astype('str')
    with open('public/current_steps.txt', 'w') as f:
        f.write(str(total_steps))
        
    # Replace the existing 'main.csv' with the combined data
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
            json.dump(data,f)
            
    except Exception as e:
        print(e)
        print('Failed to save data')
            

# handles csv file upload
@app.route("/csv", methods=['GET', 'POST'])
def csv():
    if request.method == 'POST':
        f = request.files['file']

        # Extracting uploaded file name
        data_filename = secure_filename(f.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], data_filename)

        # Saves the file to a temporary csv
        f.save(file_path)
        os.rename(file_path, os.path.join(app.config['UPLOAD_FOLDER'], 'temp.csv'))
        try:
            # Opens the csv into a dataframe to be modified by pandas
            df = pd.read_csv("public/temp.csv")

            # Checks if csv has the correct columns
            if set(['Name', 'Total Steps', "Avg Daily Steps"]).issubset(df.columns):
                # Extract necessary columns
                df = df[["Name", "Total Steps", "Avg Daily Steps"]]
                # Sort by total steps
                df = df.sort_values(by="Total Steps", ascending=False)
                # Write file to submit.csv
                df.to_csv("public/submit.csv", index=False)

                # Merges manual.csv with submit.csv
                combine_and_replace_csv()

                os.remove("public/temp.csv")
            else:
                # Incorrect csv file submitted
                os.remove("public/temp.csv")
                return jsonify({"message": "Wrong CSV file"}), 400
        except Exception as e:
            # Handle any errors
            if os.path.isfile('public/temp.csv'):
                os.remove("public/temp.csv")
            return jsonify({"message": "Error processing file", "error": str(e)}), 500

        return jsonify({"message": "File uploaded successfully"}), 200

    # Handle GET request
    elif request.method == 'GET':
        # Serve the combined CSV file (main.csv)
        if os.path.isfile("public/main.csv"):
            return send_file("public/main.csv", mimetype='text/csv', as_attachment=True)
        else:
            return jsonify({"message": "No combined CSV file available."}), 404

    return jsonify({"message": "Invalid request"}), 400

@app.route("/manual", methods=['POST'])
def manual():
    
    if request.method == 'POST':
        csvStr = request.data.decode('utf-8')
        print(csvStr)
        csvStr = StringIO(csvStr)
        
        df = pd.read_csv(csvStr, sep=",", header=0)

        # Check if CSV has the correct columns
        if set(['name', 'steps']).issubset(df.columns):
            # Extract necessary columns and rename them
            df = df[["name", "steps", "averageSteps"]]
            df.rename(columns={'steps': 'Total Steps', 'name': 'Name', 'averageSteps': 'Avg Daily Steps'}, inplace=True)

            # Append new data to manual.csv instead of replacing it
            # If manual.csv exists, append; otherwise, create a new one
            if os.path.isfile("public/manual.csv"):
                df.to_csv("public/manual.csv", mode='a', header=False, index=False)
            else:
                df.to_csv("public/manual.csv", index=False)
            # Now, read the manual.csv to sort it by Total Steps
            manual_df = pd.read_csv("public/manual.csv")
            manual_df = manual_df.sort_values(by="Total Steps", ascending=False)

            # Write the sorted DataFrame back to manual.csv
            manual_df.to_csv("public/manual.csv", index=False)

            # Call the combine_and_replace_csv function to update main.csv
            combine_and_replace_csv()

        return jsonify({"message": "CSV received and processed"}), 200
    return jsonify({"message": "fail"}), 400

      
@app.route("/login", methods=['POST'])
def login():
    if request.method == 'POST':
        #get dictionary of {username:password}
        try:
            users = load_users()
        except:
            return jsonify({"message": "Failed to load user data"}), 400
        uname = request.json["username"]
        pw = request.json["password"]
        #hash pw function here
        
        if uname in users and check_password_hash(users[uname], pw):
            #login function should be here
            return jsonify({'message': 'Successful login!'}), 200
        else:
            return jsonify({"message": 'Login failed!'}), 400

@app.route("/changepw", methods=['POST'])
def changepw():
    if request.method == 'POST':
        #get dictionary of {username:password}
        users = load_users()
        
        userpass = request.data.decode('utf-8')
        userpass = userpass.split()
        
        uname = userpass[0]
        pw = userpass[1]
        
        #hash password here
        hashed_pw = generate_password_hash(pw)
        
        try:
            save_users(uname, hashed_pw)    
        except:    
            return jsonify({"message": "Failed to load users"}), 400
        return jsonify({"message": "Password updated!"}), 200
        
"""       df = pd.read_csv(csvStr, sep=',', header = None)
      print(df) """
      
CURRENT_STEP_FILE = 'public/current_steps.txt'

# New route to get and set the current steps
@app.route("/current_steps", methods=['GET'])
def curSteps():
    if request.method == 'GET':
        # Read the current steps from the file if it exists
        if os.path.isfile(CURRENT_STEP_FILE):
            with open(CURRENT_STEP_FILE, 'r') as f:
                current_steps = f.read().strip()
                return jsonify({"current_steps": int(current_steps)}), 200
        else:
            return jsonify({"steps": 0}), 200  # Default steps if file doesn't exist

STEP_GOAL_FILE = 'public/step_goal.txt'

# New route to get and set the step goal
@app.route("/step_goal", methods=['GET', 'POST'])
def stepGoal():
    if request.method == 'GET':
        # Read the current step goal from the file if it exists
        if os.path.isfile(STEP_GOAL_FILE):
            with open(STEP_GOAL_FILE, 'r') as f:
                step_goal = f.read().strip()
                return jsonify({"step_goal": int(step_goal)}), 200
    
    if request.method == 'POST':
            new_step_goal = request.json.get('step_goal')
            if new_step_goal is not None:
                # Save the new step goal to the file
                with open(STEP_GOAL_FILE, 'w') as f:
                    f.write(str(new_step_goal))
                return jsonify({"message": "Step goal updated successfully."}), 200
            return jsonify({"message": "Invalid step goal value."}), 400
        
GOAL_FILE = 'public/goal.txt'

# New route to get and set the goal
@app.route("/goal", methods=['GET', 'POST'])
def goal():
    if request.method == 'GET':
        # Read the current goal from the file if it exists
        if os.path.isfile(GOAL_FILE):
            with open(GOAL_FILE, 'r') as f:
                current_goal = f.read().strip()
                return jsonify({"goal": int(current_goal)}), 200
        else:
            return jsonify({"goal": 1000}), 200  # Default goal if file doesn't exist

    if request.method == 'POST':
        new_goal = request.json.get('goal')
        if new_goal is not None:
            # Save the new goal to the file
            with open(GOAL_FILE, 'w') as f:
                f.write(str(new_goal))
            return jsonify({"message": "Goal updated successfully."}), 200
        return jsonify({"message": "Invalid goal value."}), 400

# ... existing routes ...
CURRENT_VALUE_FILE = 'public/current_value.txt'

# New route to get and set the current value raised
@app.route("/current_value", methods=['GET', 'POST'])
def current_value():
    if request.method == 'GET':
        # Read the current value from the file if it exists
        if os.path.isfile(CURRENT_VALUE_FILE):
            with open(CURRENT_VALUE_FILE, 'r') as f:
                current_value = f.read().strip()
                return jsonify({"current_value": int(current_value)}), 200
        else:
            return jsonify({"current_value": 0}), 200  # Default value if file doesn't exist

    if request.method == 'POST':
        new_value = request.json.get('current_value')
        if new_value is not None:
            # Save the new value to the file
            with open(CURRENT_VALUE_FILE, 'w') as f:
                f.write(str(new_value))
            return jsonify({"message": "Current value updated successfully."}), 200
        return jsonify({"message": "Invalid value."}), 400
if __name__ == '__main__':
    app.run(port=5000)
