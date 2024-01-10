from flask import Flask, request, jsonify
import os
import seo

app = Flask(__name__)


@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route("/seo", methods=["POST"])
def handle_seo():
    ww = request.form
    print(request.form)
    print(request.json)
    result = seo.get_geolocation(ww["url"])
    return jsonify(result), 200


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
