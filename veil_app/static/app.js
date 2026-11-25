/* Browser state is memory-only: no localStorage, IndexedDB or prompt cookies. */
'use strict';
const $ = (id) => document.getElementById(id);
const page = document.body.dataset.page;
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let csrf = document.querySelector('meta[name="csrf-token"]').content;
let state = null, busy = false, stage = 'INPUT', preview = null, errorMessage = '', adminView = 'dashboard';
let toastTimer;
const examples = {
  safe: '공개된 논문의 연구 방법을 요약해줘.',
  caution: '김연구의 비공개 연구 계획을 요약하고 참여자 010-1234-5678에게 보낼 안내문을 작성해줘.',
  blocked: '보안과제의 핵심기술 개발 일정을 요약해줘.'
};
const kinds = {PERSON:'이름',PHONE:'연락처',EMAIL:'이메일',KEYWORD:'연구 정보',IDENTIFIER:'식별번호'};
const reviewStatuses = {PENDING:'미검토',REVIEWED:'검토 완료',FOLLOW_UP:'후속 조치 필요'};
const riskNames = {SAFE:'안전',CAUTION:'주의',BLOCKED:'차단'};
const actions = {SENT:'안전 전송',CONVERTED_SENT:'변환 후 전송',SENT_WITH_WARNING:'경고 후 전송',CANCELLED:'취소',REJECTED:'전송 거부'};

async function api(path, data) {
  const options = {credentials:'same-origin',headers:{Accept:'application/json'}};
  if (data !== undefined) {
    options.method = 'POST';
    options.headers['Content-Type'] = 'application/json';
    options.headers['X-CSRF-Token'] = csrf;
    options.body = JSON.stringify(data);
  }
  let response;
  try { response = await fetch('/api/' + path, options); }
  catch (_) { throw new Error('PC 에이전트와 연결할 수 없어요. 실행 창을 확인하고 다시 시도해 주세요.'); }
  const result = await response.json();
  if (!response.ok) {
    if (result.state) state = result.state;
    if (response.status === 401 && page !== 'login') location.assign('/login');
    throw new Error(result.error || '작업을 완료하지 못했어요.');
  }
  if (result.csrf) csrf = result.csrf;
  return result;
}
function toast(message, error=false) {
  clearTimeout(toastTimer);
  $('toast').textContent = message;
  $('toast').className = 'toast' + (error ? ' error' : '');
  $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 6500);
}
function busyControls() {
  document.body.setAttribute('aria-busy', String(busy));
  document.querySelectorAll('button, textarea, select, input').forEach(el => {
    if (!el.dataset.lockedDisabled) el.disabled = busy;
  });
  if (page === 'workspace' && !busy && $('reason-send')) updateReason();
}
async function run(action) {
  if (busy) return;
  busy = true; busyControls();
  try { await action(); }
  catch (error) {
    if (page === 'login') {
      $('login-error').textContent = error.message;
      $('login-error').hidden = false;
    } else {
      toast(error.message, true);
      if (page === 'workspace') {
        errorMessage = error.message;
        stage = state?.prompt?.status === 'SAFE' ? 'SAFE' : state?.prompt?.status || 'INPUT';
        renderPanel();
      }
    }
  } finally { busy = false; busyControls(); }
}
function countInput() {
  const length = $('prompt-input').value.length;
  document.body.dataset.drafting = String(length > 0);
  $('char-count').textContent = length.toLocaleString() + '자' + (length > 2000 ? ' · 분석이 오래 걸릴 수 있어요' : '');
}
function requestPrompt() {
  return {prompt_id:state.prompt?.id,result_id:state.prompt?.result?.id,content:$('prompt-input').value};
}
function button(label, action, primary=false, extra='') {
  return '<button class="button ' + (primary ? 'primary' : 'secondary') + '" data-action="' + action + '" ' + extra + '>' + label + '</button>';
}
function intro(step, title, description) {
  return '<div class="panel-step">' + step + '</div><h2 class="panel-title">' + title + '</h2><p class="panel-description">' + description + '</p>';
}
function card(title, body, hint='') {
  return '<div class="card"><h3>' + title + '</h3><p>' + body + '</p>' + (hint ? '<p class="hint">' + hint + '</p>' : '') + '</div>';
}
function callout(title, body, color='green') {
  return '<div class="callout ' + color + '"><strong>' + title + '</strong><p>' + body + '</p></div>';
}
function setBadge(text, color) {
  $('status-tag').textContent = text;
  $('status-tag').className = 'tag ' + color;
  $('top-status').textContent = 'VEIL ' + text;
}
function renderPanel() {
  if (!state) return;
  document.body.dataset.stage = stage;
  const p = state.prompt, r = p?.result;
  const mode = state.policy.mode === 'FAST' ? '빠른 모드 · 마스킹' : '가명화 체험 · 규칙 검사';
  $('policy-label').textContent = mode + ' · v' + state.policy.version;
  let html = '';
  setBadge('보호 중', 'green');
  if (stage === 'BUSY' || stage === 'SENDING') {
    html = intro(stage === 'SENDING' ? 'AI RESPONSE' : 'LOCAL ANALYSIS', stage === 'SENDING' ? '답변을 기다리고 있어요' : '민감한 정보를 확인하고 있어요', stage === 'SENDING' ? '검사를 통과한 현재 입력으로 AI 답변을 요청합니다.' : '현재 입력과 같은 대화의 이전 내용을 함께 검사해요.');
    html += '<div class="panel-stack">' + card('보호 절차를 거쳐 처리 중', stage === 'SENDING' ? '승인된 입력만 AI에 보내요. 가명 대응표는 보내지 않아요.' : '보안 검사는 이 PC에서 진행해요.') + '</div><div class="progress-line"></div>';
  } else if (stage === 'PREVIEW' && preview) {
    setBadge('변환 검토', 'amber');
    html = intro('02 변환 검토', '변환 내용을 확인해 주세요', '의미가 유지됐는지 확인한 뒤 승인해 주세요.');
    html += '<div class="panel-stack"><div class="preview-card"><span class="mini-label">변환 전 · 내 PC에서만 표시</span><p class="preview-content">' + escapeHTML(preview.before) + '</p></div><div class="preview-card after"><span class="mini-label">변환 후 · AI에 보낼 내용</span><p class="preview-content">' + escapeHTML(preview.after).replace(/\[([^\]]+)\]/g, '<mark>[$1]</mark>') + '</p></div></div>';
    html += '<div class="panel-actions">' + button('변환 승인 및 재검사','approve',true) + button('승인하지 않고 돌아가기','back') + '</div><p class="panel-footnote">가명 매핑은 내 PC에만 보관되며, 외부로 전송되지 않아요.</p>';
  } else if (stage === 'REASON') {
    setBadge('주의 확인', 'amber');
    html = intro('주의 · 전송 사유', '전송 사유를 남겨 주세요', '민감정보가 포함된 내용을 그대로 전송합니다. 내용을 다시 한 번 확인해 주세요.');
    html += '<div class="panel-stack">' + callout('변환해서 보내는 것을 권장해요', '가명화 또는 마스킹하면 민감정보 노출을 줄일 수 있어요.', 'amber') + '<div class="reason-box"><label for="send-reason">전송 사유</label><textarea id="send-reason" rows="4" minlength="5" maxlength="200" placeholder="확인한 근거를 5~200자로 입력해 주세요."></textarea><div class="reason-count" id="reason-count">0 / 200</div></div></div>';
    html += '<div class="panel-actions">' + button('주의 확인 후 전송','send-reason',true,'id="reason-send" disabled') + button('돌아가기','back') + '</div><p class="panel-footnote">사유 원문은 저장하지 않으며, 입력 여부만 기록합니다.</p>';
  } else if ((stage === 'CAUTION' || stage === 'BLOCKED') && r) {
    const blocked = stage === 'BLOCKED';
    setBadge(blocked ? '전송 차단' : '변환 필요', blocked ? 'red' : 'amber');
    html = intro('01 위험 확인', blocked ? '고민감 정보의 전송을 차단했어요' : '주의 · 보안 경고를 확인해요', blocked ? '위험 정보를 변환하거나 수정한 뒤 다시 검사해 주세요.' : '개인정보와 비공개 연구 정보가 포함되어 있어요.');
    html += '<div class="panel-stack">';
    if (r.history) html += callout('이전 대화에서도 위험 정보를 찾았어요', '현재 입력을 변환해도 이전 대화의 위험이 남을 수 있어요.','amber');
    if (r.masking_required) html += callout('개인정보 변환이 필요한 입력이에요', '개인정보를 변환하거나 입력에서 제거한 뒤 다시 검사해 주세요.', 'amber');
    if (r.core) html += callout('고민감 정보 · 전송 차단', '연구실의 핵심 키워드에 해당하는 정보가 있어요. 그대로 전송할 수 없습니다.','red');
    const count = Object.values(r.counts).reduce((a,b)=>a+b,0);
    const summary = Object.entries(r.counts).map(([k,n])=>escapeHTML(kinds[k] || k)+' '+n+'건').join(' · ');
    html += card('확인된 정보 ' + count + '개', summary, '탐지 내용을 비교하려면 변환 미리보기를 열어 주세요.') + '</div>';
    html += '<div class="panel-actions">' + button('변환 미리보기','preview',true) + (!blocked && !r.masking_required ? button('주의 확인 후 전송','reason') : '') + button('요청 취소','cancel') + '</div>';
    html += '<p class="result-meta">위험 점수 ' + r.score.toFixed(2) + ' · 프롬프트 v' + p.revision + '</p>';
  } else if (stage === 'SEND_UNKNOWN') {
    setBadge('응답 미확인', 'amber');
    html = intro('RESPONSE UNKNOWN', '자동으로 다시 보내지 않아요', '이미 처리되어 요금이 발생했을 수 있어요. 입력은 유지됩니다. 다시 요청하려면 중복 처리 가능성을 확인한 뒤 새 대화를 시작해 주세요.');
  } else if (stage === 'SAFE') {
    setBadge('안전', 'green');
    html = intro('검사 완료', '안전하게 전송할 수 있어요', '현재 정책에서 위험 정보가 발견되지 않았어요.');
    html += '<div class="panel-stack">' + card('보안 검사 완료', '검사한 내용만 AI로 전달합니다.', '입력을 바꾸면 다시 검사해야 해요.') + '</div><div class="panel-actions">' + button('검사한 내용 전송','send',true) + '</div>';
  } else if (stage === 'SENT') {
    html = intro('RESPONSE RECEIVED', '답변이 도착했어요', '왼쪽 대화에서 AI의 답변을 확인해 주세요.');
    const restored = state.messages.some(m=>m.restored);
    html += '<div class="panel-stack">' + callout('보호 과정을 마쳤어요', p?.converted ? '변환한 내용을 재검사하고 전송했어요.' : '보안 검사를 통과한 내용으로 응답을 받았어요.') + (restored ? card('답변을 내 PC에서 복원했어요','가명을 원래 이름으로 바꿔 보여드려요.','마스킹한 연락처 등은 복원하지 않아요.') : card('다음 질문도 안전하게', '같은 대화의 이전 내용과 함께 검사해요.')) + '</div><div class="panel-actions">' + button('다음 질문 작성','focus',true) + '</div>';
  } else {
    const stale = stage === 'STALE', cancelled = stage === 'CANCELLED';
    html = intro('PROMPT PROTECTION', stale ? '입력이 바뀌었어요' : cancelled ? '요청을 취소했어요' : '전송 전에 확인할게요', stale ? '변경된 내용을 다시 검사해야 전송할 수 있어요.' : '현재 입력과 같은 대화의 이전 내용을 함께 검사해요.');
    html += '<dl class="desk-facts"><div><dt>검사 범위</dt><dd>현재 입력 + 이전 4개</dd></div><div><dt>처리 위치</dt><dd>이 PC에서 검사·복원</dd></div><div><dt>전송 대상</dt><dd>'+escapeHTML(state.ai.provider)+'</dd></div></dl>';
    html += '<div class="panel-actions">' + button('검사하고 보내기','analyze',true) + '</div><p class="panel-footnote">안전하면 바로 전송하고,<br>주의가 필요하면 먼저 보여드려요.</p>';
  }
  if (errorMessage) html += '<p class="inline-error" role="alert">' + escapeHTML(errorMessage) + '</p>';
  $('panel-content').innerHTML = html;
  if ($('send-reason')) $('send-reason').addEventListener('input', updateReason);
  busyControls();
}
function updateReason() {
  const value = $('send-reason')?.value.trim() || '';
  if ($('reason-count')) $('reason-count').textContent = value.length + ' / 200';
  if ($('reason-send')) $('reason-send').disabled = busy || value.length < 5 || value.length > 200;
}
function renderMessages() {
  if (!state.messages.length) {
    $('messages').innerHTML = initialMessages;
    return;
  }
  $('messages').innerHTML = state.messages.map(m => '<article class="message ' + (m.role === 'user' ? 'user' : 'assistant') + '"><div class="message-label">' + (m.role === 'user' ? '나' : escapeHTML(state.ai.provider)) + '</div><div class="message-body">' + escapeHTML(m.content) + '</div>' + (m.restored ? '<div class="restored-note">답변의 가명을 내 PC에서 복원했어요. 마스킹 정보는 복원하지 않습니다.</div>' : '') + '</article>').join('');
  $('messages').scrollTop = $('messages').scrollHeight;
}
const initialMessages = $('messages')?.innerHTML || '';
function accept(data) {
  state = data;
  stage = state.prompt?.status || 'INPUT';
  errorMessage = '';
  $('account-id').textContent = state.user.id;
  $('scenario').value = state.scenario || 'SUCCESS';
  document.querySelector('.demo-settings').hidden = !state.ai.is_demo;
  $('ai-chat-label').textContent = '현재 대화 · ' + state.ai.provider + ' / ' + state.ai.model;
  $('ai-status').textContent = state.ai.provider + (state.ai.is_demo ? ' · 외부 전송 없음' : state.ai.configured ? ' · 키 등록됨' : ' · 키 등록 필요');
  renderMessages(); renderPanel();
}
async function send(reason='') {
  stage = 'SENDING'; renderPanel();
  const data = await api('send', {...requestPrompt(),reason});
  $('prompt-input').value = ''; countInput(); accept(data);
}
async function analyze() {
  if (!$('prompt-input').value.trim()) { $('prompt-input').focus(); throw new Error('검사할 내용을 먼저 입력해 주세요.'); }
  errorMessage = ''; stage = 'BUSY'; renderPanel();
  document.querySelector('.protection-panel').scrollIntoView({behavior:'smooth',block:'nearest'});
  accept(await api('analyze',{content:$('prompt-input').value}));
  if (state.prompt.result.level === 'SAFE') await send();
}
const workActions = {
  analyze,
  preview: async () => { preview = await api('preview',requestPrompt()); stage = 'PREVIEW'; errorMessage=''; renderPanel(); },
  approve: async () => {
    const data = {...requestPrompt(),token:preview.token};
    stage='BUSY'; renderPanel();
    const next = await api('approve',data);
    $('prompt-input').value=next.prompt.content; countInput(); preview=null; accept(next);
    if (state.prompt.result.level === 'SAFE') await send();
  },
  back: async () => { stage=state.prompt.status; preview=null; renderPanel(); },
  reason: async () => { stage='REASON'; renderPanel(); setTimeout(()=>$('send-reason')?.focus(),0); },
  'send-reason': async () => send($('send-reason').value),
  send: async () => send(),
  cancel: async () => { const data=await api('cancel',requestPrompt()); $('prompt-input').value=''; countInput(); preview=null; accept(data); },
  focus: async () => { stage='INPUT'; renderPanel(); $('prompt-input').focus(); }
};
async function initWorkspace() {
  state=await api('session');
  if (!state.user) {location.assign('/login');return;}
  if (state.prompt && !['SENT','CANCELLED'].includes(state.prompt.status)) $('prompt-input').value=state.prompt.content;
  countInput(); accept(state);
  $('prompt-input').addEventListener('input',()=>{
    countInput(); preview=null; errorMessage='';
    stage=state.prompt && !['SENT','CANCELLED'].includes(state.prompt.status) ? 'STALE' : 'INPUT'; renderPanel();
  });
  $('prompt-input').addEventListener('keydown',e=>{if (e.ctrlKey && e.key==='Enter'){e.preventDefault();run(analyze);}});
  $('new-chat').addEventListener('click',()=>run(async()=>{
    accept(await api('conversation/new',{})); $('prompt-input').value=''; countInput(); preview=null; $('prompt-input').focus();
  }));
  $('scenario').addEventListener('change',()=>run(async()=>{state=await api('scenario',{scenario:$('scenario').value});toast('시연 상황을 변경했어요.');}));
}
function labels(counts) {
  return Object.entries(typeof counts === 'string' ? JSON.parse(counts) : counts).map(([k,n])=>(kinds[k]||k)+' '+n+'건').join(' · ') || '탐지 없음';
}
function renderDashboard(rows) {
  const counts={safe:0,converted:0,warning:0,cancelled:0};
  rows.forEach(r=>{const key={SENT:'safe',CONVERTED_SENT:'converted',SENT_WITH_WARNING:'warning',CANCELLED:'cancelled'}[r.action];if(key)counts[key]++;});
  $('stat-total').textContent=rows.length.toLocaleString();
  ['safe','converted','warning'].forEach(k=>$('stat-'+k).textContent=counts[k].toLocaleString());
  $('bars').innerHTML=Object.entries({safe:'안전 전송',converted:'변환 후 전송',warning:'경고 후 전송',cancelled:'요청 취소'}).map(([k,label])=>'<div class="bar-row '+k+'"><span>'+label+'</span><progress aria-label="'+label+'" value="'+counts[k]+'" max="'+Math.max(rows.length,1)+'"></progress><strong>'+counts[k]+'</strong></div>').join('');
}
function fillPolicy(p) {
  state.policy=p;
  document.querySelectorAll('.policy-version').forEach(el=>el.textContent='적용 중 · v'+p.version);
  $('keywords').value=p.keywords.join(', '); $('core-keywords').value=p.core_keywords.join(', ');
  $('caution-threshold').value=p.caution; $('block-threshold').value=p.block;
  document.querySelectorAll('input[name="mode"]').forEach(el=>el.checked=el.value===p.mode);
  document.querySelectorAll('input[name="log-level"]').forEach(el=>el.checked=el.value===p.log_level);
  $('require-pii-masking').checked=p.require_pii_masking;
  $('retention-days').value=p.retention_days; $('auto-delete').checked=p.auto_delete;
}
function switchAdmin(view) {
  adminView=view;
  document.querySelectorAll('.admin-view').forEach(el=>el.hidden=el.id!=='view-'+view);
  document.querySelectorAll('.admin-sidebar [data-view]').forEach(el=>{el.classList.toggle('active',el.dataset.view===view);el.setAttribute('aria-current',el.dataset.view===view?'page':'false');});
  if(view==='logs') return searchLogs();
}
function logTime(value) {
  return new Date(value).toLocaleString('ko-KR', {
    timeZone:'Asia/Seoul', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false
  });
}
async function searchLogs() {
  const q=new URLSearchParams({start:$('log-start').value,end:$('log-end').value,user:$('log-user').value.trim(),level:$('log-level').value});
  const {logs}=await api('logs?'+q);
  $('log-count').textContent='검색 결과 '+logs.length+'건';
  $('logs-empty').hidden=logs.length!==0;
  $('log-rows').innerHTML = logs.map(log => {
    const riskColor = {SAFE:'green',CAUTION:'amber',BLOCKED:'red'}[log.risk_level] || '';
    const options = Object.entries(reviewStatuses).map(([value, label]) =>
      '<option value="' + value + '"' + (value === log.review_status ? ' selected' : '') + '>' + label + '</option>').join('');
    const lastReview = log.reviewed_at
      ? '<div class="small muted">' + escapeHTML(log.reviewer_id) + ' · ' + escapeHTML(logTime(log.reviewed_at)) + '</div>'
      : '';
    return '<tr><td>' + escapeHTML(logTime(log.created_at)) + '</td><td>' + escapeHTML(log.user_id) +
      '</td><td><span class="tag ' + riskColor + '">' + escapeHTML(riskNames[log.risk_level] || '미검사') +
      '</span></td><td>' + escapeHTML(actions[log.action] || log.action) + '</td><td>' + escapeHTML(labels(log.counts)) +
      '</td><td><form class="log-review" data-id="' + escapeHTML(log.id) + '" data-created-at="' +
      escapeHTML(log.created_at) + '" data-revision="' + escapeHTML(log.review_revision) + '">' +
      '<select aria-label="기록 ' + escapeHTML(log.id) + ' 검토 상태">' + options +
      '</select> <button class="text-button" type="submit">저장</button></form>' + lastReview + '</td></tr>';
  }).join('');
}
async function initAdmin() {
  state=await api('session'); if(!state.user){location.assign('/login');return;}
  fillPolicy(state.policy);
  const connection = await api('ai-settings');
  const showConnection = ai => { $('ai-model').value = ai.model; $('ai-connection-status').textContent = ai.configured ? '키 등록됨 · 질문을 보내 연결을 확인하세요' : 'API 키를 등록해 주세요'; };
  showConnection(connection.ai);
  $('ai-form').addEventListener('submit', e => { e.preventDefault(); run(async () => {
    const key = $('api-key').value.trim(); $('api-key').value = '';
    const result = await api('ai-settings', {api_key:key, model:$('ai-model').value.trim()});
    showConnection(result.ai); toast('설정을 저장했어요. 연구자 화면에서 질문을 보내세요.');
  }); });
  const date=new Date(), start=new Date(date.getTime()-30*86400000);
  const kstDate=d=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(d);
  $('log-start').value=kstDate(start); $('log-end').value=kstDate(date);
  const refresh=async()=>{const data=await api('logs');renderDashboard(data.logs);};
  await refresh();
  $('refresh-dashboard').addEventListener('click',()=>run(refresh));
  $('log-filter').addEventListener('submit',e=>{e.preventDefault();run(searchLogs);});
  $('log-rows').addEventListener('submit', event => {
    const form = event.target.closest('.log-review');
    if (!form) return;
    event.preventDefault();
    run(async () => {
      await api('logs/' + form.dataset.id + '/review', {
        created_at:form.dataset.createdAt, revision:Number(form.dataset.revision),
        status:form.querySelector('select').value
      });
      await searchLogs();
      toast('검토 상태를 저장했어요.');
    });
  });
  $('policy-form').addEventListener('submit',e=>{
    e.preventDefault();
    run(async()=>{
      const next=await api('policy',{version:state.policy.version,keywords:$('keywords').value.split(',').map(s=>s.trim()).filter(Boolean),
        core_keywords:$('core-keywords').value.split(',').map(s=>s.trim()).filter(Boolean),caution:Number($('caution-threshold').value),block:Number($('block-threshold').value),
        mode:document.querySelector('input[name="mode"]:checked').value,require_pii_masking:$('require-pii-masking').checked});
      fillPolicy(next.policy);toast('보안 정책을 저장했어요. 다음 검사부터 적용됩니다.');
    });
  });
  $('retention-form').addEventListener('submit',e=>{
    e.preventDefault();
    run(async()=>{
      const next=await api('policy',{version:state.policy.version,log_level:document.querySelector('input[name="log-level"]:checked').value,
        retention_days:Number($('retention-days').value),auto_delete:$('auto-delete').checked});
      fillPolicy(next.policy);await refresh();toast('로그 보관 설정을 저장했어요.');
    });
  });
}
document.addEventListener('click',e=>{
  const logout=e.target.closest('.logout');
  if(logout)run(async()=>{await api('logout',{});state=null;preview=null;location.replace('/login');});
  const action=e.target.closest('[data-action]');
  if(action && workActions[action.dataset.action])run(workActions[action.dataset.action]);
  const example=e.target.closest('[data-example]');
  if(example && !busy){
    $('prompt-input').value=examples[example.dataset.example];
    $('prompt-input').dispatchEvent(new Event('input'));$('prompt-input').focus();
  }
  const view=e.target.closest('[data-view]');
  if(view)run(()=>switchAdmin(view.dataset.view));
});
async function init() {
  if(page==='login'){
    await api('session');
    $('login-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{
      $('login-error').hidden=true;
      const data=await api('login',{username:$('username').value,password:$('password').value});
      $('password').value='';location.assign(data.user.role==='MANAGER'?'/admin':'/workspace');
    });});
    $('toggle-password').addEventListener('click',()=>{
      const shown=$('password').type==='password';$('password').type=shown?'text':'password';
      $('toggle-password').textContent=shown?'숨기기':'보기';
      $('toggle-password').setAttribute('aria-label',shown?'비밀번호 숨기기':'비밀번호 표시');
    });
    $('manager-login').addEventListener('click',()=>{$('username').value='manager';$('password').focus();});
  } else if(page==='workspace') await initWorkspace();
  else if(page==='admin') await initAdmin();
}
run(init);
