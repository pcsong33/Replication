# CS262 Engineering Notebook

## 4/9/2023
2-fault tolerance has been partly implemented. In order to test,
run three instances of the server.py file:
- `python server.py primary 1538`
- `python server.py secondary 2538`
- `python server.py secondary 3538`
Hasn't been thoroughly tested but seems to work.

Additionally, after a server goes down, once it comes back up, it will load the users from the csv corresponding to it. Possibly some syncing issues, also not sure if we want persistence only when the whole system goes down?

Think I fixed the logging out bug


## 4/8/2023

**Current Design**: 1-fault tolerance has been partly implemented. In order to test,
run two instances of the server.py file:
- `python server.py primary 1538`
- `python server.py secondary 2538`

Make sure that the servers are run within 3 seconds of one another. Otherwise, 
the system won't be fault-tolerant, and will default to the original
chat implementation. The following measures have been implemented:

- The primary server receives requests from the client and forwards
those requests to the secondary server.
- When shutting down the primary server, the secondary server is able
to become the primary one and handle requests normally.
- When the secondary server shuts down, the primary server is able to
continue to field requests.

Bugs
- When the primary server is shut down while a client is connected and logged in 
that user becomes logged out

TODOs
- Handle scenario when both primary and secondary go down.
- Implement a function that logs queued messages into a csv file
- Implement a function that is able to read from the user_table and queued_messages csv files
and is able to recover data. 
- Add another secondary (port 3538) to make system 2-fault-tolerant
- make sure replicas work across machines
- delete users from user table when user is deleted (we'd prob just have to read and overwrite the entire CSV???)
- for qued msgs, also seems like there would be expensive deletion operations, which kinda sucks.
- unit tests


## 4/7/2023
A couple notes on steps we have taken to implement replication:
- Added an address re-usability flag in the server code to bypass the "address already in use" error.
- Created a user_table.csv file. Intended to keep track of all the users. 
- Created a server_log.csv file. Intended to act as a commit log that tracks all changes that occur
for a server. In theory, a log will be added to the primary backup's commit log only when the action has
been approved by the other replicas.

##### Next Steps
- Establish secondary backups. Workflow should resemble:
  - Client makes a request to the primary server. 
  - Primary server passes on request to the secondary servers.
  - Secondary servers add action to commit logs, and send confirmation back to the primary
  - Primary sends a confirmation request back to the client


## 4/3/2023

Initial steps have been to copy over code from the Wire Protocol project to the Replication repository. For this project, we aim to implement
replication for the wire protocol (non-gRPC) version of the chat application. Here, we summarize some notes and project questions to explore.
- The assignment specifies that the system should be 2-fault tolerant. We aim to implement fault tolerance using a primary/backup system. 2-fault 
tolerance entails having a primary and two backups. 
  - Questions: What does fault tolerance entail for the chat application? For instance, in the original application, if the server were to shut down, then the clients would also stop its running execution. In the setting of replication, if a connection is broken, should the client isntead
  try and connect to one of the backups? 
- Implementing a heartbeat: A heartbeat is one mechanism to ensure that crashes are detected. We will implement a heartbeat between 
the replicas, as well as a heartbeat between the client applications and the primary.
- Leader Elections: What protocol should we use for leader elections? And how should this protocol be communicated to the clients? Does simply establishing an order suffice (if primary fails, Backup 1 is elected.)
- Enforcing protocols for read/write requests: In lecture, the following structure was described: the client only talks to the leader. The leader talks back to the client
for write requests, but any one of the replicas may talk back to the client for read requests. How important is it for this to be implemented in this project?
