# CS262 Engineering Notebook

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
