// ========================================== //
//  Alarm & Reminder System — Frontend Logic
//  Connects to C alarm engine via Node.js API
// ========================================== //

// ==================== //
// Configuration
// ==================== //

const API_BASE = 'http://localhost:3000/api';
let backendOnline = false;

// ==================== //
// State Management
// ==================== //

let alarms = [];
let reminders = [];
let currentTab = 'alarms';
let availableSounds = [];
let editingAlarmId = null;
let editingReminderId = null;

// ==================== //
// Notification Permission
// ==================== //

const NOTIF_PERM_KEY = 'notification_permission_asked';

function initNotificationPermission() {
    if (!('Notification' in window)) return;
    const state = Notification.permission;
    if (state === 'granted' || state === 'denied') {
        localStorage.setItem(NOTIF_PERM_KEY, 'true');
        return;
    }
    if (!localStorage.getItem(NOTIF_PERM_KEY)) {
        Notification.requestPermission().then(() => {
            localStorage.setItem(NOTIF_PERM_KEY, 'true');
        });
    }
}

// ==================== //
// Audio System
// ==================== //

let audioContext = null;
let audioUnlocked = false;

function unlockAudio() {
    if (audioUnlocked) return;
    try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const buffer = audioContext.createBuffer(1, 1, 22050);
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        source.start(0);
        audioUnlocked = true;
    } catch (e) { /* Fallback */ }
}

function playBrowserSound(soundName) {
    if (audioContext && audioContext.state === 'running') {
        try {
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            osc.connect(gain);
            gain.connect(audioContext.destination);

            const freqs = {
                glass: 1200, ping: 880, hero: 660, purr: 440,
                submarine: 330, basso: 220, funk: 550, pop: 1000
            };
            osc.frequency.value = freqs[soundName] || 880;
            osc.type = 'sine';
            gain.gain.value = 0.3;
            
            const now = audioContext.currentTime;
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.8);
            osc.start(now);
            osc.stop(now + 0.8);

            // Additional beeps for "alarm" feel
            setTimeout(() => {
                if (audioContext.state !== 'running') return;
                const osc2 = audioContext.createOscillator();
                const gain2 = audioContext.createGain();
                osc2.connect(gain2);
                gain2.connect(audioContext.destination);
                osc2.frequency.value = freqs[soundName] || 880;
                gain2.gain.value = 0.3;
                osc2.start(audioContext.currentTime);
                osc2.stop(audioContext.currentTime + 0.5);
            }, 400);

            return;
        } catch (e) { }
    }
    if (audioContext && audioContext.state === 'suspended') {
        audioContext.resume().then(() => playBrowserSound(soundName));
        return;
    }
    // Simple fallback
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        osc.connect(ctx.destination);
        osc.frequency.value = 880;
        osc.start();
        setTimeout(() => { osc.stop(); ctx.close(); }, 500);
    } catch (e) { console.warn('Audio failed', e); }
}

['click', 'touchstart', 'keydown'].forEach(evt => {
    document.addEventListener(evt, unlockAudio, { once: true });
});

// ==================== //
// Initialization
// ==================== //

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    loadFromLocalStorage();
    renderAlarms();
    renderReminders();
    startClock();
    initNotificationPermission();
    checkBackendStatus();
    fetchSounds();
});

function initializeApp() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Alarm Modal
    document.getElementById('addAlarmBtn').addEventListener('click', () => openAlarmModal());
    document.getElementById('closeAlarmModal').addEventListener('click', closeAlarmModal);
    document.getElementById('cancelAlarm').addEventListener('click', closeAlarmModal);
    document.getElementById('saveAlarm').addEventListener('click', saveAlarm);

    // Reminder Modal
    document.getElementById('addReminderBtn').addEventListener('click', () => openReminderModal());
    document.getElementById('closeReminderModal').addEventListener('click', closeReminderModal);
    document.getElementById('cancelReminder').addEventListener('click', closeReminderModal);
    document.getElementById('saveReminder').addEventListener('click', saveReminder);

    document.querySelectorAll('.day-btn').forEach(btn => {
        btn.addEventListener('click', () => btn.classList.toggle('active'));
    });

    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.classList.remove('active');
        });
    });
}

// ==================== //
// Backend Status
// ==================== //

async function checkBackendStatus() {
    const statusEl = document.getElementById('backendStatus');
    try {
        const res = await fetch(`${API_BASE}/status`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
            backendOnline = true;
            statusEl.classList.add('online');
            statusEl.classList.remove('offline');
            statusEl.querySelector('.status-text').textContent = 'System Online';
        }
    } catch (e) {
        backendOnline = false;
        statusEl.classList.add('offline');
        statusEl.classList.remove('online');
        statusEl.querySelector('.status-text').textContent = 'System Offline';
    }
    setTimeout(checkBackendStatus, 15000);
}

async function fetchSounds() {
    try {
        const res = await fetch(`${API_BASE}/sounds`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
            availableSounds = await res.json();
            populateSoundSelectors();
        }
    } catch (e) {
        availableSounds = [
            { name: 'glass', description: 'Glass chime', available: true },
            { name: 'ping', description: 'Ping notification', available: true },
            { name: 'hero', description: 'Hero fanfare', available: true },
            { name: 'purr', description: 'Gentle purr', available: true },
            { name: 'submarine', description: 'Submarine sonar', available: true },
        ];
        populateSoundSelectors();
    }
}

function populateSoundSelectors() {
    const soundIcons = {
        glass: '🔔', ping: '🛎️', hero: '🎺', purr: '🐱',
        submarine: '🌊', basso: '🎵', funk: '🎶', pop: '💥'
    };
    const selectors = [
        document.getElementById('alarmSound'),
        document.getElementById('reminderSound')
    ];
    selectors.forEach(select => {
        if (!select) return;
        const currentVal = select.value;
        select.innerHTML = availableSounds.map(s => {
            const icon = soundIcons[s.name] || '🔈';
            const disabled = !s.available ? ' (unavailable)' : '';
            return `<option value="${s.name}" ${!s.available ? 'disabled' : ''}>${icon} ${s.description}${disabled}</option>`;
        }).join('');
        if (currentVal) select.value = currentVal;
    });
}

// ==================== //
// Clock & Tab Logic
// ==================== //

function startClock() {
    updateClock();
    setInterval(updateClock, 1000);
    setInterval(checkAlarms, 1000);
    setInterval(checkReminders, 60000);
}

function updateClock() {
    const now = new Date();
    document.getElementById('currentTime').textContent = now.toLocaleTimeString('en-US', { hour12: false });
    document.getElementById('currentDate').textContent = now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
}

const tabScrollPositions = {};
function switchTab(tabName) {
    tabScrollPositions[currentTab] = window.scrollY;
    currentTab = tabName;

    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tabName));
    
    // Stabilize height
    const mainContent = document.querySelector('.main-content');
    mainContent.style.minHeight = `${mainContent.offsetHeight}px`;

    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}Content`);
    });

    if (tabName === 'worldclock') {
        fetchWorldClock();
        if (!window.wcInterval) window.wcInterval = setInterval(fetchWorldClock, 5000);
    } else {
        if (window.wcInterval) { clearInterval(window.wcInterval); window.wcInterval = null; }
    }

    requestAnimationFrame(() => {
        window.scrollTo(0, tabScrollPositions[tabName] || 0);
        setTimeout(() => { mainContent.style.minHeight = ''; }, 100);
    });
}

async function fetchWorldClock() {
    const grid = document.getElementById('worldclockGrid');
    if (!grid) return;
    try {
        const res = await fetch(`${API_BASE}/worldclock`, { signal: AbortSignal.timeout(3000) });
        if (!res.ok) throw new Error();
        const zones = await res.json();
        const tzIcons = { 'Asia/Kolkata': '🇮🇳', 'America/New_York': '🇺🇸', 'Europe/London': '🇬🇧', 'Asia/Tokyo': '🇯🇵' };
        
        grid.innerHTML = zones.map(zone => {
            const hour = parseInt(zone.time.split(':')[0]);
            const isDay = hour >= 6 && hour < 18;
            return `
                <div class="worldclock-card ${isDay ? 'daytime' : 'nighttime'}">
                    <div class="wc-header">
                        <span class="wc-flag">${tzIcons[zone.tz] || '🌍'}</span>
                        <span class="wc-label">${zone.label}</span>
                        <span class="wc-daynight">${isDay ? '☀️' : '🌙'}</span>
                    </div>
                    <div class="wc-time">${zone.time}</div>
                    <div class="wc-date">${zone.date}</div>
                    <div class="wc-offset">${zone.offset}</div>
                </div>
            `;
        }).join('');
    } catch (e) {
        if (!grid.innerHTML.includes('error')) {
            grid.innerHTML = `<div class="worldclock-error"><p>System Offline</p></div>`;
        }
    }
}

// ==================== //
// HELPER: Cancel Backend Process
// ==================== //

async function cancelBackendProcess(pid) {
    if (!pid || !backendOnline) return;
    console.log('[Frontend] Cancelling/Updating backend process...');
    try {
        await fetch(`${API_BASE}/cancel`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pid })
        });
    } catch (e) {
        // Silent fail — process is gone or server down
    }
}

// ==================== //
// Utils
// ==================== //

function getLocalDateString(date = new Date()) {
    // Returns YYYY-MM-DD in local time
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function getLocalTimeString(date = new Date()) {
    // Returns HH:MM in local time
    return date.toTimeString().substring(0, 5);
}

// ==================== //
// Alarms
// ==================== //

function openAlarmModal(alarmId = null) {
    const modal = document.getElementById('alarmModal');
    modal.classList.add('active');
    
    // Ensure we are working with numbers if checking state
    if (alarmId) {
        // Edit Mode
        const alarm = alarms.find(a => a.id === alarmId);
        if (!alarm) return closeAlarmModal();
        
        editingAlarmId = alarm.id;
        document.querySelector('#alarmModal .modal-header h2').textContent = 'Edit Alarm';
        
        document.getElementById('alarmDate').value = alarm.date;
        document.getElementById('alarmTime').value = alarm.time;
        document.getElementById('alarmLabel').value = alarm.label;
        if (document.getElementById('alarmSound')) document.getElementById('alarmSound').value = alarm.sound;

        document.querySelectorAll('#alarmModal .day-btn').forEach(btn => {
            if (alarm.days.includes(btn.dataset.day)) btn.classList.add('active');
            else btn.classList.remove('active');
        });
    } else {
        // Create Mode
        editingAlarmId = null;
        document.querySelector('#alarmModal .modal-header h2').textContent = 'Add Alarm';
        
        document.getElementById('alarmDate').value = getLocalDateString();
        const now = new Date();
        now.setMinutes(now.getMinutes() + 5);
        document.getElementById('alarmTime').value = getLocalTimeString(now);
        document.getElementById('alarmLabel').value = '';
        if (document.getElementById('alarmSound')) document.getElementById('alarmSound').selectedIndex = 0;
        document.querySelectorAll('#alarmModal .day-btn').forEach(btn => btn.classList.remove('active'));
    }
}

function closeAlarmModal() {
    document.getElementById('alarmModal').classList.remove('active');
}

async function saveAlarm() {
    const date = document.getElementById('alarmDate').value;
    const time = document.getElementById('alarmTime').value;
    const label = document.getElementById('alarmLabel').value || 'Alarm';
    const sound = document.getElementById('alarmSound')?.value || 'glass';

    if (!date || !time) {
        showNotification('Please set date and time', 'error');
        return;
    }

    const selectedDays = Array.from(document.querySelectorAll('#alarmModal .day-btn.active')).map(b => b.dataset.day);

    // If editing, cancel old backend process first (fire & forget)
    if (editingAlarmId) {
        const old = alarms.find(a => a.id === editingAlarmId);
        if (old && old.backendScheduled) cancelBackendProcess(old.childPid);
    }

    const newAlarm = {
        id: editingAlarmId || Date.now(),
        date,
        time,
        label,
        sound,
        days: selectedDays,
        enabled: true,
        repeat: selectedDays.length > 0,
        backendScheduled: false, // Reset until server confirms
        childPid: null
    };

    // Update Local First (Optimistic UI)
    if (editingAlarmId) {
        const idx = alarms.findIndex(a => a.id === editingAlarmId);
        if (idx !== -1) alarms[idx] = newAlarm;
        showNotification('Alarm updated', 'info');
    } else {
        alarms.push(newAlarm);
        showNotification('Alarm saved', 'info');
    }

    saveToLocalStorage();
    renderAlarms();
    closeAlarmModal();

    // Schedule Backend
    if (backendOnline) {
        try {
            const res = await fetch(`${API_BASE}/alarm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ datetime: `${date} ${time}`, message: label, sound })
            });
            const result = await res.json();
            
            if (result.status === 'success') {
                // Update the alarm in our list with backend info
                // Need to find it again in case user fiddled with it (unlikely)
                const target = alarms.find(a => a.id === newAlarm.id);
                if (target) {
                    target.backendScheduled = true;
                    target.childPid = result.child_pid;
                    saveToLocalStorage();
                    renderAlarms(); // Re-render to show any status change (we hid the PIDs but maybe we want a subtle indicator?)
                    
                    // Optional: Show discrete success message
                    // showNotification('Scheduled with backend', 'success');
                }
            } else {
                 showNotification(result.message, 'warning');
            }
        } catch (e) {
            // Already saved locally, just backend failed.
        }
    }
}

function renderAlarms() {
    const list = document.getElementById('alarmsList');
    if (!alarms.length) {
        list.innerHTML = `<div class="empty-state"><p>No alarms set</p></div>`;
        return;
    }
    
    list.innerHTML = alarms.map(alarm => `
        <div class="item-card">
            <div class="item-header">
                <div>
                    <div class="item-time">${formatTime(alarm.time)}</div>
                    <div class="item-label">${alarm.label}</div>
                    <div class="item-date-info">📅 ${formatDate(alarm.date)}</div>
                    ${alarm.repeat ? `
                        <div class="item-days">
                            ${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(d => 
                                `<span class="day-badge ${alarm.days.includes(d)?'active':''}">${d[0]}</span>`
                            ).join('')}
                        </div>
                    ` : ''}
                </div>
                <div class="item-actions">
                    <div class="toggle-switch ${alarm.enabled ? 'active' : ''}" onclick="toggleAlarm(${alarm.id})"></div>
                    <button class="icon-btn" onclick="openAlarmModal(${alarm.id})" title="Edit">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                        </svg>
                    </button>
                    <button class="icon-btn delete" onclick="deleteAlarm(${alarm.id})" title="Delete">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

function toggleAlarm(id) {
    const a = alarms.find(a => a.id === id);
    if (a) { a.enabled = !a.enabled; saveToLocalStorage(); renderAlarms(); }
}

function deleteAlarm(id) {
    if (confirm('Delete this alarm?')) {
        const a = alarms.find(a => a.id === id);
        if (a && a.backendScheduled) cancelBackendProcess(a.childPid);
        alarms = alarms.filter(a => a.id !== id);
        saveToLocalStorage();
        renderAlarms();
    }
}

function checkAlarms() {
    const now = new Date();
    const timeStr = getLocalTimeString(now);
    const dateStr = getLocalDateString(now);
    const dayStr = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][now.getDay()];
    
    alarms.forEach(a => {
        if (a.enabled && a.time === timeStr && !a.backendScheduled) {
            // IF repeating: check day
            // IF not repeating: check DATE
            if (a.repeat) {
                if (a.days.includes(dayStr)) triggerAlarm(a);
            } else {
                if (a.date === dateStr) triggerAlarm(a);
            }
        }
    });
}

function triggerAlarm(a) {
    playBrowserSound(a.sound);
    showNotification(`⏰ ${a.label}`, 'alarm');
    sendBrowserNotification('Alarm', a.label);
    if (!a.repeat) { a.enabled = false; saveToLocalStorage(); renderAlarms(); }
}

// ==================== //
// Reminders
// ==================== //

function openReminderModal(reminderId = null) {
    const modal = document.getElementById('reminderModal');
    modal.classList.add('active');
    
    if (reminderId) {
        const r = reminders.find(x => x.id === reminderId);
        if (!r) return closeReminderModal();
        editingReminderId = r.id;
        document.querySelector('#reminderModal .modal-header h2').textContent = 'Edit Reminder';
        document.getElementById('reminderTitle').value = r.title;
        document.getElementById('reminderDate').value = r.date;
        document.getElementById('reminderTime').value = r.time;
        document.getElementById('reminderNotes').value = r.notes || '';
        document.getElementById('reminderSound').value = r.sound;
    } else {
        editingReminderId = null;
        document.querySelector('#reminderModal .modal-header h2').textContent = 'Add Reminder';
        document.getElementById('reminderTitle').value = '';
        document.getElementById('reminderDate').value = getLocalDateString();
        const now = new Date();
        now.setHours(now.getHours() + 1);
        document.getElementById('reminderTime').value = getLocalTimeString(now);
        document.getElementById('reminderNotes').value = '';
        document.getElementById('reminderSound').selectedIndex = 0;
    }
}

function closeReminderModal() {
    document.getElementById('reminderModal').classList.remove('active');
}

async function saveReminder() {
    const title = document.getElementById('reminderTitle').value;
    const date = document.getElementById('reminderDate').value;
    const time = document.getElementById('reminderTime').value;
    const notes = document.getElementById('reminderNotes').value;
    const sound = document.getElementById('reminderSound')?.value || 'glass';

    if (!title || !date || !time) {
        showNotification('Required fields missing', 'error');
        return;
    }

    if (editingReminderId) {
        const old = reminders.find(r => r.id === editingReminderId);
        if (old && old.backendScheduled) cancelBackendProcess(old.childPid);
    }

    const newReminder = {
        id: editingReminderId || Date.now(),
        title, date, time, notes, sound,
        completed: false,
        backendScheduled: false,
        childPid: null
    };

    if (editingReminderId) {
        const idx = reminders.findIndex(r => r.id === editingReminderId);
        if (idx !== -1) reminders[idx] = newReminder;
        showNotification('Reminder updated', 'info');
    } else {
        reminders.push(newReminder);
        showNotification('Reminder saved', 'info');
    }

    saveToLocalStorage();
    renderReminders();
    closeReminderModal();

    if (backendOnline) {
        try {
            const res = await fetch(`${API_BASE}/alarm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ datetime: `${date} ${time}`, message: title, sound })
            });
            const result = await res.json();
            if (result.status === 'success') {
                const target = reminders.find(r => r.id === newReminder.id);
                if (target) {
                    target.backendScheduled = true;
                    target.childPid = result.child_pid;
                    saveToLocalStorage();
                    renderReminders();
                }
            } else {
                 showNotification(result.message, 'warning');
            }
        } catch (e) { }
    }
}

function renderReminders() {
    const list = document.getElementById('remindersList');
    if (!reminders.length) {
        list.innerHTML = `<div class="empty-state"><p>No reminders yet</p></div>`;
        return;
    }
    
    // Sort logic
    const sorted = [...reminders].sort((a,b) => new Date(`${a.date}T${a.time}`) - new Date(`${b.date}T${b.time}`));

    list.innerHTML = sorted.map(r => `
        <div class="reminder-card ${r.completed ? 'completed' : ''}">
            <div class="item-header">
                <div style="flex: 1;">
                    <div class="reminder-title">${r.title}</div>
                    <div class="reminder-datetime">📅 ${formatDate(r.date)} at ${formatTime(r.time)}</div>
                    ${r.notes ? `<div class="reminder-notes">${r.notes}</div>` : ''}
                </div>
                <div class="item-actions">
                    <button class="icon-btn" onclick="toggleReminder(${r.id})">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            ${r.completed ? 
                                `<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>` : 
                                `<circle cx="12" cy="12" r="10"></circle>`
                            }
                        </svg>
                    </button>
                    <button class="icon-btn" onclick="openReminderModal(${r.id})" title="Edit">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                        </svg>
                    </button>
                    <button class="icon-btn delete" onclick="deleteReminder(${r.id})" title="Delete">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

function toggleReminder(id) {
    const r = reminders.find(x => x.id === id);
    if (r) { r.completed = !r.completed; saveToLocalStorage(); renderReminders(); }
}

function deleteReminder(id) {
    if (confirm('Delete reminder?')) {
        const r = reminders.find(x => x.id === id);
        if (r && r.backendScheduled) cancelBackendProcess(r.childPid);
        reminders = reminders.filter(x => x.id !== id);
        saveToLocalStorage();
        renderReminders();
    }
}

function checkReminders() {
    const now = new Date();
    const nowStr = `${getLocalDateString(now)}T${getLocalTimeString(now)}`;
    
    reminders.forEach(r => {
        if (!r.completed && !r.backendScheduled) {
            if (`${r.date}T${r.time}` === nowStr) triggerReminder(r);
        }
    });
}

function triggerReminder(r) {
    playBrowserSound(r.sound);
    showNotification(`🔔 ${r.title}`, 'reminder');
    sendBrowserNotification('Reminder', r.title);
}

// ==================== //
// Utils
// ==================== //

function formatTime(time) {
    const [h, m] = time.split(':');
    const hour = parseInt(h);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 || 12;
    return `${displayHour}:${m} ${ampm}`;
}

function formatDate(dateString) {
    const d = new Date(dateString + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function showNotification(message, type = 'info') {
    const n = document.createElement('div');
    n.className = `notification notification-${type}`;
    n.textContent = message;
    
    const colors = {
        success: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        error: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
        warning: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
        info: 'var(--accent-gradient)',
        alarm: 'linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)',
        reminder: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
    };

    n.style.cssText = `
        position: fixed; top: 20px; right: 20px; padding: 16px 24px;
        background: ${colors[type] || colors.info}; color: #fff;
        border-radius: var(--radius-md); box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        z-index: 10000; animation: slideInRight 0.3s ease;
        font-weight: 600; max-width: 400px;
    `;
    document.body.appendChild(n);
    setTimeout(() => {
        n.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => n.remove(), 300);
    }, 4000);
}

function saveToLocalStorage() {
    localStorage.setItem('alarms', JSON.stringify(alarms));
    localStorage.setItem('reminders', JSON.stringify(reminders));
}

function loadFromLocalStorage() {
    const sa = localStorage.getItem('alarms');
    const sr = localStorage.getItem('reminders');
    if (sa) alarms = JSON.parse(sa);
    if (sr) reminders = JSON.parse(sr);
}

function sendBrowserNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body, icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%236366f1"><circle cx="12" cy="13" r="7"/></svg>' });
    }
}
