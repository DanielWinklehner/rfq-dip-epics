"""The ready file of `python -m mist2sim --ready-file`: it exists exactly while every simulator
listens. The emulation's health check waits for it before an IOC is started."""

import asyncio
import os
import tempfile
import unittest

from helpers import Echo

from mist2sim.core import serve


class ReadyFileTest(unittest.TestCase):
    def test_exists_only_while_listening(self):
        sim = Echo("echo", baud=115200)
        path = os.path.join(tempfile.mkdtemp(), "ready")

        async def run():
            stop = asyncio.Event()
            task = asyncio.create_task(serve([sim], "127.0.0.1", stop, ready_file=path))
            for _ in range(500):
                if os.path.exists(path) or task.done():
                    break
                await asyncio.sleep(0.01)
            self.assertTrue(os.path.exists(path), "no ready file 5 s after the start")
            _, writer = await asyncio.open_connection("127.0.0.1", sim.port)   # port is open
            writer.close()
            stop.set()
            await task
            self.assertFalse(os.path.exists(path), "ready file left after the stop")

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
