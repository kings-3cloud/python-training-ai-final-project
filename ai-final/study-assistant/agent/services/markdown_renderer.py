"""
MarkdownRenderer — converts Markdown text to sanitised HTML.

Single Responsibility: only responsible for safe Markdown-to-HTML conversion.
"""
import bleach
import markdown


class MarkdownRenderer:
    """Renders Markdown to bleach-sanitised HTML safe for browser display."""

    _ALLOWED_TAGS = [
        'p', 'br', 'hr', 'blockquote',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li',
        'strong', 'em', 'code', 'pre',
        'a',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
    ]
    _ALLOWED_ATTRS = {
        'a': ['href', 'title', 'target', 'rel'],
        'code': ['class'],
    }

    def render(self, text: str) -> str:
        """Convert *text* from Markdown to sanitised HTML."""
        raw_html = markdown.markdown(
            text,
            extensions=['extra', 'sane_lists', 'nl2br']
        )
        safe_html = bleach.clean(
            raw_html,
            tags=self._ALLOWED_TAGS,
            attributes=self._ALLOWED_ATTRS,
            protocols=['http', 'https', 'mailto'],
            strip=True,
        )
        return bleach.linkify(
            safe_html,
            skip_tags=['pre', 'code'],
            callbacks=[self._external_link_attrs],
        )

    @staticmethod
    def _external_link_attrs(attrs: dict, new: bool = False) -> dict:
        """Force safe attributes on external links."""
        href_key = (None, 'href')
        href = attrs.get(href_key, '')
        if isinstance(href, str) and href.startswith(('http://', 'https://')):
            attrs[(None, 'target')] = '_blank'
            attrs[(None, 'rel')] = 'noopener noreferrer nofollow'
        return attrs
