// Guest notes (batch 8, Melvin 22 Oct 2026) — a workshop participant adds a
// text note to a species, from the species page or a walk stop. Plain
// multi-line box: type, or dictate with the keyboard's mic (nothing on the box
// blocks dictation — no inputmode / readonly tricks). Saved as an encounter
// (POST /api/encounters: participant user_id + workshop_session_id are set by
// the server; species_id; GPS when the phone gives it). Text only — the server
// refuses audio and photos for participants and never writes species,
// culinary or observation fields. Every note is escaped wherever it is shown.
(function () {
  'use strict';
  const CURATOR_USER_ID = 1;    // = app.models.encounter.CURATOR_USER_ID
  const HINT = 'Type, or dictate using the mic on your keyboard.';
  let _me = null;

  function _h(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function isParticipant() {
    if (!_me) _me = fetch('/api/me').then(r => (r.ok ? r.json() : {})).catch(() => ({}));
    return _me.then(d => d.is_participant === true);
  }

  // A participant's own notes: /api/encounters returns their own plus curator
  // encounters shared with guests; their own are the non-curator rows.
  function isOwnNote(enc) {
    return enc && enc.user_id !== CURATOR_USER_ID && (enc.text_note || '').trim() !== '';
  }

  async function mine() {
    const r = await fetch('/api/encounters');
    if (!r.ok) return [];
    return ((await r.json()).encounters || []).filter(isOwnNote);
  }

  // {species name: [note text, …]} — for Lists / browser print.
  async function mineBySpecies() {
    const out = {};
    for (const e of await mine()) {
      if (!e.species_name) continue;
      (out[e.species_name] = out[e.species_name] || []).push(e.text_note);
    }
    return out;
  }

  async function save(speciesId, text) {
    const t = (text || '').trim();
    if (!t) throw new Error('Write a note first');
    const fd = new FormData();
    fd.append('species_id', String(speciesId));
    fd.append('text_note', t);
    fd.append('encounter_type', 'guest_note');
    fd.append('encounter_date', new Date().toISOString().slice(0, 19));
    fd.append('client_uuid', (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()));
    try {
      if (window.GPS) {
        const p = await Promise.race([GPS.getOnce(), new Promise((_, rej) => setTimeout(() => rej(new Error('gps timeout')), 8000))]);
        if (p && p.lat != null) { fd.append('latitude', String(p.lat)); fd.append('longitude', String(p.lng)); }
      }
    } catch (_) { /* no GPS — the note saves without a location */ }
    const r = await fetch('/api/encounters', { method: 'POST', body: fd });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || ('HTTP ' + r.status));
    return d;
  }

  function listHtml(notes) {
    if (!notes.length) return '';
    return '<div class="guest-notes-list">' + notes.map(n =>
      '<div class="guest-note" style="white-space:pre-wrap;border-left:3px solid #7a9e50;padding:4px 8px;margin:4px 0;' +
      'font-size:0.85rem">' + _h(n.text_note) +
      (n.encounter_date ? '<div style="font-size:0.72rem;color:#888">' + _h(new Date(n.encounter_date).toLocaleString()) + '</div>' : '') +
      '</div>').join('') + '</div>';
  }

  // Box + the participant's own notes for this species, into `el`.
  async function mount(el, speciesId, speciesName) {
    if (!el || !speciesId || !(await isParticipant())) return false;
    el.innerHTML = '<div class="guest-note-box">' +
      '<div style="font-weight:600;font-size:0.85rem;margin-bottom:4px">📝 Your note on ' + _h(speciesName || 'this species') + '</div>' +
      '<textarea class="guest-note-text" rows="4" style="width:100%;box-sizing:border-box;font:inherit;padding:6px" ' +
      'placeholder="' + _h(HINT) + '" aria-label="Your note"></textarea>' +
      '<div style="font-size:0.75rem;color:#777;margin:2px 0 6px">' + _h(HINT) + '</div>' +
      '<button type="button" class="guest-note-save">Save note</button> <span class="guest-note-status" style="font-size:0.8rem"></span>' +
      '<div class="guest-note-mine"></div></div>';
    const ta = el.querySelector('.guest-note-text');
    const st = el.querySelector('.guest-note-status');
    const list = el.querySelector('.guest-note-mine');
    const refresh = async () => {
      const mineForSp = (await mine()).filter(n => n.species_id === speciesId);
      list.innerHTML = listHtml(mineForSp);
    };
    el.querySelector('.guest-note-save').onclick = async () => {
      st.textContent = 'Saving…';
      try {
        await save(speciesId, ta.value);
        ta.value = '';
        st.textContent = '✓ Saved';
        await refresh();
      } catch (e) {
        st.textContent = '✗ ' + e.message;
      }
    };
    await refresh();
    return true;
  }

  window.GuestNotes = { HINT: HINT, isParticipant: isParticipant, isOwnNote: isOwnNote, mine: mine,
                        mineBySpecies: mineBySpecies, save: save, listHtml: listHtml, mount: mount };
})();
