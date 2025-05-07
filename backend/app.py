from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pathlib import Path
import uuid
import json
import sys
import os

# Add root project path to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from examples.init_schema import run_init_schema
from examples.upload_vote import run_upload_vote
from examples.get_results import run_get_results

app = Flask(__name__, static_folder="../frontend")
CORS(app)

# In-memory storage for sessions
sessions = {}

@app.route('/')
def serve_index():
    return send_file(Path(app.static_folder) / 'index.html')

#Serve vote.html dynamically based on session_id
@app.route('/vote/<session_id>')
def serve_vote(session_id):
    return send_file(Path(app.static_folder) / 'vote.html')

# Route to handle initialization of voting schema and slot names
@app.route("/init", methods=["POST"])
def init():
    data = request.get_json()
    slots = data.get("slots", 5)
    slot_names = data.get("slot_names", [f"Option {i+1}" for i in range(slots)])
    question = data.get("question", "Secret Voting")

    # Generate a unique session ID for this voting session
    session_id = str(uuid.uuid4())

    # Initialize the schema and generate the config file
    config_path = "examples/bvote_config_voting.json"  # Ensure this matches your expected config path
    message = run_init_schema(slots=slots, config_path=config_path)

    # Store session data (slot names and initial votes)
    sessions[session_id] = {
        "voting_open": True, # Track if voting is still open
        "question": question
    }

    # Store slot names in a separate file (optional)
    with open(f"examples/slot_names_{session_id}.txt", "w") as f:
        f.write("\n".join(slot_names))
    
    # Return session ID to be used for voting and results
    return jsonify(message=message, session_id=session_id)

# Route to handle voting (users submit their votes here)
@app.route("/vote/<session_id>", methods=["POST"])
def vote(session_id):
    # Check if the session exists
    session = sessions.get(session_id)
    if not session:
        return jsonify(message="Session not found."), 404
    if not session.get("voting_open", True):
        return jsonify(message="Voting has ended."), 200
    data = request.get_json()
    voter_id = data["voter_id"]
    vote_choice = data["choice"]

    try:
        message = run_upload_vote(voter_id, vote_choice, config_path="examples/bvote_config_voting.json")
        return jsonify(message=message)

    except ValueError as e:
        print(f"Known error: {e}")
        return jsonify(message=str(e)), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify(message="Internal server error."), 500

@app.route("/vote-question/<session_id>", methods=["GET"])
def get_vote_question(session_id):
    session = sessions.get(session_id)
    if not session:
        return jsonify(message="Session not found."), 404
    return jsonify(question=session.get("question", "Secret Voting"))

# Return vote optionsthe list of options and their current vote counts
@app.route("/vote-options/<session_id>", methods=["GET"])
def get_vote_options(session_id):
    try:
        with open(f"examples/slot_names_{session_id}.txt") as f:
            slot_names = [line.strip() for line in f]
        return jsonify(slot_names=slot_names)
    except FileNotFoundError:
        return jsonify(message="Slot names not found."), 404

# Route to retrieve the voting results
@app.route("/results/<session_id>", methods=["GET"])
def get_results(session_id):
    if session_id not in sessions:
        return jsonify(message="Session not found."), 404

    try:
        # Load slot names
        with open(f"examples/slot_names_{session_id}.txt") as f:
            slot_names = [line.strip() for line in f]

        result_vector = run_get_results(config_path="examples/bvote_config_voting.json")
        results_named = dict(zip(slot_names, result_vector))
        return jsonify(results_named)
    except Exception as e:
        print(f"Error retrieving results from nilDB: {e}")
        return jsonify(message="Failed to retrieve results."), 500

# Get total vote count from nilDB
@app.route("/vote-count/<session_id>", methods=["GET"])
def vote_count(session_id):
    if session_id not in sessions:
        return jsonify(message="Session not found."), 404

    try:
        result_vector = run_get_results(config_path="examples/bvote_config_voting.json")
        total_votes = sum(result_vector)
        return jsonify(total_votes=total_votes)
    except Exception as e:
        print(f"Error retrieving vote count: {e}")
        return jsonify(message="Failed to retrieve vote count."), 500

# 🔥 Add this new route to finish voting
@app.route("/vote-finish/<session_id>", methods=["POST"])
def finish_voting(session_id):
    session = sessions.get(session_id)
    if not session:
        return jsonify(message="Session not found."), 404
    session["voting_open"] = False  # 🔥 NEW: Mark voting as finished
    return jsonify(message="Voting has been finished.")

# 🔥 Add this new route to check if voting is still open
@app.route("/voting-status/<session_id>", methods=["GET"])
def voting_status(session_id):
    session = sessions.get(session_id)
    if not session:
        return jsonify(message="Session not found."), 404
    if not session.get("voting_open", True):
        return jsonify(voting_open=False), 200
    return jsonify(voting_open=True, message="Voting is open."), 200


if __name__ == "__main__":
    app.run(debug=True)
