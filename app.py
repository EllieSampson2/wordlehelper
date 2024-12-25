from flask import Flask, render_template, request, jsonify, session
import os

app = Flask(__name__)
app.secret_key = 'elliesecretkey'

import requests
import numpy as np
import random
from collections import defaultdict

def file_to_array(filename):
    response = requests.get(filename)
    lines = response.text.splitlines()
    return lines

def check_win(feedback):
    for i in range(5):
        if feedback[i][1] != 'green':
            return False
    return True

def calculate_feedback(true_solution, guess):
    feedback = []
    for i in range(5):
      if guess[i] == true_solution[i]:
        feedback.append((guess[i], 'green'))
      elif guess[i] in true_solution:
        feedback.append((guess[i], 'yellow'))
      else:
        feedback.append((guess[i], 'gray'))
    return feedback

def narrow_belief_states(guess, feedback, belief_states):
    result = belief_states.copy()
    for state in belief_states:
        for i in range(5):
            if feedback[i][1] == 'green':
                if state[i] != feedback[i][0]:
                    result.remove(state)
                    break
            if feedback[i][1] == 'yellow':
                if feedback[i][0] not in state:
                    result.remove(state)
                    break
                if feedback[i][0] == state[i]:
                    result.remove(state)
                    break
            if feedback[i][1] == 'gray':
                if guess.count(feedback[i][0]) <= state.count(feedback[i][0]):
                    result.remove(state)
                    break
    return result

def bonus(num1, num2):
    if num2 == 0:
        return np.inf
    return np.sqrt(np.log(num1) / num2)

class MonteCarloTreeSearch:
    def __init__(self, all_guesses, answers):
        self.actions = all_guesses
        self.states = answers
        self.discount = 0.9
        self.N = defaultdict(int)
        self.Q = defaultdict(float)
        self.c = 1 # modify to change exploration constant
        self.m = 5000 # modify to change num of simulations

    def sum_counts(self, h):
        sum = 0
        for a in self.actions:
            key = (tuple(h), tuple(a))
            if key in self.N:
                sum += self.N[key]
        return sum

    def find_best_action(self, h, d, actions):
        best_action = None
        best_value = -np.inf
        Nh = self.sum_counts(h)
        this_action_value = -np.inf
        for a in actions:
            key = (tuple(h), tuple(a))
            if Nh == 0:
                this_action_value = self.Q[key]
            else:
                this_action_value = self.Q[key] + self.c * bonus(Nh, self.N[key])
            if this_action_value > best_value:
                best_value = this_action_value
                best_action = a
        return best_action

    def explore(self, h, d, actions):
        Nh = self.sum_counts(h)
        return self.find_best_action(h, d, actions)

    def simulate(self, s, h, d, actions):
        if d == 0:
            return -1
        for a in actions:
            key = (tuple(h), tuple(a))
            if key not in self.N:
                self.N[key] = 0
                self.Q[key] = 0
        a = self.explore(h, d, actions)
        o = calculate_feedback(s, a)
        if check_win(o):
            return 1
        next_actions = narrow_belief_states(a, o, actions)
        q = self.discount * self.simulate(s, h + [a] + [tuple(o)], d - 1, next_actions)
        key = (tuple(h), tuple(a))
        self.N[key] += 1
        self.Q[key] += (q - self.Q[key]) / self.N[key]
        return q

    def run_simulations(self, b, d, h=[]):
        if len(b) > 100:
            b = random.sample(b, 100)
        for i in range(self.m):
            s = random.choice(b)
            self.simulate(s, h, d, b)
        best_action = None
        best_action_value = -np.inf
        this_action_value = -np.inf
        for a in self.actions:
            key = (tuple(h), tuple(a))
            if key in self.N:
                this_action_value = self.Q[key]
            if this_action_value > best_action_value:
                best_action_value = this_action_value
                best_action = a
        return best_action

# UNSURE STARTING BELOW

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/start_game", methods=["POST"])
def start_game():
    # Reset the guesses when starting a new game
    session["guesses"] = []  # Clear the guesses stored in the session
    session.modified = True
    return jsonify({"message": "Game started", "guesses": session["guesses"]})

@app.route("/next_guess", methods=["POST"])
def next_guess():
    data = request.json
    feedback = data.get("feedback", [])
    current_guess = data.get("currentGuess", "")

    # Initialize the guesses list if it doesn't exist
    if "guesses" not in session:
        session["guesses"] = []
        session.modified = True

    # Store the guess and feedback as a 2D array (letter, feedback)
    guess_with_feedback = [(current_guess[i], feedback[i]) for i in range(len(current_guess))]
    session["guesses"].append((guess_with_feedback, current_guess))
    session.modified = True
    prev_guesses = session["guesses"]
    guesses_remaining = 6 - len(prev_guesses)
    if guesses_remaining == 6: 
    	return 'salet'
    filename_answers = 'https://www.aeio.win/answers.txt'
    answers = file_to_array(filename_answers)
    random.shuffle(answers)
    for item in prev_guesses: 
        answers = narrow_belief_states(item[1], item[0], answers)
    my_tree = MonteCarloTreeSearch(answers, answers)
    next_guess = my_tree.run_simulations(answers, guesses_remaining)

    return jsonify({
        "next_guess": next_guess,
        "previous_guesses": session["guesses"]  # Send back the previous guesses
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
