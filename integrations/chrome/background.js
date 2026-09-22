let port;
let timer;
let enabled = false;
let ready = false;

function connect() {
  if (!enabled || port) return;
  port = chrome.runtime.connectNative('com.highlight.youtube');
  port.onDisconnect.addListener(() => {
    void chrome.runtime.lastError;
    port = undefined;
    ready = false;
    clearInterval(timer);
    chrome.action.setBadgeText({text: '!'});
  });
  port.onMessage.addListener(async message => {
    if (!enabled) { port?.disconnect(); return; }
    if (message.requests) {
      ready = true;
      chrome.action.setBadgeText({text: ''});
      for (const request of message.requests) {
        if (!/^https:\/\/www\.youtube\.com\/watch\?v=[\w-]{11}$/.test(request.url)) continue;
        try {
          const cookies = await chrome.cookies.getAll({domain: 'youtube.com'});
          if (enabled && port) port.postMessage({type: 'session', job_id: request.job_id,
            nonce: request.nonce, cookies});
        } catch { chrome.action.setBadgeText({text: '!'}); }
      }
    }
  });
  port.postMessage({type: 'poll'});
  timer = setInterval(() => { if (enabled && port) port.postMessage({type: 'poll'}); }, 5000);
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL('popup.html')) return;
  if (message.type === 'enable') {
    enabled = true;
    chrome.storage.local.set({enabled: true});
    connect();
  } else if (message.type === 'disable') {
    enabled = false;
    chrome.storage.local.set({enabled: false});
    if (port) port.postMessage({type: 'disconnect'});
    clearInterval(timer);
  }
  respond({enabled, connected: ready});
});
chrome.alarms.create('reconnect', {periodInMinutes: 0.5});
chrome.alarms.onAlarm.addListener(() => connect());
chrome.storage.local.get('enabled').then(value => { enabled = value.enabled === true; connect(); });
