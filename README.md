# CS262 Replication

## Wire Protocol Chat Application
This application is located in the `wire_protocol_chat/` directory.

### Usage Instructions
By default, the server listening on port 1538 is initialized as the primary server and the servers listening on ports 2538 and 3538
are the secondary servers. To start a 2-fault-tolerant system, do the following:
1. Make sure to change the `PORT_TO_HOST` values in `server.py` to match the hostnames of the devices that you intend to run the servers on.
For example, if you are running the primary server 1538 on hostname "dhcp.harvard.edu", change the value corresponding to port 1538 to "dhcp.harvard.edu".
1. Start up the servers by running:
- `python server.py primary 1538`
- `python server.py secondary 2538`
- `python server.py secondary 3538 `
1. Change the `HOST` variable in `client.py` to match the primary server's hostname.
1. Start up a client by running `python3 client.py`. You can now use the application to chat with other clients.

### Wire Protocol
Requests from a client to the server are sent in the form `[operation]|[paramaters]` (encoded with UTF-8), where the parameters are delimited with pipes as well. The request must be less than 280 characters. Here is the list of valid operations:
* Op 1 - Create account. Parameter: username. Ex: `1|alice`.
* Op 2 - Log into existing account. Parameter: username. Ex: `2|alice`.
* Op 3 - Send a message to another account. Parameters: recipient's username, message. Ex: `3|bob|hello there`.
* Op 4 - List accounts, or subset of accounts via Unix shell-style wildcard. Parameter: wildcard (optional, no wildcard = all accounts listed). Ex: `4|a*`.
* Op 5 - Delete the account. Ex: `5`.
* Op 6 - Exit the chat application. Ex: `6`.

Responses from the server to a client are sent in the form `[message length][status][indicator][message]` (encoded with UTF-8). The first two values are given as unicode characters, so that the first three values form a 3-byte long header for the message. Here are the specs for the header and message values:
* Message length: This is the number of bytes in the message, not including the header.
* Status: This indicates the status of a server (non-chat) message. Possible statuses:
    * 0 = Success
    * 1 = Error
    * 2 = Note from server
* Indicator: This indicates whether this is a chat message from another client or a message directly from the server. The value is 0 if it is a server message and 1 if the message is a chat message.
* Message: The message is any string. If it is a chat message (so if the indicator is 1), then the message must be in the form of `[sender]|[chat message]`.


### File Overview
* `server.py` - Defines the `Server` class. 
    * Accepts connections from multiple clients, with a new thread being started for each one. 
    * Listens to requests from the clients, and responds accordingly with messages following the wire protocol. 
    * Passes chat messages between clients.
    * Keeps a global dictionary of `User` objects, to keep track of all of the accounts created, socket connections, queued messages, etc.
* `client.py` - Defines the `Client` class.
    * Connects to the server.
    * Runs a background thread to listen for and print messages from the server.
    * Takes in requests from the user via command-line input, which is packaged according to the wire protocol and sent to the server.
* `tests.py` - Unit tests. To run the tests, you must 1) run `server.py`, 2) change `HOST` in `tests.py` to match the server, and finally 3) run `python3 tests.py`
    * The tests spawn `Client` objects connected to the server. These objects send requests to the server within the tests, and the tests check whether the responses from the server are as expected.
    * If a `Too many open files` error is received when running tests, run `ulimit -n 2048` to reconfigure the maximum number of open files.

### Fault Tolerance

#### Primary-Secondary Architecture:
!![architecture.png](wire_protocol_chat%2Fimages%2Farchitecture.png)

#### Primary Server Shutdown:
![primary_disconnect.png](wire_protocol_chat%2Fimages%2Fprimary_disconnect.png)

#### Leader Election:
![leader_election.png](wire_protocol_chat%2Fimages%2Fleader_election.png)

#### Reconnect to New Primary:
![reconnect.png](wire_protocol_chat%2Fimages%2Freconnect.png)