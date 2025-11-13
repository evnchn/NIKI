## Automated Photo Session Flowchart

### 1. START AND DETECTION

This phase focuses on initializing the environment and detecting user presence.

1.  **Start:** Niki idle and scanning environment.
2.  **Decision:** Detect presence?
    *   **No:** --> Keep scanning (Loop).
    *   **Yes:** --> Proceed to **GREETING AND ENGAGEMENT**.
    *   *(Note: A path labeled "No after second prompt" also leads to Greeting, suggesting a secondary check or timeout mechanism before proceeding if presence isn't immediately confirmed.)*

### 2. GREETING AND ENGAGEMENT

This phase involves initial interaction and securing user consent/acknowledgment.

1.  **Step:** Greeting.
2.  **Step:** Niki scans faces.
3.  **Step:** Niki says hello and prompts.
4.  **Step:** Show screen prompt.
5.  **Decision:** Engagement received?
    *   **Yes:** --> Proceed to **COUNTDOWN AND CAPTURE** (Bypassing further engagement checks).
    *   **No:** --> Decision: Engagement timeout?
        *   **Yes:** --> Prompt again (Loop back to Greeting).
        *   **No:** --> (Implied wait/loop until timeout or engagement is received).

### 3. FRAMING AND PREPARATION

This phase ensures the subjects are correctly positioned and framed for the photo.

1.  **Entry Point:** Framing and preparation.
2.  **Parallel Processes:**
    *   Detect and track faces.
    *   Adjust camera and settings.
    *   Match faces to submitted pictures.
3.  **Decision:** Are all intended people visible?
    *   **No:** --> Prompt to step into view. (If this fails repeatedly, it may trigger **FALLBACKS AND EDGE CASES**).
    *   **Yes:** --> Decision: Manual activation or perfect scene?
        *   **Yes (Manual or perfect):** --> Proceed to **COUNTDOWN AND CAPTURE**.
        *   **No:** --> Loop back to Framing and preparation.

### 4. FALLBACKS AND EDGE CASES

This section handles errors, unrecognized input, or situations requiring intervention.

*   **Triggered by:** Failed presence detection, inability to frame correctly, or audio errors.

| Condition | Action(s) | Potential Outcome |
| :--- | :--- | :--- |
| **No faces detected for long period** | --> Prompt to reposition. | If repositioning is successful (indicated by "Yes (manual or perfect)"), proceed to **COUNTDOWN AND CAPTURE**. |
| | --> Cancel session. | |
| **Audio not understood** | --> Prompt to repeat. | |
| **Printer error or out of paper** | --> Prompt to see staff. | |
| | --> Save photo and end session. | |

### 5. COUNTDOWN AND CAPTURE

This phase handles the actual image acquisition.

1.  **Step:** Countdown.
2.  **Step:** Niki announces countdown.
3.  **Step:** Capture photo 1.
4.  **Step:** Adjust and confirm focus.
5.  **Step:** Capture photo 2.
6.  **Transition:** --> Proceed to **REVIEW AND SELECTION**.

### 6. REVIEW AND SELECTION

Users review the captured images and decide on the final selection or whether to retake them.

1.  **Step:** Display photos for review.
2.  **Step:** Prompt to select favorite.
3.  **Decision:** User selects photo?
    *   **Yes:** --> Proceed to **PRINT AND COMPLETION** (via "Print selected image").
    *   **No or dislikes both:** --> Decision: Redo available?
        *   **Yes (Redo used = 0):** --> Redo prompt.
            *   **Yes:** --> Redo session (Loop back to **COUNTDOWN AND CAPTURE**).
            *   **No (Implied decline):** --> No more redos prompt --> Proceed to **PRINT AND COMPLETION**.
        *   **No (Redo used = 1):** --> No more redos prompt --> Proceed to **PRINT AND COMPLETION**.

### 7. PRINT AND COMPLETION

The final phase handles output and session termination.

1.  **Step:** Print selected image.
2.  **Step:** Printing feedback.
3.  **Step:** Present printed photo.
4.  **Step:** Thank you and goodbye.
5.  **End:** Niki returns to patrol.