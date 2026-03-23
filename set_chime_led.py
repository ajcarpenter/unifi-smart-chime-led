#!/usr/bin/env python3
"""
set_chime_led.py - Toggle the UP Chime PoE LED through Protect's live DeviceConnection.

Usage:
  python3 set_chime_led.py off
  python3 set_chime_led.py on --config /path/to/chime_tool_config.local.json
"""

import argparse
import json
import textwrap

from chime_tool_config import load_config
from protect_runtime import resolve_runtime, run_remote_node_script


def build_js(config, runtime, state):
    inner = textwrap.dedent(
        """
        (async () => {
          const c = globalThis.__chimeConn;
          if (!c || !c.ws || c.ws.readyState !== 1) {
            return JSON.stringify({ error: 'CHIME_CONN_NOT_READY' });
          }
          try {
            const response = await c.request('setLEDState', { state: __STATE__ }, { ttl: 5000, useCompress: false });
            return JSON.stringify({ ok: true, requestedState: __STATE__, response });
          } catch (error) {
            return JSON.stringify({ ok: false, requestedState: __STATE__, error: error && error.message ? error.message : String(error) });
          }
        })()
        """
    ).replace("__STATE__", json.dumps(state))

    return textwrap.dedent(
        """
        const WebSocket = require('ws');
        const ws = new WebSocket(__WS_URL__);
        const hardTimeout = setTimeout(() => {
          console.error('TIMEOUT');
          process.exit(1);
        }, 15000);
        const pending = new Map();
        let nextId = 1;

        function send(method, params) {
          return new Promise((resolve, reject) => {
            const id = nextId++;
            pending.set(id, { resolve, reject });
            ws.send(JSON.stringify({ id, method, params }));
          });
        }

        async function refreshChimeConn() {
          let moduleId = __DC_MODULE_ID__;
          if (!moduleId) {
            const moduleIdResult = await send('Runtime.evaluate', {
              expression: `(() => {
                const wp = globalThis.__webpackRequire;
                if (!wp || !wp.m) {
                  throw new Error('webpack require cache unavailable');
                }
                for (const id of Object.keys(wp.m)) {
                  try {
                    const mod = wp(id);
                    const proto = mod && typeof mod.default === 'function' ? mod.default.prototype : null;
                    if (!proto) {
                      continue;
                    }
                    const names = Object.getOwnPropertyNames(proto);
                    const required = ['close', 'httpRequest', 'request', 'respondToRequest', 'event', 'error', 'send', 'onMessage', 'waitForPendingRequests', 'destroy'];
                    if (required.every((name) => names.includes(name))) {
                      return Number(id);
                    }
                  } catch (error) {
                  }
                }
                throw new Error('DeviceConnection module not found');
              })()`,
              returnByValue: true,
            });
            moduleId = moduleIdResult.result.result.value;
          }
          const protoRef = await send('Runtime.evaluate', {
            expression: '(() => globalThis.__webpackRequire(' + moduleId + ').default.prototype)()',
            returnByValue: false,
          });

          const qr = await send('Runtime.queryObjects', {
            prototypeObjectId: protoRef.result.result.objectId,
          });

          const props = await send('Runtime.getProperties', {
            objectId: qr.result.objects.objectId,
            ownProperties: true,
          });

          let items = (props.result.result || []).filter(
            (prop) => prop.name !== 'length' && prop.value && prop.value.objectId,
          );

          if (!items.length && moduleId !== 3210) {
            const fallbackProtoRef = await send('Runtime.evaluate', {
              expression: '(() => globalThis.__webpackRequire(3210).default.prototype)()',
              returnByValue: false,
            });
            const fallbackQr = await send('Runtime.queryObjects', {
              prototypeObjectId: fallbackProtoRef.result.result.objectId,
            });
            const fallbackProps = await send('Runtime.getProperties', {
              objectId: fallbackQr.result.objects.objectId,
              ownProperties: true,
            });
            items = (fallbackProps.result.result || []).filter(
              (prop) => prop.name !== 'length' && prop.value && prop.value.objectId,
            );
          }

          let activeObjectId = null;
          let fallbackObjectId = null;
          for (const item of items) {
            const info = await send('Runtime.callFunctionOn', {
              objectId: item.value.objectId,
              functionDeclaration: `function() {
                return {
                  mac: this.mac || null,
                  wsState: this.ws ? this.ws.readyState : null,
                };
              }`,
              returnByValue: true,
            });

            const value = info.result.result.value;
            if (!value || value.mac !== __CHIME_MAC__) {
              continue;
            }

            if (fallbackObjectId === null) {
              fallbackObjectId = item.value.objectId;
            }
            if (value.wsState === 1) {
              activeObjectId = item.value.objectId;
            }
          }

          const chosen = activeObjectId || fallbackObjectId;
          if (!chosen) {
            throw new Error('chime connection not found');
          }

          await send('Runtime.callFunctionOn', {
            objectId: chosen,
            functionDeclaration: 'function() { globalThis.__chimeConn = this; return { ok: true, wsState: this.ws ? this.ws.readyState : null }; }',
            returnByValue: true,
          });
        }

        ws.on('message', (data) => {
          const msg = JSON.parse(data.toString());
          if (!msg.id || !pending.has(msg.id)) {
            return;
          }
          const handlers = pending.get(msg.id);
          pending.delete(msg.id);
          handlers.resolve(msg);
        });

        ws.on('open', async () => {
          try {
            await refreshChimeConn();
            const response = await send('Runtime.evaluate', {
              expression: __INNER_EXPR__,
              awaitPromise: true,
              returnByValue: true,
              timeout: 12000,
            });
            console.log(response.result.result.value);
            clearTimeout(hardTimeout);
            ws.close();
          } catch (error) {
            console.error('ERR', error.message);
            process.exit(1);
          }
        });

        ws.on('error', (error) => {
          console.error('ERR', error.message);
          process.exit(1);
        });

        """
    ).replace("__WS_URL__", repr(runtime.inspector_ws_url)).replace("__CHIME_MAC__", json.dumps(config.chime_mac)).replace("__DC_MODULE_ID__", "null" if config.device_connection_module_id is None else str(config.device_connection_module_id)).replace("__INNER_EXPR__", json.dumps(inner))


def parse_args():
  parser = argparse.ArgumentParser(
    description="Toggle the chime LED through Protect's active DeviceConnection."
  )
  parser.add_argument("state", choices=["on", "off"], help="Target LED state")
  parser.add_argument("--config", help="Path to a local JSON config file")
  return parser.parse_args()


def main():
  args = parse_args()
  config = load_config(args.config)
  runtime = resolve_runtime(config)

  js = build_js(config, runtime, args.state)
  result = run_remote_node_script(
    config,
    "set_chime_led.js",
    js,
    timeout=30,
    node_binary=runtime.node_binary,
  )
  if result.stdout:
    print(result.stdout)
  if result.stderr:
    print(result.stderr)


if __name__ == "__main__":
  main()