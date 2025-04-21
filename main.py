"""
Main module to satisfy gunicorn's entry point requirements.
This file is needed because the Replit workflow is configured to run gunicorn main:app
"""

from flask import Flask, render_template, jsonify

# Create Flask application
app = Flask(__name__)

@app.route('/')
def index():
    """Render the index page"""
    return jsonify({"status": "ok", "message": "Telegram bot is running in a separate process"})

# Keep-alive endpoint
@app.route('/keep-alive')
def keep_alive():
    """Keep-alive endpoint for health checks"""
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)