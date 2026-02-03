# Alarm Clock & Reminder App Frontend

A beautiful, modern web-based alarm clock and reminder application with a premium dark theme design.

## Features

### ⏰ Alarms
- Set multiple alarms with custom times
- Add custom labels to alarms
- Repeat alarms on specific days of the week
- Toggle alarms on/off without deleting them
- One-time or recurring alarms
- Visual time display with AM/PM format

### 🔔 Reminders
- Create reminders with title, date, and time
- Add optional notes to reminders
- Mark reminders as complete
- Automatic sorting by date and time
- Visual completion status

### 🎨 Design Features
- **Premium Dark Theme** with glassmorphism effects
- **Smooth Animations** and micro-interactions
- **Gradient Accents** for a modern look
- **Responsive Design** - works on desktop, tablet, and mobile
- **Real-time Clock** display with date
- **Browser Notifications** support (optional)

## How to Use

### Running the App

1. **Simple Method**: Just open `index.html` in your web browser
   ```bash
   open index.html
   ```

2. **Local Server Method** (recommended for best experience):
   ```bash
   # Using Python 3
   python3 -m http.server 8000
   
   # Or using Python 2
   python -m SimpleHTTPServer 8000
   
   # Then open http://localhost:8000 in your browser
   ```

### Setting an Alarm

1. Click the **"Add Alarm"** button
2. Set the time using the time picker
3. (Optional) Add a custom label
4. (Optional) Select days for recurring alarms
5. Click **"Save Alarm"**

### Creating a Reminder

1. Switch to the **"Reminders"** tab
2. Click **"Add Reminder"**
3. Enter a title for your reminder
4. Set the date and time
5. (Optional) Add notes
6. Click **"Save Reminder"**

### Managing Items

- **Toggle Alarms**: Use the switch to enable/disable alarms
- **Complete Reminders**: Click the checkmark icon
- **Delete Items**: Click the trash icon
- **Edit**: Delete and recreate (edit functionality can be added)

## Data Persistence

All alarms and reminders are automatically saved to your browser's local storage, so they persist even after closing the browser.

## Browser Compatibility

Works best on modern browsers:
- Chrome/Edge (recommended)
- Firefox
- Safari
- Opera

## Technical Stack

- **HTML5** - Semantic structure
- **CSS3** - Modern styling with custom properties
- **Vanilla JavaScript** - No dependencies required
- **Local Storage API** - Data persistence
- **Notifications API** - Browser notifications (optional)

## Customization

You can easily customize the color scheme by editing the CSS variables in `styles.css`:

```css
:root {
    --accent-primary: #6366f1;  /* Primary accent color */
    --accent-secondary: #8b5cf6; /* Secondary accent color */
    /* ... other variables */
}
```

## Future Enhancements

Potential features to add:
- Sound/ringtone selection for alarms
- Snooze functionality
- Edit existing alarms/reminders
- Export/import data
- Multiple alarm sounds
- Integration with the C backend alarm system
- Dark/light theme toggle
- Calendar view for reminders

## Integration with Backend

This frontend can be integrated with your C-based alarm system (`/src/main.c`) by:
1. Creating a simple HTTP server in C or using a middleware
2. Exposing REST API endpoints for alarm management
3. Using WebSockets for real-time alarm triggers
4. Or using Electron to create a desktop app that interfaces with the C code

## License

Free to use and modify for your project.

---

Enjoy your beautiful alarm clock and reminder app! ⏰✨
