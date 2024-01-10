from flask import Flask, request, jsonify
import os
import seo

app = Flask(__name__)


@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route("/seo", methods=["POST"])
def handle_seo():
    print(request)
    print(request.get_data())
    print(request.get_json())
    ww = request.get_data()
    result = seo.get_geolocation(ww["url"])
    return jsonify(result), 200


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
