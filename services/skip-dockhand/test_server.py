import unittest
from unittest.mock import patch
import server


class ScopeTests(unittest.TestCase):
    def test_projection_excludes_secrets_and_config(self):
        result = server.project([{"Names": ["/homepage"], "State": "running", "Status": "Up (healthy)", "Env": ["PASSWORD=secret"], "Labels": {"secret": "secret"}, "Mounts": ["private"]}], 1)
        row = result["containers"][0]
        self.assertEqual(set(row), {"names", "state", "status"})
        self.assertEqual(result["environment_id"], 1)
        self.assertNotIn("secret", str(result))

    def test_environment_and_url_arguments_are_rejected(self):
        with patch.object(server, "collect") as collect:
            for arguments in ({"environmentId": 2}, {"url": "http://evil"}, {"container": "homepage"}):
                self.assertTrue(server.dispatch({"method": "tools/call", "params": {"name": server.TOOLS[0]["name"], "arguments": arguments}})["isError"])
            collect.assert_not_called()

    def test_mutation_tool_is_rejected(self):
        with patch.object(server, "collect") as collect:
            self.assertTrue(server.dispatch({"method": "tools/call", "params": {"name": "restart_container"}})["isError"])
            collect.assert_not_called()

    def test_two_fixed_tools_only(self):
        self.assertEqual(len(server.dispatch({"method": "tools/list"})["tools"]), 2)
        self.assertEqual(server.TOOL_ENVIRONMENTS, {"dockerhost26_container_status": 1, "minecraft_dmz_container_status": 2})

    def test_environment_label_and_invalid_scope(self):
        self.assertEqual(server.project([], 2)["host"], "Minecraft DMZ")
        with self.assertRaises(ValueError):
            server.collect(3)

    def test_tool_routes_to_fixed_environment(self):
        with patch.object(server, "collect", return_value={}) as collect:
            server.dispatch({"method": "tools/call", "params": {"name": "minecraft_dmz_container_status", "arguments": {}}})
            collect.assert_called_once_with(2)

    def test_unknown_shape_fails(self):
        with self.assertRaises(ValueError):
            server.project({"credentials": "secret"}, 1)


if __name__ == "__main__":
    unittest.main()
