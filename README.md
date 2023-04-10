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
1. Change the `HOSTS` variable in `client.py` to match the hostnames for the servers on port 1538, 2538, and 3538, respectively.
1. Start up a client by running `python3 client.py`. You can now use the application to chat with other clients.

### Wire Protocol
Requests from a client to the server are sent in the form `[operation]|[paramaters]` (encoded with UTF-8), where the parameters are delimited with pipes as well. The request must be less than 280 characters. Here is the list of valid operations:
* Op 1 - Create account. Parameter: username. Ex: `1|alice`.
* Op 2 - Log into existing account. Parameter: username. Ex: `2|alice`.
* Op 3 - Send a message to another account. Parameters: recipient's username, message. Ex: `3|bob|hello there`.
* Op 4 - List accounts, or subset of accounts via Unix shell-style wildcard. Parameter: wildcard (optional, no wildcard = all accounts listed). Ex: `4|a*`.
* Op 5 - Delete the account. Ex: `5`.
* Op 6 - Exit the chat application. Ex: `6`.
* Op 7 - Let's server know who the client is currently logged in as. Ex: `7|bob`. Note that this request cannot be invoked by the user; rather the client code internally sends this request to the new primary server if the original primary server goes down at any point.

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
    * Accepts connections from other servers, and elects a new primary server whenever a server goes down.
    * The primary server listens to requests from the clients, and responds accordingly with messages following the wire protocol. 
    * The primary server passes chat messages between clients.
    * All servers keep a global dictionary of `User` objects, to keep track of all of the accounts created, socket connections, queued messages, etc.
    * The primary server passes all client requests to the secondary servers, in order for them to keep their internal state up-to-date.
    * All servers keep a commit log of users that have been created/deleted and messages that have been queued/cleared, in order for the current state of the system to be saved if everything goes down. Whenever a server is started up, it loads in user and queued message data from the commit logs, if they exist. These commit logs are in the `tables/` directory.
* `client.py` - Defines the `Client` class.
    * Connects to the primary server.
    * Runs a background thread to listen for and print messages from the server.
    * Takes in requests from the user via command-line input, which is packaged according to the wire protocol and sent to the server.
* `replication-tests.py` - Unit tests. Run via `python3 replication-tests.py`. These tests are for testing the specific features/functions we added in this design assignment to the application.

### Fault Tolerance

#### Primary-Secondary Architecture:
When the system is started, all of the three servers connect to each other. By default, the server with the lowest port number is initialized as the primary server. Then, when clients come online, they connect to the primary server. Their requests are sent to the primary server, who then handles the request and sends back the appropriate response. These client requests are also passed from the primary to the secondary servers in order for the backup replicas to maintain the same internal state (which keeps track of which users exist, are logged in, queued messages, etc.).

![architecture.png](wire_protocol_chat%2Fimages%2Farchitecture.png)

#### Primary Server Shutdown + Leader Election:
If the primary server shuts down at any point, all connections are broken except for the connection between the replicas left.
![primary_disconnect.png](wire_protocol_chat%2Fimages%2Fprimary_disconnect.png)

The secondary servers that are left elect a new leader to become the primary server. Our election simply chooses the server with the lowest port number as the leader.
![leader_election.png](wire_protocol_chat%2Fimages%2Fleader_election.png)

#### Reconnect to New Primary:
Once a new leader has been elected as primary, the clients now connect to this new primary server. This new primary server's internal state has all of data the primary server had before it shut down, since the client requests were being passed from the primary to secondarys originally.
![reconnect.png](wire_protocol_chat%2Fimages%2Freconnect.png)
Then, the system can proceed as usual with this new primary now handling and responding to client requests. From the user perspective, they cannot detect this change, as this new primary has all of the accurate data stored and so the chat application just proceeds as it normally would.

Our system will repeat the same process if the current primary shuts down again: it elects the last server remaining as the leader, and the clients now connect to this server. Thus, our system is 2-fault tolerant, since it can run normally when up to two servers shut down. Note that if at any point one of the secondary servers shuts down instead of the primary, its connections to the other servers are just dropped but no leader election has to occur since the primary server remains intact.

### Persistence
Any time a request is received by a server that creates or deletes a user, this request is logged in the `user_table_[port].csv` file in the `tables/` directory by the server. Then, if this server is shut down and started up again, upon start up, the server loads the existing users into its internal state from the CSV file. For example, if the CSV file lines are `create,bob`, `create,alice`, `delete,bob`, the server will iterate through these lines and perform these actions on its internal state, ending up with just `alice` as an existing user.

Similarly, any time a request is received that queues a message to a user or clears the queued messages for a user (i.e. the user logs in), this request is logged in the `msgs_table_[port].csv` file in the `tables/` directory by the server. These queued messages are also loaded upon initialization. The lines in the CSV are formatted as `queue,[receiver],[sender],[message]` or `clear,[receiver]`. For example, if the file lines are `queue,bob,alice,hi`, `queue,bob,alice,hello`, `queue,alice,joe,what's up`, `clear,alice`, then the queued messages that will be loaded into the server's initial state are two messages queued to bob from alice ("hi" and "hello"). 

Keeping these "commit log" tables and loading the commits in upon initialization allow our user and message store to be persisted, even if the whole system goes down and is restarted again. Conceptually, these tables serve as a backup for our server's current internal state that allows us to repopoulate the data if the server goes down.