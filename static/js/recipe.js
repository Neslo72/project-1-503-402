document.addEventListener("DOMContentLoaded", () => {
   document.documentElement.style.scrollBehavior = "smooth";

   const CH_KEY = "recipe-save-sync";
   const STATE_PREFIX = "save-state-";
   const stateKey = (id) => `${STATE_PREFIX}${id}`;

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
         return typeof saved === "boolean" ? saved : null;
      } catch {
         return null;
      }
   }

   function broadcastSave(id, saved) {
      const payload = {
         id: Number(id),
         saved: !!saved,
         t: Date.now()
      };
      window.dispatchEvent(new CustomEvent("save-changed", {
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

   (function setupSave() {
      const btn = document.getElementById("saveBtn");
      if (!btn) return;

      try {
         const currentType = (btn.getAttribute("type") || "").toLowerCase();
         if (currentType === "" || currentType === "submit") btn.setAttribute("type", "button");
      } catch {}

      btn.addEventListener("pointerdown", (e) => {
         e.preventDefault();
         if (typeof e.stopImmediatePropagation === "function") e.stopImmediatePropagation();
         e.stopPropagation();
      }, true);

      const recipeId = Number(btn.dataset.recipeId || btn.dataset.id);
      const label = btn.querySelector(".label");

      const setUI = (saved) => {
         btn.classList.toggle("is-saved", saved);
         btn.setAttribute("aria-pressed", String(saved));
         btn.setAttribute("aria-label", saved ? "Saved" : "Save");
         if (label) label.textContent = saved ? "Saved" : "Save";
      };


      const cached = readCachedState(recipeId);
      let isSaved = (cached != null) ? cached : (btn.dataset.saved === "true");
      setUI(isSaved);


      window.addEventListener("storage", (e) => {
         if (e.key !== CH_KEY || !e.newValue) return;
         let data;
         try {
            data = JSON.parse(e.newValue);
         } catch {
            return;
         }
         if (!data || data.id !== recipeId) return;
         isSaved = !!data.saved;
         setUI(isSaved);
      });
      window.addEventListener("save-changed", (e) => {
         const {
            id,
            saved
         } = e.detail || {};
         if (id !== recipeId) return;
         isSaved = !!saved;
         setUI(isSaved);
      });
      window.addEventListener("pageshow", () => {
         const s = readCachedState(recipeId);
         if (s != null) {
            isSaved = s;
            setUI(isSaved);
         }
      });

      btn.addEventListener("click", async (e) => {
         e.preventDefault();
         if (typeof e.stopImmediatePropagation === "function") e.stopImmediatePropagation();
         e.stopPropagation();

         if (!recipeId) return;

         btn.disabled = true;
         try {
            const res = await fetch(`/api/recipe/${recipeId}/save`, {
               method: "POST",
               headers: {
                  "Content-Type": "application/json"
               },
               body: JSON.stringify({
                  saved: !isSaved
               })
            });

            if (res.status === 401) {
               window.location.href = "/login";
               return;
            }

            let data = {};
            try {
               data = await res.json();
            } catch {}

            if (!res.ok || data.success === false) {
               throw new Error(data.message || "Could not update save.");
            }

            isSaved = (typeof data.saved === "boolean") ? data.saved : !isSaved;
            setUI(isSaved);

            cacheState(recipeId, isSaved);
            broadcastSave(recipeId, isSaved);
         } catch (err) {
            console.error(err);
            alert(err.message || "Could not save recipe.");
         } finally {
            btn.disabled = false;
         }
      });
   })();


   (function setupRating() {
      const widget = document.getElementById("ratingWidget");
      if (!widget) return;

      const stars = Array.from(widget.querySelectorAll(".star"));
      const avgEl = document.getElementById("avgRating");
      const countEl = document.getElementById("ratingCount");

      const recipeId = Number(widget.getAttribute("data-recipe-id"));
      let current = Number(widget.getAttribute("data-current") || 0);
      let locked = widget.getAttribute("data-locked") === "true";

      const paint = (n, preview = false) => {
         stars.forEach((s, idx) => {
            const v = idx + 1;
            s.classList.toggle("active", v <= (preview ? n : current));
            s.classList.toggle("preview", preview && v <= n);
            if (!preview) s.classList.remove("preview");
         });
      };

      paint(current);

      stars.forEach((star) => {
         star.addEventListener("mouseenter", () => {
            if (locked) return;
            paint(Number(star.dataset.value), true);
         });
      });

      widget.addEventListener("mouseleave", () => {
         if (locked) return;
         paint(current, false);
      });

      stars.forEach((star) => {
         star.addEventListener("click", async () => {
            const value = Number(star.dataset.value);
            if (!recipeId || value < 1 || value > 5) return;

            if (locked) {
               paint(current);
               return;
            }

            current = value;
            paint(current, false);

            try {
               const res = await fetch(`/api/recipe/${recipeId}/rate`, {
                  method: "POST",
                  headers: {
                     "Content-Type": "application/json"
                  },
                  body: JSON.stringify({
                     rating: value
                  })
               });

               if (res.status === 401) {
                  current = Number(widget.getAttribute("data-current") || 0);
                  paint(current);
                  window.location.href = "/login";
                  return;
               }

               const data = await res.json();

               if (res.status === 409) {
                  const existing = Number(data.existing_rating || current || 0);
                  current = existing;
                  widget.classList.add("locked");
                  widget.setAttribute("data-locked", "true");
                  paint(current);
                  return;
               }

               if (!res.ok || !data.success) {
                  throw new Error(data.message || "Failed to rate recipe.");
               }

               locked = true;
               widget.classList.add("locked");
               widget.setAttribute("data-locked", "true");
               widget.setAttribute("data-current", String(current));

               if (avgEl && typeof data.avg_rating === "number") {
                  avgEl.textContent = data.avg_rating.toFixed(1);
               }
               if (countEl && typeof data.ratings_count === "number") {
                  countEl.textContent = String(data.ratings_count);
               }
            } catch (err) {
               console.error(err);
               alert(err.message || "Could not submit rating.");
               current = Number(widget.getAttribute("data-current") || 0);
               paint(current);
            }
         });
      });
   })();


   function fmt(ts) {
      const d = new Date(ts);
      const pad = (n) => String(n).padStart(2, "0");
      return `${pad(d.getMonth() + 1)}/${pad(d.getDate())}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
   }

   function ensureEditedFlag(metaEl) {
      if (!metaEl) return;
      let flag = metaEl.querySelector(".edited-flag");
      if (!flag) {
         flag = document.createElement("span");
         flag.className = "edited-flag";
         flag.textContent = " (edited)";
         metaEl.appendChild(flag);
      }
   }

   const form = document.getElementById("commentForm");
   const textarea = document.getElementById("commentContent");

   async function postComment(endpoint, payload) {
      const res = await fetch(endpoint, {
         method: "POST",
         headers: {
            "Content-Type": "application/json"
         },
         body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
         throw new Error(data.message || "Failed to post comment.");
      }
      return data.comment;
   }

   function ensureList() {
      const commentsWrapper = document.querySelector(".comments");
      let list = document.querySelector(".comment-list");
      if (!list) {
         if (commentsWrapper) commentsWrapper.innerHTML = "";
         list = document.createElement("ul");
         list.className = "comment-list";
         if (commentsWrapper) commentsWrapper.appendChild(list);
      }
      const noMsg = document.getElementById("noCommentsMsg");
      if (noMsg) noMsg.remove();
      return list;
   }

   function renderCommentNode(c) {
      const currentUserId = Number(document.body.dataset.userId || 0);
      const isAdmin = document.body.dataset.isAdmin === "true";
      const canManage = (currentUserId === Number(c.userid)) || isAdmin;

      const li = document.createElement("li");
      li.className = "comment-item";
      li.dataset.commentId = c.commentid;

      const header = document.createElement("div");
      header.className = "comment-header";

      const meta = document.createElement("div");
      meta.className = "comment-meta";

      const userEl = document.createElement("strong");
      userEl.className = "comment-user";
      userEl.textContent = c.username || ("User " + (c.userid ?? ""));

      const timeEl = document.createElement("span");
      timeEl.className = "comment-time";
      timeEl.textContent = c.lastedit ? fmt(c.lastedit) : fmt(new Date().toISOString());

      meta.appendChild(userEl);
      meta.appendChild(timeEl);

      if (c.edited || c.is_edited || c.was_edited) {
         ensureEditedFlag(meta);
      }

      header.appendChild(meta);

      if (canManage) {
         const dropdown = document.createElement("div");
         dropdown.className = "dropdown";

         const toggle = document.createElement("button");
         toggle.className = "menu-toggle";
         toggle.type = "button";
         toggle.setAttribute("aria-label", "Comment actions");
         toggle.setAttribute("aria-expanded", "false");
         toggle.textContent = "⋯";

         const menu = document.createElement("ul");
         menu.className = "menu";
         menu.hidden = true;

         const editLi = document.createElement("li");
         const editBtn = document.createElement("button");
         editBtn.type = "button";
         editBtn.className = "comment-edit";
         editBtn.dataset.id = c.commentid;
         editBtn.textContent = "✏️ Edit";
         editLi.appendChild(editBtn);

         const delLi = document.createElement("li");
         const delBtn = document.createElement("button");
         delBtn.type = "button";
         delBtn.className = "comment-delete";
         delBtn.dataset.id = c.commentid;
         delBtn.textContent = "🗑 Delete";
         delLi.appendChild(delBtn);

         menu.appendChild(editLi);
         menu.appendChild(delLi);
         dropdown.appendChild(toggle);
         dropdown.appendChild(menu);
         header.appendChild(dropdown);
      }

      li.appendChild(header);

      const body = document.createElement("p");
      body.className = "comment-body";
      body.textContent = c.content;
      li.appendChild(body);

      const replyBtn = document.createElement("button");
      replyBtn.type = "button";
      replyBtn.className = "reply-btn btn-save";
      replyBtn.dataset.parentId = c.commentid;
      replyBtn.textContent = "Reply";
      li.appendChild(replyBtn);

      if (canManage) {
         const editForm = document.createElement("form");
         editForm.className = "edit-form comment-form";
         editForm.hidden = true;
         editForm.setAttribute("method", "post");
         editForm.setAttribute("action", `/api/comment/${c.commentid}/edit`);

         const taE = document.createElement("textarea");
         taE.name = "content";
         taE.rows = 2;
         taE.required = true;
         taE.placeholder = "Edit your comment...";
         editForm.appendChild(taE);

         const actionsE = document.createElement("div");
         actionsE.className = "comment-actions";
         const saveE = document.createElement("button");
         saveE.type = "submit";
         saveE.className = "btn-save";
         saveE.textContent = "Save";
         const cancelE = document.createElement("button");
         cancelE.type = "button";
         cancelE.className = "btn-cancel btn-save";
         cancelE.textContent = "Cancel";
         actionsE.appendChild(saveE);
         actionsE.appendChild(cancelE);
         editForm.appendChild(actionsE);

         li.appendChild(editForm);
      }

      const replyForm = document.createElement("form");
      replyForm.className = "reply-form comment-form";
      replyForm.hidden = true;
      replyForm.setAttribute("method", "post");
      replyForm.setAttribute("action", document.getElementById("commentForm")?.getAttribute("action") || "#");

      const hid = document.createElement("input");
      hid.type = "hidden";
      hid.name = "parentID";
      hid.value = c.commentid;
      replyForm.appendChild(hid);

      const ta = document.createElement("textarea");
      ta.name = "content";
      ta.rows = 2;
      ta.required = true;
      ta.placeholder = "Write a reply...";
      replyForm.appendChild(ta);

      const actions = document.createElement("div");
      actions.className = "comment-actions";
      const post = document.createElement("button");
      post.type = "submit";
      post.className = "btn-save";
      post.textContent = "Post Reply";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "btn-cancel btn-save";
      cancel.textContent = "Cancel";
      actions.appendChild(post);
      actions.appendChild(cancel);
      replyForm.appendChild(actions);

      li.appendChild(replyForm);

      const ulChildren = document.createElement("ul");
      ulChildren.className = "comment-list comment-children";
      li.appendChild(ulChildren);

      return li;
   }

   document.addEventListener("click", (e) => {
      const btn = e.target.closest(".reply-btn");
      if (btn) {
         const li = btn.closest(".comment-item");
         const form = li?.querySelector(".reply-form");
         const ta = form?.querySelector("textarea");
         if (form) {
            form.hidden = !form.hidden;
            if (!form.hidden && ta) setTimeout(() => ta.focus(), 0);
         }
      }
   });

   document.addEventListener("click", (e) => {
      const cancel = e.target.closest(".btn-cancel");
      if (!cancel) return;

      const replyForm = cancel.closest(".reply-form");
      const editForm = cancel.closest(".edit-form");

      if (replyForm) {
         const ta = replyForm.querySelector("textarea");
         if (ta) ta.value = "";
         replyForm.hidden = true;
         return;
      }
      if (editForm) {
         const ta = editForm.querySelector("textarea");
         if (ta) ta.value = ta.getAttribute("data-original") || ta.value;
         editForm.hidden = true;
         const li = editForm.closest(".comment-item");
         li?.querySelector(".comment-body")?.classList.remove("hidden");
      }
   });

   document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      const ta = e.target.closest(".reply-form textarea, .edit-form textarea");
      if (!ta) return;
      const form = ta.closest(".reply-form, .edit-form");
      if (form) {
         ta.value = ta.getAttribute("data-original") || "";
         form.hidden = true;
         const li = form.closest(".comment-item");
         li?.querySelector(".comment-body")?.classList.remove("hidden");
         e.preventDefault();
      }
   });

   document.addEventListener("submit", async (e) => {
      const rf = e.target.closest(".reply-form");
      if (!rf) return;

      e.preventDefault();
      const endpoint = rf.getAttribute("action");
      const parentID = Number(rf.querySelector('input[name="parentID"]').value);
      const content = rf.querySelector('textarea[name="content"]').value.trim();
      if (!content) return;

      const btn = rf.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;

      try {
         const comment = await postComment(endpoint, {
            content,
            parentID
         });

         const parentLi = document.querySelector(`.comment-item[data-comment-id="${parentID}"]`);
         let childList = parentLi?.querySelector(".comment-children");
         if (!childList) {
            childList = document.createElement("ul");
            childList.className = "comment-list comment-children";
            parentLi.appendChild(childList);
         }
         const node = renderCommentNode(comment);
         childList.appendChild(node);
         rf.reset();
         rf.hidden = true;
         node.scrollIntoView({
            behavior: "smooth",
            block: "nearest"
         });
      } catch (err) {
         console.error(err);
         alert(err.message || "Could not post reply.");
      } finally {
         if (btn) btn.disabled = false;
      }
   });

   if (form && textarea) {
      form.addEventListener("submit", async (e) => {
         e.preventDefault();

         const content = textarea.value.trim();
         if (!content) return;

         const submitBtn = form.querySelector('button[type="submit"]');
         if (submitBtn) submitBtn.disabled = true;

         try {
            const endpoint = form.getAttribute("action");
            const comment = await postComment(endpoint, {
               content
            });

            const list = ensureList();
            const node = renderCommentNode(comment);
            list.prepend(node);
            textarea.value = "";
         } catch (err) {
            console.error(err);
            alert(err.message || "Could not post comment.");
         } finally {
            if (submitBtn) submitBtn.disabled = false;
         }
      });
   }

   document.addEventListener("click", (e) => {
      const toggle = e.target.closest(".menu-toggle");
      if (toggle) {
         const dd = toggle.closest(".dropdown");
         const menu = dd ? dd.querySelector(".menu") : null;
         document.querySelectorAll(".dropdown .menu").forEach((m) => (m.hidden = true));
         if (menu) {
            menu.hidden = !menu.hidden;
            toggle.setAttribute("aria-expanded", String(!menu.hidden));
         }
         e.preventDefault();
         e.stopPropagation();
         return;
      }
      document.querySelectorAll(".dropdown .menu").forEach((m) => (m.hidden = true));
   }, false);

   document.addEventListener("click", (e) => {
      const btn = e.target.closest(".comment-edit");
      if (!btn) return;

      const li = btn.closest(".comment-item");
      const editForm = li.querySelector(".edit-form");
      const body = li.querySelector(".comment-body");
      const ta = editForm.querySelector("textarea");

      ta.value = body.textContent.trim();
      ta.setAttribute("data-original", ta.value);

      body.classList.add("hidden");
      editForm.hidden = false;
      setTimeout(() => ta.focus(), 0);
   });

   document.addEventListener("submit", async (e) => {
      const ef = e.target.closest(".edit-form");
      if (!ef) return;

      e.preventDefault();

      const url = ef.getAttribute("action");
      const ta = ef.querySelector("textarea");
      const newContent = ta.value.trim();
      if (!newContent) return;

      const li = ef.closest(".comment-item");
      const body = li.querySelector(".comment-body");
      theTime = li.querySelector(".comment-time");
      const metaEl = li.querySelector(".comment-meta");
      const submitBtn = ef.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      try {
         const res = await fetch(url, {
            method: "POST",
            headers: {
               "Content-Type": "application/json"
            },
            body: JSON.stringify({
               content: newContent
            })
         });
         const data = await res.json();
         if (!res.ok || !data.success) throw new Error(data.message || "Failed to edit comment.");

         body.textContent = data.comment?.content ?? newContent;
         if (data.comment?.lastedit && theTime) {
            theTime.textContent = fmt(data.comment.lastedit);
         }

         ensureEditedFlag(metaEl);

         ef.hidden = true;
         body.classList.remove("hidden");
      } catch (err) {
         console.error(err);
         alert(err.message || "Could not update comment.");
      } finally {
         if (submitBtn) submitBtn.disabled = false;
      }
   });

   document.addEventListener("click", async (e) => {
      const btn = e.target.closest(".comment-delete");
      if (!btn) return;

      const id = Number(btn.dataset.id);
      if (!id) return;

      if (!confirm("Delete this comment? This cannot be undone.")) return;

      const li = btn.closest(".comment-item");

      const tryEndpoints = [{
            url: `/api/comment/${id}`,
            options: {
               method: "DELETE"
            }
         },
         {
            url: `/api/comment/${id}/delete`,
            options: {
               method: "POST"
            }
         }
      ];

      let ok = false,
         msg = "Failed to delete comment.";
      for (const attempt of tryEndpoints) {
         try {
            const res = await fetch(attempt.url, attempt.options);
            const data = await res.json().catch(() => ({}));
            if (res.ok && (data.success !== false)) {
               ok = true;
               break;
            } else {
               msg = data.message || msg;
            }
         } catch (err) {
            msg = err.message || msg;
         }
         if (ok) break;
      }

      if (!ok) {
         alert(msg);
         return;
      }

      const parent = li.parentElement;
      li.remove();

      if (parent && parent.classList.contains("comment-list") && parent.children.length === 0) {
         const wrapper = document.querySelector(".comments");
         if (wrapper && !document.getElementById("noCommentsMsg")) {
            const p = document.createElement("p");
            p.id = "noCommentsMsg";
            p.className = "muted";
            p.textContent = "No comments yet — be the first!";
            wrapper.appendChild(p);
         }
      }
   });
});