from flask import Flask, render_template, send_file
import os

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get-json")
def get_json():
    file_path = os.path.join(
        app.root_path,
    "test.geojson"
    )

    return send_file(
        file_path,
        mimetype="application/geo+json"
    )

if __name__ == "__main__":
    app.run(debug=True)