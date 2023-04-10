import unittest, server, client, warnings, os, csv

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
        self.silence_resource_warning()
        self.empty_directory()
        serv = server.Server()
        serv.create_user_in_csv('patrick')

        filename = f"{DIR}/users_table_{serv.port}.csv"

        # assert that file has been created
        self.assertTrue(os.path.isfile(filename))

        lst = self.csv_to_list(filename)

        # check that csv file contains correct row
        self.assertEqual(lst[0], ['create', 'patrick'])

        # create 9 more patricks
        for i in range(9):
            serv.create_user_in_csv(f'patrick_{i}')

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
        self.silence_resource_warning()
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
        patrick_messages = serv.users['patrick'].msgs
        ashley_messages = serv.users['ashley'].msgs

        expected_ashley_messages = [('patrick', 'hello')] + [('patrick', f'hello_{i}') for i in range(9)]
        self.assertEqual([], patrick_messages)
        self.assertEqual(ashley_messages, expected_ashley_messages)

    def test_leader_election(self):
        self.silence_resource_warning()
        serv = server.Server(port=3538, primary=False)
        serv.server_sockets = {1538: server.User('pete', addr=1538, active=False),
                               2538: server.User('john', addr=2538, active=False),
                               3538: server.User('will', addr=3538, active=True)}
        serv.leader_election()
        self.assertTrue(serv.primary)

        serv_1 = server.Server(port=1538, primary=False)
        serv_1.server_sockets = {1538: server.User('pete', addr=1538, active=True),
                                 2538: server.User('john', addr=2538, active=True),
                                 3528: server.User('will', addr=3538, active=False)}
        serv_1.leader_election()
        self.assertTrue(serv_1.primary)

        serv_2 = server.Server(port=2538, primary=False)
        serv_2.server_sockets = {1538: server.User('pete', addr=1538, active=True),
                                 2538: server.User('john', addr=2538, active=True),
                                 3538: server.User('will', addr=3538, active=False)}
        serv_2.leader_election()
        self.assertFalse(serv_2.primary)

        serv_3 = server.Server(port=3538, primary=False)
        serv_3.server_sockets = {1538: server.User('pete', addr=1538, active=True),
                                 2538: server.User('john', addr=2538, active=True),
                                 3538: server.User('will', addr=3538, active=False)}
        serv_3.leader_election()
        self.assertFalse(serv_3.primary)

    def test_parse_primary_message(self):
        self.silence_resource_warning()
        serv = server.Server(port=3538, primary=False)
        c_name, request = serv.parse_primary_message(request="send|mark|3|jane")
        self.assertEqual(c_name, 'jane')
        self.assertEqual(request, 'send|mark|3')

        c_name, request = serv.parse_primary_message(request="create|jane|None")
        self.assertEqual(c_name, None)
        self.assertEqual(request, 'create|jane')

    def test_on_server_shutdown(self):
        self.silence_resource_warning()
        serv = server.Server(port=1538, primary=False)
        serv.server_sockets = {1538: server.User('pete', addr=1538, active=False),
                               2538: server.User('john', addr=2538, active=False),
                               3538: server.User('will', addr=3538, active=True)}
        serv.on_server_shutdown(3538)
        self.assertFalse(serv.server_sockets[1538].active)
        self.assertFalse(serv.server_sockets[2538].active)
        self.assertFalse(serv.server_sockets[3538].active)

        serv = server.Server(port=1538, primary=False)
        serv.server_sockets = {1538: server.User('pete', addr=1538, active=True),
                               2538: server.User('john', addr=2538, active=True),
                               3538: server.User('will', addr=3538, active=True)}
        serv.on_server_shutdown(2538)
        self.assertTrue(serv.server_sockets[1538].active)
        self.assertFalse(serv.server_sockets[2538].active)
        self.assertTrue(serv.server_sockets[3538].active)
    def silence_resource_warning(self):
        warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)

if __name__ == '__main__':
    unittest.main()












