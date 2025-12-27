// Navbar
(() => {
  const btn = document.getElementById('navToggle');
  const links = document.getElementById('navLinks');
  if (!btn || !links) return;

  btn.addEventListener('click', () => {
    const open = links.classList.toggle('open');
    btn.setAttribute('aria-expanded', String(open));
  });

  // close after clicking a link (mobile)
  links.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      links.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    });
  });

  // close if tap outside
  document.addEventListener('click', (e) => {
    if (!links.classList.contains('open')) return;
    if (links.contains(e.target) || btn.contains(e.target)) return;
    links.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  });
})();


(() => {
  const btn = document.getElementById('profileBtn');
  const menu = document.getElementById('profileMenu');
  if (!btn || !menu) return;

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = menu.classList.toggle('open');
    btn.setAttribute('aria-expanded', String(open));
  });

  document.addEventListener('click', (e) => {
    if (!menu.classList.contains('open')) return;
    if (menu.contains(e.target) || btn.contains(e.target)) return;
    menu.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  });
})();

// Register

(() => {
  const form = document.getElementById('registerForm');
  if (!form) return;

  /* Organization "Others" */
  const org = document.getElementById('organization');
  const orgWrap = document.getElementById('orgOtherWrap');
  const orgOther = document.getElementById('organization_other');

  function syncOrg() {
    const isOther = org.value === 'Others';
    orgWrap.style.display = isOther ? 'block' : 'none';
    orgOther.required = isOther;
    if (!isOther) orgOther.value = '';
  }
  org.addEventListener('change', syncOrg);
  syncOrg();

  /* Password match */
  const pw = document.getElementById('password');
  const cpw = document.getElementById('confirm_password');
  const pwError = document.getElementById('pwError');
  const btn = document.getElementById('registerBtn');

  function checkPasswords() {
    if (!pw.value || !cpw.value) {
      pwError.style.display = 'none';
      btn.disabled = false;
      return;
    }
    const ok = pw.value === cpw.value;
    pwError.style.display = ok ? 'none' : 'block';
    btn.disabled = !ok;
  }
  pw.addEventListener('input', checkPasswords);
  cpw.addEventListener('input', checkPasswords);

  /* Phone (intl-tel-input) */
  const phoneInput = document.getElementById('phone');
  const phoneE164 = document.getElementById('phone_e164');

  const iti = window.intlTelInput(phoneInput, {
    initialCountry: "us",
    separateDialCode: true,
    formatOnDisplay: true,
    utilsScript:
      "https://cdn.jsdelivr.net/npm/intl-tel-input@19.5.6/build/js/utils.js"
  });

  function syncPhone() {
    if (iti.isValidNumber()) {
      phoneE164.value = iti.getNumber(); // E.164
      phoneInput.setCustomValidity('');
    } else {
      phoneE164.value = '';
      phoneInput.setCustomValidity('Invalid phone number');
    }
  }
  phoneInput.addEventListener('input', syncPhone);
  phoneInput.addEventListener('countrychange', syncPhone);

  /* ZIP → City/State autofill (non-destructive) */
  const zip = document.getElementById('zip_code');
  const city = document.getElementById('city');
  const state = document.getElementById('state');

  async function autofillFromZip() {
    const zip5 = zip.value.trim().split('-')[0];
    if (!/^\d{5}$/.test(zip5)) return;

    try {
      const res = await fetch(`https://api.zippopotam.us/us/${zip5}`);
      if (!res.ok) return;
      const data = await res.json();
      const place = data.places?.[0];
      if (!place) return;

      if (!city.value) city.value = place['place name'] || '';
      if (!state.value) state.value = place['state abbreviation'] || '';
    } catch (_) {}
  }

  zip.addEventListener('blur', autofillFromZip);
  zip.addEventListener('change', autofillFromZip);

  /* Final submit guard */
  form.addEventListener('submit', (e) => {
    syncPhone();
    checkPasswords();
    if (btn.disabled || !iti.isValidNumber()) {
      e.preventDefault();
      phoneInput.reportValidity();
    }
  });
})();


// users:
(() => {
  const modal = document.getElementById('userModal');
  if (!modal) return;

  const body = document.getElementById('modalBody');
  const closeBtn = document.getElementById('modalClose');
  const backdrop = document.getElementById('modalBackdrop');
  const cancelBtn = document.getElementById('cancelModal');
  const receiverInput = document.getElementById('receiver_id');

  // message form (hide when inactive)
  const messageForm = document.getElementById('messageForm');

  function openModal() {
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeModal() {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    body.innerHTML = '';
    receiverInput.value = '';
    if (messageForm) messageForm.style.display = '';
  }

  async function loadUser(uid) {
    const res = await fetch(`/api/user/${uid}`);
    if (!res.ok) {
      body.innerHTML = `<p class="error">Unable to load user details.</p>`;
      receiverInput.value = '';
      if (messageForm) messageForm.style.display = 'none';
      return;
    }

    const u = await res.json();

    // inactive user → show only unavailable message
    if (u.inactive === true) {
      body.innerHTML = `<p class="empty-state"><strong>User currently unavailable</strong></p>`;
      receiverInput.value = '';
      if (messageForm) messageForm.style.display = 'none';
      return;
    }

    const addr2 = u.address_line2 ? `, ${u.address_line2}` : '';
    body.innerHTML = `
      <p><strong>Username:</strong> ${u.username || ''}</p>
      <p><strong>Fullname:</strong> ${u.fullname || ''}</p>
      <p><strong>Email:</strong> ${u.email || ''}</p>
      <p><strong>Address:</strong> ${u.address_line1 || ''}${addr2}, ${u.city || ''}, ${u.state || ''} ${u.zip_code || ''}</p>
      <p><strong>Phone:</strong> ${u.phone || ''}</p>
      <p><strong>Profession:</strong> ${u.profession || ''}</p>
      <p><strong>Organization:</strong> ${u.organization || ''}</p>
      <p><strong>Role:</strong> ${u.role || ''}</p>
      <p><strong>Status:</strong> ${u.is_active ? 'Active' : 'Inactive'}</p>
    `;

    receiverInput.value = u.id;
    if (messageForm) messageForm.style.display = '';
  }

  document.querySelectorAll('.view-details-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const uid = btn.getAttribute('data-user-id');
      openModal();
      await loadUser(uid);
    });
  });

  closeBtn?.addEventListener('click', closeModal);
  backdrop?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
  });
})();

// Dashboard deactivate modal
(() => {
  const openBtn = document.getElementById('openDeactivateModal');
  const modal = document.getElementById('deactivateModal');
  if (!openBtn || !modal) return;

  const backdrop = document.getElementById('deactivateBackdrop');
  const closeBtn = document.getElementById('closeDeactivateModal');
  const cancelBtn = document.getElementById('cancelDeactivate');
  const hasErr = document.getElementById('deactivateHasError');

  function openModal() {
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeModal() {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  }

  openBtn.addEventListener('click', openModal);
  backdrop?.addEventListener('click', closeModal);
  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
  });

  // Auto-open if there was an error
  if (hasErr && hasErr.value === "1") openModal();
})();
