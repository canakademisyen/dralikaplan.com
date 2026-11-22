"""Local preview server that tells the browser never to reuse old copies.

Usage: python3 tools/serve.py [port]   (serves the built site in dist/)
"""
import functools
import http.server
import os
import sys


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dist")
    handler = functools.partial(NoCacheHandler, directory=root)
    print(f"Serving {root} at http://localhost:{port}")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
