"""Release invariants: portable OAuth config, live tool snapshot, complete safe archive."""
from __future__ import annotations
import importlib.util
import json
import re
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('package_release', ROOT / 'scripts/package_release.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class HostedMcpTest(unittest.TestCase):
    def test_remote_config_has_no_local_process_or_embedded_credentials(self):
        config = json.loads((ROOT / '.mcp.json').read_text())
        self.assertEqual(config, {'mcpServers': {'shieldlabs': {'type': 'http', 'url': 'https://mcp.shieldlabs.ai/mcp'}}})
        for directory in ('.claude-plugin', '.codex-plugin', '.grok-plugin'):
            manifest = json.loads((ROOT / directory / 'plugin.json').read_text())
            self.assertEqual(manifest['mcpServers'], './.mcp.json')

    def test_live_snapshot_covers_21_unique_tool_inputs(self):
        catalog = json.loads((ROOT / 'skills/shieldlabs-investigate/references/mcp-catalog.json').read_text())
        tools = {t['name'].removeprefix('shieldlabs_'): t for t in catalog['tools']}
        self.assertEqual(len(tools), 21)
        self.assertEqual(set(tools), {
            'check_connection', 'list_domains', 'get_domain', 'add_domain', 'patch_domain', 'delete_domain', 'rotate_server_key',
            'list_webhooks', 'get_webhook', 'create_webhook', 'patch_webhook', 'delete_webhook', 'disable_webhook',
            'enable_webhook', 'rotate_webhook_secret', 'verify_webhook', 'test_webhook',
            'get_identification', 'search_history', 'summarize_entity', 'explain_risk_score'})
        self.assertEqual(tools['check_connection']['parameters'], [])
        self.assertEqual(tools['list_domains']['parameters'], [])
        for name in ('delete_domain', 'delete_webhook', 'disable_webhook', 'rotate_server_key', 'rotate_webhook_secret'):
            confirm = next(p for p in tools[name]['parameters'] if p['name'] == 'confirm')
            self.assertTrue(confirm['required'])
            self.assertEqual(confirm['type'], 'true')
        for name in ('get_identification', 'search_history', 'summarize_entity', 'explain_risk_score'):
            self.assertIn('domain', [p['name'] for p in tools[name]['parameters']])
        self.assertEqual({name for name, tool in tools.items() if any(p['name'] == 'response_format' for p in tool['parameters'])},
                         {'get_identification', 'search_history', 'summarize_entity', 'explain_risk_score'})

    def test_active_skill_tool_names_exist_in_the_hosted_catalog(self):
        catalog = json.loads((ROOT / 'skills/shieldlabs-investigate/references/mcp-catalog.json').read_text())
        known = {tool['name'] for tool in catalog['tools']}
        pattern = re.compile(r'\b(shieldlabs_(?:verify|get|current|list|add|patch|delete|rotate|create|disable|enable|test|check|search|summarize|explain)_[a-z_]+)\b')
        for path in (ROOT / 'skills').rglob('*.md'):
            if path.name == 'tools.md':  # contains the explicit migration list of removed tools
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                unknown = set(pattern.findall(path.read_text())) - known
                self.assertEqual(unknown, set())

    def test_archive_is_reproducible_and_installs_hidden_config_with_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            archive = package.build(ROOT, out)
            first = archive.read_bytes()
            self.assertEqual(package.build(ROOT, out).read_bytes(), first)
            self.assertTrue(archive.with_suffix('.zip.sha256').is_file())
            with zipfile.ZipFile(archive) as zipped:
                names = zipped.namelist()
                self.assertFalse(any('/.env' in n or '/.git/' in n or '__pycache__' in n for n in names))
                self.assertEqual(len([n for n in names if n.endswith('/SKILL.md')]), 8)
                zipped.extractall(out / 'installed')
            installed = next((out / 'installed').iterdir())
            for directory in ('.claude-plugin', '.codex-plugin', '.grok-plugin'):
                manifest = json.loads((installed / directory / 'plugin.json').read_text())
                self.assertTrue((installed / manifest['mcpServers']).is_file())
            config = json.loads((installed / '.mcp.json').read_text())
            self.assertEqual(config['mcpServers']['shieldlabs']['url'], 'https://mcp.shieldlabs.ai/mcp')
            self.assertTrue((installed / 'skills/shieldlabs-investigate/references/mcp-catalog.json').is_file())


if __name__ == '__main__':
    unittest.main()
