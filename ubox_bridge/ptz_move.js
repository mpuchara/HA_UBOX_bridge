"use strict";
/** Bounded short PTZ on UBox, code=byte[5], speed=byte[2] (12 bytes).
 * Verified packet layout from mahumadad/ubox-p4p docs/IOCTRLS.md:
 * https://github.com/mahumadad/ubox-p4p/blob/main/docs/IOCTRLS.md
 * The upstream pinned UBoxLiveStreamSession.ptzDirection() writes speed to
 * byte[10] and byte[6]=8, so we use sendIoControl() with the correct payload.
 * Never expose arbitrary IOCTRLs or log identifiers/secrets.
 */
const path=require("path");
const CODES=Object.freeze({up:1,down:2,right:3,left:6});
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const hasDirection=d=>Object.prototype.hasOwnProperty.call(CODES,d);
const durationOK=ms=>Number.isInteger(ms)&&ms>=60&&ms<=350;
const speedOK=s=>Number.isInteger(s)&&s>=1&&s<=8;
function buildPtzPayload(direction,speed=1){
  if(direction!=="stop"&&!hasDirection(direction))throw Error("invalid_direction");
  if(!speedOK(speed))throw Error("invalid_speed");
  const payload=Buffer.alloc(12);
  if(direction!=="stop"){
    payload[2]=speed; // correct OEM layout: speed at byte 2 (NOT byte 10)
    payload[5]=CODES[direction]; // movement code byte 5
  }
  // Stop = 12 ZERO bytes, not the upstream [6]=8 payload.
  return payload;
}
async function move(manager,direction,ms,{sleep=wait,speed=1}={}){
  if(!hasDirection(direction)||!durationOK(ms)||!speedOK(speed))
    return {ok:false,reason:"invalid_command"};
  let sent=false,stopSent=false,stopError=false;
  try{
    const deadline=Date.now()+20000;
    while(Date.now()<deadline){
      const session=manager.session;
      if(session?.relayEstablished&&session?.relayPeer){
        // Calls upstream transport, NOT its incorrect directional payload.
        sent=Boolean(session.sendIoControl(
          0x1001,buildPtzPayload(direction,speed),"ptz-move"));
        break;
      }
      await sleep(150);
    }
    if(!sent)return {ok:false,reason:"relay_not_ready"};
    await sleep(ms);
  }catch{
    stopError=true;
  }finally{
    if(sent){
      // Stop even when timer or transport errors; do not leave motor latched.
      try{
        stopSent=Boolean(manager.session?.sendIoControl(
          0x1001,buildPtzPayload("stop"),"ptz-stop"));
      }catch{stopSent=false;}
      if(!stopSent){
        try{
          stopSent=Boolean(manager.session?.sendIoControl(
            0x1001,buildPtzPayload("stop"),"ptz-stop-retry"));
        }catch{stopSent=false;}
      }
      // Keep KCP alive briefly to flush the STOP before closing UDP socket.
      try{await sleep(180);}catch{/* final cleanup */}
    }
  }
  if(stopError||!stopSent)return {ok:false,reason:"stop_not_confirmed"};
  return {ok:true,direction,duration_ms:ms,speed,acknowledged:false};
}
async function run(){
  const uid=process.env.UBOX_UID||"";
  const pwd=process.env.UBOX_PASSWORD||"";
  const dir=process.env.UBOX_PTZ_DIRECTION||"";
  const ms=Number(process.env.UBOX_PTZ_MS||"");
  const speed=Number(process.env.UBOX_PTZ_SPEED||"1");
  const stream=Number(process.env.UBOX_STREAM_INDEX||"0");
  if(!/^[A-Za-z0-9]{15,24}$/.test(uid)||!pwd||!hasDirection(dir)||
     !durationOK(ms)||!speedOK(speed)||![0,1].includes(stream)){
    process.stdout.write('{"ok":false,"reason":"invalid_input"}\n');
    process.exitCode=2;return;
  }
  const {UBoxLiveStreamManager}=require(
    path.join(process.env.UBOX_WEB_DIR||"/opt/ubox-web","ubox-live-stream.js"));
  const manager=new UBoxLiveStreamManager({
    enableSessionLogs:false,enableDumpFiles:false,logDir:"/tmp",dumpDir:"/tmp"});
  let result={ok:false,reason:"session_error"};
  try{
    await manager.start({
      uid,loginId:pwd,loginPwd:"admin",device_type:0,devType:2,
      streamIndex:stream},
      {queryRetryAttempts:10,relayWakeupAttempts:20,relayStreamReqAttempts:14});
    result=await move(manager,dir,ms,{speed});
  }catch{result={ok:false,reason:"session_error"};}
  finally{try{await manager.stop();}catch{/* sanitized */}}
  process.stdout.write(JSON.stringify(result)+"\n");
  if(!result.ok)process.exitCode=1;
}
async function selfTest(){
  const packets=[];
  const fake={session:{relayEstablished:true,relayPeer:{port:1},
    sendIoControl(command,bytes,reason){
      packets.push({command,bytes:Buffer.from(bytes),reason});return true;
    }}};
  for(const [dir,code] of Object.entries(CODES)){
    const before=packets.length;
    const r=await move(fake,dir,75,{sleep:async()=>{},speed:1});
    if(!r.ok||packets.length!==before+2)throw Error("expected move+stop");
    const a=packets[before],b=packets[before+1];
    if(a.command!==0x1001||a.bytes.length!==12||a.bytes[5]!==code||
       a.bytes[2]!==1||a.bytes[6]!==0||a.bytes[10]!==0||
       b.bytes.some(v=>v!==0))throw Error("PTZ payload regression");
  }
  // Even an exception after sending movement must result in a zero stop.
  let count=0;
  const result=await move(fake,"left",70,{sleep:async()=>{
    if(++count===1)throw Error("timer");
  }});
  if(result.ok||packets.at(-1).bytes.some(x=>x!==0))
    throw Error("STOP required in exceptional path");
  const notAllowed=await move(fake,"left",1000);
  if(notAllowed.ok)throw Error("long pulse must be rejected");
  process.stdout.write("ptz pulse + stop packet self-test: passed\n");
}
if(require.main===module){
  if(process.argv.includes("--self-test"))
    selfTest().catch(()=>{process.exitCode=1;});
  else run().catch(()=>{process.stdout.write('{"ok":false,"reason":"unexpected"}\n');process.exitCode=1;});
}
module.exports={CODES,buildPtzPayload,move};
