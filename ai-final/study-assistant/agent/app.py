"""
Flask Application for the Personal Study Assistant Agent Client.

Provides a web interface for interacting with the Study Assistant agent.
"""

import io

from flask import Flask, render_template, request, jsonify
import markdown
import bleach
import PyPDF2
from werkzeug.utils import secure_filename
from agent_client import AgentClient

MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PDF_CHARS = 4000

app = Flask(__name__)


def _set_external_link_attributes(attrs, new=False):
    """Force safe external link attributes for rendered markdown links."""
    href_key = (None, 'href')
    href_value = attrs.get(href_key, '')
    if isinstance(href_value, str) and href_value.startswith(('http://', 'https://')):
        attrs[(None, 'target')] = '_blank'
        attrs[(None, 'rel')] = 'noopener noreferrer nofollow'
    return attrs


def render_markdown_to_safe_html(text: str) -> str:
    """Convert markdown to safe HTML for display in chat bubbles."""
    raw_html = markdown.markdown(
        text,
        extensions=['extra', 'sane_lists', 'nl2br']
    )

    allowed_tags = [
        'p', 'br', 'hr', 'blockquote',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li',
        'strong', 'em', 'code', 'pre',
        'a',
        'table', 'thead', 'tbody', 'tr', 'th', 'td'
    ]
    allowed_attrs = {
        'a': ['href', 'title', 'target', 'rel'],
        'code': ['class']
    }

    safe_html = bleach.clean(
        raw_html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=['http', 'https', 'mailto'],
        strip=True
    )

    safe_html = bleach.linkify(
        safe_html,
        skip_tags=['pre', 'code'],
        callbacks=[_set_external_link_attributes]
    )
    return safe_html


# Initialise the agent client once at startup
try:
    agent = AgentClient()
except Exception as e:
    print(f"Warning: Failed to initialise agent client: {e}")
    agent = None


@app.route('/')
def index():
    """Render the main chat interface."""
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    """Accept a user message and return the agent's response."""
    if not agent:
        return jsonify({
            'error': 'Agent client not initialised. Check your .env configuration.'
        }), 500

    data = request.json
    user_message = (data or {}).get('message', '').strip()

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    if len(user_message) > 10000:
        return jsonify({'error': 'Message too long'}), 400

    response = agent.send_message(user_message)
    response_html = render_markdown_to_safe_html(response)

    return jsonify({
        'response': response,
        'response_html': response_html
    })


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

    # Validate PDF magic bytes — do not trust extension alone
    if not file_bytes.startswith(b'%PDF'):
        return jsonify({'error': 'File does not appear to be a valid PDF'}), 400

    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or '' for page in reader.pages]
        text = '\n'.join(pages).strip()
    except Exception as e:
        return jsonify({'error': f'Could not read PDF: {e}'}), 422

    if not text:
        return jsonify({'error': 'No text could be extracted (the PDF may be image-only)'}), 422

    return jsonify({
        'filename': filename,
        'content': text[:MAX_PDF_CHARS],
        'truncated': len(text) > MAX_PDF_CHARS
    })


if __name__ == '__main__':
    app.run(debug=False, port=5000)
