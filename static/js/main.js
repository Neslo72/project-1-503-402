document.addEventListener('DOMContentLoaded', () => {
   document.querySelectorAll('.recipe-card').forEach(card => {
      card.addEventListener('click', evt => {
         if (
            evt.target.closest('.save-chip') ||
            evt.target.closest('button') ||
            evt.target.closest('a')
         ) return;

         const url = card.dataset.url;
         if (url) window.location.href = url;
      });
   });

   const CH_KEY = 'recipe-save-sync';
   const STATE_PREFIX = 'save-state-';
   const stateKey = id => `${STATE_PREFIX}${id}`;

   function setSaveUI(btn, saved) {
      btn.classList.toggle('is-saved', saved);
      btn.setAttribute('aria-pressed', String(saved));
      const label = btn.querySelector('.label');
      if (label) label.textContent = saved ? 'Saved' : 'Save';
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

   function cacheState(id, saved) {
      try {
         localStorage.setItem(stateKey(id), JSON.stringify({
            saved: !!saved,
            t: Date.now()
         }));
      } catch {}
   }

   function initChips(root = document) {
      root.querySelectorAll('.save-chip').forEach(btn => {
         const id = Number(btn.dataset.recipeId || btn.dataset.id);
         const cached = readCachedState(id); // prefer persisted state
         let saved;
         if (cached != null) {
            saved = cached;
         } else {
            saved =
               btn.dataset.saved === 'true' ||
               btn.getAttribute('aria-pressed') === 'true' ||
               btn.classList.contains('is-saved');
         }
         setSaveUI(btn, saved);
      });
   }
   initChips();

   function broadcast(id, saved) {
      const payload = {
         id: Number(id),
         saved: !!saved,
         t: Date.now()
      };
      window.dispatchEvent(new CustomEvent('save-changed', {
         detail: payload
      }));
      try {
         localStorage.setItem(CH_KEY, JSON.stringify(payload));
         localStorage.setItem(stateKey(id), JSON.stringify({
            saved: payload.saved,
            t: payload.t
         }));
         setTimeout(() => localStorage.removeItem(CH_KEY), 0);
      } catch {}
   }

   function chipsFor(id) {
      return document.querySelectorAll(
         `.save-chip[data-id="${id}"], .save-chip[data-recipe-id="${id}"]`
      );
   }


   window.addEventListener('storage', e => {
      if (e.key !== CH_KEY || !e.newValue) return;
      let d;
      try {
         d = JSON.parse(e.newValue);
      } catch {
         return;
      }
      chipsFor(d.id).forEach(b => setSaveUI(b, d.saved));
   });

   window.addEventListener('save-changed', e => {
      const {
         id,
         saved
      } = e.detail || {};
      if (id == null) return;
      chipsFor(id).forEach(b => setSaveUI(b, saved));
   });


   window.addEventListener('pageshow', () => {
      document.querySelectorAll('.save-chip').forEach(btn => {
         const id = Number(btn.dataset.recipeId || btn.dataset.id);
         const cached = readCachedState(id);
         if (cached != null) setSaveUI(btn, cached);
      });
   });

   document.addEventListener('click', async e => {
      const btn = e.target.closest('.save-chip');
      if (!btn) return;

      e.preventDefault();
      if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();
      e.stopPropagation();

      const recipeId = Number(btn.dataset.recipeId || btn.dataset.id);
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
         } catch {}
         if (!res.ok || data.success === false) {
            throw new Error(data.message || 'Could not update save.');
         }

         const nextState = typeof data.saved === 'boolean' ? data.saved : !currentlySaved;

         chipsFor(recipeId).forEach(b => setSaveUI(b, nextState));
         cacheState(recipeId, nextState);
         broadcast(recipeId, nextState);
      } catch (err) {
         console.error(err);
         alert(err.message || 'Could not update save.');
      } finally {
         btn.disabled = false;
      }
   });

   new MutationObserver(muts => {
      muts.forEach(m => m.addedNodes.forEach(n => {
         if (n.nodeType === 1) initChips(n);
      }));
   }).observe(document.body, {
      childList: true,
      subtree: true
   });
});