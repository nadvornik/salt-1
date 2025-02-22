import salt.ext.tornado.gen
import salt.transport.client


def run_loop_in_thread(loop, evt):
    """
    Run the provided loop until an event is set
    """
    loop.make_current()

    @salt.ext.tornado.gen.coroutine
    def stopper():
        while True:
            if evt.is_set():
                loop.stop()
                break
            yield salt.ext.tornado.gen.sleep(0.3)

    loop.add_callback(stopper)
    try:
        loop.start()
    finally:
        loop.close()


class ReqChannelMixin:
    def test_basic(self):
        """
        Test a variety of messages, make sure we get the expected responses
        """
        msgs = [
            {"foo": "bar"},
            {"bar": "baz"},
            {"baz": "qux", "list": [1, 2, 3]},
        ]
        for msg in msgs:
            ret = self.channel.send(dict(msg), timeout=2, tries=1)
            self.assertEqual(ret["load"], msg)

    def test_normalization(self):
        """
        Since we use msgpack, we need to test that list types are converted to lists
        """
        types = {
            "list": list,
        }
        msgs = [
            {"list": tuple([1, 2, 3])},
        ]
        for msg in msgs:
            ret = self.channel.send(msg, timeout=2, tries=1)
            for k, v in ret["load"].items():
                self.assertEqual(types[k], type(v))

    def test_badload(self):
        """
        Test a variety of bad requests, make sure that we get some sort of error
        """
        msgs = ["", [], tuple()]
        for msg in msgs:
            ret = self.channel.send(msg, timeout=2, tries=1)
            self.assertEqual(ret, "payload and load must be a dict")


class PubChannelMixin:
    def test_basic(self):
        self.pub = None

        def handle_pub(ret):
            self.pub = ret
            self.stop()

        self.pub_channel = salt.transport.client.AsyncPubChannel.factory(
            self.minion_opts, io_loop=self.io_loop
        )
        connect_future = self.pub_channel.connect()
        connect_future.add_done_callback(lambda f: self.stop())
        self.wait()
        connect_future.result()
        self.pub_channel.on_recv(handle_pub)
        load = {
            "fun": "f",
            "arg": "a",
            "tgt": "t",
            "jid": "j",
            "ret": "r",
            "tgt_type": "glob",
        }
        self.server_channel.publish(load)
        self.wait()
        self.assertEqual(self.pub["load"], load)
        self.pub_channel.on_recv(None)
        self.server_channel.publish(load)
        with self.assertRaises(self.failureException):
            self.wait(timeout=0.5)

        # close our pub_channel, to pass our FD checks
        self.pub_channel.close()
        del self.pub_channel
