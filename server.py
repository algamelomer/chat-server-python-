import socket
import threading

class ChatServer:
    def __init__(self, host='localhost', port=8903):
        self.host = host
        self.port = port
        self.client_list 
        self.lock = threading.Lock()

    def broadcast(self, message, exclude=None):
        """Broadcast a message to all clients except the excluded one."""
        with self.lock:
            for client_socket, _ in self.client_list:
                if client_socket != exclude:
                    try:
                        client_socket.sendall(message.encode())
                    except Exception as e:
                        print(f"Broadcast error: {e}")

    def handle_client(self, client_socket):
        """Handle communication with a single client."""
        try:
            # Receive username
            username = client_socket.makefile('r').readline().strip()
            if not username.startswith("LOGIN "):
                client_socket.sendall(b"ERROR Invalid login format\n")
                client_socket.close()
                return
            username = username[6:]
            
            # Check if username is unique
            with self.lock:
                if any(u == username for _, u in self.client_list):
                    client_socket.sendall(b"ERROR Username already taken\n")
                    client_socket.close()
                    return
                self.client_list.append((client_socket, username))
            
            # Send confirmation and current user list
            client_socket.sendall(b"OK\n")
            user_list = " ".join(u for _, u in self.client_list)
            client_socket.sendall(f"USER_LIST {user_list}\n".encode())
            self.broadcast(f"USER_JOIN {username}\n", exclude=client_socket)

            # Main communication loop
            while True:
                message = client_socket.makefile('r').readline().strip()
                if not message:  # Client disconnected
                    break
                if message.startswith("MSG "):
                    self.broadcast(f"MSG_FROM {username} {message[4:]}\n")
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            # Clean up on disconnect
            with self.lock:
                self.client_list = [(s, u) for s, u in self.client_list if s != client_socket]
            self.broadcast(f"USER_LEAVE {username}\n")
            client_socket.close()

    def start(self):
        """Start the server and listen for incoming connections."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        print(f"Server listening on {self.host}:{self.port}")
        
        while True:
            client_socket, addr = server_socket.accept()
            print(f"New connection from {addr}")
            thread = threading.Thread(target=self.handle_client, args=(client_socket,))
            thread.start()

if __name__ == "__main__":
    server = ChatServer()
    server.start()