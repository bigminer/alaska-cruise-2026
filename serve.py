#!/usr/bin/env python3
"""Local server for the slideshow with HTTP Range support (required for
seeking inside videos — python -m http.server can't do this)."""
import os, re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PORT = 8471


class RangeHandler(SimpleHTTPRequestHandler):
    range_span = None

    def do_GET(self):
        self.range_span = None
        super().do_GET()

    def send_head(self):
        path = self.translate_path(self.path)
        rng = self.headers.get("Range")
        if os.path.isdir(path) or not rng:
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None
        size = os.fstat(f.fileno()).st_size
        m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
        if not m or (m.group(1) == "" and m.group(2) == ""):
            f.close()
            return super().send_head()
        a, b = m.groups()
        if a == "":
            start = max(0, size - int(b))
            end = size - 1
        else:
            start = int(a)
            end = min(int(b), size - 1) if b else size - 1
        if start > end or start >= size:
            f.close()
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        f.seek(start)
        self.range_span = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        if self.range_span is None:
            return super().copyfile(source, outputfile)
        remaining = self.range_span
        while remaining > 0:
            chunk = source.read(min(65536, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)

    def end_headers(self):
        # advertise seekability on all responses
        if not any(h.lower() == "accept-ranges"
                   for h in getattr(self, "_headers_sent", [])):
            pass
        super().end_headers()

    def log_message(self, *args):
        pass  # quiet


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), RangeHandler).serve_forever()
