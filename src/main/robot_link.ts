// Real-time link between the app and the physical ESP32 hexapod.
//
// The robot's config -- geometry, servo range, frame delay, speed limits and
// command list -- is read from the robot itself when connecting
// (robot_http.ts). The firmware version is asked for over UDP at the same
// time, which also shows that the robot hears the motion channel. Angles become
// ticks, and ticks packets, in shared/protocol.ts.
//
// A timer republishes the most recent pose at a steady rate: the firmware drops
// out of real-time mode if it stops hearing from us, and a steady stream turns
// sporadic edits into smooth motion. It also plays sequences frame by frame, at
// the robot's own frame rate, and lets go of a controller drive that is no
// longer being renewed.

import { createSocket, type Socket } from "node:dgram";
import type { Pose } from "../shared/path_generator";
import {
    motionPacket,
    parseVersionReply,
    posePacket,
    poseToTicks,
    RT_ENTER,
    RT_EXIT,
    RT_PING,
    STANDBY_POSE,
    sessionPacket,
    versionRequest,
} from "../shared/protocol";
import {
    clampSpeed,
    commandId,
    type Firmware,
    getSequenceFps,
    parseRobotConfig,
    type RobotConfig,
    RobotConfigError,
} from "../shared/robot_config";
import {
    ROBOT_DEFAULT_IP,
    ROBOT_DEFAULT_MAX_STEP,
    ROBOT_DRIVE_HOLD_S,
    ROBOT_PING_HZ,
    ROBOT_SEQUENCE_MAX_STEP,
    ROBOT_STREAM_HZ,
    ROBOT_UDP_PORT,
    ROBOT_VERSION_ATTEMPTS,
    ROBOT_VERSION_TIMEOUT_S,
} from "../shared/settings";
import * as http from "./robot_http";
import { loadStartupConfig, saveCachedConfig } from "./storage";

export interface LinkStatus {
    connected: boolean;
    streaming: boolean;
    ip: string;
    packets_sent: number;
    last_error: string | null;
    max_step: number;
    speed_pct: number;
    robot_name: string;
    robot_label: string;
    config_source: string;
    config_version: number;
    firmware: Firmware | null;
}

/** Ask the robot at `address` for its config. */
export async function fetchRobotConfig(address: string, timeoutS?: number): Promise<RobotConfig> {
    let payload: unknown;
    try {
        payload = await http.getRobotConfig(address, timeoutS);
    } catch (error) {
        throw new RobotConfigError(`Couldn't read the robot's config: ${(error as Error).message}`);
    }
    return parseRobotConfig(payload, "robot");
}

export interface LinkOptions {
    udpPort?: number;
    /** Seconds, monotonic; replaceable for tests. */
    clock?: () => number;
    /** Sends a packet; replaceable for tests. Defaults to the UDP socket. */
    send?: (packet: Uint8Array) => boolean;
    /** Whether to cache a connected robot's config on disk. */
    cache?: boolean;
}

export class RobotLink {
    private readonly udpPort: number;
    private readonly clock: () => number;
    private readonly sendOverride?: (packet: Uint8Array) => boolean;
    private readonly cache: boolean;

    private socket: Socket | null = null;
    private timer: ReturnType<typeof setInterval> | null = null;
    private nextPing = 0;

    robotConfig: RobotConfig;
    configVersion = 0;
    ip = ROBOT_DEFAULT_IP;
    connected = false;
    firmware: Firmware | null = null;
    streaming = false;
    maxStep = ROBOT_DEFAULT_MAX_STEP;
    speedPct: number;
    private ticks: number[];
    private seq = 0;
    private packetsSent = 0;
    lastError: string | null = null;

    // Sequence playback, driven by the stream timer.
    private sequence: number[][] | null = null;
    private sequenceIndex = 0;
    private sequenceLoop = true;
    private sequenceNextTime = 0;
    private sequenceFpsOverride: number | null = null;
    sequenceFps: number;

    // The gait the controller is holding the robot in, and when the hold runs
    // out unless it is renewed (see drive()).
    private driveMotion: string | null = null;
    private driveDeadline: number | null = null;

    constructor(robotConfig?: RobotConfig | null, options: LinkOptions = {}) {
        this.udpPort = options.udpPort ?? ROBOT_UDP_PORT;
        this.clock = options.clock ?? (() => performance.now() / 1000);
        this.sendOverride = options.send;
        this.cache = options.cache ?? true;
        this.robotConfig = robotConfig ?? loadStartupConfig();
        this.speedPct = this.robotConfig.speed.default;
        this.ticks = poseToTicks(STANDBY_POSE, this.robotConfig);
        this.sequenceFps = getSequenceFps(this.robotConfig, this.speedPct);
    }

    status(): LinkStatus {
        return {
            connected: this.connected,
            streaming: this.streaming,
            ip: this.ip,
            packets_sent: this.packetsSent,
            last_error: this.lastError,
            max_step: this.maxStep,
            speed_pct: this.speedPct,
            robot_name: this.robotConfig.name,
            robot_label: this.robotConfig.label,
            config_source: this.robotConfig.source,
            config_version: this.configVersion,
            firmware: this.firmware,
        };
    }

    // ------------------------------------------------------------ connection

    /** Read the robot's config, then open the socket and enter real-time mode.
     *
     * The config comes first: the robot's geometry decides how every pose is
     * turned into servo ticks, so nothing is sent until it is known. A robot
     * that does not answer leaves the link disconnected with the reason in
     * lastError. */
    async connect(ip?: string | null): Promise<boolean> {
        const address = (ip || this.ip || ROBOT_DEFAULT_IP).trim();
        let robotConfig: RobotConfig;
        try {
            robotConfig = await fetchRobotConfig(address);
        } catch (error) {
            this.ip = address;
            this.lastError = (error as Error).message;
            return false;
        }
        if (this.cache) {
            saveCachedConfig(robotConfig);
        }
        this.loadConfig(robotConfig);

        // /robot_config carries the version too, so an unanswered query still
        // leaves something to show; it only means the UDP side is unconfirmed.
        const firmware = (await this.queryFirmware(address)) ?? robotConfig.firmware;

        this.ip = address;
        this.firmware = firmware;
        if (!this.socket && !this.sendOverride) {
            try {
                this.socket = createSocket("udp4");
                this.socket.on("error", (error) => {
                    this.lastError = error.message;
                });
            } catch (error) {
                this.lastError = (error as Error).message;
                return false;
            }
        }
        this.connected = true;
        this.lastError = null;
        this.sendSession(RT_ENTER);
        this.startTimer();
        return true;
    }

    /** Ask the robot for its firmware version over UDP: what
     * parseVersionReply() decodes, or null if no answer came. The query has a
     * socket of its own, and the firmware does not count it as control input. */
    async queryFirmware(ip?: string): Promise<Firmware | null> {
        const [host] = http.splitAddress(ip ?? this.ip);
        this.seq += 1;
        const seq = this.seq;
        const request = versionRequest(seq);
        const socket = createSocket("udp4");
        try {
            await new Promise<void>((resolve, reject) => {
                socket.once("error", reject);
                socket.bind(0, () => {
                    socket.off("error", reject);
                    resolve();
                });
            });
        } catch {
            socket.close();
            return null;
        }
        try {
            for (let attempt = 0; attempt < ROBOT_VERSION_ATTEMPTS; attempt++) {
                const reply = await new Promise<Firmware | null | "error">((resolve) => {
                    const timer = setTimeout(() => finish(null), ROBOT_VERSION_TIMEOUT_S * 1000);
                    const onMessage = (data: Buffer) => {
                        // Skip anything that is not the answer, e.g. a late
                        // reply to an earlier query.
                        const parsed = parseVersionReply(new Uint8Array(data), seq);
                        if (parsed) finish(parsed);
                    };
                    // Unreachable; Windows also reports a closed port this way.
                    const onError = () => finish("error");
                    function finish(value: Firmware | null | "error") {
                        clearTimeout(timer);
                        socket.off("message", onMessage);
                        socket.off("error", onError);
                        resolve(value);
                    }
                    socket.on("message", onMessage);
                    socket.on("error", onError);
                    socket.send(request, this.udpPort, host, (error) => {
                        if (error) finish("error");
                    });
                });
                if (reply === "error") {
                    return null;
                }
                if (reply) {
                    return reply;
                }
            }
            return null;
        } finally {
            socket.close();
        }
    }

    /** Switch the link to a newly read robot config. */
    loadConfig(robotConfig: RobotConfig): void {
        this.robotConfig = robotConfig;
        this.configVersion += 1;
        // The robot's own speed is what its native gaits are playing at.
        this.speedPct = clampSpeed(robotConfig, robotConfig.speed.current ?? this.speedPct);
        this.sequence = null;
        this.sequenceIndex = 0;
        this.sequenceFpsOverride = null;
        this.sequenceFps = getSequenceFps(robotConfig, this.speedPct);
        this.ticks = poseToTicks(STANDBY_POSE, robotConfig);
    }

    /** Return the robot to LUT control and close the socket. */
    disconnect(): void {
        this.sendSession(RT_EXIT);
        this.stopTimer();
        this.connected = false;
        this.firmware = null;
        this.streaming = false;
        this.sequence = null;
        this.sequenceIndex = 0;
        this.driveMotion = null;
        this.driveDeadline = null;
        if (this.socket) {
            const socket = this.socket;
            this.socket = null;
            // After the RT_EXIT queued above has gone.
            setTimeout(() => socket.close(), 50);
        }
    }

    setMaxStep(maxStep: number): void {
        this.maxStep = Math.max(1, Math.trunc(maxStep));
    }

    setStreaming(streaming: boolean): void {
        this.streaming = Boolean(streaming) && this.connected;
    }

    /** How fast gaits play, in percent of the robot's tuned frame rate: the
     * robot's own gaits -- sent to it now, and with every motion command after
     * -- and sequences streamed from the app, whose frame rate is scaled to
     * match. The speed that was applied. */
    async setMotionSpeed(pct: number): Promise<number> {
        pct = clampSpeed(this.robotConfig, pct);
        this.speedPct = pct;
        if (this.sequenceFpsOverride === null) {
            this.sequenceFps = getSequenceFps(this.robotConfig, pct);
        }
        if (this.connected) {
            try {
                await http.setSpeed(this.ip, pct);
            } catch (error) {
                // Not fatal: the next motion command carries the speed anyway.
                this.lastError = `Speed not applied: ${(error as Error).message}`;
            }
        }
        return pct;
    }

    // --------------------------------------------------------------- sending

    /** Set the pose streamed to the robot. Posing by hand takes precedence
     * over any sequence in flight. */
    sendPose(pose: Pose | typeof STANDBY_POSE, snap = false): void {
        this.ticks = poseToTicks(pose, this.robotConfig);
        this.sequence = null;
        this.sequenceIndex = 0;
        this.driveMotion = null;
        this.driveDeadline = null;
        if (this.streaming) {
            this.sendPosePacket(snap);
        }
    }

    /** Ask the robot to run one of its own gait LUTs: played from flash, its
     * smoothness does not depend on WiFi. */
    sendMotionCommand(motionName: string): boolean {
        const id = commandId(this.robotConfig, motionName);
        if (id === null) {
            return false;
        }
        // Streaming and LUT playback are mutually exclusive on the robot: the
        // firmware leaves real-time mode as soon as it sees a motion command.
        this.streaming = false;
        this.sequence = null;
        this.sequenceIndex = 0;
        this.driveMotion = null;
        this.driveDeadline = null;
        this.seq += 1;
        return this.send(motionPacket(id, this.seq, this.speedPct));
    }

    /** Run one of the robot's own gaits for as long as it is held.
     *
     * The controller calls this again and again while a pad is held, and with
     * "standby" when it is let go. Only a change of gait is sent; a repeat just
     * renews the hold. If the calls stop without a standby, the stream timer
     * sends one ROBOT_DRIVE_HOLD_S after the last (expireDrive). False for a
     * motion the robot does not have, or when it could not be sent. */
    drive(motionName: string): boolean {
        const deadline = this.clock() + ROBOT_DRIVE_HOLD_S;
        if (motionName === this.driveMotion) {
            this.driveDeadline = deadline;
            return true;
        }
        if (!this.sendMotionCommand(motionName)) {
            return false;
        }
        if (motionName !== "standby") {
            this.driveMotion = motionName;
            this.driveDeadline = deadline;
        }
        return true;
    }

    /** Send the robot to standby if the controller's hold has run out. */
    expireDrive(): void {
        if (this.driveDeadline !== null && this.clock() > this.driveDeadline) {
            this.sendMotionCommand("standby");
        }
    }

    /** Stream poses as a sequence, timed by the stream timer. Without an
     * explicit `fps` the frames play at the rate the robot would play its own
     * LUT at the current speed. */
    playSequence(poses: Pose[], loop = true, fps: number | null = null): boolean {
        const frames = poses.map((pose) => poseToTicks(pose, this.robotConfig));
        if (!frames.length) {
            return false;
        }
        this.driveMotion = null;
        this.driveDeadline = null;
        this.sequence = frames;
        this.sequenceIndex = 0;
        this.sequenceLoop = loop;
        this.sequenceFpsOverride = fps;
        this.sequenceFps = fps || getSequenceFps(this.robotConfig, this.speedPct);
        this.sequenceNextTime = 0;
        this.streaming = this.connected;
        return true;
    }

    /** Stop sequence playback and hold the last frame. */
    stopSequence(): void {
        this.sequence = null;
        this.sequenceIndex = 0;
    }

    /** The frame that is due now, else null.
     *
     * If the timer woke late (Windows timer granularity is ~15 ms, coarser than
     * a 12 ms gait frame) this skips the frames that fell due in the meantime
     * rather than emitting them all late, so the sequence keeps correct
     * wall-clock timing instead of drifting slower and slower. */
    private advanceSequence(): number[] | null {
        const now = this.clock();
        if (!this.sequence || now < this.sequenceNextTime) {
            return null;
        }
        const period = 1.0 / this.sequenceFps;
        let overdue: number;
        if (this.sequenceNextTime === 0) {
            // First frame of a new sequence.
            this.sequenceNextTime = now;
            overdue = 1;
        } else {
            overdue = Math.trunc((now - this.sequenceNextTime) / period) + 1;
        }
        let frame: number[] | null = null;
        for (let i = 0; i < overdue && this.sequence; i++) {
            frame = this.sequence[this.sequenceIndex];
            this.sequenceIndex += 1;
            if (this.sequenceIndex >= this.sequence.length) {
                this.sequenceIndex = 0;
                if (!this.sequenceLoop) {
                    this.sequence = null;
                }
            }
        }
        // Advance the schedule by whole frame periods from when the frame was
        // *due*, not from when the timer happened to wake.
        this.sequenceNextTime += overdue * period;
        if (this.sequenceNextTime <= now) {
            // Fell far behind (a long stall): resynchronise.
            this.sequenceNextTime = now + period;
        }
        if (frame) {
            this.ticks = frame;
        }
        return frame;
    }

    private sendPosePacket(snap = false, maxStep?: number): boolean {
        this.seq += 1;
        return this.send(posePacket(this.ticks, this.seq, maxStep || this.maxStep, snap));
    }

    private sendSession(action: number): boolean {
        this.seq += 1;
        return this.send(sessionPacket(action, this.seq));
    }

    private send(packet: Uint8Array): boolean {
        if (this.sendOverride) {
            const sent = this.sendOverride(packet);
            if (sent) this.packetsSent += 1;
            return sent;
        }
        if (!this.socket) {
            return false;
        }
        // An HTTP port on the address is for the web routes only.
        const [host] = http.splitAddress(this.ip);
        this.socket.send(packet, this.udpPort, host, (error) => {
            if (error) {
                this.lastError = error.message;
            }
        });
        this.packetsSent += 1;
        this.lastError = null;
        return true;
    }

    // ------------------------------------------------------------ heartbeat

    private startTimer(): void {
        if (this.timer) {
            return;
        }
        this.nextPing = 0;
        this.timer = setInterval(() => this.tick(), 1000 / ROBOT_STREAM_HZ);
    }

    private stopTimer(): void {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    /** One beat of the stream: run by the timer, and by the tests. */
    tick(): void {
        if (!this.connected) {
            return;
        }
        this.expireDrive();
        if (!this.streaming) {
            // Keeps the firmware's real-time session from timing out while
            // nothing is moving; rate-limited separately. Any packet also feeds
            // the firmware's LUT failsafe, so this is what keeps a native gait
            // walking as well.
            const now = this.clock();
            if (now >= this.nextPing) {
                this.sendSession(RT_PING);
                this.nextPing = now + 1 / ROBOT_PING_HZ;
            }
            return;
        }
        if (this.sequence) {
            // Sequence frames are small deltas meant to be played back to
            // back, so the slew limit is relaxed for them.
            if (this.advanceSequence()) {
                this.sendPosePacket(false, ROBOT_SEQUENCE_MAX_STEP);
            }
        } else {
            this.sendPosePacket();
        }
    }
}
