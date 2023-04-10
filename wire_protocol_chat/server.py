import socket
import fnmatch
import threading
import csv
import sys
import time
import os.path

DIR = 'tables'
PORTS = {1538, 2538, 3538}
PORT_TO_HOST = {
    1538: 'dhcp-10-250-0-195.harvard.edu',
    2538: 'dhcp-10-250-224-250.harvard.edu',
    3538: 'dhcp-10-250-0-195.harvard.edu'
}

'''
A User object represents an account that is created. It keeps track of the username, whether the user 
is active or not, the client socket logged into the account, and the undelivered messages to the user.
'''
class User:
    def __init__(self, name, socket=None, addr=None, active=False):
        self.name = name
        self.socket = socket
        self.addr = addr
        self.active = active
        self.msgs = []
        self.lock = threading.Lock()
    
    # For setting the socket and address of the user when a client logs in.
    def set_socket_addr(self, socket, addr):
        self.socket = socket
        self.addr = addr

    # When the client logged in as the user disconnects
    def disconnect(self):
        if self.socket:
            self.socket.close()
        self.socket = None
        self.addr = None
        self.active = False

    # Used by another client to queue a message to this user if they are inactive.
    # Multiple clients on diff threads may attempt to queue msgs simultaneously, so a lock is needed.
    def queue_msg(self, sender, msg):
        with self.lock:
            self.msgs.append((sender, msg))

    # For clearing the queue of messages after they have been sent.
    def clear_msgs(self):
        self.msgs = []

'''
The Server object accepts connections from multiple clients, and listens to client requests in order 
to respond and pass chat messages between clients. It keeps a global dictionary of all User objects.
'''
class Server:
    def __init__(self, primary=True, port=1538):
        self.port = port
        self.server_ports = PORTS - {port}

        # can maybe utilize User object instead of dict
        self.server_sockets = dict()
        self.s = socket.socket()
        self.host = socket.gethostname()
        self.ip = socket.gethostbyname(self.host)
        self.users = {}
        self.lock = threading.Lock()
        self.primary = primary

    # Package and send messages from server to client according to wire protocol
    def send_msg_to_client(self, c_socket, status, is_chat, msg):
        # Only send messages to the client if you are the primary server
        if self.primary:
            msg_len = len(msg)
            data = chr(msg_len) + chr(status) + str(is_chat) + msg
            c_socket.sendall(data.encode())
    
    def create_user_in_csv(self, name): # TODO: need to store more info than this? need store addr? need file unique to port?
        with open(f'{DIR}/users_table_{self.port}.csv', 'a') as csv_file:
            csv.writer(csv_file).writerow(['create', name])

    def delete_user_in_csv(self, name):
        with open(f'{DIR}/users_table_{self.port}.csv', 'a') as csv_file:
            csv.writer(csv_file).writerow(['delete', name])

    def load_users_from_csv(self):
        users = {}

        with open(f'{DIR}/users_table_{self.port}.csv', 'r') as csv_file:
            for line in csv_file:
                line = line.strip('\n').split(',')
                name = line[1]
                if line[0] == 'create':
                    users[name] = User(name)
                elif line[0] == 'delete':
                    users.pop(name)

        return users
    
    def queue_msg_in_csv(self, receiver, sender, msg):
        with open(f'{DIR}/msgs_table_{self.port}.csv', 'a') as csv_file:
            csv.writer(csv_file).writerow(['queue', receiver, sender, msg])

    def clear_msgs_in_csv(self, name):
        with open(f'{DIR}/msgs_table_{self.port}.csv', 'a') as csv_file:
            csv.writer(csv_file).writerow(['clear', name])

    def load_msgs_from_csv(self):
        with open(f'{DIR}/msgs_table_{self.port}.csv', 'r') as csv_file:
            for line in csv_file:
                line = line.strip('\n').split(',')
                receiver = line[1]

                if receiver not in self.users:
                    continue

                if line[0] == 'queue':
                    sender, msg = line[2], line[3]
                    self.users[receiver].queue_msg(sender, msg)
                elif line[0] == 'clear':
                    self.users[receiver].clear_msgs()
            
    # Op 1 - Create Account
    def create_account(self, c_socket, c_name, addr, name):
        # Client is already logged in
        if c_name:
            self.send_msg_to_client(c_socket, 1, 0, f'Unable to create account: You are already logged in as {c_name}. Please exit and start a new client to log into a different account.')
            return 1
        
        with self.lock:
            # Username is already registered
            if name in self.users:
                self.send_msg_to_client(c_socket, 1, 0, 'Unable to create account: This username is already taken.')
                return 1
            
            # Register user - create new User object
            self.users[name] = User(name, c_socket, addr, True)

            # log users table in csv file.
            self.create_user_in_csv(name)

        self.send_msg_to_client(c_socket, 0, 0, f'Account created! Logged in as {name}.')
        print(f'{name} has created an account.')
        return 0

    # Op 2 - Login
    def login(self, c_socket, c_name, addr, name):
        # Client is already logged in
        if c_name:
            self.send_msg_to_client(c_socket, 1, 0, f'Unable to login: You are already logged in as {c_name}. Please exit  and start a new client to log into a different account.')
            return 1

        # Username does not exist
        if name not in self.users:
            self.send_msg_to_client(c_socket, 1, 0, 'Unable to login: This username does not exist. If you would like to use this username, please create a new account.')
            return 1

        with self.users[name].lock:
            # User already active
            if self.users[name].active:
                self.send_msg_to_client(c_socket, 1, 0, 'Unable to login: This user is already connected to the server.')
                return 1
            
            self.users[name].set_socket_addr(c_socket, addr)
            self.users[name].active = True

        self.send_msg_to_client(c_socket, 0, 0, f'Logged in as {name}.')
        print(f'{name} is logged in.')
        return 0

    # Upon login, send messages user missed
    def send_queued_chats(self, c_socket, c_name):
        client = self.users[c_name]
        total_msgs = len(client.msgs)

        # No new messages
        if (total_msgs == 0):
            self.send_msg_to_client(c_socket, 2, 0, 'No new messages since you\'ve been gone.')
            return 0

        for sender, queued_msg in client.msgs:
            # Check if queued message is from a deleted user, and display name with [deleted] if so
            deleted_flag = ""
            if sender not in self.users:
                deleted_flag = " [deleted]"

            self.send_msg_to_client(c_socket, 0, 1, sender + deleted_flag + '|' + queued_msg)
            print(f'{sender} sent {queued_msg} to {c_name}')

        self.send_msg_to_client(c_socket, 2, 0, f'You have {total_msgs} missed messages above.')
        client.clear_msgs()
        self.clear_msgs_in_csv(c_name)

    # Op 3 - Send chat messages from client to client
    def send_chat(self, c_socket, c_name, receiver, msg):
        # Must be logged in
        if not c_name:
            self.send_msg_to_client(c_socket, 1, 0, 'Must be logged in to perform this operation. Please login or create an account.')
            return 1

        # Validate recipient
        if receiver not in self.users:
            self.send_msg_to_client(c_socket, 1, 0, 'Recipient username cannot be found.')
            return 1
        if receiver == c_name:
            self.send_msg_to_client(c_socket, 1, 0, 'Cannot send messages to yourself.')
            return 1
        
        receiver_client = self.users[receiver]

        # Queue message if receiver inactive
        if not receiver_client.active:
            receiver_client.queue_msg(c_name, msg)
            self.queue_msg_in_csv(receiver, c_name, msg)

            self.send_msg_to_client(c_socket, 0, 0, f'Message sent to {receiver}.')
            print(f'{c_name} queued {msg} to {receiver}')

            return 0

        # Send message on demand if active
        try:
            self.send_msg_to_client(receiver_client.socket, 0, 1, c_name + '|' + msg)
            self.send_msg_to_client(c_socket, 0, 0, f'Message sent to {receiver}.')
            print(f'{c_name} sent {msg} to {receiver}')
            return 0
        # Handle case where receiver unexpectedly died
        except:
            self.send_msg_to_client(c_socket, 1, 0, f'Message could not be sent to {receiver}. Please try again.')
            print(f'\n[-] Connection with {receiver_client.name} has broken. Disconnecting client.\n')
            
            receiver_client.disconnect()
            
            # Tell backups that the receiver client died
            if self.primary and receiver:
                print(receiver)
                self.send_backups_message('6', receiver)

            return 1

    def parse_primary_message(self, request):
        # find client logged into primary server
        c_name_rec = request.split('|')[-1]
        c_name = None if c_name_rec == "None" else c_name_rec

        # reform request
        request = "|".join(request.split('|')[:-1])
        return c_name, request

    def send_backups_message(self, request, c_name):
        for port in self.server_sockets:
            if self.primary and self.server_sockets[port].active:
                print('sent to port ' + str(port))
                backup_request = request + "|" + str(c_name)
                self.server_sockets[port].socket.sendall(backup_request.encode())

    def on_server_shutdown(self, addr):
        if isinstance(addr, int):
            self.server_sockets[addr].active = False
            print(f"disconnected from {addr}")
            if not self.primary:
                self.leader_election()

    def leader_election(self):
        # leader election
        servers = list(self.server_sockets.values())
        new_primary = min([x.addr if x.active else 3538 for x in servers] + [self.port])
        # if server port is lowest, it is elected to be primary
        if self.port == new_primary:
            self.primary = True
            print('PRIMARY HERE')

    # Threaded execution for each client
    def on_new_client(self, c_socket, addr):
        c_name = None
        client = None

        try:
            while True:
                request = c_socket.recv(1024).decode()
                # replica server has shutdown
                if request == '':
                    self.on_server_shutdown(addr)
                    c_socket.close()
                    break

                # if backup, parse message from primary
                if not self.primary:
                    # assume that no user is logged in
                    c_name = None
                    client = None
                    c_name, request = self.parse_primary_message(request)
                else:
                    # pass on message to all connected backups
                    self.send_backups_message(request, c_name)

                # Unpack data according to wire protocol
                op, msg = request.split('|', 1) if '|' in request else (request, '')
                op, msg = op.strip(), msg.strip()

                # Create an account
                if op == '1':
                    print('create')
                    status = self.create_account(c_socket, c_name, addr, msg)

                    # Successfully created account
                    if status == 0:
                        c_name = msg
                        client = self.users[c_name]
            
                # Log into existing account
                elif op == '2':
                    status = self.login(c_socket, c_name, addr, msg)

                    # Successfully logged in
                    if status == 0:
                        c_name = msg
                        client = self.users[c_name]

                        # Send any undelivered messages 
                        self.send_queued_chats(c_socket, c_name)

                # Send message to another client
                elif op == '3':
                    msg = msg.split('|', 1)
                    receiver, msg = msg[0].strip(), msg[1].strip()
                    self.send_chat(c_socket, c_name, receiver, msg)

                # List accounts
                elif op == '4':
                    accounts = '\n' 

                    for key in fnmatch.filter(self.users.keys(), msg if msg else '*'):
                        accounts += '- ' + key + '\n'

                    self.send_msg_to_client(c_socket, 0, 0, accounts)
                    
                # Delete account
                elif op == '5':
                    # Must be logged in for primary
                    if self.primary and not client:
                        self.send_msg_to_client(c_socket, 1, 0, 'Must be logged in to perform this operation. Please login or create an account.')
                        continue
                    
                    with self.lock:
                        self.users.pop(c_name)
                        self.delete_user_in_csv(c_name)
                        self.send_msg_to_client(c_socket, 0, 0, f'Account {c_name} has been deleted. You are now logged out.')

                    print(f'{c_name} has deleted their account.')
                    c_name = None
                    client = None

                # Exit the chat
                elif op == '6':
                    # Deactivate the client
                    if c_name:
                        print(f'\n[-] {c_name} has left. Disconnecting client.\n')
                        self.users[c_name].active = False

                    # Remove connection if primary
                    if self.primary:
                        if client:
                            client.disconnect()
                        break
                
                # Logging into new primary server
                elif op == '7':
                    c_name = msg.split('|')[0]
                    client = self.users[c_name]
                    self.users[c_name].set_socket_addr(c_socket, addr)
                    self.users[c_name].active = True

                # Request was malformed
                else:
                    self.send_msg_to_client(c_socket, 1, 0, 'Invalid operation. Please input your request as [operation]|[params].')
            

        # Handle client disconnect if unexpected broken connection (e.g. ctrl+c)
        except (BrokenPipeError, ConnectionResetError) as e:
            if client:
                print(f'\n[-] Connection with {c_name} has broken. Disconnecting client.\n')
                client.disconnect()

    def connect_replicas(self, s_port):
        try:
            sock = socket.socket()
            sock.connect((PORT_TO_HOST[s_port], s_port))
            self.server_sockets[s_port] = User(s_port, sock, active=True, addr=s_port)
            print(f'\nConnected with replica on port {s_port}!')
            t = threading.Thread(target=self.on_new_client, args=(sock, s_port))
            t.start()
        except ConnectionRefusedError:
            print(f"\nUnable to connect with replica on port {s_port}")

    # Main execution for starting server and listening for connections
    def start_server(self):
        try: 
            # Print out host/IP
            print(f'\n{self.host} ({self.port})')

            # Allow address reuse
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind socket to port
            self.s.bind((self.host, self.port))

            print('\nServer started!')
            # Sleep before connecting with backups
            backups = self.server_ports
            print('\nWaiting to connect with replicas...')

            # Fault-tolerant system is created if backups are run within 3 seconds of the primary starting up
            time.sleep(3)

            for s_port in backups:
                t = threading.Thread(target=self.connect_replicas, args=(s_port,))
                t.start()

            # Load persisted data if exists
            if os.path.isfile(f'{DIR}/users_table_{self.port}.csv'):
                self.users = self.load_users_from_csv()
            if os.path.isfile(f'{DIR}/msgs_table_{self.port}.csv'):
                self.load_msgs_from_csv()
                

            # Listen for client connections
            self.s.listen(5)
            print('\nWaiting for incoming connections...')

            while True:
                c_socket, addr = self.s.accept()

                print(f'\n[+] Connected to {addr[0]} ({addr[1]})\n')

                # Start a new thread for each client
                t = threading.Thread(target=self.on_new_client, args=(c_socket, addr))
                t.start()

        except KeyboardInterrupt:
            print('\nServer closed with KeyboardInterrupt!')

            for c in self.users:
                if self.users[c].socket:
                    self.users[c].socket.close()

            self.s.close()


if __name__ == "__main__":
    primary = True
    port = 1538
    if len(sys.argv) > 2:
        if sys.argv[1] == 'secondary':
            primary = False
        port = int(sys.argv[2])
    server = Server(primary, port)
    server.start_server()
