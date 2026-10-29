"""Tests for the helper scripts of the shieldlabs-setup skill (standard library unittest)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "shieldlabs-setup" / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module  # dataclasses look the module up while the class is created
    spec.loader.exec_module(module)
    return module


detect_stack = load("detect_stack")
audit_scan = load("audit_scan")


def write(root: Path, files: dict) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


class DetectStackTest(unittest.TestCase):
    def test_cloudflare_worker_with_react(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, {"package.json": json.dumps({"dependencies": {"react": "19", "@cloudflare/vite-plugin": "2"}})})
            app = detect_stack.detect_node(root / "package.json", root)
            self.assertIn("Cloudflare Workers", app["server"])
            self.assertIn("shieldlabs-server (references/node.md)", app["skills"])
            self.assertIn("@shieldlabs-ai/node", " ".join(app["install"]))

    def test_monorepo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, {
                "web/package.json": json.dumps({"dependencies": {"next": "15.0.0", "react": "19.0.0"}}),
                "web/app/page.tsx": "export default function Page() { return null; }\n",
                "api/pyproject.toml": '[project]\nname = "api"\ndependencies = ["fastapi>=0.110", "uvicorn"]\n',
                "worker/go.mod": "module example.com/worker\n\ngo 1.23\n\nrequire github.com/go-chi/chi/v5 v5.0.12\n",
                "legacy/composer.json": json.dumps({"require": {"laravel/framework": "^11.0"}}),
                "billing/pom.xml": "<project><parent><artifactId>spring-boot-starter-parent</artifactId></parent></project>",
                "admin/Admin.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>',
                "spa/package.json": json.dumps({"dependencies": {"vue": "3.5.0"}, "devDependencies": {"vite": "5.0.0"}}),
                "spa/pnpm-lock.yaml": "lockfileVersion: 9\n",
            })
            result = detect_stack.detect(root)
            apps = {app["path"]: app for app in result["apps"]}
            self.assertEqual(apps["web"]["frontend"], "Next.js (App Router)")
            self.assertIn("@shieldlabs-ai/next", apps["web"]["install"][0])
            self.assertIn("@shieldlabs-ai/node", apps["web"]["install"][0])
            self.assertEqual(apps["api"]["server"], "Python (FastAPI)")
            self.assertEqual(apps["api"]["install"], ["pip install shieldlabs"])
            self.assertEqual(apps["worker"]["server"], "Go (chi)")
            self.assertEqual(apps["legacy"]["server"], "PHP (Laravel)")
            self.assertEqual(apps["billing"]["server"], "JVM (Spring Boot)")
            self.assertEqual(apps["admin"]["server"], ".NET (ASP.NET Core)")
            self.assertEqual(apps["spa"]["frontend"], "Vue")
            self.assertTrue(apps["spa"]["install"][0].startswith("pnpm add @shieldlabs-ai/vue @shieldlabs-ai/js"))
            self.assertEqual(result["shieldlabs_installed"], [])

    def test_existing_packages_and_env_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, {
                "package.json": json.dumps({"dependencies": {"react": "18.3.0", "@shieldlabs-ai/react": "^1.0.0",
                                                             "@shieldlabs-ai/js": "^1.0.0", "express": "4.19.0"}}),
                ".gitignore": "node_modules\n.env\n",
                ".env": "SHIELDLABS_API_KEY=sec_your_private_key\n",
                ".env.example": "SHIELDLABS_API_KEY=\n",
            })
            result = detect_stack.detect(root)
            app = result["apps"][0]
            self.assertEqual(app["frontend"], "React")
            self.assertEqual(app["server"], "Node.js (Express)")
            self.assertEqual(app["installed"], ["@shieldlabs-ai/js", "@shieldlabs-ai/react"])
            self.assertEqual(app["install"], ["npm install @shieldlabs-ai/node@1.3.0"])
            env = {entry["file"]: entry for entry in result["env_files"]}
            self.assertTrue(env[".env"]["ignored_by_gitignore"])
            self.assertTrue(env[".env.example"]["example"])
            self.assertIn("React", detect_stack.render(result))

    def test_other_frontends_and_server_rendered_apps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, {
                "site/package.json": json.dumps({"dependencies": {"astro": "4.0.0"}}),
                "backend/requirements.txt": "Django==5.0\n",
            })
            result = detect_stack.detect(root)
            apps = {app["path"]: app for app in result["apps"]}
            self.assertEqual(apps["site"]["frontend"], "Astro (framework-agnostic loader)")
            self.assertEqual(apps["site"]["install"], ["npm install @shieldlabs-ai/js@1.1.0"])
            self.assertEqual(apps["backend"]["server"], "Python (Django)")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, {"composer.json": json.dumps({"require": {"symfony/framework-bundle": "^7.0"}})})
            text = detect_stack.render(detect_stack.detect(root))
            self.assertIn("PHP (Symfony)", text)
            self.assertIn("server-rendered or static pages load @shieldlabs-ai/js", text)

    def test_static_pages_served_by_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, {
                "package.json": json.dumps({"dependencies": {"fastify": "5.0.0", "@fastify/static": "8.0.0"}}),
                "public/index.html": "<form id=\"signup\"></form>\n",
            })
            app = detect_stack.detect(root)["apps"][0]
            self.assertEqual(app["frontend"], "Static HTML pages (public/index.html)")
            self.assertEqual(app["server"], "Node.js (Fastify)")
            self.assertEqual(app["install"], ["npm install @shieldlabs-ai/js@1.1.0 @shieldlabs-ai/node@1.3.0"])
            self.assertIn("shieldlabs-browser (references/vanilla.md)", app["skills"])

    def test_empty_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = detect_stack.detect(Path(tmp))
            self.assertEqual(result["apps"], [])
            self.assertIn("No frontend or backend manifest found", detect_stack.render(result))


BAD_CLIENT = """
'use client';
import { useEffect } from 'react';
import { useIdentify } from '@shieldlabs-ai/react';

export function SignupForm({ user, pathname }) {
  const { identify } = useIdentify();
  useEffect(() => {
    identify({ userId: user.email });
  }, [pathname]);
  const key = process.env.NEXT_PUBLIC_SHIELDLABS_API_KEY;
  return null;
}
"""

BAD_SERVER = """
import express from 'express';
import { ShieldLabs } from '@shieldlabs-ai/node';

const app = express();
app.use(express.json());
const shieldlabs = new ShieldLabs({ apiKey: 'sec_abcdefgh-ijklmnop-qrstuvwx' });

app.post('/signup', async (req, res) => {
  const identification = await shieldlabs.identifications.get(req.body.requestId);
  if ((identification?.risk_score ?? 0) >= 60) return res.sendStatus(403);
  res.sendStatus(201);
});
"""

BAD_WEBHOOK = """
import express from 'express';
import { webhooks } from '@shieldlabs-ai/node';

const app = express();
app.use(express.json());
app.post('/webhooks/shieldlabs', (req, res) => {
  const event = webhooks.constructEvent(JSON.stringify(req.body), req.get('x-shield-signature'), process.env.SHIELDLABS_WEBHOOK_SECRET);
  console.log(event.event_type);
  res.sendStatus(200);
});
"""

GOOD_SERVER = """
import express from 'express';
import { ShieldLabs, ShieldLabsError, SignatureVerificationError, evaluateIdentification, webhooks } from '@shieldlabs-ai/node';

const shieldlabs = new ShieldLabs({ apiKey: process.env.SHIELDLABS_API_KEY });
const app = express();

app.post('/webhooks/shieldlabs', express.raw({ type: 'application/json' }), async (req, res) => {
  let event;
  try {
    event = webhooks.constructEvent(req.body, req.get('x-shield-signature'), process.env.SHIELDLABS_WEBHOOK_SECRET);
  } catch (error) {
    return res.sendStatus(error instanceof SignatureVerificationError ? 401 : 400);
  }
  if (event.event_type === 'identification.scored' && (await claimDelivery(event.data.request_id))) await enqueue(event.data);
  return res.sendStatus(200);
});

app.use(express.json());

app.post('/api/signup', async (req, res) => {
  let identification = null;
  try {
    identification = await shieldlabs.identifications.get(req.body.requestId);
  } catch (error) {
    if (!(error instanceof ShieldLabsError)) throw error;
  }
  const firstUse = identification ? await claimRequestId(identification.request_id) : false;
  const verdict = evaluateIdentification(identification, { isReplay: () => !firstUse });
  return res.sendStatus(verdict.ok ? 201 : 403);
});
"""


class AuditScanTest(unittest.TestCase):
    def scan(self, files: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, files)
            return audit_scan.scan(root)

    @staticmethod
    def checks(result: dict) -> set:
        return {finding["check"] for finding in result["findings"]}

    def test_flags_a_broken_integration(self) -> None:
        result = self.scan({
            "web/SignupForm.tsx": BAD_CLIENT,
            "api/signup.js": BAD_SERVER,
            "api/webhook.js": BAD_WEBHOOK,
            ".env": "SHIELDLABS_API_KEY=sec_realkey1-realkey2-realkey3\n",
            "public/snippet.js": "// copied ShieldLabs agent\nexport const shieldlabs = 1;\n",
        })
        found = self.checks(result)
        for check in ("SL01", "SL02", "SL04", "SL06", "SL07", "SL08", "SL09", "SL11", "SL12", "SL13", "SL15"):
            self.assertIn(check, found, f"{check} not reported: {sorted(found)}")
        self.assertTrue(result["shieldlabs_integration_found"])

    def test_generated_worker_and_installed_skills_are_not_application_code(self) -> None:
        result = self.scan({
            ".cloudflare/output/bundle.js": BAD_SERVER,
            ".agents/skills/shieldlabs-setup/scripts/audit_scan.py": BAD_SERVER,
            "server.js": GOOD_SERVER,
        })
        self.assertEqual(result["findings"], [])

    def test_sdk_format_placeholder_is_not_a_secret(self) -> None:
        result = self.scan({"server.js": "const message = 'apiKey must look like sec_xxxxxxxx-xxxxxxxx-xxxxxxxx';"})
        self.assertNotIn("SL01", self.checks(result))

    def test_masks_secrets(self) -> None:
        result = self.scan({"api/signup.js": BAD_SERVER, ".env": "SHIELDLABS_API_KEY=sec_realkey1-realkey2-realkey3\n"})
        text = json.dumps(result)
        self.assertNotIn("sec_abcdefgh-ijklmnop-qrstuvwx", text)
        self.assertNotIn("sec_realkey1-realkey2-realkey3", text)
        self.assertIn("sec_********-********-********", audit_scan.render(result))

    def test_clean_integration_has_no_findings(self) -> None:
        result = self.scan({
            "server.js": GOOD_SERVER,
            ".gitignore": ".env\n",
            ".env": "SHIELDLABS_API_KEY=sec_realkey1-realkey2-realkey3\n",
            ".env.example": "SHIELDLABS_API_KEY=sec_your_private_key\n",
        })
        self.assertEqual(result["findings"], [], json.dumps(result["findings"], indent=2))

    def test_null_fallback_is_not_a_clean_default(self) -> None:
        result = self.scan({"api/log.ts": """
            import { getIdentification } from '@shieldlabs-ai/next/server';
            export function describe(identification) {
              console.info('verdict', identification?.risk_score ?? null, identification?.request_id ?? null);
            }
        """})
        self.assertNotIn("SL08", self.checks(result))
        result = self.scan({"api/check.ts": """
            import { getIdentification } from '@shieldlabs-ai/next/server';
            export const score = (identification) => identification?.risk_score ?? 0;
            export const low = (identification) => identification?.risk_score ?? 10;
        """})
        self.assertEqual([f["line"] for f in result["findings"] if f["check"] == "SL08"], [2, 3])

    def test_guards_in_another_file(self) -> None:
        result = self.scan({
            "server/shieldlabs.js": """
                import { ShieldLabs } from '@shieldlabs-ai/node';
                const shieldlabs = new ShieldLabs({ apiKey: process.env.SHIELDLABS_API_KEY });
                export async function readIdentification(requestId) {
                  try { return await shieldlabs.identifications.get(requestId); } catch { return null; }
                }
            """,
            "server/risk-policy.js": """
                import { evaluateIdentification } from '@shieldlabs-ai/node';
                export function decide(identification, firstUse) {
                  return evaluateIdentification(identification, { isReplay: () => !firstUse });
                }
            """,
        })
        self.assertFalse(self.checks(result) & {"SL06", "SL07"}, json.dumps(result["findings"], indent=2))

    def test_user_hid_and_raw_ids(self) -> None:
        result = self.scan({"checkout.tsx": """
            import { useIdentify } from '@shieldlabs-ai/react';
            export function Checkout({ session }) {
              const good = useIdentify({ userId: session.userHid });
              const bad = useIdentify({ userId: session.user.id });
              return null;
            }
        """})
        self.assertEqual([f["check"] for f in result["findings"]], ["SL10"])

    def test_test_fixtures_are_not_secrets(self) -> None:
        result = self.scan({"tests/fixtures.js": "export const key = 'sec_abcdefgh-ijklmnop-qrstuvwx';\n"})
        self.assertNotIn("SL01", self.checks(result))

    def test_signed_test_deliveries_are_not_hand_written_checks(self) -> None:
        signer = """
            import { createHmac } from 'node:crypto';
            import { ShieldLabs } from '@shieldlabs-ai/node';
            export function sign(body, secret) {
              return { 'X-Shield-Signature': 'sha256=' + createHmac('sha256', secret).update(body).digest('hex') };
            }
        """
        for name in ("tests/webhook.js", "src/__tests__/webhook.js", "src/webhook.test.ts", "e2e/deliveries.spec.ts"):
            self.assertNotIn("SL05", self.checks(self.scan({name: signer})), name)
        self.assertIn("SL05", self.checks(self.scan({"src/verify-webhook.js": signer})))

    def test_documented_placeholders_are_not_secrets(self) -> None:
        result = self.scan({
            "docker-compose.yml": "environment:\n  SHIELDLABS_API_KEY: sec_test0000-test0000-test0000\n",
            "scripts/check.mjs": "const secret = 'whsec_00112233445566778899aabbccddeeff';\n",
        })
        self.assertNotIn("SL01", self.checks(result))

    def test_no_integration(self) -> None:
        result = self.scan({"index.js": "console.log('hello');\n"})
        self.assertFalse(result["shieldlabs_integration_found"])
        self.assertIn("No ShieldLabs integration found", audit_scan.render(result))

    def test_strict_exit_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, {"api/signup.js": BAD_SERVER})
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(audit_scan.main(["audit_scan.py", str(root), "--json"]), 0)
                self.assertEqual(audit_scan.main(["audit_scan.py", str(root), "--strict", "--json"]), 1)
            self.assertIn('"SL06"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
