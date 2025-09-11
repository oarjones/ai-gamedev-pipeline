from app.services.process_manager import ProcessManager, ManagedProcess


def test_stop_order_preference(monkeypatch):
    pm = ProcessManager()
    order = []

    class Dummy(ManagedProcess):
        def __init__(self, name: str):
            super().__init__(name=name, command=["echo", name])
        def stop(self, graceful: bool = True) -> None:
            order.append(self.name)

    # Inject fake processes in start order: unity -> unity_bridge -> blender -> blender_bridge
    pm.procs = {
        "unity": Dummy("unity"),
        "unity_bridge": Dummy("unity_bridge"),
        "blender": Dummy("blender"),
        "blender_bridge": Dummy("blender_bridge"),
    }

    pm.stopAll()
    assert order == ["blender_bridge", "unity_bridge", "blender", "unity"]


def test_status_contains_last_stderr():
    mp = ManagedProcess(name="x", command=["echo", "x"])
    # simulate stderr content
    mp._stderr_buf.append(b"error: something happened\n")
    st = mp.status()
    assert "lastStderr" in st
    assert "something happened" in st["lastStderr"]

