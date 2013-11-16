import getopt
import socket
from collections import namedtuple

Event = namedtuple("Event", ["name", "data"])


def setup_socket(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    return sock


def consumer(func):
    def start(*args, **kwargs):
        c = func(*args, **kwargs)
        c.next()
        return c
    return start


def parse_input_sender(argv):
    help = """To set host, type --domain=localhost or -d localhost
                To set port, type --port=9000 or -p 9000
                To set file, type --file=9000 or -f 9000
                Try python client.py -d localhost -p 9000 -f 1b"""
    try:
        opts, args = getopt.getopt(
            argv, "hd:p:f:", ["help", "domain=", "port=", "file="])
    except getopt.GetoptError:
        print help
        exit(2)
    host, file_name, port = (-1,) * 3
    for opt, arg in opts:
        if opt in ['-h', "help"]:
            print help
            exit(2)
        elif opt in ("-p", "--port"):
            port = int(arg)
        elif opt in ("-d", "--domain"):
            host = arg
        elif opt in ("-f", "--file"):
            file_name = arg
    if -1 in [host, file_name, port]:
        print "OI! You didn't supply one of the required values!!!!"
        print help
        exit(2)
    return host, port, file_name


def parse_input_reciever(argv):
    help = """To set port, type --port=9000 or -p 9000
                To set lossfile, type --file=file_name or -f file_name
            """
    try:
        opts, args = getopt.getopt(
            argv, "hd:p:f:", ["help", "port=", "file="])
    except getopt.GetoptError:
        print help
        exit(2)
    host, file_name, port = (-1,) * 3
    for opt, arg in opts:
        if opt in ['-h', "help"]:
            print help
            exit(2)
        elif opt in ("-p", "--port"):
            port = int(arg)
        elif opt in ("-f", "--file"):
            file_name = arg
    if -1 in [file_name, port]:
        print "OI! You didn't supply one of the required values!!!!"
        print help
        exit(2)
    return port, file_name


class Node(object):

    """docstring for Node"""

    def __init__(self, key, next):
        super(Node, self).__init__()
        self.key = key
        self.next = next


class SentList(object):

    """docstring for SentList"""

    def __init__(self):
        super(SentList, self).__init__()
        self.len = 0

    def add(s, key):
        s.len += 1
        if s.head:
            node = Node(key, None)
            s.tail.next = node
            s.tail = node
        else:
            s.head = Node(key, None)
            s.tail = s.head

    def pop(s):
        if s.head:
            s.len -= 1
            t = s.head
            s.head = t.next
            return t.key
        return None

    def peek(s):
        return s.head.key


class SequenceCounter(object):

    """docstring for SequenceCounter"""

    def __init__(self, max_count):
        super(SequenceCounter, self).__init__()
        self.max_count = max_count
        self.current_count = -1

    def next(s):
        s.current_count += 1
        if s.current_count == s.max_count:
            s.current_count = 0
        return s.current_count


class SegmentCount(object):

    """Segment, ack_count tuple"""

    def __init__(self, segment, ack_count):
        super(SegmentCount, self).__init__()
        self.ack_count = ack_count
        self.segment = segment


class Window(object):

    """Current Window"""

    def __init__(s, **kwargs):
        super(Window, s).__init__()
        s.MSS = kwargs["MSS"]
        s.ssthresh = kwargs["ssthresh"]
        s.max_cwnd = kwargs["max_cwnd"]
        s.sequence_counter = SequenceCounter(kwargs["max_sequence_number"])
        s.timeout_length = kwargs["timeout_length"]
        s.cwnd = s.MSS
        s.dup_ack_count = 0
        s.empty_window = False
        s.sent = {}
        s.state_machine = kwargs["state_machine"]
        s.sent_list = SentList()

    def unused_capacity(s):
        used = len(s.sent) * s.MSS
        return int((s.cwnd - used) / s.MSS)

    def increase_cwnd(s, more_in_bytes):
        x = s.cwnd + more_in_bytes
        s.cwnd = x if x < s.max_cwnd else s.max_cwnd

    def shift_window(s):
        while s.sent[s.sent_list.peek()].ack_count > 0:
            del s.sent[s.sent_list.pop()]

    def add_ack(s, key):
        if key in s.sent:
            ack_count = s.sent[key].ack_count
            if ack_count == 0:
                event = Event("new_ack", key)
                s.sent[key].ack_count += 1
            elif ack_count == 1:
                s.dup_ack_count += 1
                if s.dup_ack_count > 3:
                    event = Event("triple_ack", key)
                else:
                    event = Event("dup_ack", key)
        return event

    def add_new_segments(s):
        for _ in s.unused_capacity():
            key = s.sequence_counter.next()
            try:
                s.sent[key] = SegmentCount(s.state_machine.get_segment(), 0)
                s.sent_list.add(key)
                s.empty_window = False
            except StopIteration:
                s.empty_window = True
                break

    def run(s):
        s.shift_window()
        s.add_new_segments()
        for _ in s.unused_capacity():
