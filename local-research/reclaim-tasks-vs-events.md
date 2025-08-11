Querying perplexity using sonar-pro for: How does Reclaim.ai work with tasks and Google Calendar? When you create a task in Reclaim, does it show up as both a task in Reclaim AND an event in Google Calendar? Or does it only become a calendar event after Reclaim schedules it? with maxTokens: 21000
Short answer: A **Reclaim Task** doesn’t appear as a Google Calendar event until Reclaim actually schedules it; once scheduled, it shows up as one or more calendar events representing the task’s time blocks.[4] If you create a task in Google Tasks and have the integration on, Reclaim syncs it into a Reclaim Task first, then schedules it into calendar events per your settings.[2]

Key details:
- Reclaim’s Google Tasks integration is a two‑way sync: items you add in Google Tasks become **Reclaim Tasks**, and Reclaim then auto‑schedules those tasks as events on your Google Calendar according to your preferences.[2]  
- The only required field for a Google Task to sync is the title; that title is used for the Reclaim Task and for the titles of the calendar events Reclaim creates when it schedules the task.[1]  
- Reclaim’s model: tasks are separate from events until scheduling happens. When Reclaim schedules a task, it creates one or more **Task events** on your calendar that you can move, skip, or extend; these events reflect the time blocks for that task.[4]  
- You can manage Reclaim Tasks and their scheduled events directly in Google Calendar using Reclaim’s add‑on (e.g., adjust, complete, or reschedule) without leaving Calendar.[5]  
- You can also add tasks from Google Calendar’s Google Tasks sidebar; Reclaim will sync them and schedule time based on your default task settings if no due date is specified.[2]  

Practical implication:
- Immediately after creating a task in Reclaim (or syncing one from Google Tasks), you’ll see it as a **task in Reclaim**, but you won’t see any calendar entry until Reclaim finds time and places **task events** on your Google Calendar.[4]  
- Once scheduled, those events are standard calendar entries with the task’s title, and they will update as Reclaim reschedules them.[1]