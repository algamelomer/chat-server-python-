import flet as ft
import socket
import threading
import queue
import time

class ChatClient:
    def __init__(self, host='localhost', port=12345):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.username = None
        self.selected_user = None
        self.message_queue = queue.Queue()
        # UI components
        self.user_list_container = ft.Column(scroll=ft.ScrollMode.AUTO)
        self.chat_display = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        self.message_input = ft.TextField(label="Type a message", expand=True)
        self.send_btn = ft.ElevatedButton("Send")
        self.is_users_page = False  # Track if on users page for refresh

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            threading.Thread(target=self.receive_messages, daemon=True).start()
        except Exception as e:
            print(f"Connection failed: {e}")
            self.connected = False

    def send_message(self, message):
        if self.connected and message:
            try:
                self.socket.sendall(message.encode())
            except:
                self.connected = False

    def receive_messages(self):
        while self.connected:
            try:
                message = self.socket.recv(1024).decode().strip()
                if message:
                    self.message_queue.put(message)
            except:
                self.connected = False
                break

    def get_message(self):
        try:
            return self.message_queue.get_nowait()
        except queue.Empty:
            return None

def main(page: ft.Page):
    page.title = "Chat Application"
    client = ChatClient()
    client.connect()

    def process_messages():
        while True:
            msg = client.get_message()
            if msg:
                if msg.startswith("LOGIN_OK:"):
                    client.username = msg.split(":", 1)[1]
                    page.go("/users")
                elif msg == "REGISTER_OK":
                    page.go("/login")
                    page.add(ft.Text("Registration successful, please login", color=ft.Colors.GREEN))
                elif msg.startswith("ERROR:"):
                    page.add(ft.Text(msg[6:], color=ft.Colors.RED))
                elif msg.startswith("ALL_USERS:"):
                    all_users, active = msg[10:].split(":", 1)
                    all_users = all_users.split(",") if all_users else []
                    active_users = active.split(",") if active else []
                    update_user_list(all_users, active_users)
                elif msg.startswith("HISTORY:"):
                    client.chat_display.controls.clear()
                    history = msg[8:].split("|")
                    for h in history:
                        if h:
                            sender, message = h.split(":", 1)
                            client.chat_display.controls.append(ft.Text(f"{sender}: {message}"))
                elif msg.startswith("MESSAGE:"):
                    sender, message = msg[8:].split(":", 1)
                    if sender == client.selected_user:
                        client.chat_display.controls.append(ft.Text(f"{sender}: {message}"))
                page.update()
            time.sleep(0.1)

    def refresh_users_page():
        while True:
            if client.is_users_page and client.connected:
                client.send_message("GET_ALL_USERS")
            time.sleep(0.5)  # Refresh every 500ms

    # Start message processing and user refresh threads
    threading.Thread(target=process_messages, daemon=True).start()
    threading.Thread(target=refresh_users_page, daemon=True).start()

    def update_user_list(all_users, active_users):
        client.user_list_container.controls.clear()
        for user in all_users:
            if user and user != client.username:
                status = "Online" if user in active_users else "Offline"
                button = ft.TextButton(
                    f"{user} ({status})",
                    on_click=lambda e, u=user: select_user(u)
                )
                client.user_list_container.controls.append(button)
        page.update()

    def select_user(user):
        client.selected_user = user
        page.go(f"/chat/{user}")
        client.send_message(f"GET_HISTORY {user}")

    def send_message(recipient, message):
        if recipient and message.strip():
            client.send_message(f"SEND {recipient} {message}")
            client.chat_display.controls.append(ft.Text(f"You: {message}"))
            client.message_input.value = ""
            page.update()

    def login_page():
        client.is_users_page = False
        page.controls.clear()
        username = ft.TextField(label="Username", width=300)
        password = ft.TextField(label="Password", password=True, width=300)
        error_text = ft.Text("", color=ft.Colors.RED)
        def attempt_login(e):
            if not username.value or not password.value:
                error_text.value = "Username and password cannot be empty"
            else:
                client.send_message(f"LOGIN {username.value} {password.value}")
            page.update()
        login_btn = ft.ElevatedButton("Login", on_click=attempt_login)
        register_btn = ft.ElevatedButton("Go to Register", on_click=lambda e: page.go("/register"))
        page.add(ft.Column([username, password, error_text, login_btn, register_btn], alignment=ft.MainAxisAlignment.CENTER))

    def register_page():
        client.is_users_page = False
        page.controls.clear()
        username = ft.TextField(label="Username", width=300)
        password = ft.TextField(label="Password", password=True, width=300)
        confirm_password = ft.TextField(label="Confirm Password", password=True, width=300)
        error_text = ft.Text("", color=ft.Colors.RED)
        def attempt_register(e):
            if not username.value or not password.value:
                error_text.value = "Username and password cannot be empty"
            elif password.value != confirm_password.value:
                error_text.value = "Passwords do not match"
            else:
                client.send_message(f"REGISTER {username.value} {password.value}")
            page.update()
        register_btn = ft.ElevatedButton("Register", on_click=attempt_register)
        back_btn = ft.ElevatedButton("Back to Login", on_click=lambda e: page.go("/login"))
        page.add(ft.Column([username, password, confirm_password, error_text, register_btn, back_btn], alignment=ft.MainAxisAlignment.CENTER))

    def users_page():
        client.is_users_page = True
        page.controls.clear()
        client.send_message("GET_ALL_USERS")
        page.add(ft.Column([
            ft.Text(f"Logged in as: {client.username}"),
            ft.Text("Users"),
            client.user_list_container,
            ft.ElevatedButton("Logout", on_click=lambda e: logout())
        ]))

    def chat_page(user):
        client.is_users_page = False
        page.controls.clear()
        client.send_btn.on_click = lambda e: send_message(user, client.message_input.value)
        page.add(ft.Column([
            ft.Text(f"Chatting with: {user}"),
            client.chat_display,
            ft.Row([client.message_input, client.send_btn]),
            ft.ElevatedButton("Back to Users", on_click=lambda e: page.go("/users"))
        ]))

    def logout():
        client.is_users_page = False
        if client.connected:
            client.connected = False
            client.socket.close()
        client.username = None
        client.selected_user = None
        page.go("/login")

    def route_change(route):
        page.controls.clear()
        if page.route == "/login":
            login_page()
        elif page.route == "/register":
            register_page()
        elif page.route == "/users":
            users_page()
        elif page.route.startswith("/chat/"):
            user = page.route.split("/")[-1]
            client.selected_user = user
            chat_page(user)
        page.update()

    page.on_route_change = route_change
    page.go("/login")

if __name__ == "__main__":
    ft.app(target=main)