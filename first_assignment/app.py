from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "message": "Backend is running"
    })

@app.route("/hello")
def hello():
    return jsonify({
        "message": "Hello, World!"
    })

@app.route("/status")
def status():
    return jsonify({
        "status": "ok"
    })

if __name__ == "__main__":
    app.run(debug=True)