async function update(type) {
  const value = await chrome.runtime.sendMessage({type});
  document.querySelector('#state').textContent = !value.enabled ? 'ยังไม่เปิดใช้งาน' :
    value.connected ? 'เชื่อมต่อแล้ว — วางลิงก์ใน Codex ได้เลย' : 'เปิดใช้งานแล้ว แต่ยังเชื่อมตัวรับในเครื่องไม่ได้';
}
document.querySelector('#enable').addEventListener('click', () => update('enable'));
document.querySelector('#disable').addEventListener('click', () => update('disable'));
update('status');

setInterval(() => update("status"), 1500);
