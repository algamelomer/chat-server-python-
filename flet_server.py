import socket
import threading
import sqlite3
import time
import hashlib

conn = sqlite3.connect('chat_app.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
cursor.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER, receiver_id INTEGER, message TEXT, timestamp REAL)')
conn.commit()

active_users = {}  # {username: client_socket}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_id(username):
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    return result[0] if result else None

def store_message(sender_username, receiver_username, message):
    sender_id = get_user_id(sender_username)
    receiver_id = get_user_id(receiver_username)
    if sender_id and receiver_id:
        cursor.execute('INSERT INTO messages (sender_id, receiver_id, message, timestamp) VALUES (?, ?, ?, ?)',
                       (sender_id, receiver_id, message, time.time()))
        conn.commit()

def get_chat_history(user1, user2):
    user1_id = get_user_id(user1)
    user2_id = get_user_id(user2)
    if user1_id and user2_id:
        cursor.execute('SELECT u.username, m.message FROM messages m JOIN users u ON m.sender_id = u.id WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?) ORDER BY m.timestamp ASC', (user1_id, user2_id, user2_id, user1_id))
        return cursor.fetchall()
    return []

def get_all_users():
    cursor.execute('SELECT username FROM users')
    return [row[0] for row in cursor.fetchall()]

def broadcast_active_users():
    user_list = ",".join(active_users.keys())
    for client_socket in active_users.values():
        client_socket.send(f"ACTIVE_USERS:{user_list}".encode())

def handle_client(client_socket):
    try:
        while True:
            message = client_socket.recv(1024).decode().strip()
            if not message:
                break
            parts = message.split(" ", 2)
            command = parts[0]
            if command == "LOGIN":
                username, password = parts[1], parts[2]
                cursor.execute('SELECT id FROM users WHERE username = ? AND password = ?', (username, hash_password(password)))
                if cursor.fetchone():
                    if username not in active_users:
                        active_users[username] = client_socket
                        client_socket.send(f"LOGIN_OK:{username}".encode())
                        broadcast_active_users()
                    else:
                        client_socket.send("ERROR:Already logged in".encode())
                else:
                    client_socket.send("ERROR:Invalid credentials".encode())
            elif command == "REGISTER":
                username, password = parts[1], parts[2]
                cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                if cursor.fetchone():
                    client_socket.send("ERROR:Username already taken".encode())
                else:
                    cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hash_password(password)))
                    conn.commit()
                    client_socket.send("REGISTER_OK".encode())
            elif command == "SEND":
                recipient, msg = parts[1], parts[2]
                sender = [k for k, v in active_users.items() if v == client_socket][0]
                store_message(sender, recipient, msg)
                if recipient in active_users:
                    active_users[recipient].send(f"MESSAGE:{sender}:{msg}".encode())
            elif command == "GET_HISTORY":
                other_user = parts[1]
                username = [k for k, v in active_users.items() if v == client_socket][0]
                history = get_chat_history(username, other_user)
                history_str = "|".join([f"{sender}:{msg}" for sender, msg in history])
                client_socket.send(f"HISTORY:{history_str}".encode())
            elif command == "GET_ALL_USERS":
                all_users = get_all_users()
                active = ",".join(active_users.keys())
                client_socket.send(f"ALL_USERS:{','.join(all_users)}:{active}".encode())
    except:
        pass
    finally:
        for username, sock in list(active_users.items()):
            if sock == client_socket:
                del active_users[username]
                broadcast_active_users()
                break
        client_socket.close()

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('localhost', 12345))
server_socket.listen(5)
print("Server running on localhost:12345")
while True:
    client_socket, addr = server_socket.accept()
    threading.Thread(target=handle_client, args=(client_socket,)).start()