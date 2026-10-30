#!/usr/bin/env python3
"""Detect the frontend and backend stacks of a project for a ShieldLabs integration.

Usage: python3 detect_stack.py [PROJECT_DIR] [--json] [--max-depth N]

Read-only and offline. Walks the project (skipping dependency and build folders), reads the
package manifests it finds (package.json, pyproject.toml, requirements*.txt, Pipfile, setup.py,
setup.cfg, go.mod, composer.json, pom.xml, build.gradle, build.gradle.kts, *.csproj) and prints
each app with the ShieldLabs packages that fit it, the matching skill references, the ShieldLabs
packages already installed and the environment files it saw. Standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "out", "target", "bin", "obj", ".next",
    ".nuxt", ".output", ".svelte-kit", ".angular", ".turbo", ".vercel", ".venv", "venv", "env",
    "__pycache__", ".tox", ".mypy_cache", ".pytest_cache", "coverage", ".idea", ".vscode", ".gradle",
}
PY_MANIFESTS = ("pyproject.toml", "Pipfile", "setup.py", "setup.cfg")

# Frontend frameworks, most specific first: (dependency, name, browser packages, browser reference).
FRONTENDS: List[Tuple[str, str, List[str], str]] = [
    ("next", "Next.js", ["@shieldlabs-ai/next", "@shieldlabs-ai/react", "@shieldlabs-ai/js", "@shieldlabs-ai/node"], "nextjs.md"),
    ("nuxt", "Nuxt", ["@shieldlabs-ai/vue", "@shieldlabs-ai/js"], "vue-nuxt.md"),
    ("@sveltejs/kit", "SvelteKit", ["@shieldlabs-ai/svelte", "@shieldlabs-ai/js"], "svelte-sveltekit.md"),
    ("@angular/core", "Angular", ["@shieldlabs-ai/angular", "@shieldlabs-ai/js"], "angular.md"),
    ("svelte", "Svelte", ["@shieldlabs-ai/svelte", "@shieldlabs-ai/js"], "svelte-sveltekit.md"),
    ("vue", "Vue", ["@shieldlabs-ai/vue", "@shieldlabs-ai/js"], "vue-nuxt.md"),
    ("react", "React", ["@shieldlabs-ai/react", "@shieldlabs-ai/js"], "react.md"),
]
# Other frontends and build tools: the framework-agnostic loader fits them.
OTHER_FRONTENDS: List[Tuple[str, str]] = [
    ("astro", "Astro"), ("solid-js", "Solid"), ("preact", "Preact"), ("lit", "Lit"),
    ("@builder.io/qwik", "Qwik"), ("ember-source", "Ember"), ("vite", "Vite"), ("webpack", "webpack"),
    ("parcel", "Parcel"), ("esbuild", "esbuild"),
]
# Node.js server frameworks and full-stack frameworks with server code.
NODE_SERVERS: List[Tuple[str, str]] = [
    ("next", "Next.js route handlers and Server Actions"),
    ("nuxt", "Nuxt server routes"),
    ("@sveltejs/kit", "SvelteKit form actions and endpoints"),
    ("@remix-run/node", "Remix"),
    ("@react-router/node", "React Router"),
    ("@nestjs/core", "NestJS"),
    ("express", "Express"),
    ("fastify", "Fastify"),
    ("koa", "Koa"),
    ("hono", "Hono"),
    ("@hapi/hapi", "hapi"),
]
# HTML pages a Node.js server may send as they are (no template engine, no frontend build).
STATIC_PAGES = ("index.html", "public/index.html", "static/index.html")
PY_FRAMEWORKS = ["django", "fastapi", "flask", "starlette", "litestar", "quart", "sanic", "aiohttp", "tornado", "pyramid", "falcon"]
GO_FRAMEWORKS = [("github.com/gin-gonic/gin", "Gin"), ("github.com/labstack/echo", "Echo"),
                 ("github.com/gofiber/fiber", "Fiber"), ("github.com/go-chi/chi", "chi")]
PHP_FRAMEWORKS = [("laravel/framework", "Laravel"), ("symfony/framework-bundle", "Symfony"),
                  ("symfony/http-kernel", "Symfony"), ("slim/slim", "Slim")]
JVM_FRAMEWORKS = [("spring-boot", "Spring Boot"), ("io.quarkus", "Quarkus"), ("io.micronaut", "Micronaut"),
                  ("io.ktor", "Ktor"), ("io.javalin", "Javalin")]

SERVER_SDKS = {
    "node": ("@shieldlabs-ai/node", "node.md"),
    "python": ("shieldlabs", "python.md"),
    "go": ("github.com/ShieldLabs-ai/shieldlabs-go", "go.md"),
    "php": ("shieldlabs/shieldlabs-php", "php.md"),
    "java": ("ai.shieldlabs:shieldlabs-java", "java.md"),
    "dotnet": ("ShieldLabs", "dotnet.md"),
}


def walk(root: Path, max_depth: int):
    """Yields files under root, skipping dependency and build folders."""
    stack = [(root, 0)]
    while stack:
        folder, depth = stack.pop()
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name not in SKIP_DIRS and not entry.name.startswith(".") and depth < max_depth:
                    stack.append((entry, depth + 1))
            elif entry.is_file():
                yield entry


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def node_install(folder: Path, root: Path) -> str:
    for base in (folder, root):
        if (base / "pnpm-lock.yaml").exists():
            return "pnpm add"
        if (base / "yarn.lock").exists():
            return "yarn add"
        if (base / "bun.lockb").exists() or (base / "bun.lock").exists():
            return "bun add"
    return "npm install"


def python_install(folder: Path) -> str:
    if (folder / "poetry.lock").exists():
        return "poetry add shieldlabs"
    if (folder / "uv.lock").exists():
        return "uv add shieldlabs"
    if (folder / "Pipfile").exists():
        return "pipenv install shieldlabs"
    return "pip install shieldlabs"


def detect_node(manifest: Path, root: Path) -> Optional[dict]:
    try:
        data = json.loads(read_text(manifest))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    deps: Dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            deps.update({str(k): str(v) for k, v in section.items()})
    folder = manifest.parent
    app = {"path": rel(folder, root), "manifest": rel(manifest, root), "language": "node",
           "frontend": None, "server": None, "install": [], "skills": [], "installed": []}
    app["installed"] = sorted(name for name in deps if name.startswith("@shieldlabs-ai/"))
    browser_packages: List[str] = []
    for dep, name, packages, reference in FRONTENDS:
        if dep in deps:
            label = name
            if dep == "next":
                routers = [label for sub, label in (("app", "App Router"), ("src/app", "App Router"),
                                                    ("pages", "Pages Router"), ("src/pages", "Pages Router"))
                           if (folder / sub).is_dir()]
                if routers:
                    label += " (" + ", ".join(sorted(set(routers))) + ")"
            app["frontend"] = label
            browser_packages = packages
            app["skills"].append(f"shieldlabs-browser (references/{reference})")
            break
    if app["frontend"] is None:
        other = next((name for dep, name in OTHER_FRONTENDS if dep in deps), None)
        page = next((name for name in STATIC_PAGES if (folder / name).is_file()), None)
        if other or page:
            app["frontend"] = f"{other} (framework-agnostic loader)" if other else f"Static HTML pages ({page})"
            browser_packages = ["@shieldlabs-ai/js"]
            app["skills"].append("shieldlabs-browser (references/vanilla.md)")
    for dep, name in NODE_SERVERS:
        if dep in deps:
            app["server"] = f"Node.js ({name})"
            break
    if app["server"] is None and "@cloudflare/vite-plugin" in deps:
        app["server"] = "Cloudflare Workers (fetch handler; Node SDK edge export conditions)"
    packages = list(browser_packages)
    if app["server"] and "@shieldlabs-ai/node" not in packages:
        packages.append("@shieldlabs-ai/node")
    if app["server"] and "next" in deps:
        app["skills"].append("shieldlabs-server (@shieldlabs-ai/node: shieldlabs-browser references/nextjs.md)")
    elif app["server"]:
        app["skills"].append("shieldlabs-server (references/node.md)")
    missing = [p for p in packages if p not in deps]
    if missing:
        pins = {"@shieldlabs-ai/js": "@shieldlabs-ai/js@1.1.0", "@shieldlabs-ai/node": "@shieldlabs-ai/node@1.3.2"}
        app["install"].append(f"{node_install(folder, root)} {' '.join(pins.get(package, package) for package in missing)}")
    if app["frontend"] is None and app["server"] is None and not app["installed"]:
        return None
    return app


def python_dependencies(folder: Path) -> str:
    text = ""
    for name in PY_MANIFESTS:
        text += "\n" + read_text(folder / name)
    for path in sorted(folder.glob("requirements*.txt")):
        text += "\n" + read_text(path)
    return text.lower()


def detect_python(folder: Path, root: Path) -> Optional[dict]:
    text = python_dependencies(folder)
    frameworks = [f for f in PY_FRAMEWORKS if re.search(r"(^|[\s\"'\[,=])" + re.escape(f) + r"(\b|[\[<>=~!;\"'])", text, re.M)]
    installed = ["shieldlabs"] if re.search(r"(^|[\s\"'\[,])shieldlabs(\b|[\[<>=~!;\"'])", text, re.M) else []
    if not frameworks and not installed:
        return None
    return {"path": rel(folder, root), "manifest": ", ".join(sorted(p.name for p in manifests_in(folder, "python"))),
            "language": "python", "frontend": None,
            "server": "Python (" + ", ".join(name.capitalize() if name != "fastapi" else "FastAPI" for name in frameworks) + ")" if frameworks else "Python",
            "install": [] if installed else [python_install(folder)],
            "skills": ["shieldlabs-server (references/python.md)"], "installed": installed}


def detect_go(manifest: Path, root: Path) -> dict:
    text = read_text(manifest)
    framework = next((name for module, name in GO_FRAMEWORKS if module in text), "net/http")
    installed = ["github.com/ShieldLabs-ai/shieldlabs-go"] if "github.com/ShieldLabs-ai/shieldlabs-go" in text else []
    return {"path": rel(manifest.parent, root), "manifest": rel(manifest, root), "language": "go", "frontend": None,
            "server": f"Go ({framework})", "install": [] if installed else ["go get github.com/ShieldLabs-ai/shieldlabs-go"],
            "skills": ["shieldlabs-server (references/go.md)"], "installed": installed}


def detect_php(manifest: Path, root: Path) -> Optional[dict]:
    try:
        data = json.loads(read_text(manifest))
    except ValueError:
        return None
    require = {}
    for key in ("require", "require-dev"):
        if isinstance(data, dict) and isinstance(data.get(key), dict):
            require.update(data[key])
    framework = next((name for package, name in PHP_FRAMEWORKS if package in require), "plain PHP")
    installed = ["shieldlabs/shieldlabs-php"] if "shieldlabs/shieldlabs-php" in require else []
    return {"path": rel(manifest.parent, root), "manifest": rel(manifest, root), "language": "php", "frontend": None,
            "server": f"PHP ({framework})", "install": [] if installed else ["composer require shieldlabs/shieldlabs-php"],
            "skills": ["shieldlabs-server (references/php.md)"], "installed": installed}


def detect_jvm(manifest: Path, root: Path) -> dict:
    text = read_text(manifest)
    framework = next((name for marker, name in JVM_FRAMEWORKS if marker in text), "Java")
    installed = ["ai.shieldlabs:shieldlabs-java"] if "ai.shieldlabs" in text else []
    install = "Maven: ai.shieldlabs:shieldlabs-java" if manifest.name == "pom.xml" else 'Gradle: implementation("ai.shieldlabs:shieldlabs-java:<version>")'
    return {"path": rel(manifest.parent, root), "manifest": rel(manifest, root), "language": "java", "frontend": None,
            "server": f"JVM ({framework})", "install": [] if installed else [install],
            "skills": ["shieldlabs-server (references/java.md)"], "installed": installed}


def detect_dotnet(manifest: Path, root: Path) -> dict:
    text = read_text(manifest)
    web = "Microsoft.NET.Sdk.Web" in text
    installed = ["ShieldLabs"] if re.search(r'<PackageReference\s+Include="ShieldLabs"', text) else []
    return {"path": rel(manifest.parent, root), "manifest": rel(manifest, root), "language": "dotnet", "frontend": None,
            "server": ".NET (ASP.NET Core)" if web else ".NET", "install": [] if installed else ["dotnet add package ShieldLabs"],
            "skills": ["shieldlabs-server (references/dotnet.md)"], "installed": installed}


def manifests_in(folder: Path, language: str) -> List[Path]:
    if language == "python":
        found = [folder / name for name in PY_MANIFESTS if (folder / name).exists()]
        return found + sorted(folder.glob("requirements*.txt"))
    return []


def env_files(root: Path) -> List[dict]:
    patterns = []
    gitignore = root / ".gitignore"
    if gitignore.exists():
        for line in read_text(gitignore).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    result = []
    for path in sorted(root.glob(".env*")):
        if not path.is_file():
            continue
        name = path.name
        ignored = any(fnmatch.fnmatch(name, p.lstrip("/")) for p in patterns if not p.startswith("!"))
        if any(fnmatch.fnmatch(name, p[1:].lstrip("/")) for p in patterns if p.startswith("!")):
            ignored = False
        result.append({"file": name, "ignored_by_gitignore": ignored, "example": name.endswith(".example") or name.endswith(".sample")})
    return result


def rel(path: Path, root: Path) -> str:
    try:
        value = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        value = path.as_posix()
    return value or "."


def detect(root: Path, max_depth: int = 4) -> dict:
    apps: List[dict] = []
    python_folders = set()
    for path in walk(root, max_depth):
        name = path.name
        app = None
        if name == "package.json":
            app = detect_node(path, root)
        elif name in PY_MANIFESTS or fnmatch.fnmatch(name, "requirements*.txt"):
            if path.parent not in python_folders:
                python_folders.add(path.parent)
                app = detect_python(path.parent, root)
        elif name == "go.mod":
            app = detect_go(path, root)
        elif name == "composer.json":
            app = detect_php(path, root)
        elif name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            app = detect_jvm(path, root)
        elif name.endswith(".csproj"):
            app = detect_dotnet(path, root)
        if app:
            apps.append(app)
    installed = sorted({pkg for app in apps for pkg in app["installed"]})
    return {"root": str(root.resolve()), "apps": apps, "shieldlabs_installed": installed, "env_files": env_files(root)}


def render(result: dict) -> str:
    lines = [f"ShieldLabs stack detection for {result['root']}", ""]
    if not result["apps"]:
        lines.append("No frontend or backend manifest found. Plain HTML pages can use @shieldlabs-ai/js (the IIFE build);")
        lines.append("see shieldlabs-browser (references/vanilla.md) and shieldlabs-server (references/other-languages.md).")
    for app in result["apps"]:
        lines.append(f"App: {app['path']} ({app['manifest']})")
        if app["frontend"]:
            lines.append(f"  Frontend: {app['frontend']}")
        if app["server"]:
            lines.append(f"  Server:   {app['server']}")
        for command in app["install"]:
            lines.append(f"  Install:  {command}")
        if app["installed"]:
            lines.append(f"  Already installed: {', '.join(app['installed'])}")
        if app["skills"]:
            lines.append(f"  Skills:   {'; '.join(app['skills'])}")
        lines.append("")
    if result["apps"] and not any(app["frontend"] for app in result["apps"]):
        lines.append("No frontend framework found: server-rendered or static pages load @shieldlabs-ai/js (npm, or")
        lines.append("its IIFE build) in their HTML, and the server writes the Public Key into the page; see")
        lines.append("shieldlabs-browser (references/vanilla.md) and shieldlabs-setup (references/environment.md).")
        lines.append("")
    lines.append("ShieldLabs packages already installed: " + (", ".join(result["shieldlabs_installed"]) or "none"))
    if result["env_files"]:
        described = []
        for env in result["env_files"]:
            state = "example" if env["example"] else ("ignored by .gitignore" if env["ignored_by_gitignore"] else "NOT ignored by .gitignore")
            described.append(f"{env['file']} ({state})")
        lines.append("Environment files at the root: " + ", ".join(described))
    else:
        lines.append("Environment files at the root: none (add .env.example with placeholders and keep .env out of git)")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Detect the stack of a project for a ShieldLabs integration.")
    parser.add_argument("project", nargs="?", default=".", help="project directory (default: current directory)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--max-depth", type=int, default=4, help="folder depth to search (default 4)")
    args = parser.parse_args(argv[1:])
    root = Path(args.project)
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2
    result = detect(root, args.max_depth)
    print(json.dumps(result, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
