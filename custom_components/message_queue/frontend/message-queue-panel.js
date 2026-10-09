class MessageQueuePanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._initialized = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._render();
      this._initialized = true;
    }
    this._updateQueueList();
  }

  _getQueues() {
    if (!this._hass) return [];
    const states = this._hass.states;
    return Object.keys(states)
      .filter((id) => id.startsWith("sensor.message_queue_"))
      .map((id) => {
        const name = id.replace("sensor.message_queue_", "");
        const state = states[id];
        return {
          id,
          name,
          message: state.state || "",
          expires_at: state.attributes.expires_at || null,
          queue_length: state.attributes.queue_length || 0,
        };
      });
  }

  _updateQueueList() {
    const queues = this._getQueues();
    const select = this.querySelector("#queueSelect");
    const checkboxes = this.querySelector("#queueCheckboxes");
    const statusList = this.querySelector("#queueStatus");

    if (!select) return;

    // Update single queue dropdown
    const currentValue = select.value;
    select.innerHTML = queues
      .map((q) => `<option value="${q.name}">${q.name}</option>`)
      .join("");
    if (currentValue && queues.some((q) => q.name === currentValue)) {
      select.value = currentValue;
    }

    // Update multiple queue checkboxes
    if (checkboxes) {
      checkboxes.innerHTML = queues
        .map(
          (q) => `
        <label class="checkbox-item">
          <input type="checkbox" name="queue_cb" value="${q.name}">
          <span>${q.name}</span>
        </label>`
        )
        .join("");
    }

    // Update status display
    if (statusList) {
      if (queues.length === 0) {
        statusList.innerHTML =
          '<p class="empty">No queues configured. Add queues in Settings &gt; Devices &amp; Services &gt; Message Queue &gt; Configure.</p>';
      } else {
        statusList.innerHTML = queues
          .map(
            (q) => `
          <div class="status-item">
            <div class="status-name">${q.name}</div>
            <div class="status-message">${q.message || '<span class="empty-msg">empty</span>'}</div>
            <div class="status-meta">${q.queue_length} message${q.queue_length !== 1 ? "s" : ""}${q.expires_at ? " \u00b7 expires " + new Date(q.expires_at).toLocaleTimeString() : ""}</div>
          </div>`
          )
          .join("");
      }
    }
  }

  async _sendMessage(e) {
    e.preventDefault();
    const form = this.querySelector("#messageForm");
    const status = this.querySelector("#statusMsg");
    const message = this.querySelector("#message").value;
    const sendTo = this.querySelector('input[name="sendTo"]:checked').value;
    const expType = this.querySelector(
      'input[name="expirationType"]:checked'
    ).value;

    const data = { message };

    if (expType === "seconds") {
      data.show_seconds = parseInt(this.querySelector("#showSeconds").value);
    } else {
      const dt = this.querySelector("#showUntil").value;
      if (dt) data.show_until = new Date(dt).toISOString();
    }

    let service;
    if (sendTo === "single") {
      service = "push_message";
      data.queue = this.querySelector("#queueSelect").value;
    } else if (sendTo === "multiple") {
      service = "push_message_to_multiple";
      data.queues = Array.from(
        this.querySelectorAll('input[name="queue_cb"]:checked')
      ).map((cb) => cb.value);
      if (data.queues.length === 0) {
        this._showStatus("Select at least one queue.", "error");
        return;
      }
    } else {
      service = "push_message_to_all";
    }

    try {
      await this._hass.callService("message_queue", service, data);
      this._showStatus("Message sent.", "success");
      this.querySelector("#message").value = "";
    } catch (err) {
      this._showStatus("Error: " + err.message, "error");
    }
  }

  async _clearQueue() {
    const queue = this.querySelector("#queueSelect").value;
    if (!queue) return;
    try {
      await this._hass.callService("message_queue", "clear_queue", { queue });
      this._showStatus(`Queue "${queue}" cleared.`, "success");
    } catch (err) {
      this._showStatus("Error: " + err.message, "error");
    }
  }

  _showStatus(msg, type) {
    const el = this.querySelector("#statusMsg");
    el.textContent = msg;
    el.className = "status-msg " + type;
    if (type === "success") {
      setTimeout(() => {
        el.className = "status-msg";
      }, 4000);
    }
  }

  _updateVisibility() {
    const sendTo = this.querySelector('input[name="sendTo"]:checked').value;
    this.querySelector("#singleGroup").style.display =
      sendTo === "single" ? "" : "none";
    this.querySelector("#multipleGroup").style.display =
      sendTo === "multiple" ? "" : "none";

    const expType = this.querySelector(
      'input[name="expirationType"]:checked'
    ).value;
    this.querySelector("#secondsField").style.display =
      expType === "seconds" ? "" : "none";
    this.querySelector("#untilField").style.display =
      expType === "until" ? "" : "none";
  }

  _render() {
    this.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 16px;
          max-width: 600px;
          margin: 0 auto;
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
          color: var(--primary-text-color, #212121);
        }
        h1 { font-size: 24px; margin: 0 0 4px; }
        .subtitle { color: var(--secondary-text-color, #727272); margin-bottom: 20px; font-size: 14px; }
        .card {
          background: var(--card-background-color, #fff);
          border-radius: 8px;
          padding: 20px;
          margin-bottom: 16px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,.1));
        }
        .card h2 { font-size: 16px; margin: 0 0 12px; }
        label { display: block; font-size: 14px; font-weight: 500; margin-bottom: 6px; }
        textarea, input[type="text"], input[type="number"], input[type="datetime-local"], select {
          width: 100%; padding: 8px 10px; border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px; font-size: 14px; font-family: inherit;
          background: var(--card-background-color, #fff); color: var(--primary-text-color, #212121);
          box-sizing: border-box;
        }
        textarea { min-height: 80px; resize: vertical; }
        textarea:focus, input:focus, select:focus { outline: none; border-color: var(--primary-color, #03a9f4); }
        .form-group { margin-bottom: 16px; }
        .radio-group { display: flex; gap: 16px; flex-wrap: wrap; }
        .radio-option { display: flex; align-items: center; gap: 6px; cursor: pointer; }
        .radio-option label { margin: 0; font-weight: normal; cursor: pointer; }
        .exp-box { background: var(--secondary-background-color, #f5f5f5); padding: 12px; border-radius: 4px; margin-top: 8px; }
        .help { font-size: 12px; color: var(--secondary-text-color, #727272); margin-top: 4px; }
        .btn-row { display: flex; gap: 10px; margin-top: 20px; }
        button {
          padding: 10px 20px; border: none; border-radius: 4px; font-size: 14px;
          font-weight: 500; cursor: pointer;
        }
        .btn-primary { background: var(--primary-color, #03a9f4); color: #fff; flex: 1; }
        .btn-primary:hover { opacity: 0.9; }
        .btn-secondary { background: var(--secondary-background-color, #f5f5f5); color: var(--primary-text-color, #212121); }
        .btn-secondary:hover { background: var(--divider-color, #e0e0e0); }
        .status-msg { padding: 10px; border-radius: 4px; margin-bottom: 12px; font-size: 14px; display: none; }
        .status-msg.success { display: block; background: #d4edda; color: #155724; }
        .status-msg.error { display: block; background: #f8d7da; color: #721c24; }
        .checkbox-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; cursor: pointer; }
        .checkbox-item span { font-weight: normal; }
        .status-item {
          padding: 10px; border-radius: 4px; margin-bottom: 8px;
          background: var(--secondary-background-color, #f5f5f5);
        }
        .status-name { font-weight: 500; font-size: 14px; }
        .status-message { font-size: 13px; margin: 4px 0; word-break: break-word; }
        .status-meta { font-size: 12px; color: var(--secondary-text-color, #727272); }
        .empty-msg { font-style: italic; color: var(--secondary-text-color, #727272); }
        .empty { color: var(--secondary-text-color, #727272); font-size: 13px; font-style: italic; }
      </style>

      <h1>Messages</h1>
      <p class="subtitle">Send messages to your display queues</p>

      <div id="statusMsg" class="status-msg"></div>

      <div class="card">
        <h2>Send Message</h2>
        <form id="messageForm">
          <div class="form-group">
            <label for="message">Message</label>
            <textarea id="message" placeholder="Enter your message..." required></textarea>
          </div>

          <div class="form-group">
            <label>Send to</label>
            <div class="radio-group">
              <div class="radio-option">
                <input type="radio" id="sendSingle" name="sendTo" value="single" checked>
                <label for="sendSingle">Single queue</label>
              </div>
              <div class="radio-option">
                <input type="radio" id="sendMultiple" name="sendTo" value="multiple">
                <label for="sendMultiple">Multiple queues</label>
              </div>
              <div class="radio-option">
                <input type="radio" id="sendAll" name="sendTo" value="all">
                <label for="sendAll">All queues</label>
              </div>
            </div>
          </div>

          <div class="form-group" id="singleGroup">
            <label for="queueSelect">Queue</label>
            <select id="queueSelect"></select>
          </div>

          <div class="form-group" id="multipleGroup" style="display:none">
            <label>Select queues</label>
            <div id="queueCheckboxes"></div>
          </div>

          <div class="form-group">
            <label>Expiration</label>
            <div class="radio-group">
              <div class="radio-option">
                <input type="radio" id="expSeconds" name="expirationType" value="seconds" checked>
                <label for="expSeconds">Duration</label>
              </div>
              <div class="radio-option">
                <input type="radio" id="expUntil" name="expirationType" value="until">
                <label for="expUntil">Show until</label>
              </div>
            </div>
          </div>

          <div class="exp-box">
            <div id="secondsField">
              <label for="showSeconds">Duration (seconds)</label>
              <input type="number" id="showSeconds" value="300" min="1">
              <div class="help">Default: 300 seconds (5 minutes)</div>
            </div>
            <div id="untilField" style="display:none">
              <label for="showUntil">Show until</label>
              <input type="datetime-local" id="showUntil">
              <div class="help">Message disappears at this time</div>
            </div>
          </div>

          <div class="btn-row">
            <button type="submit" class="btn-primary">Send Message</button>
            <button type="button" class="btn-secondary" id="clearBtn">Clear Queue</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h2>Queue Status</h2>
        <div id="queueStatus"></div>
      </div>
    `;

    // Bind events
    this.querySelector("#messageForm").addEventListener("submit", (e) =>
      this._sendMessage(e)
    );
    this.querySelector("#clearBtn").addEventListener("click", () =>
      this._clearQueue()
    );
    this.querySelectorAll('input[name="sendTo"]').forEach((r) =>
      r.addEventListener("change", () => this._updateVisibility())
    );
    this.querySelectorAll('input[name="expirationType"]').forEach((r) =>
      r.addEventListener("change", () => this._updateVisibility())
    );

    this._updateVisibility();
    this._updateQueueList();
  }
}

customElements.define("message-queue-panel", MessageQueuePanel);
