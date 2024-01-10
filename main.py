from flask import Flask, request, jsonify
import os
import seo

app = Flask(__name__)


@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route("/seo", methods=["POST"])
def handle_seo():
    ww = request.json
    print(request.json)
    print(request.get_json())
    print(ww.get('url'))
    result = seo.get_geolocation()
    return jsonify(result), 200


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
