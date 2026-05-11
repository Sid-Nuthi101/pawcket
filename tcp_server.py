import socket
from pawcket import HTTPRequest, yarn, make_response
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 9200  # Port to listen on

def handle_connection(conn, yarnball: yarn):
    # Configure reciever
    data = conn.recv(4096)
    data = data.decode(errors="replace")
    request = HTTPRequest(data)
    
    # Execute the route's function
    response = yarnball.route_to_thread(request)
    
    # Send the response data to the client
    conn.sendall(str(response).encode("utf-8"))

def start_tcp_server(yarnball: yarn):
    print(f"Port open on http://{HOST}:{PORT}")
    print(f"Found routes: {yarnball.threads}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # Disable Naggle
        s.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )
        s.bind((HOST, PORT))
        s.listen()
        while True:
            conn, addr = s.accept()
            with conn:
                # Handle the connection
                handle_connection(conn, yarnball)
