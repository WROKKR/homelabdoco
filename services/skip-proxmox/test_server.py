import unittest
from unittest.mock import patch
import server


class ScopeTests(unittest.TestCase):
    def test_vm_projection(self):
        result = server.project({"status": "running", "cpu": 0.1, "mem": 100, "maxmem": 200, "name": "secret", "token": "secret"}, "homeassistant_vm_status")
        self.assertEqual(result["vmid"], 116)
        self.assertEqual(result["state"], "running")
        self.assertEqual(result["cpu_percent"], 10)
        self.assertNotIn("secret", str(result))

    def test_node_projection(self):
        result = server.project({"memory": {"used": 100, "total": 200, "password": "secret"}, "rootfs": {"used": 10}, "cpu": 0.2}, "yggdrasil_host_status")
        self.assertEqual(result["memory_bytes"]["used"], 100)
        self.assertEqual(result["memory_used_percent"], 50)
        self.assertNotIn("secret", str(result))

    def test_units_and_available_are_preserved(self):
        result = server.project({"memory": {"total": 8 * 1024**3, "used": 3 * 1024**3, "free": 1024**3, "available": 4 * 1024**3}}, "yggdrasil_host_status")
        self.assertEqual(result["memory_gib"], {"total": 8, "used": 3, "free": 1, "available": 4})
        self.assertEqual(result["memory_used_percent"], 37.5)

    def test_rejects_scope_and_mutation(self):
        with patch.object(server, "collect") as collect:
            for name, args in (("restart_vm", {}), ("homeassistant_vm_status", {"vmid": 119}), ("yggdrasil_host_status", {"url": "http://evil"})):
                result = server.dispatch({"method": "tools/call", "params": {"name": name, "arguments": args}})
                self.assertTrue(result["isError"])
            collect.assert_not_called()

    def test_exact_routes(self):
        self.assertEqual({v[0] for v in server.ROUTES.values()}, {"/status", "/qemu/116/status/current", "/qemu/118/status/current"})
        self.assertEqual(len(server.TOOLS), 3)

    def test_error_does_not_expose_secret(self):
        with patch.object(server, "collect", side_effect=RuntimeError("secret")):
            result = server.dispatch({"method": "tools/call", "params": {"name": "yggdrasil_host_status"}})
            self.assertTrue(result["isError"])
            self.assertNotIn("secret", str(result))


if __name__ == "__main__":
    unittest.main()
