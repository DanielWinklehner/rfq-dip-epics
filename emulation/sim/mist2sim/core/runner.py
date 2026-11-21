"""Running simulators: in the foreground (python -m mist2sim) or in a background thread (tests)."""

import asyncio
import signal
import threading


async def serve(sims, host="0.0.0.0", stop_event=None):
    """Start all simulators and run until stop_event is set (or SIGTERM / SIGINT)."""
    stop_event = stop_event or asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except (NotImplementedError, RuntimeError, ValueError):
            pass   # not in the main thread
    started = []
    try:
        for sim in sims:
            await sim.start(host)
            started.append(sim)
        await stop_event.wait()
    finally:
        for sim in started:
            await sim.stop()


class SimThread:
    """Runs simulators on 127.0.0.1 in a background thread:

        with SimThread([sim]) as t:
            ... connect to sim.port and sim.control_port ...
    """

    def __init__(self, sims, host="127.0.0.1"):
        self.sims = list(sims)
        self.host = host
        self._ready = threading.Event()
        self._error = None

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(10)
        if self._error:
            raise self._error
        return self

    def __exit__(self, *exc):
        self.loop.call_soon_threadsafe(self._stop.set)
        self._thread.join(10)

    def call(self, fn, *args):
        """Run fn(*args) in the simulator thread and return its result."""
        fut = asyncio.run_coroutine_threadsafe(self._call(fn, *args), self.loop)
        return fut.result(10)

    @staticmethod
    async def _call(fn, *args):
        return fn(*args)

    def _run(self):
        self.loop = asyncio.new_event_loop()

        async def main():
            self._stop = asyncio.Event()
            try:
                for sim in self.sims:
                    await sim.start(self.host)
            except Exception as exc:
                self._error = exc
                self._ready.set()
                return
            self._ready.set()
            await self._stop.wait()
            for sim in self.sims:
                await sim.stop()

        try:
            self.loop.run_until_complete(main())
        finally:
            self.loop.close()
