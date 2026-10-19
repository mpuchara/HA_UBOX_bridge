"use strict";
/** Short, bounded PTZ movement using the same pinned P4P stack as snapshots.
 * Never logs UID, device password, or raw P4P packets. No generic IOCTRL API.
 */
const path = require("path");
const directions = Object.freeze({up:1,down:2,right:3,left:6});
const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const cleanDirection = direction => Object.hasOwn(directions,direction) ? direction : null;
const bounds = value => Number.isSafeInteger(value) && value>=150 && value<=800;

async function move(manager, direction, milliseconds, {sleep=wait}={}) {
  if (!cleanDirection(direction) || !bounds(milliseconds)) {
    return {ok:false,reason:"invalid_command"};
  }
  let moved=false, stopped=false;
  try {
    // Wait for relay and stream readiness before sending IOCTRL.
    const until=Date.now()+20000;
    while (Date.now()<until) {
      const session=manager.session;
      if (session?.relayEstablished && session?.relayPeer) {
        // Upstream returns 'sent' (transport-level only, NOT hardware ACK).
        const reply=manager.sendPtzCommand({action:"move",direction,speed:1});
        moved=Boolean(reply?.ok);
        break;
      }
      await sleep(150);
    }
    if (!moved) return {ok:false,reason:"relay_not_ready"};
    await sleep(milliseconds);
    return {ok:true,direction,duration_ms:milliseconds,acknowledged:false};
  } finally {
    // ALWAYS send STOP on the same session, also on exceptions.
    if (moved) {
      try { stopped=Boolean(manager.sendPtzCommand({action:"stop"})?.ok); }
      catch { /* session may have dropped: best effort only */ }
      if (!stopped) {
        // One bounded retry while session still exists.
        try { manager.sendPtzCommand({action:"stop"}); }
        catch { /* suppress identifiers */ }
      }
    }
  }
}

async function run() {
  const uid=process.env.UBOX_UID||"";
  const password=process.env.UBOX_PASSWORD||"";
  const direction=process.env.UBOX_PTZ_DIRECTION||"";
  const duration=Number(process.env.UBOX_PTZ_MS||"");
  const streamIndex=Number(process.env.UBOX_STREAM_INDEX||"0");
  if (!/^[A-Za-z0-9]{15,24}$/.test(uid) || !password ||
      !cleanDirection(direction) || !bounds(duration) || ![0,1].includes(streamIndex)) {
    process.stdout.write('{"ok":false,"reason":"invalid_input"}\n');
    process.exitCode=2;
    return;
  }
  const {UBoxLiveStreamManager}=require(
    path.join(process.env.UBOX_WEB_DIR||"/opt/ubox-web","ubox-live-stream.js"));
  const manager=new UBoxLiveStreamManager({
    enableSessionLogs:false,enableDumpFiles:false,logDir:"/tmp",dumpDir:"/tmp"});
  let result={ok:false,reason:"session_error"};
  try {
    await manager.start({
      uid,loginId:password,loginPwd:"admin",device_type:0,
      devType:2,streamIndex},
      {queryRetryAttempts:10,relayWakeupAttempts:20,relayStreamReqAttempts:14});
    result=await move(manager,direction,duration);
  } catch {
    result={ok:false,reason:"session_error"};
  } finally {
    // Stop is already sent by move finally. Manager shutdown also closes stream.
    try {await manager.stop();} catch { /* no sensitive logs */ }
  }
  process.stdout.write(JSON.stringify(result)+"\n");
  if(!result.ok)process.exitCode=1;
}
if(require.main===module) {
  if(process.argv.includes("--self-test")) {
    const events=[];
    const fake={session:{relayEstablished:true,relayPeer:{address:"test"}},
      sendPtzCommand(x){events.push(x.action);return {ok:true};}};
    move(fake,"right",180,{sleep:()=>Promise.resolve()})
      .then(r=>{if(!r.ok||events.join(",")!=="move,stop")process.exitCode=1;
                  else process.stdout.write("ptz self-test: passed\n");})
      .catch(()=>{process.exitCode=1;});
  } else run().catch(()=>{process.stdout.write('{"ok":false,"reason":"unexpected"}\n');process.exitCode=1;});
}
module.exports={move};
