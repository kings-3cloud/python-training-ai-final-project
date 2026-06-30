"""
Flask Application for the Personal Study Assistant Agent Client.

Single Responsibility: HTTP route handling only.
All business logic is delegated to AgentClient, MarkdownRenderer,
PdfExtractor, and the factories module.
"""
import logging
import os

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

from factories import create_agent_client
from services.markdown_renderer import MarkdownRenderer
from services.pdf_extractor import PdfExtractor

load_dotenv()

logger = logging.getLogger(__name__)

MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MB

app = Flask(__name__)

# ── Application-level collaborators (created once at startup) ─────────────────
_renderer = MarkdownRenderer()
_extractor = PdfExtractor()

_current_mode = os.environ.get("DEFAULT_MODE", "online")
try:
    agent = create_agent_client(_current_mode)
except Exception as exc:
    logger.warning("Failed to initialise agent client: %s", exc)
    agent = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Render the main chat interface."""
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    """Accept a user message and return the agent's response."""
    if not agent:
        return jsonify({'error': 'Agent client not initialised. Check your .env configuration.'}), 500

    data = request.json
    user_message = (data or {}).get('message', '').strip()

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    if len(user_message) > 10000:
        return jsonify({'error': 'Message too long'}), 400

    response = agent.send_message(user_message)
    return jsonify({
        'response': response,
        'response_html': _renderer.render(response),
    })


@app.route('/mode', methods=['GET'])
def get_mode():
    """Return the current agent mode."""
    return jsonify({'mode': agent.mode if agent else _current_mode})


@app.route('/mode', methods=['POST'])
def set_mode():
    """Switch between online and offline agent modes."""
    global agent, _current_mode
    data = request.json or {}
    new_mode = data.get('mode', '').strip().lower()

    if new_mode not in ('online', 'offline'):
        return jsonify({'error': 'mode must be "online" or "offline"'}), 400

    if agent and agent.mode == new_mode:
        return jsonify({'mode': new_mode, 'changed': False})

    try:
        agent = create_agent_client(new_mode)
        _current_mode = new_mode
        return jsonify({'mode': new_mode, 'changed': True})
    except Exception as exc:
        return jsonify({'error': f'Could not switch to {new_mode} mode: {exc}'}), 500


@app.route('/reset', methods=['POST'])
def reset():
    """Reset the conversation history to start a fresh study session."""
    if agent:
        agent.reset_session()
    return jsonify({'status': 'success'})


@app.route('/upload', methods=['POST'])
def upload_pdf():
    """Accept a PDF file upload, extract its text, and return the content."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400

    file_bytes = file.read()
    if len(file_bytes) > MAX_PDF_SIZE:
        return jsonify({'error': 'File too large (max 10 MB)'}), 400

    try:
        text, truncated = _extractor.extract(file_bytes)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 422
    except Exception as exc:
        return jsonify({'error': f'Could not read PDF: {exc}'}), 422

    return jsonify({
        'filename': filename,
        'content': text,
        'truncated': truncated,
    })


if __name__ == '__main__':
    app.run(debug=False, port=5000)

