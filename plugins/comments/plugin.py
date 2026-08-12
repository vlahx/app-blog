from __future__ import annotations

import logging
from html import escape
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.config import get_telegram_bot_username
from app.core.i18n import get_plugin_translation, resolve_locale
from app.core.plugin_manager import get_plugin_setting
from app.core.template_hooks import register_post_article_footer
from app.core.templates import render_template
from app.utils.auth import get_current_user_from_request, role_required
from plugins.comments.db import (
    add_comment,
    count_comments_for_post,
    delete_comment,
    list_all_comments,
    list_comments_for_post,
    update_comment_status,
)

logger = logging.getLogger(__name__)


def pt(request: Request, key: str, default_val: str = "") -> str:
    loc = getattr(request.state, "locale", None) or resolve_locale(request)
    return get_plugin_translation("comments", loc, key, default_val)


def register(app: FastAPI, plugin_id: str = "comments") -> None:

    @app.post("/api/comments/add", include_in_schema=False)
    async def comments_add(
        request: Request,
        post_slug: str = Form(...),
        content: str = Form(...),
        parent_id: int | None = Form(None),
    ):
        try:
            user = get_current_user_from_request(request)
        except Exception:
            user = getattr(request.state, "current_user", None)
        if not user:
            return JSONResponse(
                {"ok": False, "err": pt(request, "error_auth_required", "Trebuie să fii autentificat cu Telegram pentru a lăsa un comentariu.")},
                status_code=401,
            )

        if user.role == "pending":
            return JSONResponse(
                {"ok": False, "err": pt(request, "error_pending_user", "Contul tău este în așteptare și nu poți posta încă.")},
                status_code=403,
            )

        clean_text = (content or "").strip()
        if not clean_text:
            return JSONResponse({"ok": False, "err": pt(request, "error_empty", "Comentariul nu poate fi gol.")}, status_code=400)
        if len(clean_text) > 2000:
            return JSONResponse({"ok": False, "err": pt(request, "error_too_long", "Comentariul este prea lung (max 2000 caractere).")}, status_code=400)

        auto_approve_setting = get_plugin_setting("comments", "auto_approve", "1")
        status = "approved" if auto_approve_setting in ("1", "true", "True") else "pending"

        author_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"User #{user.id}"
        avatar_url = user.image_url or ""

        comment_data = add_comment(
            post_slug=post_slug.strip(),
            user_id=user.id,
            user_name=author_name,
            user_avatar=avatar_url,
            content=clean_text,
            status=status,
            parent_id=parent_id,
        )

        msg = pt(request, "success_msg", "Comentariul tău a fost adăugat cu succes!") if status == "approved" else pt(request, "pending_msg", "Comentariul a fost trimis spre moderare.")
        return JSONResponse({"ok": True, "msg": msg, "comment": comment_data})

    @app.post("/api/comments/delete", include_in_schema=False)
    async def comments_delete(
        request: Request,
        comment_id: int = Form(...),
    ):
        try:
            user = get_current_user_from_request(request)
        except Exception:
            user = getattr(request.state, "current_user", None)
        if not user:
            return JSONResponse({"ok": False, "err": "Unauthorized"}, status_code=401)

        is_admin_or_editor = user.role in ("admin", "editor")
        ok = delete_comment(comment_id, user_id=user.id, is_admin=is_admin_or_editor)
        if not ok:
            return JSONResponse({"ok": False, "err": pt(request, "error_cannot_delete", "Nu poți șterge acest comentariu.")}, status_code=403)

        return JSONResponse({"ok": True})

    @app.get("/admin/comments", response_class=HTMLResponse)
    @role_required("admin", "editor")
    async def admin_comments_page(request: Request, status: str | None = None):
        comments = list_all_comments(status=status, limit=150)
        templates = getattr(request.app.state, "templates", None)
        if not templates:
            from app.core.templates import build_templates
            templates = build_templates("templates")
        return render_template(
            templates,
            request=request,
            name="admin/comments.html",
            context={
                "title": "Moderare Comentarii",
                "comments": comments,
                "selected_status": status or "all",
            },
        )

    @app.post("/admin/comments/status")
    @role_required("admin", "editor")
    async def admin_comment_update_status(
        request: Request,
        comment_id: int = Form(...),
        new_status: str = Form(...),
    ):
        update_comment_status(comment_id, new_status)
        return RedirectResponse(url="/admin/comments?msg=Status+actualizat!", status_code=303)

    @app.post("/admin/comments/delete")
    @role_required("admin", "editor")
    async def admin_comment_delete(
        request: Request,
        comment_id: int = Form(...),
    ):
        delete_comment(comment_id, is_admin=True)
        return RedirectResponse(url="/admin/comments?msg=Comentariu+șters!", status_code=303)

    def render_single_comment_card(c: dict, user: object, request: Request, is_reply: bool = False) -> str:
        cid = c["id"]
        c_user_id = c["user_id"]
        c_name = escape(c["user_name"])
        c_text = escape(c["content"]).replace("\n", "<br>")
        c_date = c["created_at"]
        c_avatar = escape(c.get("user_avatar") or "")

        txt_delete_btn = pt(request, "delete_btn", "🗑️ Șterge")
        txt_reply_btn = pt(request, "reply_btn", "💬 Răspunde")

        if c_avatar:
            avatar_html = f'<img src="{c_avatar}" alt="{c_name}" class="rounded-circle me-3" width="42" height="42" style="object-fit:cover;">'
        else:
            avatar_html = f'<div class="bg-primary text-white rounded-circle d-flex align-items-center justify-content-center fw-bold me-3" style="width:42px;height:42px;flex-shrink:0;">{c_name[0].upper()}</div>'

        can_delete = user and (user.id == c_user_id or getattr(user, "role", "") in ("admin", "editor"))
        del_btn_html = f'<button type="button" class="btn btn-sm btn-link text-danger text-decoration-none p-0" onclick="deleteComment({cid})" title="{txt_delete_btn}">{txt_delete_btn}</button>' if can_delete else ""
        reply_btn_html = f'<button type="button" class="btn btn-sm btn-link text-primary text-decoration-none p-0 ms-2" onclick="initReply({cid}, &quot;{c_name}&quot;)" title="{txt_reply_btn}">{txt_reply_btn}</button>' if user else ""

        border_class = "border-start border-3 border-primary" if is_reply else "border"
        margin_class = "ms-4 ms-md-5 mt-2" if is_reply else ""

        html = []
        html.append(f'<div class="card {border_class} {margin_class} shadow-sm p-3 rounded-3 mb-3" id="comment-{cid}">')
        html.append(f'  <div class="d-flex align-items-center mb-2">')
        html.append(f'    {avatar_html}')
        html.append(f'    <div>')
        html.append(f'      <div class="fw-bold text-body">{c_name}</div>')
        html.append(f'      <div class="small text-secondary">{c_date}</div>')
        html.append(f'    </div>')
        html.append(f'    <div class="ms-auto d-flex align-items-center gap-2">')
        html.append(f'      {reply_btn_html}')
        html.append(f'      {del_btn_html}')
        html.append(f'    </div>')
        html.append(f'  </div>')
        html.append(f'  <div class="text-body ms-5 ps-2">{c_text}</div>')

        # Render nested replies
        replies = c.get("replies", [])
        if replies:
            html.append('  <div class="replies-list mt-3">')
            for r in replies:
                html.append(render_single_comment_card(r, user, request, is_reply=True))
            html.append('  </div>')

        html.append(f'</div>')
        return "".join(html)

    def render_comments_widget(post: object, request: Request) -> str:
        slug = getattr(post, "slug", "")
        if not slug:
            return ""

        try:
            user = get_current_user_from_request(request)
        except Exception:
            user = getattr(request.state, "current_user", None)

        comments = list_comments_for_post(slug, status="approved")
        
        # Calculate total comments including replies
        def count_all(items):
            tot = 0
            for item in items:
                tot += 1 + count_all(item.get("replies", []))
            return tot
            
        count = count_all(comments)

        bot_username = get_telegram_bot_username() or ""
        origin = request.url.scheme + "://" + request.url.netloc
        current_path = request.url.path
        auth_next_url = f"{origin}/admin/login/telegram?next={quote(current_path)}"

        txt_title = pt(request, "title", "💬 Comentarii")
        txt_no_comments = pt(request, "no_comments", "Fii primul care lasă un comentariu la acest articol!")
        txt_placeholder = pt(request, "placeholder", "Scrie un comentariu respectuos...")
        txt_submit = pt(request, "submit_btn", "🚀 Publică Comentariul")
        txt_login_title = pt(request, "login_prompt_title", "💬 Alătură-te conversației")
        txt_login_desc = pt(request, "login_prompt_desc", "Autentifică-te rapid cu contul tău de Telegram pentru a lăsa un comentariu.")
        txt_comment_as = pt(request, "comment_as", "Comentezi ca")
        txt_logout = pt(request, "logout", "Deconectare")
        txt_delete_confirm = pt(request, "delete_confirm", "Ești sigur că vrei să ștergi acest comentariu?")
        txt_sending = pt(request, "sending", "Se trimite...")
        txt_replying_to = pt(request, "replying_to", "Răspunzi lui")
        txt_cancel_reply = pt(request, "cancel_reply", "Anulează")

        html = [
            '<section id="comments-section" class="mt-5 pt-4 border-top">',
            '  <div class="d-flex justify-content-between align-items-center mb-4">',
            f'    <h3 class="h4 fw-bold mb-0">{txt_title} (<span id="comments-count">{count}</span>)</h3>',
            '  </div>',
        ]

        html.append('<div id="comments-list" class="d-flex flex-column gap-2 mb-4">')
        if not comments:
            html.append(f'<div id="no-comments-msg" class="text-muted fst-italic py-3">{txt_no_comments}</div>')
        else:
            for c in comments:
                html.append(render_single_comment_card(c, user, request, is_reply=False))

        html.append('</div>')

        if user and getattr(user, "role", "") != "pending":
            u_name = escape(f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "User")
            u_avatar = escape(user.image_url or "")
            if u_avatar:
                u_avatar_html = f'<img src="{u_avatar}" alt="{u_name}" class="rounded-circle me-2" width="32" height="32">'
            else:
                u_avatar_html = f'<span class="badge bg-primary rounded-circle p-2 me-2">{u_name[0].upper()}</span>'

            html.append('<div class="card card-modern p-4 border shadow-sm rounded-3" id="comment-form-card">')
            html.append('  <div class="d-flex align-items-center mb-3">')
            html.append(f'    {u_avatar_html}')
            html.append(f'    <span class="fw-semibold text-body">{txt_comment_as} <strong>{u_name}</strong></span>')
            html.append(f'    <a href="/admin/logout" class="btn btn-sm btn-outline-secondary ms-auto py-0 px-2" style="font-size:0.8rem">{txt_logout}</a>')
            html.append('  </div>')
            html.append('  <div id="reply-indicator" class="alert alert-info py-2 px-3 mb-3 d-none align-items-center justify-content-between small">')
            html.append(f'    <span>↪ {txt_replying_to} <strong id="reply-author-name"></strong></span>')
            html.append(f'    <button type="button" class="btn-close ms-2" style="font-size:0.7rem;" onclick="cancelReply()" title="{txt_cancel_reply}"></button>')
            html.append('  </div>')
            html.append('  <form id="comment-form" onsubmit="postComment(event)">')
            html.append(f'    <input type="hidden" id="comment-post-slug" value="{slug}">')
            html.append('    <input type="hidden" id="comment-parent-id" value="">')
            html.append('    <div class="mb-3">')
            html.append(f'      <textarea id="comment-text" class="form-control" rows="3" placeholder="{txt_placeholder}" required></textarea>')
            html.append('    </div>')
            html.append('    <div class="d-flex justify-content-between align-items-center">')
            html.append('      <span id="comment-form-status" class="small text-secondary"></span>')
            html.append(f'      <button type="submit" id="comment-submit-btn" class="btn btn-primary fw-semibold px-4">{txt_submit}</button>')
            html.append('    </div>')
            html.append('  </form>')
            html.append('</div>')
        else:
            html.append('<div class="card border p-4 text-center rounded-3 shadow-sm">')
            html.append(f'  <h5 class="fw-bold mb-2">{txt_login_title}</h5>')
            html.append(f'  <p class="text-secondary mb-3">{txt_login_desc}</p>')
            html.append('  <div class="d-flex justify-content-center align-items-center gap-2">')
            html.append(f'    <script async src="https://telegram.org/js/telegram-widget.js?22" data-telegram-login="{bot_username}" data-size="large" data-auth-url="{auth_next_url}" data-request-access="write"></script>')
            html.append('  </div>')
            html.append('</div>')

        html.append("</section>")

        html.append(f'''
        <script>
        function initReply(commentId, authorName) {{
            const parentInput = document.getElementById('comment-parent-id');
            const indicator = document.getElementById('reply-indicator');
            const authorSpan = document.getElementById('reply-author-name');
            const txtInput = document.getElementById('comment-text');
            const formCard = document.getElementById('comment-form-card');

            if (parentInput && indicator && authorSpan) {{
                parentInput.value = commentId;
                authorSpan.textContent = authorName;
                indicator.classList.remove('d-none');
                indicator.classList.add('d-flex');
                if (formCard) formCard.scrollIntoView({{ behavior: 'smooth' }});
                if (txtInput) txtInput.focus();
            }}
        }}

        function cancelReply() {{
            const parentInput = document.getElementById('comment-parent-id');
            const indicator = document.getElementById('reply-indicator');
            if (parentInput && indicator) {{
                parentInput.value = '';
                indicator.classList.remove('d-flex');
                indicator.classList.add('d-none');
            }}
        }}

        async function postComment(e) {{
            e.preventDefault();
            const slugInput = document.getElementById('comment-post-slug');
            const parentInput = document.getElementById('comment-parent-id');
            const txtInput = document.getElementById('comment-text');
            const btn = document.getElementById('comment-submit-btn');
            const status = document.getElementById('comment-form-status');

            const slug = slugInput ? slugInput.value : '';
            const parentId = parentInput ? parentInput.value : '';
            const text = (txtInput.value || '').trim();

            if (!text || !slug) return;

            btn.disabled = true;
            status.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> {txt_sending}';

            const formData = new FormData();
            formData.append('post_slug', slug);
            formData.append('content', text);
            if (parentId) {{
                formData.append('parent_id', parentId);
            }}

            try {{
                const res = await fetch('/api/comments/add', {{
                    method: 'POST',
                    body: formData
                }});
                const data = await res.json();
                if (data.ok) {{
                    txtInput.value = '';
                    cancelReply();
                    status.innerHTML = '<span class="text-success fw-semibold">✅ ' + (data.msg || 'Done!') + '</span>';
                    setTimeout(() => {{ window.location.reload(); }}, 600);
                }} else {{
                    status.innerHTML = '<span class="text-danger fw-semibold">❌ ' + (data.err || 'Error') + '</span>';
                    btn.disabled = false;
                }}
            }} catch (err) {{
                status.innerHTML = '<span class="text-danger fw-semibold">❌ Network error. Try again.</span>';
                btn.disabled = false;
            }}
        }}

        async function deleteComment(cid) {{
            if (!confirm('{txt_delete_confirm}')) return;
            const formData = new FormData();
            formData.append('comment_id', cid);

            try {{
                const res = await fetch('/api/comments/delete', {{
                    method: 'POST',
                    body: formData
                }});
                const data = await res.json();
                if (data.ok) {{
                    window.location.reload();
                }} else {{
                    alert(data.err || 'Error deleting comment');
                }}
            }} catch(e) {{
                alert('Server error');
            }}
        }}
        </script>
        ''')

        return "\n".join(html)

    register_post_article_footer(render_comments_widget)
