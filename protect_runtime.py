#!/usr/bin/env python3

from __future__ import annotations

import base64
import json
import shlex
import subprocess
from dataclasses import dataclass

from chime_tool_config import ChimeToolConfig


@dataclass(frozen=True)
class SshResult:
    stdout: str
    stderr: str
    returncode: int


@dataclass(frozen=True)
class ResolvedProtectRuntime:
    node_binary: str
    inspector_ws_url: str


def ssh_cmd(config: ChimeToolConfig, cmd: str, timeout: int = 30) -> SshResult:
    quoted_password = shlex.quote(config.nvr_password)
    quoted_user_host = shlex.quote(f"{config.nvr_user}@{config.nvr_host}")
    full = (
        f"sshpass -p {quoted_password} ssh -o StrictHostKeyChecking=no "
        f"-o UserKnownHostsFile=/dev/null {quoted_user_host} {cmd}"
    )
    result = subprocess.run(
        full,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return SshResult(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )


def run_remote_node_script(
    config: ChimeToolConfig,
    script_name: str,
    js_code: str,
    timeout: int = 30,
    node_binary: str | None = None,
) -> SshResult:
    b64 = base64.b64encode(js_code.encode()).decode()
    selected_node = node_binary or config.node_binary
    if not selected_node:
        raise ValueError("node_binary must be provided or discoverable before running a remote script")
    cmd = (
        "'echo "
        + b64
        + f" | base64 -d > /tmp/{script_name} && "
        + "NODE_PATH=/usr/share/unifi-protect/app/node_modules "
        + f"{selected_node} /tmp/{script_name}'"
    )
    return ssh_cmd(config, cmd, timeout=timeout)


def discover_node_binary(config: ChimeToolConfig) -> str:
    if config.node_binary:
        return config.node_binary

    result = ssh_cmd(
        config,
        "'command -v node24 || command -v node20 || command -v node || which node24 || which node20 || which node'",
        timeout=15,
    )
    node_binary = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if not node_binary:
        raise ValueError("Could not discover a Node.js binary on the NVR")
    return node_binary


def discover_inspector_ws_url(config: ChimeToolConfig, node_binary: str) -> str:
    if config.inspector_ws_url:
        return config.inspector_ws_url

    remote_js = """
const http = require('http');
const WebSocket = require('ws');

function fetchTargets() {
    return new Promise((resolve, reject) => {
        http.get('http://127.0.0.1:9229/json', (res) => {
            let data = '';
            res.on('data', (chunk) => {
                data += chunk;
            });
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch (error) {
                    reject(error);
                }
            });
        }).on('error', reject);
    });
}

function probeTarget(url) {
    return new Promise((resolve) => {
        const ws = new WebSocket(url);
        const id = 1;
        const timer = setTimeout(() => {
            try { ws.terminate(); } catch (error) {}
            resolve(false);
        }, 3000);

        ws.on('open', () => {
            ws.send(JSON.stringify({
                id,
                method: 'Runtime.evaluate',
                params: {
                    expression: 'typeof globalThis.__webpackRequire === "function"',
                    returnByValue: true,
                },
            }));
        });

        ws.on('message', (data) => {
            try {
                const msg = JSON.parse(data.toString());
                if (msg.id !== id) {
                    return;
                }
                clearTimeout(timer);
                ws.close();
                resolve(!!(msg.result && msg.result.result && msg.result.result.value));
            } catch (error) {
                clearTimeout(timer);
                try { ws.close(); } catch (closeError) {}
                resolve(false);
            }
        });

        ws.on('error', () => {
            clearTimeout(timer);
            resolve(false);
        });
    });
}

(async () => {
    const targets = await fetchTargets();
    if (!Array.isArray(targets) || !targets.length) {
        process.exit(2);
    }
    for (const target of targets) {
        if (!target.webSocketDebuggerUrl) {
            continue;
        }
        if (await probeTarget(target.webSocketDebuggerUrl)) {
            console.log(target.webSocketDebuggerUrl);
            return;
        }
    }
    process.exit(3);
})().catch((error) => {
    console.error(error.message);
    process.exit(1);
});
"""
    result = run_remote_node_script(
        config,
        "discover_inspector_ws_url.js",
        remote_js,
        timeout=15,
        node_binary=node_binary,
    )
    ws_url = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if not ws_url:
        stderr = result.stderr.strip() or "unknown error"
        raise ValueError(f"Could not discover the inspector WebSocket URL: {stderr}")
    return ws_url


def resolve_runtime(config: ChimeToolConfig) -> ResolvedProtectRuntime:
    node_binary = discover_node_binary(config)
    inspector_ws_url = discover_inspector_ws_url(config, node_binary)
    return ResolvedProtectRuntime(
        node_binary=node_binary,
        inspector_ws_url=inspector_ws_url,
    )