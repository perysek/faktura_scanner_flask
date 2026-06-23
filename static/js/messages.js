/**
 * Client-side UI message resolver.
 *
 * The active tone's flat {id: text} map is injected into the page as
 * `window.UI_MESSAGES` by the inject_globals context processor (see
 * config/ui_messages.py + base.html <head>). This file only resolves an id to
 * its text and interpolates {param} placeholders — the catalog itself lives in
 * Python.
 *
 * Usage:
 *   Notifications.success(MSG('invoice.save_success', { count: savedCount }));
 *   Modals.confirm({ title: MSG('modal.confirm.title') });
 *
 * Fail-visible: an unknown id returns the id string itself, never throws — a
 * missing translation shows as "invoice.save_success" rather than blowing up a
 * toast or a confirm dialog.
 */
function MSG(id, params) {
    var map = (typeof window !== 'undefined' && window.UI_MESSAGES) || {};
    var text = Object.prototype.hasOwnProperty.call(map, id) ? map[id] : id;
    if (params) {
        for (var key in params) {
            if (Object.prototype.hasOwnProperty.call(params, key)) {
                // global replace without regex (avoids escaping the value)
                text = text.split('{' + key + '}').join(String(params[key]));
            }
        }
    }
    return text;
}
