"""Spec 0002 — living architecture docs: the census engine and ledger."""
import json
import os
import unittest

from helpers import REPO, TempCase

CENSUS = os.path.join(REPO, ".claude", "scripts", "census.py")

ORDER_HANDLER = """namespace Shop.Orders
{
    // class Ghost : IRequestHandler<X> {}   <- a comment, not a handler
    public class PlaceOrderHandler : IRequestHandler<PlaceOrder, Result>
    {
        public static class Keys { public const string Timeout = "Orders:Timeout"; }
        public void Run(IConfiguration configuration)
        {
            var t = configuration.GetValue<int>(Keys.Timeout);
            var url = configuration["Orders:BaseUrl"];
        }
    }
    public enum OrderStatus { Draft, Placed = 2, [Obsolete] Cancelled }
}
"""
CONTROLLER = """namespace Shop.Api
{
    [Route("api/[controller]")]
    public class OrdersController : ControllerBase
    {
        [HttpGet("{id}")] public IActionResult Get(int id) => Ok();
        [HttpPost] public IActionResult Create() => Ok();
    }
}
"""


class CensusCase(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("shop", {
            "src/Orders/PlaceOrderHandler.cs": ORDER_HANDLER,
            "src/Api/OrdersController.cs": CONTROLLER,
            "src/Orders.Domain/Order.cs": "namespace Shop.Orders.Domain { public class Order {} }\n",
        })
        self.configure({"enabled": True, "extractor": "dotnet-layered"})
        self.docs = os.path.join(self.repo, "docs")
        self.write(os.path.join(self.docs, "architecture", "module-structure.md"),
                   "---\ndoc_type: architecture\nstatus: active\n---\n"
                   "`PlaceOrderHandler` reads `Orders:Timeout`.\n"
                   "Domain never references infrastructure.\n"
                   '<!-- census-probe id=R-01 kind=rule paths="src/*.Domain/*.cs" pattern="using [A-Za-z.]*Infrastructure" -->\n'
                   '<!-- census-probe id=F-01 kind=finding paths="src/**/*.cs" pattern="Thread\\.Sleep" -->\n')

    def configure(self, census):
        self.write(os.path.join(self.repo, ".claude", "project-config.json"),
                   json.dumps({"main_integration_branch": "main", "census": census}))

    def census(self, *args, check=True):
        result = self.run_py(CENSUS, "--project-dir", self.repo, *args, check=check)
        return json.loads(result.stdout), result.returncode

    def commit(self, files, message):
        for rel, text in files.items():
            self.write(os.path.join(self.repo, rel), text)
        self.git(self.repo, "add", "-A", "--", "src")
        self.git(self.repo, "commit", "-q", "-m", message)
        return self.git(self.repo, "rev-parse", "HEAD")


class TestInventory(CensusCase):
    def test_extractor_inventory(self):
        report, _ = self.census("run", "--write")
        rows = open(os.path.join(self.docs, "architecture", "census", "census.tsv"), encoding="utf-8").read()
        self.assertIn("handler\tShop.Orders.PlaceOrderHandler\t", rows)
        self.assertNotIn("Ghost", rows)
        self.assertIn("config\tOrders:BaseUrl\t", rows)
        self.assertIn("enum\tOrderStatus.Cancelled\t", rows)
        self.assertIn("endpoint\tGET /api/Orders/{id}\t", rows)
        self.assertIn("endpoint\tPOST /api/Orders\t", rows)
        self.assertFalse(report["baseline"])
        mentions = open(os.path.join(self.docs, "architecture", "census", "mentions.tsv"), encoding="utf-8").read()
        self.assertIn("handler\tShop.Orders.PlaceOrderHandler\tarchitecture/module-structure.md", mentions)

    def test_ac02_config_key_held_in_const(self):
        self.census("run", "--write")
        rows = open(os.path.join(self.docs, "architecture", "census", "census.tsv"), encoding="utf-8").read()
        self.assertIn("config\tOrders:Timeout\t", rows)
        self.assertNotIn("?Keys.Timeout", rows)

    def test_ac01_feature_branch_is_not_drift(self):
        self.census("run", "--write")
        self.git(self.repo, "checkout", "-q", "-b", "feature/refund")
        self.commit({"src/Orders/RefundHandler.cs": "namespace Shop.Orders { public class RefundHandler : IRequestHandler<R, X> {} }\n"}, "refund")
        self.write(os.path.join(self.repo, "src", "Orders", "Uncommitted.cs"), "public class DraftHandler {}\n")
        report, _ = self.census("run")
        self.assertFalse(report["drift"], report)
        self.assertEqual(report["added"], [])
        self.git(self.repo, "checkout", "-q", "main")
        self.git(self.repo, "merge", "-q", "feature/refund")
        report, _ = self.census("run")
        self.assertEqual(report["added"], ["handler\tShop.Orders.RefundHandler"])

    def test_removed_item_reports_docs_that_still_cite_it(self):
        self.census("run", "--write")
        self.git(self.repo, "rm", "-q", "src/Orders/PlaceOrderHandler.cs")
        self.git(self.repo, "commit", "-q", "-m", "drop handler")
        report, _ = self.census("run")
        removed = {r["item"]: r["still_cited_by"] for r in report["removed"]}
        self.assertEqual(removed["handler\tShop.Orders.PlaceOrderHandler"], ["architecture/module-structure.md"])

    def test_probes_rule_and_finding(self):
        report, _ = self.census("run")
        states = {p["id"]: p["state"] for p in report["probes"]}
        self.assertEqual(states, {"R-01": "holds", "F-01": "silent"})
        self.commit({"src/Orders.Domain/Order.cs": "using Shop.Infrastructure;\nclass Order { void W() { Thread.Sleep(1); } }\n"}, "bad")
        report, _ = self.census("run")
        states = {p["id"]: p["state"] for p in report["probes"]}
        self.assertEqual(states, {"R-01": "violated", "F-01": "alive"})
        self.assertTrue(report["drift"])

    def test_ac03_extractor_none(self):
        self.configure({"enabled": True, "extractor": "none"})
        report, _ = self.census("run", "--write")
        self.assertEqual(report["inventory_size"], 0)
        self.assertEqual(len(report["probes"]), 2)
        self.census("ledger", "init")
        added, _ = self.census("ledger", "add-pending", "--spec", "0001", "--task", "1", "--files", "src/a.cs")
        self.assertEqual(added["added"]["id"], "p-0001")

    def test_census_never_writes_to_code(self):
        before = self.git(self.repo, "status", "--porcelain", "--", "src")
        self.census("run", "--write")
        self.assertEqual(self.git(self.repo, "status", "--porcelain", "--", "src"), before)


class TestLedger(CensusCase):
    def test_ac04_watermark_advances_only_when_everything_is_handled(self):
        self.census("ledger", "init")
        self.census("ledger", "add-pending", "--spec", "0007", "--task", "2", "--files", "src/Orders/A.cs",
                    "--docs", "architecture/module-structure.md")
        first = self.commit({"src/Orders/A.cs": "class A {}\n"}, "a")
        second = self.commit({"src/Orders/B.cs": "class B {}\n"}, "b")

        listing, _ = self.census("commits")
        self.assertEqual([c["commit"] for c in listing["commits"]], [first, second])
        self.assertEqual(listing["commits"][0]["pending_matches"], ["p-0001"])

        result, code = self.census("ledger", "advance", check=False)
        self.assertEqual((code, result["advanced"]), (1, False))
        self.assertEqual([u["commit"] for u in result["unhandled"]], [first, second])

        self.census("ledger", "document", first, "--docs", "architecture/module-structure.md", "--pending", "p-0001")
        result, code = self.census("ledger", "advance", check=False)
        self.assertEqual([u["commit"] for u in result["unhandled"]], [second])
        self.assertFalse(result["advanced"])

        self.census("ledger", "document", second, "--skip", "test-only change")
        result, code = self.census("ledger", "advance")
        self.assertEqual((code, result["advanced"], result["unhandled"]), (0, True, []))
        self.assertEqual(result["watermark"], second)
        ledger = json.load(open(os.path.join(self.docs, "architecture", "census", "ledger.json"), encoding="utf-8"))
        self.assertEqual((ledger["pending"], ledger["documented"]), ([], []))

    def test_init_refuses_to_reset(self):
        self.census("ledger", "init")
        result, code = self.census("ledger", "init", check=False)
        self.assertEqual(code, 2)
        self.assertIn("refusing", result["error"])


if __name__ == "__main__":
    unittest.main()
