"use strict";
/**
 * Experimental UBox live snapshot via asyrk/ubox-web's dynamic relay client.
 * The device password arrives via ENV; never expose raw upstream events/UIDs.
 * No cloud login here: Python cloud_api.py already resolves P2P credentials.
 */
const fs = require("fs");
const path = require("path");

function safeInteger(value, fallback=0, max=999999999) {
  const n = Number(value);
  return Number.isFinite(n) ? Math.max(0, Math.min(max, Math.trunc(n))) : fallback;
}
function summarize(session, frameCount=0, size=0, format=null, phaseCounts={}) {
  const c = session?.counters || {};
  const whitelist = [
    "rx", "tx", "decoded", "queryPackets", "relayWakePackets",
    "kcpSegments", "kcpMessages", "videoFrames", "h264Frames",
    "h264DroppedFrames", "knockPackets", "knockAcks", "rdtFrames"
  ];
  const counters = {};
  for (const name of whitelist) counters[name] = safeInteger(c[name]);
  const stages = {};
  for (const name of [
    "p4p-query-rsp", "relay-wakeup-rsp", "relay-stream-rsp",
    "session-auto-restart", "h264-frame", "video-watchdog-kick",
    "relay-stream-req-sent", "relay-reestablish-timeout"
  ]) stages[name] = safeInteger(phaseCounts[name], 0, 99999);
  return {
    backend: "ubox-web", relay_established: Boolean(session?.relayEstablished),
    discovered_relay_count: safeInteger(session?.learnedVpgTargets?.length,0,100),
    codec: ["h264","hevc"].includes(format) ? format : null,
    video_frames_collected: safeInteger(frameCount),
    stream_bytes: safeInteger(size), stages, counters,
  };
}
function assembleFrames(frames, detectStreamFormat, isAnnexBKeyframe) {
  if (!Array.isArray(frames) || !frames.length) return null;
  const safe = frames.filter(frame => Buffer.isBuffer(frame) && frame.length && frame.length < 3*1024*1024);
  if (!safe.length) return null;
  const format = safe.map(frame => detectStreamFormat(frame)).find(f => f === "h264" || f === "hevc") || null;
  if (!format) return null;
  // Feed full Annex-B sequence to ffmpeg so codec headers preceding the IDR
  // are retained. Output only if a complete keyframe was observed.
  if (!safe.some(frame => isAnnexBKeyframe(frame, format))) return null;
  const bytes = safe.reduce((total, frame) => total + frame.length, 0);
  if (bytes > 16*1024*1024) return null;
  return { format, buffer: Buffer.concat(safe) };
}
async function run() {
  const uid = process.env.UBOX_UID || "";
  const pwd = process.env.UBOX_PASSWORD || "";
  const output = process.env.UBOX_OUTPUT || "";
  if (!/^[A-Za-z0-9]{15,24}$/.test(uid) || !pwd || !output || !path.isAbsolute(output)) {
    process.stdout.write(JSON.stringify({ok:false, reason:"missing_inputs"})+"\n");
    process.exitCode = 2; return;
  }
  const root = process.env.UBOX_WEB_DIR || "/opt/ubox-web";
  const { UBoxLiveStreamManager } = require(path.join(root,"ubox-live-stream.js"));
  const { detectStreamFormat, isAnnexBKeyframe } = require(path.join(root,"video-codec.js"));

  // 'ubox-web' stores raw protocol logs and camera identifiers by default.
  // Both facilities are disabled here; only allowlisted metrics go to stdout.
  const manager = new UBoxLiveStreamManager({
    dumpDir: path.dirname(output), logDir: path.dirname(output),
    enableSessionLogs: false, enableDumpFiles: false,
  });
  const phaseCounts = {};
  const originalEmit = manager.emit.bind(manager);
  manager.emit = (name, detail={}) => {
    if (Object.prototype.hasOwnProperty.call(phaseCounts, name)) {
      phaseCounts[name] += 1;
    } else if (Object.keys(phaseCounts).length < 80) {
      phaseCounts[name] = 1;
    }
    // Retain upstream manager behavior without any disk logs.
    return originalEmit(name, detail);
  };

  let success = false, summary = null, errorCode = null;
  const maxSeconds = Math.max(10,Math.min(75,safeInteger(process.env.UBOX_WAIT_SECONDS,45,75)));
  const deadline = Date.now() + maxSeconds*1000;
  try {
    await manager.start({
      uid,
      // The upstream reverse-engineered client historically uses loginId for
      // device_pwd; loginPwd is normally the account's camera user ('admin').
      loginId: pwd,
      loginPwd: "admin",
      device_type: 0,
      devType: 2,
      streamIndex: 0,
    }, {queryRetryAttempts:10, relayWakeupAttempts:20, relayStreamReqAttempts:14});
    let firstFrameAt = 0;
    while (Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve,500));
      const session = manager.session;
      if (!session) continue;
      const state = session.h264Tracks.get("primary");
      const frames = state ? state.backlog : [];
      if (!frames.length) continue;
      if (!firstFrameAt) firstFrameAt=Date.now();
      // Buffer one second of real video so IDR/SPS/PPS are more likely complete.
      const assembled = assembleFrames(frames, detectStreamFormat, isAnnexBKeyframe);
      if (assembled && (frames.length >= 8 || Date.now()-firstFrameAt >= 2000)) {
        fs.writeFileSync(output, assembled.buffer, {mode:0o600,flag:"wx"});
        summary = summarize(session, frames.length, assembled.buffer.length, assembled.format, phaseCounts);
        success = true;
        break;
      }
    }
    if (!summary) summary = summarize(manager.session,0,0,null,phaseCounts);
    if (!success) errorCode = "no_decodable_video";
  } catch (e) {
    errorCode="node_stream_failure";
    summary=summarize(manager.session,0,0,null,phaseCounts);
  } finally {
    try { await manager.stop(); } catch { /* do not disclose internals */ }
  }
  process.stdout.write(JSON.stringify({ok:success,reason:errorCode,diagnostics:summary})+"\n");
  if(!success) process.exitCode=1;
}

if(require.main===module) {
  if (process.argv.includes("--self-test")) {
    const fake={counters:{rx:12,h264Frames:2},relayEstablished:true,learnedVpgTargets:[{}]};
    const safe = summarize(fake,2,123,"h264",{"p4p-query-rsp":1});
    if(safe.counters.rx!==12||safe.stages["p4p-query-rsp"]!==1||JSON.stringify(safe).includes("password"))
      process.exit(1);
    process.stdout.write("safe self-test: passed\n");
  } else {
    run().catch(() => {
      process.stdout.write('{"ok":false,"reason":"unexpected_failure"}\n');
      process.exitCode=1;
    });
  }
}
module.exports={summarize,assembleFrames};
