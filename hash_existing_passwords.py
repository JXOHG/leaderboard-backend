import json
from werkzeug.security import generate_password_hash

def hash_existing_passwords():
    try:
        # Load existing user data
        with open('users.json', 'r') as f:
            users = json.load(f)
        
        # Hash each plaintext password
        for username, password in users.items():
            # Check if password is already hashed by checking length or a prefix if applicable
            if not password.startswith('pbkdf2:sha256'):
                users[username] = generate_password_hash(password)
        
        # Save updated user data with hashed passwords
        with open('users.json', 'w') as f:
            json.dump(users, f)
        
        print("Successfully converted all plaintext passwords to hashed passwords.")
    
    except Exception as e:
        print("Error updating passwords:", e)

# Run the script
hash_existing_passwords()
