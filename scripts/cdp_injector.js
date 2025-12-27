#!/usr/bin/env node
/**
 * CDP Injector - Real memory injection via Chrome DevTools Protocol
 *
 * Injects JavaScript directly into Claude's V8 heap.
 * Requires: NODE_OPTIONS="--inspect" when starting Claude
 *
 * Usage:
 *   node cdp_injector.js list              # List available inspectors
 *   node cdp_injector.js inject <port> <js> # Inject JS into process
 *   node cdp_injector.js notify <port>     # Inject nclaude check
 */

const http = require('http');
const net = require('net');
const crypto = require('crypto');

async function listInspectors() {
    const inspectors = [];

    for (let port = 9229; port < 9250; port++) {
        try {
            const info = await new Promise((resolve, reject) => {
                const req = http.get(`http://127.0.0.1:${port}/json`, { timeout: 500 }, (res) => {
                    let data = '';
                    res.on('data', chunk => data += chunk);
                    res.on('end', () => resolve(JSON.parse(data)));
                });
                req.on('error', reject);
                req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
            });

            if (info && info.length > 0) {
                inspectors.push({
                    port,
                    title: info[0].title,
                    url: info[0].webSocketDebuggerUrl
                });
            }
        } catch (e) {
            // Port not listening
        }
    }

    return inspectors;
}

async function getInspectorUrl(port) {
    return new Promise((resolve, reject) => {
        http.get(`http://127.0.0.1:${port}/json`, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                const info = JSON.parse(data);
                resolve(info[0]?.webSocketDebuggerUrl);
            });
        }).on('error', reject);
    });
}

async function injectCode(wsUrl, jsCode) {
    const url = new URL(wsUrl);

    return new Promise((resolve, reject) => {
        const socket = net.connect(parseInt(url.port), url.hostname, () => {
            const key = crypto.randomBytes(16).toString('base64');
            const request = [
                `GET ${url.pathname} HTTP/1.1`,
                `Host: ${url.host}`,
                'Upgrade: websocket',
                'Connection: Upgrade',
                `Sec-WebSocket-Key: ${key}`,
                'Sec-WebSocket-Version: 13',
                '', ''
            ].join('\r\n');
            socket.write(request);
        });

        let handshakeDone = false;
        let responseBuffer = Buffer.alloc(0);

        socket.on('data', (data) => {
            if (!handshakeDone && data.toString().includes('101')) {
                handshakeDone = true;

                const msg = JSON.stringify({
                    id: 1,
                    method: 'Runtime.evaluate',
                    params: {
                        expression: jsCode,
                        returnByValue: true
                    }
                });

                const payload = Buffer.from(msg);
                const mask = crypto.randomBytes(4);
                let frame;

                if (payload.length < 126) {
                    frame = Buffer.alloc(6 + payload.length);
                    frame[0] = 0x81;
                    frame[1] = 0x80 | payload.length;
                    mask.copy(frame, 2);
                    for (let i = 0; i < payload.length; i++) {
                        frame[6 + i] = payload[i] ^ mask[i % 4];
                    }
                } else {
                    frame = Buffer.alloc(8 + payload.length);
                    frame[0] = 0x81;
                    frame[1] = 0x80 | 126;
                    frame.writeUInt16BE(payload.length, 2);
                    mask.copy(frame, 4);
                    for (let i = 0; i < payload.length; i++) {
                        frame[8 + i] = payload[i] ^ mask[i % 4];
                    }
                }

                socket.write(frame);
            } else if (handshakeDone) {
                responseBuffer = Buffer.concat([responseBuffer, data]);

                try {
                    // Try to parse WebSocket frame
                    if (responseBuffer.length > 2) {
                        const payloadLen = responseBuffer[1] & 0x7f;
                        const payloadStart = payloadLen < 126 ? 2 : 4;

                        if (responseBuffer.length >= payloadStart + payloadLen) {
                            const payload = responseBuffer.slice(payloadStart, payloadStart + payloadLen);
                            const result = JSON.parse(payload.toString());
                            socket.end();
                            resolve(result);
                        }
                    }
                } catch(e) {
                    // Keep buffering
                }
            }
        });

        socket.on('error', reject);
        setTimeout(() => { socket.end(); resolve(null); }, 5000);
    });
}

async function main() {
    const args = process.argv.slice(2);
    const command = args[0] || 'list';

    if (command === 'list') {
        console.log('Scanning for Node inspectors...');
        const inspectors = await listInspectors();

        if (inspectors.length === 0) {
            console.log('No inspectors found.');
            console.log('Start Claude with: NODE_OPTIONS="--inspect" claude');
        } else {
            console.log(JSON.stringify(inspectors, null, 2));
        }
    }
    else if (command === 'inject') {
        const port = parseInt(args[1]) || 9229;
        const code = args[2] || 'global.__TEST = true; "injected"';

        const wsUrl = await getInspectorUrl(port);
        if (!wsUrl) {
            console.error(`No inspector on port ${port}`);
            process.exit(1);
        }

        console.log(`Injecting into ${wsUrl}...`);
        const result = await injectCode(wsUrl, code);
        console.log(JSON.stringify(result, null, 2));
    }
    else if (command === 'notify') {
        const port = parseInt(args[1]) || 9229;

        const wsUrl = await getInspectorUrl(port);
        if (!wsUrl) {
            console.error(`No inspector on port ${port}`);
            process.exit(1);
        }

        // Inject nclaude message notification
        const code = `
            (function() {
                // Create visual notification in Claude's context
                console.log('\\n🔔 [NCLAUDE] New message received - check logs!\\n');

                // Store notification state
                if (!global.__NCLAUDE) global.__NCLAUDE = {};
                global.__NCLAUDE.lastNotification = Date.now();
                global.__NCLAUDE.pendingMessages = (global.__NCLAUDE.pendingMessages || 0) + 1;

                return {
                    success: true,
                    timestamp: new Date().toISOString(),
                    pending: global.__NCLAUDE.pendingMessages
                };
            })()
        `;

        console.log(`Sending notification to port ${port}...`);
        const result = await injectCode(wsUrl, code);
        console.log(JSON.stringify(result, null, 2));
    }
    else {
        console.log('Usage:');
        console.log('  node cdp_injector.js list              # List inspectors');
        console.log('  node cdp_injector.js inject <port> <js> # Inject JS');
        console.log('  node cdp_injector.js notify <port>     # Send notification');
    }
}

main().catch(console.error);
