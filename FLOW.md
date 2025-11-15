## Automated Photo Session Flowchart

*This document outlines the high-level flow for Niki's automated photo session. It is designed to be implemented as a state machine or series of functions in `main.py`, with the AI assistant guiding the process via conversations and tool calls.*

### Overall Flow
1. **Start** → 2. **Greeting** → 3. **Framing** → 5. **Capture** → 6. **Review** → 7. **Print**
   - Loops and fallbacks handle errors and retries.
   - AI uses tools for camera assessment and user input waits.

---

### 1. START AND DETECTION
*Initialize and detect user presence. This could be a background loop in the AI system.*

- Niki is idle, scanning for presence.
- **Decision: Presence detected?**
  - Yes → Go to 2. Greeting
  - No → Continue scanning (loop)

*Annotation: Use a sensor or camera detection tool. If no detection after timeout, proceed anyway or alert.*

---

### 2. GREETING AND ENGAGEMENT
*Initial interaction to engage users and get consent.*

- Greet users.
- Scan faces.
- Say hello and prompt for engagement (e.g., "Smile for the camera!").
- Show on-screen prompt.
- **Decision: Engagement received?**
  - Yes → Go to 5. Capture (skip framing if ready)
  - No → **Decision: Timeout?**
    - Yes → Prompt again (loop to greeting)
    - No → Wait (loop)

*Annotation: AI speaks prompts, waits for user input via `wait_for_user_engagement` tool. Engagement could be voice, gesture, or button press. Both user and admin can press Yes/No buttons. In Niki mode, a friendly emoji and message are displayed while waiting.*

---

### 3. FRAMING AND PREPARATION
*Position and frame subjects correctly.*

- Detect and track faces.
- Adjust camera settings.
- Match faces to any submitted pictures (if applicable).
- **Decision: All people visible and framed?**
  - Yes → **Decision: Ready to capture?** (manual trigger or auto-detect perfect scene)
    - Yes → Go to 5. Capture
    - No → Continue framing (loop)
  - No → Prompt to reposition. If repeated failures → Go to 4. Fallbacks

*Annotation: Use `assess_camera_framing` tool to evaluate. Loop until good framing or fallback.*

---

### 4. FALLBACKS AND EDGE CASES
*Handle errors and special cases.*

- **No faces detected (long period):** Prompt reposition or cancel session.
- **Audio not understood:** Prompt to repeat.
- **Printer error/out of paper:** Alert staff or save photo and end.
- After handling, resume flow or end session.

*Annotation: Implement as error handlers in the state machine. May require admin intervention.*

---

### 5. COUNTDOWN AND CAPTURE
*Take the photos.*

- Start countdown.
- Announce countdown.
- Capture photo 1.
- Adjust focus if needed.
- Capture photo 2.
- Go to 6. Review

*Annotation: Camera control functions. Capture multiple shots for selection.*

---

### 6. REVIEW AND SELECTION
*User reviews and selects photo.*

- Display captured photos.
- Prompt to select favorite.
- **Decision: Photo selected?**
  - Yes → Go to 7. Print
  - No → **Decision: Redo available?** (e.g., max 1 redo)
    - Yes → Prompt for redo
      - Yes → Go to 5. Capture
      - No → Go to 7. Print (with default or no photo)
    - No → Go to 7. Print

*Annotation: Use UI for display, `wait_for_user_choose_photo` for selection. Track redo count.*

---

### 7. PRINT AND COMPLETION
*Output and end session.*

- Print selected image.
- Provide feedback during printing.
- Present printed photo.
- Thank user and say goodbye.
- Return to idle (start of flow).

*Annotation: Printer integration. End session, reset state.*

---

*Notes for Implementation:*
- Use a state variable to track current phase.
- AI responses drive the flow via tool calls.
- Handle timeouts, errors, and user inputs gracefully.
- Test each phase separately before integrating.