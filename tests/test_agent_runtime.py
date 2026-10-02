import unittest

from aria_agent.policy import PolicyEngine, SAFE, SENSITIVE
from aria_agent.storage import AgentStore
from aria_agent.workers import WorkerRegistry
from aria_agent.runtime import AgentRuntime


class AgentRuntimeTests(unittest.TestCase):
    def test_policy_requires_approval_for_sensitive_action(self):
        policy = PolicyEngine("supervised")
        self.assertTrue(policy.requires_approval("app.send", sends_external_message=True))

    def test_policy_allows_safe_read(self):
        policy = PolicyEngine("supervised")
        self.assertFalse(policy.requires_approval("web.search"))

    def test_worker_network_is_broad(self):
        names = {w.name for w in WorkerRegistry().all()}
        for expected in {"job_finder", "job_creator", "income", "sales", "communicator", "app_operator", "developer", "reviewer"}:
            self.assertIn(expected, names)
        self.assertGreaterEqual(len(names), 20)

    def test_memory_fallback(self):
        store = AgentStore("")
        store.write_memory("u1", "goal", "Build a business", 0.8)
        rows = store.read_memory("u1")
        self.assertEqual(rows[0]["content"], "Build a business")

    def test_runtime_capabilities(self):
        runtime = AgentRuntime(AgentStore(""))
        manifest = runtime.capability_manifest("u1")
        self.assertIn("app.inspect", {x["name"] for x in manifest["builtin_tools"]})
        self.assertGreaterEqual(len(manifest["workers"]), 20)

    def test_fallback_job_plan(self):
        runtime = AgentRuntime(AgentStore(""))
        plan = runtime._fallback_plan("Find me a software internship in Nigeria")
        self.assertEqual(plan["steps"][0]["tool"], "jobs.search")


if __name__ == "__main__":
    unittest.main()
