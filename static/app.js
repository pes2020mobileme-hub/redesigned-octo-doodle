(function () {
  "use strict";

  var templatesEl = document.getElementById("templates-data");
  var TEMPLATES = templatesEl ? JSON.parse(templatesEl.textContent || "[]") : [];

  var $ = function (sel) { return document.querySelector(sel); };

  function esc(str) {
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function nameIcon(name) {
    var m = String(name || "").match(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u);
    return m ? m[0] : "📁";
  }

  var running = false;
  var currentFilter = "";
  var roomData = { categories: [], loaded: false };

  /* ---------------- server select ---------------- */

  function setGuildHint(text) {
    var el = $("#guild-hint");
    if (el) el.textContent = text;
  }

  function selectedGuild() {
    return $("#guild-id").value.trim();
  }

  function guildInvalid() {
    var g = selectedGuild();
    if (!/^\d{17,20}$/.test(g)) {
      toast("⚠️ ยังไม่ได้เลือกเซิร์ฟเวอร์ กดเริ่ม Bot + เชิญบอทก่อน", "error");
      return true;
    }
    return false;
  }

  async function loadServers() {
    try {
      var res = await fetch("/api/status");
      var data = await res.json();
      var sel = $("#guild-id");
      var cur = sel.value;
      sel.innerHTML = '<option value="">— เลือกเซิร์ฟเวอร์ —</option>';
      var guilds = data.guilds || [];
      guilds.forEach(function (g) {
        var o = document.createElement("option");
        o.value = g.id;
        o.textContent = "🖥️ " + g.name;
        sel.appendChild(o);
      });
      var keep = cur && guilds.some(function (g) { return g.id === cur; });
      if (keep) sel.value = cur;

      var invite = $("#btn-invite");
      if (data.invite_url) {
        invite.href = data.invite_url;
        invite.style.display = "";
      } else {
        invite.style.display = "none";
      }

      if (data.online) {
        if (!guilds.length) {
          setGuildHint("บอทออนแล้ว — กด \"➕ เชิญบอท\" เลือกเซิร์ฟเวอร์ แล้วกด ▶ เริ่มสร้าง");
        } else {
          setGuildHint("เลือกเซิร์ฟเวอร์ แล้วกด \"⚡ สร้างเลย\" บน Template ที่ต้องการ");
        }
      } else {
        setGuildHint("กด \"▶ เริ่ม Bot\" ก่อน แล้วรายชื่อเซิร์ฟเวอร์จะโผล่ที่นี่อัตโนมัติ");
      }
    } catch (e) {}
  }

  /* ---------------- rooms (delete) ---------------- */

  function roomChecked() {
    var box = $("#room-list");
    var category_ids = [];
    var channel_ids = [];
    [].slice.call(box.querySelectorAll('input[data-room="cat"]:checked')).forEach(function (el) {
      category_ids.push(el.dataset.id);
    });
    [].slice.call(box.querySelectorAll('input[data-room="ch"]:checked')).forEach(function (el) {
      channel_ids.push(el.dataset.id);
    });
    return { category_ids: category_ids, channel_ids: channel_ids };
  }

  function roomsTotal() {
    return roomData.categories.reduce(function (n, c) { return n + 1 + c.channels.length; }, 0);
  }

  function updateRoomButtons() {
    var sel = roomChecked();
    var total = sel.category_ids.length + sel.channel_ids.length;
    $("#btn-delete-rooms").disabled = !total || running;
    $("#btn-delete-all").disabled = !roomData.loaded || !roomData.categories.length || running;
    var countEl = $("#room-count");
    countEl.textContent = roomData.loaded
      ? "ทั้งหมด " + roomsTotal() + " ห้อง · เลือก " + total + " ห้อง"
      : "";
  }

  function renderRooms() {
    var box = $("#room-list");
    box.innerHTML = "";
    if (!roomData.loaded) {
      box.innerHTML = '<div class="room-empty">เลือกเซิร์ฟเวอร์ด้านบน แล้วกด "📂 โหลดห้องที่มีอยู่" เพื่อดูรายการ</div>';
      $("#chk-select-all").checked = false;
      updateRoomButtons();
      return;
    }
    if (!roomData.categories.length) {
      box.innerHTML = '<div class="room-empty">ไม่พบ Category ในเซิร์ฟเวอร์นี้ (หรือเซิร์ฟเวอร์ว่าง)</div>';
      $("#chk-select-all").checked = false;
      updateRoomButtons();
      return;
    }
    roomData.categories.forEach(function (cat) {
      var wrap = document.createElement("div");
      wrap.className = "room-cat";
      wrap.innerHTML =
        '<div class="room-cat-head">' +
        '<input type="checkbox" data-room="cat" data-id="' + esc(cat.id) + '">' +
        '<span>📁 ' + esc(cat.name) + '</span>' +
        '<span class="room-count-badge">' + cat.channels.length + ' ช่อง</span>' +
        '<button class="icon-btn del-room" data-kind="cat" data-id="' + esc(cat.id) + '" title="ลบ Category นี้">🗑️</button>' +
        "</div>";
      var chBox = document.createElement("div");
      chBox.className = "room-channels";
      (cat.channels || []).forEach(function (ch) {
        var icon = ch.type === "voice" ? "🔊" : "💬";
        var prefix = ch.type === "voice" ? "" : "#";
        var row = document.createElement("div");
        row.className = "room-ch";
        row.innerHTML =
          '<input type="checkbox" data-room="ch" data-id="' + esc(ch.id) + '">' +
          "<span>" + icon + " " + prefix + esc(ch.name) + "</span>" +
          '<button class="icon-btn del-room" data-kind="ch" data-id="' + esc(ch.id) + '" title="ลบ Channel นี้">🗑️</button>';
        chBox.appendChild(row);
      });
      wrap.appendChild(chBox);
      box.appendChild(wrap);
    });
    $("#chk-select-all").checked = false;
    updateRoomButtons();
  }

  async function loadRooms() {
    if (guildInvalid()) return;
    var btn = $("#btn-load-rooms");
    btn.disabled = true;
    btn.textContent = "⏳ กำลังโหลด...";
    try {
      var res = await fetch("/api/guild-structure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ guild_id: selectedGuild() })
      });
      var data = await res.json();
      if (data.success) {
        roomData.categories = data.categories || [];
        roomData.loaded = true;
        renderRooms();
        toast("📂 โหลดรายการห้องแล้ว", "success");
      } else {
        toast("❌ " + (data.error || "โหลดไม่สำเร็จ"), "error");
      }
    } catch (err) {
      toast("❌ ไม่สามารถติดต่อเซิร์ฟเวอร์ได้", "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "📂 โหลดห้องที่มีอยู่";
    }
  }

  async function callDelete(category_ids, channel_ids) {
    var res = await fetch("/api/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ guild_id: selectedGuild(), category_ids: category_ids, channel_ids: channel_ids })
    });
    var data = await res.json();
    if (data.success) {
      toast("🗑️ ลบเสร็จ: " + data.result.categories_deleted + " Category / " + data.result.channels_deleted + " ช่อง", "success");
      showLogLine("✅ ลบ Category " + data.result.categories_deleted + " · 💬 ลบ Channel " + data.result.channels_deleted, "success");
      roomData.categories = [];
      roomData.loaded = false;
      renderRooms();
      loadRooms();
    } else {
      toast("❌ " + (data.error || "ลบไม่สำเร็จ"), "error");
    }
  }

  async function deleteRooms() {
    var sel = roomChecked();
    var total = sel.category_ids.length + sel.channel_ids.length;
    if (!total) {
      toast("⚠️ ยังไม่ได้เลือกห้อง", "error");
      return;
    }
    if (!confirm("⚠️ ยืนยันจะลบ " + total + " ห้อง?\nCategory ที่ลบจะลบช่องข้างในไปด้วย (ทำแล้วย้อนกลับไม่ได้)")) return;
    if (running) return;
    running = true;
    updateRoomButtons();
    var btn = $("#btn-delete-rooms");
    btn.disabled = true;
    btn.textContent = "🗑️ กำลังลบ...";
    try {
      await callDelete(sel.category_ids, sel.channel_ids);
    } catch (err) {
      toast("❌ ไม่สามารถติดต่อเซิร์ฟเวอร์ได้", "error");
    } finally {
      running = false;
      btn.disabled = false;
      btn.textContent = "🗑️ ลบที่เลือก";
      updateRoomButtons();
    }
  }

  async function deleteOneRoom(category_ids, channel_ids) {
    if (running) return;
    running = true;
    updateRoomButtons();
    try {
      await callDelete(category_ids, channel_ids);
    } catch (err) {
      toast("❌ ไม่สามารถติดต่อเซิร์ฟเวอร์ได้", "error");
    } finally {
      running = false;
      updateRoomButtons();
    }
  }

  async function deleteAllRooms() {
    if (running) return;
    var allCatIds = roomData.categories.map(function (c) { return c.id; });
    if (!allCatIds.length) {
      toast("⚠️ ไม่มีห้องให้ลบ", "error");
      return;
    }
    if (!confirm("⚠️ ยืนยันลบ ทั้งหมด " + allCatIds.length + " Categories และทุกช่องในเซิร์ฟเวอร์?\nทำแล้วย้อนกลับไม่ได้!")) return;
    running = true;
    updateRoomButtons();
    var btn = $("#btn-delete-all");
    btn.disabled = true;
    btn.textContent = "🗑️ กำลังลบ...";
    try {
      await callDelete(allCatIds, []);
    } catch (err) {
      toast("❌ ไม่สามารถติดต่อเซิร์ฟเวอร์ได้", "error");
    } finally {
      running = false;
      btn.disabled = false;
      btn.textContent = "🗑️ ลบทั้งหมด";
      updateRoomButtons();
    }
  }

  function onRoomListClick(e) {
    var btn = e.target.closest(".del-room");
    if (!btn) return;
    var ids = [btn.dataset.id];
    var kind = btn.dataset.kind === "cat" ? "cat" : "ch";
    var label = kind === "cat" ? "Category" : "Channel";
    if (!confirm("🗑️ ยืนยันลบ " + label + " นี้? (ทำแล้วย้อนกลับไม่ได้)")) return;
    deleteOneRoom(kind === "cat" ? ids : [], kind === "ch" ? ids : []);
  }

  /* ---------------- templates ---------------- */

  function renderTemplates() {
    var grid = $("#template-grid");
    grid.innerHTML = "";
    TEMPLATES.forEach(function (t) {
      var tw = t.categories || [];
      var totalCh = tw.reduce(function (n, c) { return n + (c.channels ? c.channels.length : 0); }, 0);
      var card = document.createElement("div");
      card.className = "tpl-card";
      card.dataset.id = t.id;
      card.dataset.name = (t.name || "").toLowerCase();
      card.dataset.filter = (t.category || "").toLowerCase();
      card.innerHTML =
        '<div class="tpl-icon">' + nameIcon(t.name) + "</div>" +
        '<div class="tpl-name">' + esc(t.name) + "</div>" +
        '<div class="tpl-desc">' + esc(t.description || "") + "</div>" +
        '<div class="tpl-meta"><span>📁 ' + tw.length + " Categories</span><span>💬 " + totalCh + " Channels</span></div>" +
        '<div class="tpl-actions">' +
        '<button class="btn btn-ghost" data-act="preview">👁 Preview</button>' +
        '<button class="btn btn-primary" data-act="build">⚡ สร้างเลย</button>' +
        "</div>";
      grid.appendChild(card);
    });
  }

  function renderPills() {
    var cats = [];
    TEMPLATES.forEach(function (t) {
      var c = (t.category || "").trim();
      if (c && cats.indexOf(c) === -1) cats.push(c);
    });
    var box = $("#filter-pills");
    box.innerHTML = "";
    var add = function (label, key) {
      var b = document.createElement("button");
      b.className = "pill" + (key === currentFilter ? " active" : "");
      b.textContent = label;
      b.dataset.filter = key;
      box.appendChild(b);
    };
    add("ทั้งหมด", "");
    cats.forEach(function (c) { add(c, c.toLowerCase()); });
  }

  function applyFilter() {
    var q = $("#search").value.trim().toLowerCase();
    document.querySelectorAll(".tpl-card").forEach(function (card) {
      var okFilter = !currentFilter || card.dataset.filter === currentFilter;
      var okName = !q || card.dataset.name.indexOf(q) !== -1;
      card.style.display = okFilter && okName ? "" : "none";
    });
  }

  function showTemplatePreview(t) {
    var tw = t.categories || [];
    var totalCh = tw.reduce(function (n, c) { return n + (c.channels ? c.channels.length : 0); }, 0);
    var html =
      '<div class="pv-server">🧩 ' + esc(t.name) +
      ' <span class="pv-sub">' + esc(t.description || "") + "</span></div>" +
      '<div class="pv-total">📁 ' + tw.length + " Categories · 💬 " + totalCh + " Channels</div>";
    tw.forEach(function (cat) {
      html += '<details class="pv-cat" open><summary>📁 ' + esc(cat.name) + "</summary>";
      (cat.channels || []).forEach(function (ch) {
        var icon = ch.type === "voice" ? "🔊" : "💬";
        var prefix = ch.type === "voice" ? "" : "#";
        html += '<div class="pv-ch">' + icon + " " + prefix + esc(ch.name);
        if (ch.type !== "voice" && ch.message) html += ' <span class="badge b-blue">📨 ข้อความ</span>';
        if (ch.embed && ch.embed.enabled) html += ' <span class="badge b-purple">🎨 Embed</span>';
        html += "</div>";
      });
      html += "</details>";
    });
    $("#modal-title").textContent = "👁️ " + (t.name || "Preview Template");
    $("#modal-body").innerHTML = html;
    $("#btn-preview-build").dataset.template = t.id;
    $("#modal").classList.add("open");
  }

  /* ---------------- build: one click ---------------- */

  async function buildTemplate(t) {
    if (running) return;
    if (guildInvalid()) return;
    running = true;
    var btn = $("#btn-preview-build");
    if (btn) btn.disabled = true;
    $("#modal").classList.remove("open");
    toast('🚀 กำลังสร้าง Template "' + esc(t.name) + '"...', "info");
    try {
      var res = await fetch("/api/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ guild_id: selectedGuild(), template_id: t.id })
      });
      var data = await res.json();
      if (data.success) {
        toast("🎉 สร้างเสร็จทั้งหมด", "success");
        showResult(data.result);
      } else {
        toast("❌ " + (data.error || "เกิดข้อผิดพลาด"), "error");
        showLogLine("❌ " + (data.error || "เกิดข้อผิดพลาด"), "error");
      }
    } catch (err) {
      toast("❌ ไม่สามารถติดต่อเซิร์ฟเวอร์ได้", "error");
    } finally {
      running = false;
      if (btn) btn.disabled = false;
    }
  }

  function showResult(result) {
    if (!result) return;
    var parts = [];
    parts.push("📁 Category " + result.categories_created + "/" + result.categories_reused);
    parts.push("💬 Channel " + result.channels_created + "/" + result.channels_reused);
    if (result.messages_sent) parts.push("📨 ข้อความ " + result.messages_sent);
    if (result.embeds_sent) parts.push("🎨 Embed " + result.embeds_sent);
    if (result.roles_created) parts.push("🎭 Role " + result.roles_created + "/" + result.roles_reused);
    if (result.role_button_msgs) parts.push("🔘 ปุ่ม " + result.role_button_msgs);
    if (result.tickets_setup) parts.push("🎫 Ticket " + result.tickets_setup);
    showLogLine("✅ สร้างเสร็จ: " + parts.join(" · "), "success");
  }

  function showLogLine(msg, type) {
    var box = $("#log");
    var line = document.createElement("div");
    line.className = "log-line " + (type || "info");
    line.innerHTML = '<span class="log-time">--:--:--</span><span class="log-msg">' + esc(msg) + "</span>";
    box.appendChild(line);
    box.scrollTop = box.scrollHeight;
  }

  /* ---------------- misc ---------------- */

  function toast(msg, type) {
    var box = $("#toast");
    var el = document.createElement("div");
    el.className = "toast " + (type || "info");
    el.innerHTML = msg;
    box.appendChild(el);
    setTimeout(function () { el.classList.add("show"); }, 10);
    setTimeout(function () {
      el.classList.remove("show");
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 300);
    }, 3500);
  }

  function connectLogs() {
    var box = $("#log");
    if (!window.EventSource) return;
    var es = new EventSource("/api/logs");
    es.onmessage = function (ev) {
      var entry = null;
      try {
        entry = JSON.parse(ev.data);
      } catch (e) {
        entry = { message: ev.data };
      }
      var type = entry.type === "error" ? "error" : (entry.type === "success" ? "success" : "info");
      var line = document.createElement("div");
      line.className = "log-line " + type;
      line.innerHTML =
        '<span class="log-time">' + esc(entry.timestamp || "--:--:--") + "</span>" +
        '<span class="log-msg">' + esc(entry.message || "") + "</span>";
      box.appendChild(line);
      box.scrollTop = box.scrollHeight;
    };
  }

  async function refreshStatus() {
    try {
      var res = await fetch("/api/status");
      var data = await res.json();
      var on = !!data.online;
      var dot = $("#status-dot");
      dot.className = "status-dot " + (on ? "on" : "off");
      $("#status-text").textContent = on ? "Bot Online" : "Bot Offline";
      var btn = $("#btn-start");
      if (on) {
        btn.disabled = true;
        btn.textContent = "✅ Bot Online";
      } else {
        btn.disabled = false;
        btn.textContent = "▶ เริ่ม Bot";
      }
      return data;
    } catch (e) { return null; }
  }

  async function startBot() {
    var btn = $("#btn-start");
    if (btn.disabled) return;
    btn.disabled = true;
    btn.textContent = "⏳ กำลังเริ่ม...";
    try {
      var res = await fetch("/api/start", { method: "POST" });
      var data = await res.json();
      if (data.success) {
        toast(data.message ? "ℹ️ " + data.message : "🤖 กำลังเริ่ม Bot", "info");
      } else {
        toast("❌ " + (data.error || "เริ่ม Bot ไม่สำเร็จ"), "error");
        btn.disabled = false;
        btn.textContent = "▶ เริ่ม Bot";
      }
    } catch (e) {
      toast("❌ ไม่สามารถเริ่ม Bot ได้", "error");
      btn.disabled = false;
      btn.textContent = "▶ เริ่ม Bot";
    }
    setTimeout(refreshAndServers, 3000);
  }

  async function refreshAndServers() {
    await refreshStatus();
    loadServers();
  }

  function wire() {
    $("#btn-start").addEventListener("click", startBot);
    $("#btn-refresh-guilds").addEventListener("click", loadServers);
    $("#btn-load-rooms").addEventListener("click", loadRooms);
    $("#btn-delete-rooms").addEventListener("click", deleteRooms);
    $("#btn-delete-all").addEventListener("click", deleteAllRooms);
    $("#room-list").addEventListener("change", updateRoomButtons);
    $("#room-list").addEventListener("click", onRoomListClick);
    $("#chk-select-all").addEventListener("change", function () {
      var on = this.checked;
      $("#room-list").querySelectorAll('input[data-room="cat"], input[data-room="ch"]').forEach(function (el) {
        el.checked = on;
      });
      updateRoomButtons();
    });
    $("#guild-id").addEventListener("change", function () {
      roomData.categories = [];
      roomData.loaded = false;
      renderRooms();
    });

    $("#search").addEventListener("input", applyFilter);
    $("#filter-pills").addEventListener("click", function (e) {
      var b = e.target.closest(".pill");
      if (!b) return;
      currentFilter = b.dataset.filter || "";
      renderPills();
      applyFilter();
    });

    $("#template-grid").addEventListener("click", function (e) {
      var btn = e.target.closest("button");
      if (!btn) return;
      var card = btn.closest(".tpl-card");
      if (!card) return;
      var t = TEMPLATES.find(function (x) { return x.id === card.dataset.id; });
      if (!t) return;
      if (btn.dataset.act === "preview") {
        showTemplatePreview(t);
      } else if (btn.dataset.act === "build") {
        if (guildInvalid()) return;
        if (confirm('⚡ สร้าง Template "' + esc(t.name) + '" ลงเซิร์ฟเวอร์ที่เลือกทันที?')) {
          buildTemplate(t);
        }
      }
    });

    $("#btn-preview-build").addEventListener("click", function () {
      var tid = this.dataset.template;
      var t = TEMPLATES.find(function (x) { return x.id === tid; });
      if (!t) return;
      if (confirm('⚡ สร้าง Template "' + esc(t.name) + '" ลงเซิร์ฟเวอร์ที่เลือกทันที?')) {
        buildTemplate(t);
      }
    });

    $("#modal").addEventListener("click", function (e) {
      if (e.target.closest("[data-close]")) {
        $("#modal").classList.remove("open");
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") $("#modal").classList.remove("open");
    });
  }

  renderTemplates();
  renderPills();
  connectLogs();
  wire();
  refreshAndServers();
  setInterval(refreshAndServers, 5000);
})();