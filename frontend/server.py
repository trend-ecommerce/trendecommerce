# TrendEcommerce AI - Frontend Local Server
# Executa um servidor HTTP local para testar a interface de autenticação.


import http.server
import socketserver
import os
import sys
import webbrowser

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        # Redirecionamento amigável para rotas diretas de SPA (ex: /ranking -> /#/ranking)
        clean_path = self.path.split('?')[0].split('#')[0].strip('/')
        if clean_path:
            target_file = os.path.join(DIRECTORY, clean_path)
            # Se não for um arquivo/diretório existente e não possuir extensão (.css, .js, .png, etc.)
            if not os.path.exists(target_file) and '.' not in os.path.basename(clean_path):
                self.send_response(302)
                self.send_header('Location', f"/#/{clean_path}")
                self.end_headers()
                return
        return super().do_GET()

    def log_message(self, format, *args):
        print(f"[TrendEcommerce Server] {self.address_string()} - {format % args}")

def run_server():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    os.chdir(DIRECTORY)
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}"
        print("=" * 60)
        print("🚀 TrendEcommerce AI - Frontend Server Iniciado")
        print(f"📡 Acesse: {url}")
        print("=" * 60)
        print("Pressione Ctrl+C para encerrar o servidor.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Servidor encerrado.")

if __name__ == "__main__":
    run_server()