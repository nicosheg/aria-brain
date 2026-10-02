import unittest
from unittest.mock import patch

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

    def test_approval_executes_exact_step_once(self):
        runtime = AgentRuntime(AgentStore(""))
        plan = {
            "goal": "Create a record",
            "steps": [
                {"tool": "app.write", "args": {"name": "Nicholas"}, "reason": "Create the requested record"}
            ],
        }
        with patch.object(runtime, "_plan", return_value=plan), patch.object(
            runtime, "_execute_tool", return_value={"created": True}
        ) as execute:
            paused = runtime.run("u2", "Create a record for Nicholas")
            self.assertEqual(paused["status"], "approval_required")
            approval_id = paused["approval"]["id"]
            completed = runtime.approve("u2", approval_id)
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(execute.call_count, 1)

    def test_automation_secret_and_trigger(self):
        import hashlib
        store = AgentStore("")
        runtime = AgentRuntime(store)
        created = runtime.create_automation("u3", "New lead", "lead.created", "Research and qualify this new lead")
        self.assertTrue(created["secret"])
        stored = store.get_automation(created["id"], "u3")
        self.assertEqual(stored["secret_hash"], hashlib.sha256(created["secret"].encode()).hexdigest())


if __name__ == "__main__":
    unittest.main()
