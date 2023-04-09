import time, socket
from threading import Thread

# Change this below to match the server hosts / ports
HOSTS = ['dhcp-10-250-224-250.harvard.edu', 'dhcp-10-250-224-250.harvard.edu', 'dhcp-10-250-224-250.harvard.edu']
PORTS = [1538, 2538, 3538]

## Wire Protocol Constants ##

# Maximum number of bytes for a single request to the server
MAX_REQUEST_LEN = 280 

# Number of bytes in header for message from server to client
NUM_HEADER_BYTES = 3

# Dictionary that converts user-input operations to wire protocol operations
OP_TO_OPCODE = {
    'create': '1',
    'login': '2',
    'send': '3',
    'list': '4',
    'delete': '5',
    'exit': '6'
}

'''
The Client object connects to the server running the chat application. It listens for incoming messages from 
the server. It also takes in requests from the user via command-line input to be sent to the server.
'''
class Client:
    def __init__(self, ports=PORTS, hosts=HOSTS):
        self.sock = socket.socket()
        self.primary_idx = 0
        self.hosts = hosts
        self.ports = ports
        self.name = None

    # Prints out the instructions for how the user should format requests to use the chat application
    def print_intro_message(self):
        print(' -------------------------------------------------------------------------------------------------------------------')
        print('|                                             Welcome to the Chat Room!                                             |')
        print(' -------------------------------------------------------------------------------------------------------------------')

        print('INSTRUCTIONS: This chat room supports the following requests in the format \'[request type]|[params]\'')
        print('- create|[username] --> Create account')
        print('- login|[username] --> Log into existing account')
        print('- send|[recipient]|[message] --> Send a message to another user')
        print('- list|[wildcard (optional)] --> List accounts, via Unix shell-style wildcard (no wildcard = all accounts listed)')
        print('- delete --> Delete account')
        print('- exit --> Exit the chat application')

        print(' --------------------------------------------------------------------------------------------------------------------')

    # Connect to backup port if primary is down. Currently, only tries to connect to port 2538
    def connect_to_backup(self):
        if self.primary_idx >= 2:
            # TODO: change function to attempt to connect to all servers before giving all servers down message -- do we actually want to attempt to reconnect?
            print("All servers are down. Attempting to reconnect in 5 seconds.") 
            raise RuntimeError("Server connection broken.")

        # Leader election = lowest index server
        self.primary_idx += 1
        self.sock.close()
        self.sock = socket.socket()
        self.sock.connect((self.hosts[self.primary_idx], self.ports[self.primary_idx]))
        
        # Let new primary server know if logged in
        # if self.name:
        #     encoded_request = ('7|' + self.name).encode()
        #     self.sock.send(encoded_request)

    # Receive exactly k bytes from the server
    def recv_k_bytes(self, k):
        bytes_recd = 0
        msg = ''

        while bytes_recd < k:
            next_recv = self.sock.recv(k - bytes_recd).decode()

            # Primary server connection broken
            if next_recv == '':
                self.connect_to_backup()

            bytes_recd += len(next_recv)
            msg += next_recv
            
        return msg

    # Receive a single response from the server
    def recv_response_from_server(self):
        # Messages send as [msg_len][status][is_chat][msg] according to wire protocol
        header = self.recv_k_bytes(NUM_HEADER_BYTES)
        msg_len, status, is_chat = ord(header[0]), ord(header[1]), int(header[2])
        msg = self.recv_k_bytes(msg_len)

        return status, is_chat, msg

    # For background thread that listens for incoming messages to print
    def print_messages_from_server(self):
        status, is_chat, msg = self.recv_response_from_server()

        while msg:
            # Message from another client
            if is_chat:
                msg = msg.split('|', 1)
                sender = msg[0].strip()
                msg = msg[1].strip()

                print(f'\nMessage from {sender}: {msg}\n')
            # Message from the server
            else:
                if status == 0:
                    print(f'\nSUCCESS: {msg}\n')

                    if 'Logged in as' in msg:
                        self.name = msg.split(' ')[-1].strip('.')

                    if 'You are now logged out' in msg:
                        self.name = None

                elif status == 1:
                    print(f'\nERROR: {msg}\n')
                elif status == 2:
                    print(f'\nSERVER MESSAGE: {msg}\n')
            
            status, is_chat, msg = self.recv_response_from_server()


    # Validate requests before sending to server
    def validate_request(self, request):
        # Length limit
        if len(request) > MAX_REQUEST_LEN:
            print('\nINPUT ERROR: Please limit requests to 280 characters.\n')
            return 1

        op, msg = request.split('|', 1) if '|' in request else (request, '')
        op, msg = op.strip(), msg.strip()

        # Operation does not exist
        if op not in OP_TO_OPCODE:
            print('\nINPUT ERROR: Invalid operation. Please input your request as [operation]|[params].\n')
            return 1

        # Validate parameters
        if op == 'create' or op == 'login':
            if not msg:
                print('\nINPUT ERROR: Unable to create account: Username cannot be blank.\n')
                return 1
        elif op == 'send':
            msg_params = msg.split('|', 1)
            if len(msg_params) < 2:
                print('\nINPUT ERROR: Not enough parameters specified. To send a message to another user, please type 3|[recipient]|[message].\n')
                return 1
            if msg_params[1].strip() == '':
                print('\nINPUT ERROR: Message cannot be blank.\n')
                return 1

        return 0

    # Encode request to match wire protocol and send to server
    def pack_and_send_request(self, request):
        op, msg = request.split('|', 1) if '|' in request else (request, '')
        op, msg = op.strip(), msg.strip()

        opcode = OP_TO_OPCODE[op]
        encoded_request = (opcode + '|' + msg).encode()
        self.sock.send(encoded_request) 

    # Main execution for communicating with chat server
    def connect_to_server(self):
        print('\nWelcome to Chat Room\n')
        print('Initialising....\n')
        time.sleep(1)

        print(f'\nTrying to connect to {self.hosts[self.primary_idx]} ({self.ports[self.primary_idx]})\n')
        time.sleep(1)

        # connect to default port 1538
        try:
            self.sock.connect((self.hosts[self.primary_idx], self.ports[self.primary_idx]))

        # attempt to connect to backup
        except ConnectionRefusedError:
            self.connect_to_backup()

        print('Connected...\n')

        background_thread = Thread(target=self.print_messages_from_server)
        background_thread.daemon = True
        background_thread.start()

        self.print_intro_message()

        # Send message to the server to deliver to recipient
        while True:
            request = input()

            status = self.validate_request(request)

            # Continue if request is invalid
            if status == 1:
                continue

            # Send request to server
            self.pack_and_send_request(request)

            # Client is exiting 
            if request.split('|', 1)[0] == 'exit':
                break
            

if __name__ == "__main__":
    client = Client()
    client.connect_to_server()
