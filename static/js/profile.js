document.addEventListener('DOMContentLoaded', () => {
   const fileInput = document.getElementById('fileInput');
   const uploadBox = document.getElementById('uploadBox');
   const plusSign = document.getElementById('plusSign');
   const changeImageBtn = document.getElementById('changeImageBtn');
   const editBtn = document.getElementById('editBtn');
   const saveBtn = document.getElementById('saveBtn');
   const editFields = document.getElementById('editFields');
   const staticFields = document.getElementById('staticFields');
   const tabBtn = document.querySelectorAll('.tab-btn');
   const tabPanes = document.querySelectorAll('.tab-pane');
   const nameInput = document.getElementById('nameInput');
   const nameError = document.getElementById('nameError');

   const CH_KEY = 'recipe-save-sync';
   const STATE_PREFIX = 'save-state-';
   const stateKey = id => `${STATE_PREFIX}${id}`;

   function cacheState(id, saved) {
      try {
         localStorage.setItem(stateKey(id), JSON.stringify({
            saved: !!saved,
            t: Date.now()
         }));
      } catch {}
   }

   function readCachedState(id) {
      try {
         const raw = localStorage.getItem(stateKey(id));
         if (!raw) return null;
         const {
            saved
         } = JSON.parse(raw);
         return typeof saved === 'boolean' ? saved : null;
      } catch {
         return null;
      }
   }

   function broadcastSaveChange(recipeId, saved) {
      const payload = {
         id: Number(recipeId),
         saved: Boolean(saved),
         t: Date.now()
      };
      window.dispatchEvent(new CustomEvent('save-changed', {
         detail: payload
      }));
      try {
         localStorage.setItem(CH_KEY, JSON.stringify(payload));
         localStorage.setItem(stateKey(recipeId), JSON.stringify({
            saved: payload.saved,
            t: payload.t
         }));
         setTimeout(() => localStorage.removeItem(CH_KEY), 0);
      } catch {}
   }

   let isEditing = false;
   let hasImage = false;
   if (fileInput) fileInput.disabled = true;
   loadProfile();

   function sanitizeText(text, maxLength = 500) {
      if (!text) return '';
      const cleaned = text.replace(/<[^>]*>/g, '').trim();
      return cleaned.substring(0, maxLength);
   }

   function validateFile(file) {
      const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
      const maxSize = (5 * 1024 * 1024) / 2; // 2.5 MB
      if (!allowedTypes.includes(file.type)) {
         return {
            valid: false,
            error: 'Please upload a valid image file (JPEG, PNG, GIF, or WebP)'
         };
      }
      if (file.size > maxSize) {
         return {
            valid: false,
            error: 'Image must be smaller than 5MB'
         };
      }
      return {
         valid: true
      };
   }

   async function loadProfile() {
      try {
         const response = await fetch('/api/get-profile');
         if (!response.ok) throw new Error('Failed to load profile');

         const data = await response.json();
         if (data.success && data.profile) {
            const profile = data.profile;

            if (profile.name) {
               const cleanName = sanitizeText(profile.name, 100);
               document.getElementById('displayName').textContent = cleanName;
               nameInput.value = cleanName;
            } else {
               document.getElementById('displayName').textContent = 'Your Name';
               nameInput.value = '';
            }

            if (profile.bio) {
               const cleanBio = sanitizeText(profile.bio, 500);
               document.getElementById('displayBio').textContent = cleanBio;
               document.getElementById('bioInput').value = cleanBio;
            } else {
               document.getElementById('displayBio').textContent =
                  'Your bio will appear here. Click "Edit Profile" to add information about yourself.';
               document.getElementById('bioInput').value = '';
            }

            if (profile.has_image) {
               const img = document.getElementById('profileImg');
               img.src = '/api/profile-image?' + new Date().getTime();
               img.classList.remove('hidden');
               plusSign.style.display = 'none';
               hasImage = true;
            }
         }
      } catch (error) {
         console.error('Error loading profile:', error);
         document.getElementById('displayName').textContent = 'Your Name';
         document.getElementById('displayBio').textContent = 'Failed to load profile. Please refresh the page.';
      }
   }


   nameInput.addEventListener('input', function () {
      const nameLength = nameInput.value.trim().length;
      if (nameLength > 0 && nameLength < 4) {
         nameError.style.display = 'block';
         nameInput.style.borderColor = 'red';
      } else {
         nameError.style.display = 'none';
         nameInput.style.borderColor = '';
      }
   });

   uploadBox?.addEventListener('click', () => {
      if (isEditing) fileInput.click();
   });
   plusSign?.addEventListener('click', e => {
      e.stopPropagation();
      if (isEditing) fileInput.click();
   });

   editBtn?.addEventListener('click', () => {
      isEditing = true;
      if (fileInput) fileInput.disabled = false;
      editFields.classList.remove('hidden');
      staticFields.classList.add('hidden');
      uploadBox.classList.add('editable');
      plusSign.classList.add('editable');
      if (hasImage) changeImageBtn.classList.remove('hidden');
   });

   saveBtn?.addEventListener('click', async () => {
      const nameRaw = nameInput.value.trim();
      const bioRaw = document.getElementById('bioInput').value.trim();

      if (nameRaw.length < 4) {
         alert('Name must be at least 4 characters long');
         nameError.style.display = 'block';
         nameInput.style.borderColor = 'red';
         return;
      }
      if (nameRaw.length > 100) {
         alert('Name must be 100 characters or less');
         return;
      }
      if (bioRaw.length > 500) {
         alert('Bio must be 500 characters or less');
         return;
      }

      isEditing = false;
      if (fileInput) fileInput.disabled = true;
      editFields.classList.add('hidden');
      staticFields.classList.remove('hidden');
      changeImageBtn.classList.add('hidden');
      uploadBox.classList.remove('editable');
      plusSign.classList.remove('editable');
      nameError.style.display = 'none';
      nameInput.style.borderColor = '';

      const name = nameRaw || 'Your Name';
      const bio = bioRaw || 'Your bio will appear here. Click "Edit Profile" to add information about yourself.';
      document.getElementById('displayName').textContent = name;
      document.getElementById('displayBio').textContent = bio;

      const formData = new FormData();
      formData.append('name', name);
      formData.append('bio', bio);
      if (fileInput.files[0]) formData.append('image', fileInput.files[0]);

      try {
         const response = await fetch('/api/save-profile', {
            method: 'POST',
            body: formData
         });
         const result = await response.json();
         if (response.ok && result.success) await loadProfile();
         else {
            console.error('Failed to save profile:', result.message || 'Unknown error');
            alert('Failed to save profile: ' + (result.message || 'Unknown error'));
         }
      } catch (error) {
         console.error('Error saving profile:', error);
         alert('Error saving profile. Please try again.');
      }
   });

   fileInput?.addEventListener('change', async function (event) {
      const file = event.target.files[0];
      if (!file) return;
      const validation = validateFile(file);
      if (!validation.valid) {
         alert(validation.error);
         fileInput.value = '';
         return;
      }

      const displayReader = new FileReader();
      displayReader.onload = function (e) {
         const img = document.getElementById('profileImg');
         img.src = e.target.result;
         img.classList.remove('hidden');
         plusSign.style.display = 'none';
         hasImage = true;
         if (isEditing) changeImageBtn.classList.remove('hidden');
      };
      displayReader.onerror = function () {
         console.error('Error reading file');
         alert('Failed to load image preview');
         fileInput.value = '';
      };
      displayReader.readAsDataURL(file);
   });

   changeImageBtn?.addEventListener('click', () => fileInput.click());

   tabBtn.forEach(btn => {
      btn.addEventListener('click', () => {
         const tabName = btn.getAttribute('data-tab');
         tabBtn.forEach(b => b.classList.remove('active'));
         tabPanes.forEach(pane => pane.classList.remove('active'));
         btn.classList.add('active');
         document.getElementById(tabName).classList.add('active');
      });
   });


   document.querySelectorAll('.recipe-card').forEach(card => {
      card.addEventListener('click', (event) => {
         if (event.target.closest('button') || event.target.closest('a') || event.target.closest('.save-chip')) return;
         const url = card.dataset.url;
         if (url) window.location.href = url;
      });
   });



   function setSaveChipUI(btn, saved) {
      btn.classList.toggle('is-saved', saved);
      btn.setAttribute('aria-pressed', String(saved));
      const label = btn.querySelector('.label');
      if (label) label.textContent = saved ? 'Saved' : 'Save';
   }

   function initSaveChips(root = document) {
      root.querySelectorAll('.save-chip').forEach(btn => {
         const id = Number(btn.dataset.recipeId || btn.dataset.id);
         const cached = readCachedState(id); // prefer persisted state
         let initSaved;
         if (cached != null) {
            initSaved = cached;
         } else {
            initSaved =
               btn.dataset.saved === 'true' ||
               btn.getAttribute('aria-pressed') === 'true' ||
               btn.classList.contains('is-saved');
         }
         setSaveChipUI(btn, initSaved);
      });
   }
   initSaveChips();


   window.addEventListener('pageshow', () => {
      document.querySelectorAll('.save-chip').forEach(btn => {
         const id = Number(btn.dataset.recipeId || btn.dataset.id);
         const cached = readCachedState(id);
         if (cached != null) setSaveChipUI(btn, cached);
      });
   });


   window.addEventListener('storage', (e) => {
      if (e.key !== CH_KEY || !e.newValue) return;
      let data;
      try {
         data = JSON.parse(e.newValue);
      } catch {
         return;
      }
      document.querySelectorAll(`.save-chip[data-id="${data.id}"], .save-chip[data-recipe-id="${data.id}"]`)
         .forEach(btn => setSaveChipUI(btn, data.saved));
   });


   window.addEventListener('save-changed', (e) => {
      const {
         id,
         saved
      } = e.detail || {};
      if (typeof id === 'undefined') return;
      document.querySelectorAll(`.save-chip[data-id="${id}"], .save-chip[data-recipe-id="${id}"]`)
         .forEach(btn => setSaveChipUI(btn, saved));
   });


   document.addEventListener('click', async (e) => {
      const btn = e.target.closest('.save-chip');
      if (!btn) return;

      e.preventDefault();
      if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();
      e.stopPropagation();

      const recipeId = Number(btn.dataset.id || btn.dataset.recipeId);
      if (!recipeId) return;

      const currentlySaved =
         btn.classList.contains('is-saved') ||
         btn.getAttribute('aria-pressed') === 'true' ||
         btn.dataset.saved === 'true';

      btn.disabled = true;

      try {
         const res = await fetch(`/api/recipe/${recipeId}/save`, {
            method: 'POST',
            headers: {
               'Content-Type': 'application/json'
            },
            body: JSON.stringify({
               saved: !currentlySaved
            })
         });

         if (res.status === 401) {
            window.location.href = '/login';
            return;
         }

         let data = {};
         try {
            data = await res.json();
         } catch {
            data = {};
         }

         if (!res.ok || data.success === false) {
            throw new Error(data.message || 'Could not update save.');
         }

         const nextState = (typeof data.saved === 'boolean') ? data.saved : !currentlySaved;


         document.querySelectorAll(`.save-chip[data-id="${recipeId}"], .save-chip[data-recipe-id="${recipeId}"]`)
            .forEach(el => setSaveChipUI(el, nextState));


         cacheState(recipeId, nextState);
         broadcastSaveChange(recipeId, nextState);


         const savedPane = document.getElementById('saved');
         const savedPaneActive = savedPane?.classList.contains('active');
         if (savedPaneActive && nextState === false) {
            const card = btn.closest('.recipe-card');
            const grid = card?.parentElement;
            if (card) card.remove();

            if (grid && grid.querySelectorAll('.recipe-card').length === 0) {
               const msg = document.createElement('p');
               msg.textContent = "You don't have any saved posts";
               grid.parentElement.replaceChildren(msg);
            }
         }
      } catch (err) {
         console.error(err);
         alert(err.message || 'Could not update save.');
      } finally {
         btn.disabled = false;
      }
   }, true);


   const mo = new MutationObserver(muts => {
      muts.forEach(m => m.addedNodes.forEach(n => {
         if (n.nodeType === 1) initSaveChips(n);
      }));
   });
   mo.observe(document.body, {
      childList: true,
      subtree: true
   });
});