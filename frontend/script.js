// ==================== //
// State Management
// ==================== //

let alarms = [];
let reminders = [];
let currentTab = 'alarms';

// ==================== //
// Initialize App
// ==================== //

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    loadFromLocalStorage();
    renderAlarms();
    renderReminders();
    startClock();
});

function initializeApp() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Alarm modal controls
    document.getElementById('addAlarmBtn').addEventListener('click', openAlarmModal);
    document.getElementById('closeAlarmModal').addEventListener('click', closeAlarmModal);
    document.getElementById('cancelAlarm').addEventListener('click', closeAlarmModal);
    document.getElementById('saveAlarm').addEventListener('click', saveAlarm);

    // Reminder modal controls
    document.getElementById('addReminderBtn').addEventListener('click', openReminderModal);
    document.getElementById('closeReminderModal').addEventListener('click', closeReminderModal);
    document.getElementById('cancelReminder').addEventListener('click', closeReminderModal);
    document.getElementById('saveReminder').addEventListener('click', saveReminder);

    // Day selector buttons
    document.querySelectorAll('.day-btn').forEach(btn => {
        btn.addEventListener('click', () => btn.classList.toggle('active'));
    });

    // Close modal on outside click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
}

// ==================== //
// Clock Functionality
// ==================== //

function startClock() {
    updateClock();
    setInterval(updateClock, 1000);
    setInterval(checkAlarms, 1000);
    setInterval(checkReminders, 60000); // Check every minute
}

function updateClock() {
    const now = new Date();
    
    // Update time
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    document.getElementById('currentTime').textContent = `${hours}:${minutes}:${seconds}`;
    
    // Update date
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('currentDate').textContent = now.toLocaleDateString('en-US', options);
}

// ==================== //
// Tab Management
// ==================== //

function switchTab(tabName) {
    currentTab = tabName;
    
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}Content`);
    });
}

// ==================== //
// Alarm Functions
// ==================== //

function openAlarmModal() {
    document.getElementById('alarmModal').classList.add('active');
    // Set default time to current time + 1 hour
    const now = new Date();
    now.setHours(now.getHours() + 1);
    const timeString = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    document.getElementById('alarmTime').value = timeString;
}

function closeAlarmModal() {
    document.getElementById('alarmModal').classList.remove('active');
    resetAlarmForm();
}

function resetAlarmForm() {
    document.getElementById('alarmTime').value = '';
    document.getElementById('alarmLabel').value = '';
    document.querySelectorAll('#alarmModal .day-btn').forEach(btn => {
        btn.classList.remove('active');
    });
}

function saveAlarm() {
    const time = document.getElementById('alarmTime').value;
    const label = document.getElementById('alarmLabel').value || 'Alarm';
    
    if (!time) {
        alert('Please set a time for the alarm');
        return;
    }
    
    const selectedDays = Array.from(document.querySelectorAll('#alarmModal .day-btn.active'))
        .map(btn => btn.dataset.day);
    
    const alarm = {
        id: Date.now(),
        time,
        label,
        days: selectedDays,
        enabled: true,
        repeat: selectedDays.length > 0
    };
    
    alarms.push(alarm);
    saveToLocalStorage();
    renderAlarms();
    closeAlarmModal();
    
    // Show success notification
    showNotification('Alarm set successfully!', 'success');
}

function renderAlarms() {
    const alarmsList = document.getElementById('alarmsList');
    
    if (alarms.length === 0) {
        alarmsList.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="13" r="7"></circle>
                    <polyline points="12 10 12 13 14 15"></polyline>
                    <path d="M17 3L19 5"></path>
                    <path d="M5 3L7 5"></path>
                </svg>
                <p>No alarms set</p>
            </div>
        `;
        return;
    }
    
    alarmsList.innerHTML = alarms.map(alarm => `
        <div class="item-card">
            <div class="item-header">
                <div>
                    <div class="item-time">${formatTime(alarm.time)}</div>
                    <div class="item-label">${alarm.label}</div>
                    ${alarm.repeat ? `
                        <div class="item-days">
                            ${['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => `
                                <span class="day-badge ${alarm.days.includes(day) ? 'active' : ''}">${day[0]}</span>
                            `).join('')}
                        </div>
                    ` : '<div class="item-label" style="font-size: 0.875rem; color: var(--text-muted);">One time</div>'}
                </div>
                <div class="item-actions">
                    <div class="toggle-switch ${alarm.enabled ? 'active' : ''}" onclick="toggleAlarm(${alarm.id})"></div>
                    <button class="icon-btn delete" onclick="deleteAlarm(${alarm.id})">
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
    const alarm = alarms.find(a => a.id === id);
    if (alarm) {
        alarm.enabled = !alarm.enabled;
        saveToLocalStorage();
        renderAlarms();
    }
}

function deleteAlarm(id) {
    if (confirm('Are you sure you want to delete this alarm?')) {
        alarms = alarms.filter(a => a.id !== id);
        saveToLocalStorage();
        renderAlarms();
        showNotification('Alarm deleted', 'info');
    }
}

function checkAlarms() {
    const now = new Date();
    const currentTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const currentDay = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][now.getDay()];
    
    alarms.forEach(alarm => {
        if (alarm.enabled && alarm.time === currentTime) {
            if (!alarm.repeat || alarm.days.includes(currentDay)) {
                triggerAlarm(alarm);
            }
        }
    });
}

function triggerAlarm(alarm) {
    // Play alarm sound (you can add actual audio here)
    showNotification(`⏰ ${alarm.label}`, 'alarm');
    
    // Disable one-time alarms after they ring
    if (!alarm.repeat) {
        alarm.enabled = false;
        saveToLocalStorage();
        renderAlarms();
    }
}

// ==================== //
// Reminder Functions
// ==================== //

function openReminderModal() {
    document.getElementById('reminderModal').classList.add('active');
    // Set default date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('reminderDate').value = today;
    // Set default time to current time + 1 hour
    const now = new Date();
    now.setHours(now.getHours() + 1);
    const timeString = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    document.getElementById('reminderTime').value = timeString;
}

function closeReminderModal() {
    document.getElementById('reminderModal').classList.remove('active');
    resetReminderForm();
}

function resetReminderForm() {
    document.getElementById('reminderTitle').value = '';
    document.getElementById('reminderDate').value = '';
    document.getElementById('reminderTime').value = '';
    document.getElementById('reminderNotes').value = '';
}

function saveReminder() {
    const title = document.getElementById('reminderTitle').value;
    const date = document.getElementById('reminderDate').value;
    const time = document.getElementById('reminderTime').value;
    const notes = document.getElementById('reminderNotes').value;
    
    if (!title || !date || !time) {
        alert('Please fill in all required fields');
        return;
    }
    
    const reminder = {
        id: Date.now(),
        title,
        date,
        time,
        notes,
        completed: false
    };
    
    reminders.push(reminder);
    saveToLocalStorage();
    renderReminders();
    closeReminderModal();
    
    showNotification('Reminder created successfully!', 'success');
}

function renderReminders() {
    const remindersList = document.getElementById('remindersList');
    
    if (reminders.length === 0) {
        remindersList.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                    <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
                </svg>
                <p>No reminders yet</p>
            </div>
        `;
        return;
    }
    
    // Sort reminders by date and time
    const sortedReminders = [...reminders].sort((a, b) => {
        const dateA = new Date(`${a.date}T${a.time}`);
        const dateB = new Date(`${b.date}T${b.time}`);
        return dateA - dateB;
    });
    
    remindersList.innerHTML = sortedReminders.map(reminder => `
        <div class="reminder-card ${reminder.completed ? 'completed' : ''}">
            <div class="item-header">
                <div style="flex: 1;">
                    <div class="reminder-title">${reminder.title}</div>
                    <div class="reminder-datetime">
                        📅 ${formatDate(reminder.date)} at ${formatTime(reminder.time)}
                    </div>
                    ${reminder.notes ? `<div class="reminder-notes">${reminder.notes}</div>` : ''}
                </div>
                <div class="item-actions">
                    <button class="icon-btn" onclick="toggleReminder(${reminder.id})" title="${reminder.completed ? 'Mark as incomplete' : 'Mark as complete'}">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            ${reminder.completed ? 
                                '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>' :
                                '<circle cx="12" cy="12" r="10"></circle>'
                            }
                        </svg>
                    </button>
                    <button class="icon-btn delete" onclick="deleteReminder(${reminder.id})">
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
    const reminder = reminders.find(r => r.id === id);
    if (reminder) {
        reminder.completed = !reminder.completed;
        saveToLocalStorage();
        renderReminders();
    }
}

function deleteReminder(id) {
    if (confirm('Are you sure you want to delete this reminder?')) {
        reminders = reminders.filter(r => r.id !== id);
        saveToLocalStorage();
        renderReminders();
        showNotification('Reminder deleted', 'info');
    }
}

function checkReminders() {
    const now = new Date();
    const currentDateTime = `${now.toISOString().split('T')[0]}T${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    
    reminders.forEach(reminder => {
        if (!reminder.completed) {
            const reminderDateTime = `${reminder.date}T${reminder.time}`;
            if (reminderDateTime === currentDateTime) {
                triggerReminder(reminder);
            }
        }
    });
}

function triggerReminder(reminder) {
    showNotification(`🔔 ${reminder.title}`, 'reminder');
}

// ==================== //
// Utility Functions
// ==================== //

function formatTime(time) {
    const [hours, minutes] = time.split(':');
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 || 12;
    return `${displayHour}:${minutes} ${ampm}`;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const options = { month: 'short', day: 'numeric', year: 'numeric' };
    return date.toLocaleDateString('en-US', options);
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: var(--accent-gradient);
        color: var(--text-primary);
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-lg), var(--shadow-glow);
        z-index: 10000;
        animation: slideInRight 0.3s ease;
        font-weight: 600;
        max-width: 300px;
    `;
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add notification animations to CSS dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
    
    .reminder-card.completed {
        opacity: 0.6;
    }
    
    .reminder-card.completed .reminder-title {
        text-decoration: line-through;
    }
`;
document.head.appendChild(style);

// ==================== //
// Local Storage
// ==================== //

function saveToLocalStorage() {
    localStorage.setItem('alarms', JSON.stringify(alarms));
    localStorage.setItem('reminders', JSON.stringify(reminders));
}

function loadFromLocalStorage() {
    const savedAlarms = localStorage.getItem('alarms');
    const savedReminders = localStorage.getItem('reminders');
    
    if (savedAlarms) {
        alarms = JSON.parse(savedAlarms);
    }
    
    if (savedReminders) {
        reminders = JSON.parse(savedReminders);
    }
}

// ==================== //
// Browser Notifications API (Optional Enhancement)
// ==================== //

// Request notification permission on load
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}

function sendBrowserNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, {
            body: body,
            icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%236366f1"><circle cx="12" cy="13" r="7"/></svg>',
            badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%236366f1"><circle cx="12" cy="13" r="7"/></svg>'
        });
    }
}
