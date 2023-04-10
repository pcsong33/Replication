import unittest, server, client, threading, time, sys, os, csv

HOST = 'dhcp-10-250-203-22.harvard.edu'
DIR = server.DIR = 'test_tables'


class ReplicationTest(unittest.TestCase):
    # Helper function to check if a server response is exactly what we expect
    def empty_directory(self):
        for file_name in os.listdir(DIR):
            file = f'{DIR}/{file_name}'
            if os.path.isfile(file):
                os.remove(file)

    # Helper function to create test directory
    def create_dir(self):
        if os.path.isdir(DIR):
            self.empty_directory(DIR)
        else:
            os.mkdir(DIR)

    def csv_to_list(self, filename):
        rows = []
        with open(filename, 'r', newline='') as f:
            csvreader = csv.reader(f)
            for row in csvreader:
                rows.append(row)
        return rows

    def test_user_csv_functions(self):
        self.empty_directory()
        serv = server.Server()
        serv.create_user_in_csv('patrick', 123)

        filename = f"{DIR}/users_table_{serv.port}.csv"

        # assert that file has been created
        self.assertTrue(os.path.isfile(filename))

        lst = self.csv_to_list(filename)

        # check that csv file contains correct row
        self.assertEqual(lst[0], ['create', 'patrick', '123'])

        # create 9 more patricks
        for i in range(9):
            serv.create_user_in_csv(f'patrick_{i}', '123')

        # check that csv file contains 10 people
        self.assertEqual(len(self.csv_to_list(filename)), 10)

        # delete original patrick
        serv.delete_user_in_csv('patrick')
        self.assertIn(['delete', 'patrick'], self.csv_to_list(filename))

        users = serv.load_users_from_csv()
        for i, user in enumerate(users):
            self.assertEqual(user, f'patrick_{i}')
            self.assertEqual(users[user].name, f'patrick_{i}')

        self.assertNotIn('patrick', users)

    def test_msg_csv_functions(self):
        self.empty_directory()
        serv = server.Server()
        serv.users = {'patrick': server.User('patrick'), 'ashley': server.User('ashley')}
        serv.queue_msg_in_csv('ashley', 'patrick', 'hello')

        filename = f"{DIR}/msgs_table_{serv.port}.csv"

        # assert that file has been created
        self.assertTrue(os.path.isfile(filename))

        # check that csv file contains correct row
        lst = self.csv_to_list(filename)
        self.assertEqual(lst[0], ['queue', 'ashley', 'patrick', 'hello'])

        # create 9 more ashley to patrick messages
        for i in range(9):
            serv.queue_msg_in_csv('ashley', 'patrick', f'hello_{i}')

        for i in range(10):
            serv.queue_msg_in_csv('patrick', 'ashley', f'hello_{i}')

        # check that csv file contains 10 messages
        self.assertEqual(len(self.csv_to_list(filename)), 20)

        serv.clear_msgs_in_csv('patrick')
        self.assertIn(['clear', 'patrick'], self.csv_to_list(filename))

        serv.load_msgs_from_csv()
        print(serv.users)
        patrick_messages = serv.users['patrick'].msgs
        ashley_messages = serv.users['ashley'].msgs

        expected_ashley_messages = [('patrick', 'hello')] + [('patrick', f'hello_{i}') for i in range(9)]
        self.assertEqual([], patrick_messages)
        self.assertEqual(ashley_messages, expected_ashley_messages)

    def test_leader_election(self):
        serv = server.Server(port=3538)
        serv.users = [server.User('pete', addr=1538, active=False),
                      server.User('john', addr=2538, active=False),
                      server.User('will', addr=3538, active=True)]
        serv.leader_election()
        self.assertTrue(serv.primary)

        serv_1 = server.Server(port=3538)
        serv_1.users = [server.User('pete', addr=1538, active=True),
                      server.User('john', addr=2538, active=True),
                      server.User('will', addr=3538, active=False)]
        serv_1.leader_election()
        self.assertTrue(serv.primary)

        serv_1 = server.Server(port=3538)
        serv_1.users = [server.User('pete', addr=1538, active=True),
                        server.User('john', addr=2538, active=True),
                        server.User('will', addr=3538, active=False)]
        serv_1.leader_election()
        self.assertTrue(serv.primary)
