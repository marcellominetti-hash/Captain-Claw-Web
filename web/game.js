const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const hero = document.getElementById('hero');
const shell = document.getElementById('gameShell');
const pauseCard = document.getElementById('pauseCard');
const winCard = document.getElementById('winCard');
const winStats = document.getElementById('winStats');

const VIEW_W = 960, VIEW_H = 540;
const WORLD_W = 5200;
const GRAVITY = 1900;
const keys = Object.create(null);
const held = { left:false, right:false };
let running = false, paused = false, won = false;
let last = performance.now(), cameraX = 0, elapsed = 0;
let audioCtx = null;

const player = {
  x:120,y:360,w:42,h:58,vx:0,vy:0,
  speed:300,jump:720,onGround:false,coyote:0,
  facing:1,hp:5,maxHp:5,invuln:0,attack:0,attackCd:0,
  treasure:0,score:0,checkpointX:120,checkpointY:360
};

const platforms = [
  {x:0,y:470,w:850,h:70},{x:930,y:470,w:640,h:70},{x:1640,y:470,w:620,h:70},
  {x:2350,y:470,w:820,h:70},{x:3280,y:470,w:660,h:70},{x:4050,y:470,w:1150,h:70},
  {x:300,y:390,w:170,h:22},{x:560,y:330,w:160,h:22},{x:1010,y:365,w:180,h:22},
  {x:1280,y:300,w:180,h:22},{x:1740,y:360,w:170,h:22},{x:1980,y:285,w:170,h:22},
  {x:2480,y:380,w:180,h:22},{x:2780,y:310,w:170,h:22},{x:3380,y:365,w:180,h:22},
  {x:3670,y:300,w:180,h:22},{x:4200,y:380,w:180,h:22},{x:4520,y:305,w:180,h:22},
  {x:4800,y:240,w:160,h:22}
];

const treasureSeed = [
  [350,350],[420,350],[600,285],[675,285],[1060,325],[1135,325],[1320,260],[1400,260],
  [1790,320],[2040,245],[2520,340],[2600,340],[2820,270],[2890,270],[3430,325],[3730,260],
  [4245,340],[4315,340],[4560,265],[4860,200],[4930,200]
];
let treasures = [];

const enemySeed = [
  {x:690,y:410,l:590,r:815},{x:1120,y:410,l:980,r:1510},{x:1850,y:410,l:1660,r:2200},
  {x:2680,y:410,l:2380,r:3120},{x:3500,y:410,l:3310,r:3890},{x:4370,y:410,l:4070,r:4720},
  {x:4580,y:245,l:4520,r:4680}
];
let enemies = [];

const checkpoint = {x:2590,y:428,w:22,h:42,active:false};
const goal = {x:5030,y:390,w:42,h:80};

function resetWorld(){
  treasures = treasureSeed.map(([x,y],i)=>({x,y,r:10,taken:false,bob:i*0.7}));
  enemies = enemySeed.map((e,i)=>({...e,w:40,h:50,vx:(i%2?1:-1)*75,hp:2,dead:false,hit:0,attackCd:0}));
  checkpoint.active=false;
  Object.assign(player,{x:120,y:360,vx:0,vy:0,hp:5,invuln:0,attack:0,attackCd:0,treasure:0,score:0,checkpointX:120,checkpointY:360});
  cameraX=0; elapsed=0; won=false; winCard.classList.add('hidden');
}

function rects(a,b){return a.x < b.x+b.w && a.x+a.w > b.x && a.y < b.y+b.h && a.y+a.h > b.y;}

function tone(freq=440,dur=.08,type='square',gain=.045){
  try{
    if(!audioCtx) audioCtx = new (window.AudioContext||window.webkitAudioContext)();
    if(audioCtx.state==='suspended') audioCtx.resume();
    const o=audioCtx.createOscillator(), g=audioCtx.createGain();
    o.type=type;o.frequency.value=freq;g.gain.value=gain;
    o.connect(g);g.connect(audioCtx.destination);o.start();g.gain.exponentialRampToValueAtTime(.0001,audioCtx.currentTime+dur);o.stop(audioCtx.currentTime+dur);
  }catch{}
}

function pressJump(){
  if(!running||paused||won)return;
  if(player.onGround||player.coyote>0){player.vy=-player.jump;player.onGround=false;player.coyote=0;tone(520,.09,'triangle',.04);}
}
function pressAttack(){
  if(!running||paused||won||player.attackCd>0)return;
  player.attack=.18;player.attackCd=.28;tone(180,.06,'sawtooth',.035);
}

window.addEventListener('keydown',e=>{
  if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Space'].includes(e.code))e.preventDefault();
  keys[e.code]=true;
  if((e.code==='Space'||e.code==='KeyW'||e.code==='ArrowUp')&&!e.repeat)pressJump();
  if((e.code==='ControlLeft'||e.code==='ControlRight'||e.code==='KeyX')&&!e.repeat)pressAttack();
  if(e.code==='Escape'&&!e.repeat)togglePause();
});
window.addEventListener('keyup',e=>keys[e.code]=false);

function bindTouch(){
  document.querySelectorAll('[data-hold]').forEach(btn=>{
    const name=btn.dataset.hold;
    const down=e=>{e.preventDefault();held[name]=true;};
    const up=e=>{e.preventDefault();held[name]=false;};
    btn.addEventListener('pointerdown',down);btn.addEventListener('pointerup',up);btn.addEventListener('pointercancel',up);btn.addEventListener('pointerleave',up);
  });
  document.querySelectorAll('[data-action]').forEach(btn=>{
    btn.addEventListener('pointerdown',e=>{e.preventDefault();btn.dataset.action==='jump'?pressJump():pressAttack();});
  });
}
bindTouch();

function gamepad(){
  const pads=navigator.getGamepads?.()||[]; const p=pads[0]; if(!p)return;
  const x=p.axes[0]||0; held.left=x<-.25;held.right=x>.25;
  if(p.buttons[0]?.pressed&&!gamepad.jumpWas)pressJump(); gamepad.jumpWas=!!p.buttons[0]?.pressed;
  if(p.buttons[2]?.pressed&&!gamepad.atkWas)pressAttack(); gamepad.atkWas=!!p.buttons[2]?.pressed;
}

function axisMove(entity,dt){
  entity.x += entity.vx*dt;
  for(const p of platforms){
    if(rects(entity,p)){
      if(entity.vx>0)entity.x=p.x-entity.w; else if(entity.vx<0)entity.x=p.x+p.w;
      entity.vx=0;
    }
  }
  entity.y += entity.vy*dt; entity.onGround=false;
  for(const p of platforms){
    if(rects(entity,p)){
      if(entity.vy>0){entity.y=p.y-entity.h;entity.vy=0;entity.onGround=true;}
      else if(entity.vy<0){entity.y=p.y+p.h;entity.vy=0;}
    }
  }
}

function hurt(dmg=1,knock=260){
  if(player.invuln>0||won)return;
  player.hp-=dmg;player.invuln=1.05;player.vy=-360;player.vx=-player.facing*knock;tone(90,.18,'sawtooth',.05);
  if(player.hp<=0) setTimeout(respawn,180);
}
function respawn(){
  player.hp=player.maxHp;player.x=player.checkpointX;player.y=player.checkpointY;player.vx=0;player.vy=0;player.invuln=1.2;
  tone(240,.15,'triangle',.05);
}

function update(dt){
  if(paused||won)return;
  elapsed+=dt; gamepad();
  player.invuln=Math.max(0,player.invuln-dt);player.attack=Math.max(0,player.attack-dt);player.attackCd=Math.max(0,player.attackCd-dt);
  player.coyote=player.onGround?.11:Math.max(0,player.coyote-dt);

  const left=keys.KeyA||keys.ArrowLeft||held.left, right=keys.KeyD||keys.ArrowRight||held.right;
  const target=(right?1:0)-(left?1:0);
  if(target){player.vx += (target*player.speed-player.vx)*Math.min(1,dt*12);player.facing=target;}
  else player.vx*=Math.pow(.0008,dt);
  player.vy+=GRAVITY*dt; if(player.vy>1100)player.vy=1100;
  axisMove(player,dt);

  if(player.y>650)respawn();
  player.x=Math.max(0,Math.min(WORLD_W-player.w,player.x));

  const attackBox={x:player.facing>0?player.x+player.w-4:player.x-52,y:player.y+10,w:56,h:36};
  for(const e of enemies){
    if(e.dead)continue;
    e.hit=Math.max(0,e.hit-dt);e.attackCd=Math.max(0,e.attackCd-dt);
    const dx=(player.x+player.w/2)-(e.x+e.w/2);
    if(Math.abs(dx)<220) e.vx=Math.sign(dx)*95; else if(e.x<e.l)e.vx=Math.abs(e.vx)||70; else if(e.x+e.w>e.r)e.vx=-Math.abs(e.vx)||-70;
    e.x+=e.vx*dt;
    if(e.x<e.l){e.x=e.l;e.vx=Math.abs(e.vx);} if(e.x+e.w>e.r){e.x=e.r-e.w;e.vx=-Math.abs(e.vx);}
    if(player.attack>0&&e.hit<=0&&rects(attackBox,e)){e.hp--;e.hit=.25;e.vx=player.facing*260;tone(300,.05,'square',.035);if(e.hp<=0){e.dead=true;player.score+=250;tone(620,.12,'triangle',.04);}}
    if(!e.dead&&rects(player,e)&&e.attackCd<=0){e.attackCd=.7;hurt();}
  }

  for(const t of treasures){
    if(t.taken)continue;
    const tr={x:t.x-t.r,y:t.y-t.r,w:t.r*2,h:t.r*2};
    if(rects(player,tr)){t.taken=true;player.treasure++;player.score+=100;tone(760,.07,'sine',.04);}
  }

  if(!checkpoint.active&&rects(player,checkpoint)){
    checkpoint.active=true;player.checkpointX=checkpoint.x-30;player.checkpointY=checkpoint.y-80;player.hp=player.maxHp;player.score+=500;tone(880,.16,'sine',.05);
  }
  if(rects(player,goal)){won=true;player.score+=1000;winStats.textContent=`Tesori ${player.treasure}/${treasures.length} · Punteggio ${player.score} · ${Math.floor(elapsed)}s`;winCard.classList.remove('hidden');tone(660,.3,'triangle',.055);}

  const desired=Math.max(0,Math.min(WORLD_W-VIEW_W,player.x+player.w/2-VIEW_W*.42));
  cameraX += (desired-cameraX)*Math.min(1,dt*5.5);
}

function drawBackground(){
  const g=ctx.createLinearGradient(0,0,0,VIEW_H);g.addColorStop(0,'#132d44');g.addColorStop(.6,'#315f70');g.addColorStop(1,'#b87b52');ctx.fillStyle=g;ctx.fillRect(0,0,VIEW_W,VIEW_H);
  ctx.fillStyle='rgba(255,205,139,.72)';ctx.beginPath();ctx.arc(760,95,44,0,Math.PI*2);ctx.fill();
  const far=-(cameraX*.18)%1250;
  for(let k=-1;k<2;k++){
    const base=far+k*1250;
    ctx.fillStyle='#233f4d';ctx.beginPath();ctx.moveTo(base,350);ctx.lineTo(base+180,210);ctx.lineTo(base+320,350);ctx.lineTo(base+500,180);ctx.lineTo(base+710,350);ctx.closePath();ctx.fill();
  }
  ctx.fillStyle='#174253';ctx.fillRect(0,430,VIEW_W,110);
  ctx.fillStyle='rgba(255,255,255,.14)';for(let i=0;i<7;i++)ctx.fillRect(((i*190-cameraX*.35)%1200)-100,445+i%2*16,110,3);
  const px=-(cameraX*.48)%900;
  for(let k=-1;k<3;k++) drawHarborSilhouette(px+k*900,330);
}
function drawHarborSilhouette(x,y){
  ctx.fillStyle='#172632';ctx.fillRect(x,y,130,100);ctx.fillRect(x+155,y+25,105,75);ctx.fillRect(x+290,y-20,150,120);ctx.fillRect(x+485,y+15,120,85);
  ctx.fillStyle='#203747';for(const wx of [18,55,92])ctx.fillRect(x+wx,y+24,13,20);
  ctx.strokeStyle='#1c2d39';ctx.lineWidth=8;ctx.beginPath();ctx.moveTo(x+690,y+100);ctx.lineTo(x+720,y-70);ctx.stroke();ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(x+718,y-60);ctx.lineTo(x+810,y+20);ctx.stroke();
}

function drawPlatforms(){
  for(const p of platforms){
    const x=p.x-cameraX;if(x>VIEW_W||x+p.w<0)continue;
    ctx.fillStyle=p.h>30?'#4a2d22':'#593929';ctx.fillRect(x,p.y,p.w,p.h);
    ctx.fillStyle='#9a6947';ctx.fillRect(x,p.y,p.w,8);
    ctx.strokeStyle='rgba(30,12,8,.5)';ctx.lineWidth=2;for(let bx=x+24;bx<x+p.w;bx+=52){ctx.beginPath();ctx.moveTo(bx,p.y+8);ctx.lineTo(bx-8,p.y+p.h);ctx.stroke();}
  }
}

function drawTreasure(t){
  if(t.taken)return;const x=t.x-cameraX,y=t.y+Math.sin(elapsed*3+t.bob)*4;
  ctx.fillStyle='#ffd15a';ctx.beginPath();ctx.arc(x,y,t.r,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#9c5c21';ctx.lineWidth=3;ctx.stroke();ctx.fillStyle='#fff0a6';ctx.fillRect(x-2,y-7,4,11);
}
function drawCheckpoint(){
  const x=checkpoint.x-cameraX;ctx.fillStyle='#3b261b';ctx.fillRect(x,checkpoint.y-45,6,87);ctx.fillStyle=checkpoint.active?'#e6ad49':'#8c3e35';ctx.beginPath();ctx.moveTo(x+6,checkpoint.y-42);ctx.lineTo(x+56,checkpoint.y-28);ctx.lineTo(x+6,checkpoint.y-14);ctx.closePath();ctx.fill();
}
function drawGoal(){
  const x=goal.x-cameraX;ctx.fillStyle='#2b211a';ctx.fillRect(x,goal.y-70,7,150);ctx.fillStyle='#d98a3f';ctx.beginPath();ctx.moveTo(x+7,goal.y-65);ctx.lineTo(x+74,goal.y-42);ctx.lineTo(x+7,goal.y-19);ctx.closePath();ctx.fill();ctx.fillStyle='#f5d591';ctx.font='bold 18px serif';ctx.fillText('★',x+28,goal.y-35);
}

function drawEnemy(e){
  if(e.dead)return;const x=e.x-cameraX,y=e.y;ctx.save();ctx.translate(x+e.w/2,y+e.h/2);if(e.hit>0)ctx.globalAlpha=.45;
  const dir=e.vx>=0?1:-1;ctx.scale(dir,1);
  ctx.fillStyle='#615650';ctx.beginPath();ctx.ellipse(0,6,17,21,0,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#796c63';ctx.beginPath();ctx.arc(3,-15,14,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#796c63';ctx.beginPath();ctx.moveTo(-8,-25);ctx.lineTo(-16,-38);ctx.lineTo(-2,-30);ctx.closePath();ctx.fill();
  ctx.fillStyle='#b94439';ctx.fillRect(-14,-4,28,8);ctx.fillStyle='#171b20';ctx.beginPath();ctx.arc(8,-18,2.5,0,Math.PI*2);ctx.fill();
  ctx.strokeStyle='#d9dde2';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(13,4);ctx.lineTo(31,-5);ctx.stroke();
  ctx.restore();
}

function drawPlayer(){
  if(player.invuln>0&&Math.floor(player.invuln*14)%2===0)return;
  const x=player.x-cameraX+player.w/2,y=player.y+player.h/2;ctx.save();ctx.translate(x,y);ctx.scale(player.facing,1);
  ctx.strokeStyle='#8d5a37';ctx.lineWidth=8;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(-15,16);ctx.quadraticCurveTo(-38,10,-34,-7);ctx.stroke();
  ctx.fillStyle='#b66c3d';ctx.beginPath();ctx.ellipse(0,8,18,22,0,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#cf8050';ctx.beginPath();ctx.arc(2,-17,15,0,Math.PI*2);ctx.fill();
  ctx.beginPath();ctx.moveTo(-9,-27);ctx.lineTo(-4,-42);ctx.lineTo(3,-29);ctx.closePath();ctx.fill();ctx.beginPath();ctx.moveTo(9,-28);ctx.lineTo(16,-40);ctx.lineTo(16,-24);ctx.closePath();ctx.fill();
  ctx.fillStyle='#1b2430';ctx.fillRect(-14,-29,29,6);ctx.beginPath();ctx.moveTo(-8,-31);ctx.quadraticCurveTo(6,-46,20,-32);ctx.lineTo(14,-25);ctx.closePath();ctx.fill();
  ctx.fillStyle='#e6b046';ctx.fillRect(-16,0,33,6);ctx.fillStyle='#15202a';ctx.beginPath();ctx.arc(8,-18,2.2,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#f0efe7';ctx.beginPath();ctx.moveTo(15,-14);ctx.lineTo(21,-11);ctx.lineTo(15,-9);ctx.closePath();ctx.fill();
  ctx.strokeStyle='#e3e8ee';ctx.lineWidth=4;ctx.beginPath();ctx.moveTo(13,5);ctx.lineTo(35,-5);ctx.stroke();ctx.strokeStyle='#9a642e';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(12,4);ctx.lineTo(17,12);ctx.stroke();
  if(player.attack>0){ctx.strokeStyle='#f7efcf';ctx.lineWidth=5;ctx.beginPath();ctx.arc(15,-2,43,-1.2,.9);ctx.stroke();}
  ctx.restore();
}

function drawHUD(){
  ctx.save();ctx.fillStyle='rgba(6,10,16,.72)';ctx.fillRect(18,16,280,58);ctx.strokeStyle='rgba(255,255,255,.13)';ctx.strokeRect(18,16,280,58);
  for(let i=0;i<player.maxHp;i++){ctx.fillStyle=i<player.hp?'#d9504f':'#3d444d';const x=38+i*32,y=45;ctx.beginPath();ctx.arc(x-5,y-4,7,0,Math.PI*2);ctx.arc(x+5,y-4,7,0,Math.PI*2);ctx.lineTo(x,y+10);ctx.closePath();ctx.fill();}
  ctx.fillStyle='#ffd15a';ctx.beginPath();ctx.arc(220,44,10,0,Math.PI*2);ctx.fill();ctx.fillStyle='#fff';ctx.font='700 16px system-ui';ctx.fillText(`× ${player.treasure}/${treasures.length}`,238,50);ctx.restore();
}

function render(){
  ctx.clearRect(0,0,VIEW_W,VIEW_H);drawBackground();drawPlatforms();treasures.forEach(drawTreasure);drawCheckpoint();drawGoal();enemies.forEach(drawEnemy);drawPlayer();drawHUD();
}

function loop(now){
  const dt=Math.min(.033,(now-last)/1000);last=now;if(running){update(dt);render();}requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

function start(){
  hero.classList.add('hidden');shell.classList.remove('hidden');running=true;paused=false;last=performance.now();canvas.focus();
}
function togglePause(){
  if(!running||won)return;paused=!paused;pauseCard.classList.toggle('hidden',!paused);
}

document.getElementById('playBtn').addEventListener('click',()=>{resetWorld();start();});
document.getElementById('restartBtn').addEventListener('click',()=>{resetWorld();paused=false;pauseCard.classList.add('hidden');canvas.focus();});
document.getElementById('resumeBtn').addEventListener('click',()=>{paused=false;pauseCard.classList.add('hidden');canvas.focus();});
document.getElementById('againBtn').addEventListener('click',()=>{resetWorld();canvas.focus();});
document.getElementById('fullscreenBtn').addEventListener('click',()=>document.fullscreenElement?document.exitFullscreen():document.getElementById('gameShell').requestFullscreen?.());
const dialog=document.getElementById('controlsDialog');document.getElementById('controlsBtn').addEventListener('click',()=>dialog.showModal());document.getElementById('closeControls').addEventListener('click',()=>dialog.close());

if('serviceWorker' in navigator)window.addEventListener('load',()=>navigator.serviceWorker.register('./sw.js').catch(()=>{}));
