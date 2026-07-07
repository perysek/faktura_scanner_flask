# Component: Undo Toast (soft-delete "Cofnij")

**Source:** `templates/components/undo_toast.html`
**Type:** Self-contained `<script>` exposing one global function. No markup, no macro.
**CSS delivery:** 100% inline (styles set via `element.style.cssText` in JS) — **zero**
CSS/token/build dependency. This component works in any project as-is.

---

## 1. Purpose & when to use

After a **soft delete** (record flagged deleted, restorable), call `showUndoToast()` to show a
bottom-right toast with a **"Cofnij"** (Undo) button that POSTs to a restore endpoint. It is the
forgiving counterpart to the hard-delete [`confirm-modal.md`](confirm-modal.md): confirm modal
*prevents* mistakes up front; undo toast *reverses* them after the fact.

Use undo-toast when deletion is reversible server-side. Use confirm-modal when it is not.

---

## 2. Public API

```javascript
showUndoToast(message, restoreUrl, duration = 8000);
```

| Param | Meaning |
|---|---|
| `message` | Confirmation text shown in the toast (e.g. `'Klient usunięty'`). |
| `restoreUrl` | **POST** URL that restores the record. Must return JSON `{ success: bool, message?, error? }`. |
| `duration` | Visible time in ms before auto-hide. Default `8000`. |

Behaviour:

- Only **one** undo toast at a time — a new call removes the previous (`#undo-toast`).
- Clicking **Cofnij**: `POST restoreUrl` → on `success`, shows the returned `message`, removes the
  Undo button, then **reloads the page** (~2.2 s later) to surface the restored row. On failure it
  shows `error` and re-enables the button.
- Clicking **×** dismisses immediately.
- **Hovering the toast cancels the auto-hide timer** (so users reading it don't lose the chance).
- Fades via `opacity` transition (200 ms).

---

## 3. Server contract

The restore endpoint **must**:

- Accept `POST`.
- Return JSON: `{ "success": true, "message": "Przywrócono klienta" }`
  or `{ "success": false, "error": "Nie można przywrócić" }`.

```python
@bp.route('/api/clients/<int:id>/restore', methods=['POST'])
def restore_client(id):
    ok = clients.restore(id)
    if ok:
        return jsonify(success=True, message='Przywrócono klienta')
    return jsonify(success=False, error='Nie można przywrócić'), 400
```

Typical caller (after a successful soft-delete AJAX call):

```javascript
showUndoToast('Klient usunięty', `/api/clients/${id}/restore`, 8000);
```

---

## 4. Styling (informational — nothing to port)

All styles are inlined in JS, but they now reference the **live refined tokens** — each with a
hardcoded fallback, so the toast still renders correctly in a project with no tokens at all:

- White bg (`#fff`), **green left border (4px)** via `var(--color-success-action, #10b981)`; the
  box border is neutral `var(--color-border, #e8e6e1)`.
- `border-radius: var(--radius-md, 3px)` on the toast (elevated card) and `var(--radius-sm, 2px)`
  on the "Cofnij" button — on-system with the refined 2–3px scale.
- Message text `var(--color-ink, #1a1a1a)`; close "×" `var(--color-ink-subtle, #6b6b6b)`.
- "Cofnij" button blue via `var(--color-focus-ring, #2563eb)`; hover tint `rgba(37,99,235,0.1)`.
- Elevation `box-shadow: 0 8px 32px rgba(0,0,0,0.18)` — **shared with the confirm-modal panel** so
  both floating surfaces read at the same depth.
- Fixed `bottom:1.5rem; right:1.5rem; z-index:9999; max-width:400px`.

---

## 5. Fresh-project integration

1. Copy `templates/components/undo_toast.html`.
2. Include it **once** in `base.html` (or only on pages with soft-delete):
   ```jinja2
   {% include 'components/undo_toast.html' %}
   ```
3. Nothing else — no `@layer` classes, no build step. The `var(--color-*, fallback)` pattern means
   it renders correctly even in a project where none of these tokens are defined; if the tokens
   *are* present it inherits the theme automatically.
4. Implement a `POST` restore endpoint returning the JSON contract above.

---

## 6. Gotchas

- **Inline styles reference live tokens *with fallbacks* — keep the fallbacks.** The
  `var(--color-*, #hex)` form is deliberate: the token themes it when present, the literal hex keeps
  it correct in a token-less project and on any deploy that skipped a CSS rebuild. Don't strip the
  fallback to "tidy it up".
- **It reloads the page on undo** — fine for server-rendered list pages, but in an SPA-ish flow
  you'd replace `location.reload()` with a targeted row re-insert.
- Don't stack it with toast `Notifications.*` for the same action; pick one feedback channel.
- **Historical note:** this component previously used the deleted `--pp-success` / `--pp-blue`
  tokens and soft `0.75rem` / `0.375rem` radii; it was realigned to `--color-*` / `--radius-*` on
  2026-07-07. If you spot `--pp-*` elsewhere (e.g. `appointments/superadmin_edit*.html`), it's the
  same legacy drift awaiting the same fix.
