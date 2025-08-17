import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the connection string from your .env file
MONGO_URI = os.getenv('MONGO_URI')

print("--- Database Connection Test ---")
print(f"Attempting to connect with URI: {MONGO_URI}")

# Check if the URI was even found
if not MONGO_URI:
    print("\n[FATAL ERROR]: The MONGO_URI was not found in your .env file.")
    print("Please ensure the .env file exists and the variable is named MONGO_URI.")
else:
    try:
        # Try to create a new client and connect to the server
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        
        # The ismaster command is cheap and does not require auth.
        # It will trigger a connection attempt
        client.admin.command('ismaster')
        
        print("\n[SUCCESS]: MongoDB connection established successfully!")
        
    except ConnectionFailure as e:
        print(f"\n[CONNECTION FAILED]: Could not connect to MongoDB.")
        print(f"Reason: {e}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR]: An error occurred: {e}")

print("--- Test Finished ---")