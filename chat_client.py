import flet as ft
import socket
import threading
import queue
import time
from datetime import datetime

class ChatClient:
    def __init__(self, host='localhost', port=12345):
        print("[DEBUG] Initializing ChatClient with host:", host, "and port:", port)
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.username = None
        self.selected_user = None
        self.message_queue = queue.Queue()
        self.theme = ft.ThemeMode.LIGHT
        
        # UI Components
        self.user_list_container = ft.ListView(expand=True, spacing=10, auto_scroll=True)
        self.chat_display = ft.ListView(
            expand=True,
            spacing=10,
            padding=20,
            auto_scroll=True
        )
        self.message_input = ft.TextField(
            label="Type your message...",
            border_color=ft.Colors.BLUE_400,
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=5,
            on_submit=lambda e: self.send_current_message(),
            content_padding=10
        )
        self.send_btn = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            icon_color=ft.Colors.BLUE_400,
            tooltip="Send",
            on_click=lambda e: self.send_current_message()
        )

    def connect(self):
        print("[DEBUG] Connecting to server:", self.host, ":", self.port)
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print("[DEBUG] Server connection successful")
            threading.Thread(target=self.receive_messages, daemon=True).start()
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            self.connected = False

    def send_message(self, message):
        if self.connected and message:
            try:
                self.socket.sendall(message.encode())
                return True
            except Exception as e:
                print(f"[ERROR] Failed to send message: {e}")
                self.connected = False
                return False
        return False

    def send_current_message(self):
        msg = self.message_input.value.strip()
        if msg and self.selected_user:
            if self.send_message(f"SEND {self.selected_user} {msg}"):
                self.add_message_to_chat(msg, is_mine=True)
                self.message_input.value = ""
                self.page.update()

    def add_message_to_chat(self, text, is_mine, sender=None):
        sender_name = "Me" if is_mine else sender
        timestamp = datetime.now().strftime("%H:%M")
        self.chat_display.controls.append(
            ft.Container(
                ft.Column([
                    ft.Row([
                        ft.Text(sender_name, weight=ft.FontWeight.BOLD, size=12),
                        ft.Text(timestamp, size=10, color=ft.Colors.GREY_500)
                    ], spacing=5),
                    ft.Text(text, color=ft.Colors.WHITE if is_mine else ft.Colors.BLACK)
                ], spacing=3),
                alignment=ft.alignment.center_right if is_mine else ft.alignment.center_left,
                padding=ft.padding.symmetric(horizontal=15, vertical=10),
                margin=ft.margin.only(
                    left=50 if not is_mine else 0,
                    right=0 if not is_mine else 50,
                    top=5,
                    bottom=5
                ),
                border_radius=15,
                bgcolor=ft.Colors.BLUE_400 if is_mine else ft.Colors.GREY_200,
                border=ft.border.all(1, ft.Colors.GREY_300 if not is_mine else ft.Colors.BLUE_600)
            )
        )
        self.chat_display.scroll_to(offset=-1, duration=300)

    def receive_messages(self):
        while self.connected:
            try:
                message = self.socket.recv(1024).decode().strip()
                if message:
                    self.message_queue.put(message)
                else:
                    self.connected = False
            except Exception as e:
                print(f"[ERROR] Connection error: {e}")
                self.connected = False
                break

    def get_message(self):
        try:
            return self.message_queue.get_nowait()
        except queue.Empty:
            return None

def main(page: ft.Page):
    page.title = "Chat Application"
    page.window_width = 400
    page.window_height = 700
    page.theme_mode = ft.ThemeMode.LIGHT
    
    client = ChatClient()
    client.page = page
    client.connect()

    def show_snack(message, color=ft.Colors.GREEN):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=color,
            behavior=ft.SnackBarBehavior.FLOATING
        )
        page.snack_bar.open = True
        page.update()

    client.show_snack = show_snack
    
    def process_messages():
        while True:
            msg = client.get_message()
            if msg:
                if msg.startswith("LOGIN_OK:"):
                    client.username = msg.split(":", 1)[1]
                    page.go("/users")

                elif msg == "REGISTER_OK":
                    page.go("/login")
                    show_snack("Registration successful, please login", ft.Colors.GREEN)

                elif msg.startswith("ERROR:"):
                    show_snack(msg[6:], ft.Colors.RED)

                elif msg.startswith("ALL_USERS:"):
                    try:
                        _, users_part = msg.split(":", 1)
                        if ":" in users_part:
                            all_users, active = users_part.split(":", 1)
                        else:
                            all_users = users_part
                            active = ""
                        all_users = all_users.split(",") if all_users else []
                        active_users = active.split(",") if active else []
                        update_user_list(all_users, active_users)
                    except Exception as e:
                        print(f"[ERROR] User list parsing failed: {e}")

                elif msg.startswith("HISTORY:"):
                    client.chat_display.controls.clear()
                    history = msg[8:].split("|")
                    for h in history:
                        if h:
                            try:
                                sender, message = h.split(":", 1)
                                client.add_message_to_chat(message, sender == client.username, sender)
                            except ValueError:
                                print("[ERROR] Invalid history format")

                elif msg.startswith("MESSAGE:"):
                    try:
                        sender, message = msg[8:].split(":", 1)
                        if sender == client.selected_user:
                            client.add_message_to_chat(message, False, sender)
                    except ValueError:
                        print("[ERROR] Invalid message format")

                page.update()
            time.sleep(0.1)

    def update_user_list(all_users, active_users):
        client.user_list_container.controls.clear()
        
        # Active users
        active_tiles = [
            ft.ListTile(
                leading=ft.Icon(ft.Icons.PERSON, color=ft.Colors.GREEN),
                title=ft.Text(user, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text("Online", color=ft.Colors.GREEN),
                trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT),
                on_click=lambda e, u=user: select_user(u)
            )
            for user in active_users if user and user != client.username
        ]
        
        # Inactive users
        inactive_tiles = [
            ft.ListTile(
                leading=ft.Icon(ft.Icons.PERSON_OUTLINE, color=ft.Colors.GREY),
                title=ft.Text(user),
                subtitle=ft.Text("Offline", color=ft.Colors.GREY),
                trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT),
                on_click=lambda e, u=user: select_user(u)
            )
            for user in all_users if user and user != client.username and user not in active_users
        ]
        
        if active_tiles:
            client.user_list_container.controls.append(
                ft.Text("Active Users", size=16, weight=ft.FontWeight.BOLD)
            )
            client.user_list_container.controls.extend(active_tiles)
        
        if inactive_tiles:
            client.user_list_container.controls.append(
                ft.Text("Inactive Users", size=16, weight=ft.FontWeight.BOLD)
            )
            client.user_list_container.controls.extend(inactive_tiles)
        
        page.update()

    def select_user(user):
        client.selected_user = user
        page.go(f"/chat/{user}")
        client.send_message(f"GET_HISTORY {user}")

    def login_page():
        username = ft.TextField(label="Username", border_color=ft.Colors.BLUE_400)
        password = ft.TextField(label="Password", password=True, border_color=ft.Colors.BLUE_400)

        def attempt_login(e):
            if not username.value or not password.value:
                show_snack("Username or password is missing!", ft.Colors.RED)
                return
            client.send_message(f"LOGIN {username.value} {password.value}")

        return ft.View("/", [
            ft.Container(
                ft.Column([
                    ft.Image(src="https://picsum.photos/200/300", width=150, height=150, border_radius=100),
                    ft.Text("Welcome!", size=24, weight=ft.FontWeight.BOLD),
                    username, password,
                    ft.ElevatedButton("Login", on_click=attempt_login, color=ft.Colors.BLUE_400),
                    ft.TextButton("Create a new account", on_click=lambda _: page.go("/register"))
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20
            )
        ])

    def register_page():
        username = ft.TextField(label="Username", border_color=ft.Colors.BLUE_400)
        password = ft.TextField(label="Password", password=True, border_color=ft.Colors.BLUE_400)
        confirm = ft.TextField(label="Confirm Password", password=True, border_color=ft.Colors.BLUE_400)

        def attempt_register(e):
            if not username.value or not password.value:
                show_snack("All fields are required!", ft.Colors.RED)
                return
            if password.value != confirm.value:
                show_snack("Passwords do not match!", ft.Colors.RED)
                return
            client.send_message(f"REGISTER {username.value} {password.value}")

        return ft.View("/register", [
            ft.Container(
                ft.Column([
                    ft.Image(src="https://picsum.photos/200/300", width=150, height=150, border_radius=100),
                    ft.Text("Create Account", size=24, weight=ft.FontWeight.BOLD),
                    username, password, confirm,
                    ft.ElevatedButton("Register", on_click=attempt_register, color=ft.Colors.BLUE_400),
                    ft.TextButton("Back to login", on_click=lambda _: page.go("/login"))
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20
            )
        ])

    def users_page():
        client.send_message("GET_ALL_USERS")
        return ft.View(
            "/users",
            [
                ft.AppBar(
                    title=ft.Text(f"Welcome {client.username}"),
                    actions=[
                        ft.IconButton(
                            ft.icons.LOGOUT,
                            on_click=lambda _: logout()
                        )
                    ]
                ),
                ft.Container(
                    ft.Column([
                        ft.Text("User List", size=20),
                        ft.Container(
                            client.user_list_container,
                            expand=True,
                            border=ft.border.all(1),
                            border_radius=10,
                            padding=10
                        )
                    ]),
                    padding=20,
                    expand=True
                )
            ]
        )

    def chat_page(user):
        return ft.View(
            f"/chat/{user}",
            [
                ft.AppBar(
                    leading=ft.IconButton(
                        ft.icons.ARROW_BACK,
                        on_click=lambda _: page.go("/users")
                    ),
                    title=ft.Text(f"Chat with {user}")
                ),
                ft.Container(
                    ft.Column([
                        ft.Container(
                            client.chat_display,
                            expand=True,
                            border=ft.border.all(1),
                            border_radius=10,
                            padding=10
                        ),
                        ft.Row([client.message_input, client.send_btn])
                    ], spacing=10),
                    padding=15,
                    expand=True
                )
            ]
        )

    def logout():
        client.connected = False
        if client.socket:
            client.socket.close()
        page.go("/login")

    def route_change(route):
        page.views.clear()
        if page.route in ("/", "/login"):
            page.views.append(login_page())
        elif page.route == "/register":
            page.views.append(register_page())
        elif page.route == "/users":
            page.views.append(users_page())
        elif page.route.startswith("/chat/"):
            page.views.append(chat_page(page.route.split("/")[-1]))
        page.update()

    threading.Thread(target=process_messages, daemon=True).start()
    page.on_route_change = route_change
    page.go("/login")

if __name__ == "__main__":
    ft.app(target=main)