// A stand-in hexapod for trying the app without the hardware.
//
//     npm run fake-robot                      # a Nougat on 127.0.0.1:8080
//     npm run fake-robot -- mochi --port 8081
//
// Serves the firmware's HTTP routes the app uses -- /robot_config and the speed
// routes -- with the same replies and refusals as the ESP32, answers firmware
// version queries on UDP port 1234, and prints every other UDP packet sent
// there. In the app, connect to 127.0.0.1:8080: the port goes to HTTP, UDP
// always goes to 1234.
//
// The config it reports is one of the fixtures in tests/fixtures/robot_config,
// which are the firmware's own replies. The tests use FakeRobot directly.
// Nothing here is imported by the app itself.

import { createSocket, type RemoteInfo, type Socket } from "node:dgram";
import { readFileSync } from "node:fs";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const FIXTURES = join(
    dirname(fileURLToPath(import.meta.url)),
    "..",
    "tests",
    "fixtures",
    "robot_config",
);

export const UDP_PORT = 1234;
const MAGIC_VERSION = 0xa8;

type Payload = Record<string, any>;

/** The firmware's answer to a version query, or null if `request` is not one.
 * The version is the one the payload reports, so UDP and HTTP agree. */
export function versionReply(request: Uint8Array, payload: Payload): Buffer | null {
    if (request.length !== 5 || request[0] !== MAGIC_VERSION) {
        return null;
    }
    const seq = Buffer.from(request).readUInt32LE(1);
    const firmware = payload.firmware || {};
    const [major, minor, patch] = String(firmware.version ?? "0.0.0")
        .split(".")
        .map(Number);
    const head = Buffer.alloc(9);
    head.writeUInt8(MAGIC_VERSION, 0);
    head.writeUInt32LE(seq, 1);
    head.writeUInt8(payload.protocol, 5);
    head.writeUInt8(major, 6);
    head.writeUInt8(minor, 7);
    head.writeUInt8(patch, 8);
    return Buffer.concat([head, Buffer.from(String(firmware.build ?? "fake"), "utf-8")]);
}

export interface FakeRobotOptions {
    host?: string;
    port?: number;
    /** Listen for UDP on this port (0 for any); none if left out. */
    udpPort?: number;
    onPacket?: (data: Buffer) => void;
    /** False plays firmware that predates the version query. */
    answerVersion?: boolean;
}

/** A robot on this machine: HTTP, and UDP when `udpPort` is given.
 * `requests` records [method, path, body] for each request and `packets`
 * each UDP datagram other than a version query, for the tests. */
export class FakeRobot {
    payload: Payload;
    speed: number;
    readonly requests: [string, string, string | null][] = [];
    readonly packets: Buffer[] = [];
    private readonly options: FakeRobotOptions;
    private server: Server;
    private udp: Socket | null = null;

    constructor(payload: Payload, options: FakeRobotOptions = {}) {
        this.payload = payload;
        this.options = { host: "127.0.0.1", port: 0, answerVersion: true, ...options };
        this.speed = payload.speed?.current ?? 60;
        this.server = createServer((req, res) => this.handle(req, res));
    }

    static fromFixture(name: string, options: FakeRobotOptions = {}): FakeRobot {
        return new FakeRobot(
            JSON.parse(readFileSync(join(FIXTURES, `${name}.json`), "utf-8")),
            options,
        );
    }

    get address(): string {
        const info = this.server.address() as AddressInfo;
        return `${info.address}:${info.port}`;
    }

    get udpPort(): number | null {
        return this.udp ? this.udp.address().port : null;
    }

    async start(): Promise<this> {
        const { host, port, udpPort } = this.options;
        await new Promise<void>((resolve) => this.server.listen(port, host, resolve));
        if (udpPort !== undefined) {
            const udp = createSocket("udp4");
            this.udp = udp;
            udp.on("message", (data, sender) => this.onDatagram(data, sender));
            udp.on("error", () => {});
            await new Promise<void>((resolve) => udp.bind(udpPort, host, resolve));
        }
        return this;
    }

    async stop(): Promise<void> {
        this.server.closeAllConnections?.();
        await new Promise<void>((resolve) => this.server.close(() => resolve()));
        if (this.udp) {
            const udp = this.udp;
            this.udp = null;
            await new Promise<void>((resolve) => udp.close(() => resolve()));
        }
    }

    private onDatagram(data: Buffer, sender: RemoteInfo): void {
        const reply = versionReply(data, this.payload);
        if (reply) {
            if (this.options.answerVersion) {
                this.udp?.send(reply, sender.port, sender.address);
            }
            return;
        }
        this.packets.push(data);
        this.options.onPacket?.(data);
    }

    private handle(req: IncomingMessage, res: ServerResponse): void {
        const url = new URL(req.url ?? "/", "http://robot");
        let body = "";
        req.on("data", (chunk) => {
            body += chunk;
        });
        req.on("end", () => {
            const reply = (status: number, text: string, type = "text/plain") => {
                res.writeHead(status, {
                    "Content-Type": type,
                    "Content-Length": Buffer.byteLength(text),
                });
                res.end(text);
            };
            const json = (obj: unknown) => reply(200, JSON.stringify(obj), "application/json");
            this.requests.push([
                req.method ?? "GET",
                url.pathname,
                req.method === "POST" ? body : null,
            ]);
            if (req.method === "GET" && url.pathname === "/robot_config") {
                json({
                    ...this.payload,
                    speed: { ...(this.payload.speed ?? {}), current: this.speed },
                });
            } else if (req.method === "GET" && url.pathname === "/get_speed") {
                json({ speed: this.speed });
            } else if (req.method === "POST" && url.pathname === "/set_speed") {
                const pct = url.searchParams.get("pct");
                if (!pct) {
                    reply(400, "Missing pct");
                    return;
                }
                this.speed = Math.max(20, Math.min(100, Math.trunc(Number(pct))));
                json({ speed: this.speed });
            } else {
                reply(404, "Not found");
            }
        });
    }
}

/** One packet, as a line to read. */
export function describePacket(data: Buffer): string {
    const magic = data[0];
    if (magic === 0xa5 && (data.length === 6 || data.length === 7)) {
        const speed = data.length === 7 ? data[6] : null;
        return `MOTION cmd=${data[1]} seq=${data.readUInt32LE(2)} speed=${speed} (${data.length} bytes)`;
    }
    if (magic === 0xa6 && data.length === 44) {
        const ticks = Array.from({ length: 18 }, (_, i) => data.readInt16LE(8 + 2 * i));
        return `POSE seq=${data.readUInt32LE(4)} max_step=${data.readUInt16LE(2)} flags=${data[1]} ticks=[${ticks.join(", ")}]`;
    }
    if (magic === 0xa7 && data.length === 6) {
        const names: Record<number, string> = { 0: "EXIT", 1: "ENTER", 2: "RELAX", 3: "PING" };
        return `SESSION ${names[data[1]] ?? data[1]} seq=${data.readUInt32LE(2)}`;
    }
    return `unknown ${data.length} bytes: ${data.subarray(0, 16).toString("hex")}`;
}

async function main(): Promise<void> {
    const args = process.argv.slice(2);
    const option = (name: string) => {
        const i = args.indexOf(name);
        return i >= 0 ? args.splice(i, 2)[1] : undefined;
    };
    const quietPings = args.includes("--quiet-pings");
    const host = option("--host") ?? "127.0.0.1";
    const port = Number(option("--port") ?? 8080);
    const name = args.find((a) => !a.startsWith("--")) ?? "nougat";
    const robot = await FakeRobot.fromFixture(name, {
        host,
        port,
        udpPort: UDP_PORT,
        onPacket: (data) => {
            const text = describePacket(data);
            if (!(quietPings && text.startsWith("SESSION PING"))) {
                console.log(text);
            }
        },
    }).start();
    const firmware = robot.payload.firmware?.version ?? "0.0.0";
    console.log(
        `Fake ${name} (firmware ${firmware}) serving HTTP on ${robot.address}, UDP on ${host}:${UDP_PORT}`,
    );
    process.on("SIGINT", () => {
        robot.stop().then(() => process.exit(0));
    });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
    main();
}
