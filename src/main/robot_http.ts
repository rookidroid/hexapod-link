// HTTP client for the routes the ESP32 firmware serves on port 80.
//
// The UDP link is one-way and carries motion; everything that needs an answer
// goes over HTTP instead: the robot's own config (GET /robot_config) and the
// gait playback speed. These are the same routes the firmware's built-in web
// page uses, so nothing here is private to this app.
//
// The robot address may carry an HTTP port ("127.0.0.1:8080"). The firmware
// always listens on 80, but a stand-in robot on a development machine usually
// cannot bind it, and the UDP side ignores the port either way.

import { ROBOT_HTTP_PORT, ROBOT_HTTP_TIMEOUT_S } from "../shared/settings";

export class RobotHttpError extends Error {
    override name = "RobotHttpError";
}

/** Split "host[:port]" into [host, httpPort]. */
export function splitAddress(address: string | null | undefined): [string, number] {
    const text = (address || "").trim();
    const colon = text.lastIndexOf(":");
    if (colon > 0) {
        const port = text.slice(colon + 1);
        if (/^\d+$/.test(port)) {
            return [text.slice(0, colon), Number(port)];
        }
    }
    return [text, ROBOT_HTTP_PORT];
}

export function robotUrl(address: string, path: string): string {
    const [host, port] = splitAddress(address);
    return `http://${port === 80 ? host : `${host}:${port}`}${path}`;
}

async function request(
    address: string,
    path: string,
    method: "GET" | "POST" = "GET",
    timeoutS?: number,
): Promise<string> {
    const url = robotUrl(address, path);
    let response: Response;
    try {
        response = await fetch(url, {
            method,
            // The ESP32 WebServer waits for a body on a POST without a length.
            body: method === "POST" ? "" : undefined,
            signal: AbortSignal.timeout((timeoutS ?? ROBOT_HTTP_TIMEOUT_S) * 1000),
        });
    } catch (error) {
        const reason =
            (error as Error & { cause?: Error }).cause?.message || (error as Error).message;
        throw new RobotHttpError(`Couldn't reach ${url}: ${reason}`);
    }
    const text = await response.text();
    if (!response.ok) {
        // The firmware explains its refusals in the body, which is what the
        // user needs to see.
        throw new RobotHttpError(text.trim() || `HTTP ${response.status} from ${url}`);
    }
    return text;
}

export async function getJson(address: string, path: string, timeoutS?: number): Promise<unknown> {
    const text = await request(address, path, "GET", timeoutS);
    try {
        return JSON.parse(text);
    } catch {
        throw new RobotHttpError(`${robotUrl(address, path)} did not return JSON`);
    }
}

/** The raw payload of GET /robot_config. */
export function getRobotConfig(address: string, timeoutS?: number): Promise<unknown> {
    return getJson(address, "/robot_config", timeoutS);
}

/** Set the LUT playback speed; the speed the robot settled on. */
export async function setSpeed(address: string, pct: number): Promise<number> {
    const text = await request(address, `/set_speed?pct=${Math.trunc(pct)}`, "POST");
    try {
        const speed = Math.trunc(Number(JSON.parse(text).speed));
        if (Number.isFinite(speed)) {
            return speed;
        }
    } catch {
        // Fall through to the error below.
    }
    throw new RobotHttpError(`Unexpected /set_speed reply: ${text}`);
}
