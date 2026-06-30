# fetch_url_content tool: fetches and returns the text content of a given URL.

import io
import httpx

MAX_CHARS = 4000


def fetch_url_content(url: str) -> str:
    """
    Fetch the text content of a URL.

    - For .pdf URLs, extracts text via PyPDF2.
    - For all other URLs, returns the response body as plain text.
    - Always truncates to MAX_CHARS characters.
    - Returns an error string instead of raising on failure.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            response = client.get(url)
            response.raise_for_status()

        if url.lower().endswith(".pdf"):
            try:
                import PyPDF2  # noqa: PLC0415

                reader = PyPDF2.PdfReader(io.BytesIO(response.content))
                pages = [page.extract_text() or "" for page in reader.pages]
                text = "\n".join(pages)
            except ImportError:
                return "Error: PyPDF2 is not installed. Run `pip install pypdf2`."
            except Exception as pdf_err:
                return f"Error reading PDF: {pdf_err}"
        else:
            text = response.text

        return text[:MAX_CHARS]

    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} when fetching {url}"
    except httpx.RequestError as e:
        return f"Error: Could not reach {url} — {e}"
    except Exception as e:
        return f"Error: Unexpected failure — {e}"


if __name__ == "__main__":
    # Quick smoke-test — replace with any URL you like
    test_url = "https://example.com"
    result = fetch_url_content(test_url)
    print(f"--- fetch_url_content({test_url!r}) ---")
    print(result[:500])
