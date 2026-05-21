from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from sentence_transformers import SentenceTransformer

print("Loading model...")
model = SentenceTransformer('all-mpnet-base-v2')
print("Model loaded.")

class EmbedHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        req = json.loads(post_data.decode('utf-8'))
        text = req.get('text', '')
        
        embedding = model.encode([text])[0].tolist()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'embedding': embedding}).encode('utf-8'))

def run(server_class=HTTPServer, handler_class=EmbedHandler, port=8001):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting embed server on port {port}...')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
