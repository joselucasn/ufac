"""
auth.py - Sistema de autenticacao nativo para o Dashboard UFAC.
SQLite + bcrypt + sessao via st.session_state com timeout.
Audit logs com IP, user_agent, timestamp.
Fiscal ve apenas contratos onde e responsavel.
"""

import sqlite3
import bcrypt
import csv
import streamlit as st
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, List

DB_PATH = Path(__file__).parent / "auth.db"
CSV_PATH = Path(__file__).parent / "planilha_dados.csv"
SESSION_TIMEOUT_MINUTES = 240  # 4 horas
ACRE_TZ = timezone(timedelta(hours=-5))


# ─────────────────────────────── Database ───────────────────────────────

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        fiscal_name TEXT,
        created_at TEXT,
        last_login TEXT,
        active INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        event TEXT NOT NULL,
        ip TEXT,
        user_agent TEXT,
        details TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_audit_user_date
                    ON audit_logs(username, created_at)""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_audit_event_date
                    ON audit_logs(event, created_at)""")
    conn.commit()
    return conn


def _now_ac_str() -> str:
    return datetime.now(ACRE_TZ).isoformat()


def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _check_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False


# ─────────────────────────────── Audit ───────────────────────────────

def audit_log(username: str, event: str, ip: str = "", user_agent: str = "", details: str = ""):
    try:
        conn = _conn()
        try:
            conn.execute(
                "INSERT INTO audit_logs (username, event, ip, user_agent, details, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (username, event, ip, user_agent[:500] if user_agent else "", details, _now_ac_str()),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def audit_list(limit: int = 100) -> list:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT id, username, event, ip, user_agent, details, created_at "
            "FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _get_client_ip() -> str:
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        headers = _get_websocket_headers()
        return headers.get("X-Real-IP", headers.get("X-Forwarded-For", "unknown"))
    except Exception:
        return "unknown"


def _get_user_agent() -> str:
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        headers = _get_websocket_headers()
        return headers.get("User-Agent", "unknown")
    except Exception:
        return "unknown"


# ─────────────────────────────── Contratos por Fiscal ─────────────────

_CONTRACT_CACHE = {}

def get_fiscal_contracts(fiscal_name: str) -> list:
    if not fiscal_name:
        return []
    if fiscal_name in _CONTRACT_CACHE:
        return _CONTRACT_CACHE[fiscal_name]
    if not CSV_PATH.exists():
        return []

    contratos = set()
    try:
        with open(CSV_PATH, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            fcol = None
            ccol = None
            for k in reader.fieldnames or []:
                if "fiscal respons" in k.lower():
                    fcol = k
                if k.strip() == "Contrato":
                    ccol = k
            if not fcol or not ccol:
                return []
            for row in reader:
                f = str(row.get(fcol, "")).strip()
                c = str(row.get(ccol, "")).strip()
                if f and c and f.lower() not in ("nan", "", "none", "-", "n/a"):
                    if fiscal_name.lower() in f.lower() or f.lower() in fiscal_name.lower():
                        contratos.add(c)
    except Exception:
        pass

    result = sorted(contratos)
    _CONTRACT_CACHE[fiscal_name] = result
    return result


# ─────────────────────────────── User CRUD ──────────────────────────────

def _ensure_admin():
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM users WHERE role='admin' AND active=1"
        ).fetchone()
        if row["n"] == 0:
            conn.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, role, fiscal_name, created_at) "
                "VALUES (?, ?, 'admin', 'Jose Lucas', ?)",
                ("joselucas", _hash_pw("Cafus124@#"), _now_ac_str()),
            )
            conn.commit()
    finally:
        conn.close()


def authenticate(username: str, password: str) -> Optional[dict]:
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND active=1",
            (username.strip().lower(),),
        ).fetchone()
        if row is None:
            return None
        if not _check_pw(password, row["password_hash"]):
            return None
        conn.execute(
            "UPDATE users SET last_login=? WHERE id=?",
            (_now_ac_str(), row["id"]),
        )
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def change_password(user_id: int, old_pw: str, new_pw: str) -> tuple:
    if len(new_pw) < 8:
        return False, "Senha deve ter pelo menos 8 caracteres."
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if row is None:
            return False, "Usuario nao encontrado."
        if not _check_pw(old_pw, row["password_hash"]):
            return False, "Senha atual incorreta."
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (_hash_pw(new_pw), user_id),
        )
        conn.commit()
        return True, "Senha alterada com sucesso."
    finally:
        conn.close()


def admin_reset_password(user_id: int, new_pw: str) -> tuple:
    if len(new_pw) < 8:
        return False, "Senha deve ter pelo menos 8 caracteres."
    conn = _conn()
    try:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (_hash_pw(new_pw), user_id),
        )
        conn.commit()
        return True, "Senha redefinida."
    finally:
        conn.close()


def admin_create_user(username: str, password: str, role: str = "user",
                      fiscal_name: str = "") -> tuple:
    username = username.strip().lower()
    if not username or len(password) < 8:
        return False, "Usuario invalido ou senha < 8 caracteres."
    if role not in ("user", "admin"):
        return False, "Papel invalido."
    conn = _conn()
    try:
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, fiscal_name, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, _hash_pw(password), role, fiscal_name, _now_ac_str()),
            )
            conn.commit()
            return True, f"Usuario criado."
        except sqlite3.IntegrityError:
            return False, "Usuario ja existe."
    finally:
        conn.close()


def admin_list_users() -> list:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT id, username, role, fiscal_name, created_at, last_login, active "
            "FROM users ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def admin_toggle_active(user_id: int) -> tuple:
    conn = _conn()
    try:
        conn.execute(
            "UPDATE users SET active = CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=?",
            (user_id,),
        )
        conn.commit()
        return True, "Status alterado."
    finally:
        conn.close()


def admin_delete_user(user_id: int) -> tuple:
    conn = _conn()
    try:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        return True, "Usuario excluido."
    finally:
        conn.close()


# ─────────────────────────────── Session ────────────────────────────────

def _session_timeout_expired() -> bool:
    if "auth_last_active" not in st.session_state:
        return True
    last = st.session_state["auth_last_active"]
    if datetime.now(ACRE_TZ) - last > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        return True
    return False


def _touch_session():
    st.session_state["auth_last_active"] = datetime.now(ACRE_TZ)


def logout():
    u = st.session_state.get("auth_user")
    if u:
        audit_log(u["username"], "logout", _get_client_ip(), _get_user_agent())
    for key in ("auth_user", "auth_last_active", "auth_username"):
        st.session_state.pop(key, None)


def require_auth(render_login_if_needed=True, render_dashboard_fn=None) -> bool:
    if "auth_last_active" in st.session_state:
        st.session_state["auth_last_active"] = datetime.now(ACRE_TZ)

    if "auth_user" in st.session_state and st.session_state["auth_user"]:
        if _session_timeout_expired():
            logout()
            st.session_state["_auth_timeout_msg"] = True
            st.rerun()
        _touch_session()
        return True

    if not render_login_if_needed:
        return False

    _render_login_screen()
    return False


# ─────────────────────────────── Login Screen ───────────────────────────

def _render_login_screen():
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none !important;}
    header[data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 2rem;}
    .login-card {
        background: #1a1a2e; border: 1px solid #2a2a4e; border-radius: 12px;
        padding: 2.5rem 2rem; max-width: 420px; margin: 2rem auto;
        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
    }
    .login-logo {text-align:center; margin-bottom: 1.5rem; font-size: 3rem;}
    .login-title {text-align:center; color:#e0e0e0; font-size:1.4rem; font-weight:700; margin-bottom:1.5rem;}
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns([1, 2, 1])
    with cols[1]:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-logo">⚡</div>'
            '<div class="login-title">Portal UFAC — Vivace Engenharia</div>',
            unsafe_allow_html=True,
        )
        with st.form("login_form", clear_on_submit=False):
            user = st.text_input("Usuario", autocomplete="username").strip().lower()
            pw = st.text_input("Senha", type="password", autocomplete="current-password")
            submit = st.form_submit_button("Entrar", use_container_width=True, type="primary")
            if submit:
                if not user or not pw:
                    st.error("Preencha usuario e senha.")
                else:
                    now = datetime.now(ACRE_TZ)
                    attempts = st.session_state.get("auth_attempts", [])
                    attempts = [t for t in attempts if now - t < timedelta(minutes=1)]
                    if len(attempts) >= 5:
                        st.error("Muitas tentativas. Aguarde 1 minuto.")
                        audit_log(user, "login_blocked_rate", _get_client_ip(), _get_user_agent())
                    else:
                        u = authenticate(user, pw)
                        if u is None:
                            attempts.append(now)
                            st.session_state["auth_attempts"] = attempts
                            st.error("Usuario ou senha incorretos.")
                            audit_log(user, "login_failed", _get_client_ip(), _get_user_agent())
                        else:
                            st.session_state["auth_user"] = u
                            st.session_state["auth_username"] = u["username"]
                            _touch_session()
                            audit_log(u["username"], "login_success", _get_client_ip(), _get_user_agent(),
                                      "role=" + u["role"])
                            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────── Sidebar Menu ───────────────────────────

_EVENT_ICONS = {
    "login_success": "✅",
    "login_failed": "❌",
    "login_blocked_rate": "🚫",
    "logout": "🚪",
    "password_changed": "🔑",
    "admin_user_created": "➕",
    "admin_password_reset": "🔐",
    "admin_user_activated": "🟢",
    "admin_user_deactivated": "🔴",
    "admin_user_deleted": "🗑️",
}


def render_sidebar_menu():
    u = st.session_state.get("auth_user")
    if not u:
        return

    with st.sidebar:
        st.markdown("---")
        fiscal_display = u.get("fiscal_name") or u["username"]
        role_badge = "🔐 Admin" if u["role"] == "admin" else "📋 Fiscal"
        contracts = get_fiscal_contracts(u.get("fiscal_name", ""))
        contract_text = ""
        if contracts and u["role"] != "admin":
            contract_text = " · Contratos: " + ", ".join(contracts)

        col_img, col_name = st.columns([1, 3])
        with col_img:
            st.image("logo_vivace.png", width=60)
        with col_name:
            st.markdown(f"### {fiscal_display}")
        st.caption(f"`{u['username']}` · {role_badge}{contract_text}")

        if u.get("last_login"):
            last = u["last_login"][:16].replace("T", " ")
            st.caption(f"Ultimo login: {last}")
        if "auth_last_active" in st.session_state:
            remaining = SESSION_TIMEOUT_MINUTES - int(
                (datetime.now(ACRE_TZ) - st.session_state["auth_last_active"]).total_seconds() / 60
            )
            st.caption(f"Sessao: ~{remaining}min restantes")

        with st.expander("🔑 Trocar minha senha"):
            with st.form("change_pw"):
                old_pw = st.text_input("Senha atual", type="password", key="pw_old")
                new1 = st.text_input("Nova senha (min. 8)", type="password", key="pw_new1")
                new2 = st.text_input("Confirmar nova senha", type="password", key="pw_new2")
                if st.form_submit_button("Alterar senha"):
                    if new1 != new2:
                        st.error("As senhas nao conferem.")
                    else:
                        ok, msg = change_password(u["id"], old_pw, new1)
                        if ok:
                            audit_log(u["username"], "password_changed", _get_client_ip(), _get_user_agent())
                            st.success(msg)
                        else:
                            st.error(msg)

        if u["role"] == "admin":
            _render_admin_panel()

        st.markdown("---")
        if st.button("🚪 Sair", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()


def _render_admin_panel():
    u = st.session_state.get("auth_user")
    with st.expander("⚙️ Gestao de Usuarios", expanded=False):
        tab_novo, tab_lista, tab_audit = st.tabs(["➕ Novo", "📋 Usuarios", "📜 Logs"])

        with tab_novo:
            with st.form("create_user_form"):
                new_user = st.text_input("Usuario", key="new_u")
                new_pw = st.text_input("Senha (min. 8)", type="password", key="new_pw")
                new_name = st.text_input("Nome do fiscal (deve bater com a planilha)", key="new_name")
                new_role = st.selectbox("Papel", ["user", "admin"], key="new_role")
                if st.form_submit_button("Criar usuario"):
                    ok, msg = admin_create_user(new_user, new_pw, new_role, new_name)
                    if ok:
                        audit_log(u["username"], "admin_user_created", _get_client_ip(), _get_user_agent(),
                                  "new_user=" + new_user + " role=" + new_role)
                        st.success(msg)
                    else:
                        st.error(msg)

        with tab_lista:
            users = admin_list_users()
            if not users:
                st.info("Nenhum usuario cadastrado.")
            for usr in users:
                status = "🟢 ativo" if usr["active"] else "🔴 inativo"
                ctrs = get_fiscal_contracts(usr.get("fiscal_name", ""))
                ctrs_str = " · " + ", ".join(ctrs) if ctrs else ""
                with st.container():
                    c1, c2, c3 = st.columns([3, 2, 2])
                    with c1:
                        name_or_dash = usr.get("fiscal_name") or "—"
                        st.markdown(
                            "<b>" + usr["username"] + "</b> " + status + "<br>"
                            "<small>" + name_or_dash + " · " + usr["role"] + ctrs_str + "</small>",
                            unsafe_allow_html=True,
                        )
                    with c2:
                        new_pw = st.text_input("Redefinir senha", type="password", key="rst_" + str(usr["id"]),
                                               placeholder="Nova senha (8+)")
                        if new_pw and st.button("Salvar", key="save_pw_" + str(usr["id"])):
                            ok, msg = admin_reset_password(usr["id"], new_pw)
                            if ok:
                                audit_log(u["username"], "admin_password_reset", _get_client_ip(), _get_user_agent(),
                                          "target=" + usr["username"])
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    with c3:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            toggle_label = "Desativar" if usr["active"] else "Ativar"
                            if st.button(toggle_label, key="togg_" + str(usr["id"])):
                                admin_toggle_active(usr["id"])
                                evt = "admin_user_deactivated" if usr["active"] else "admin_user_activated"
                                audit_log(u["username"], evt, _get_client_ip(), _get_user_agent(),
                                          "target=" + usr["username"])
                                st.rerun()
                        with col_b:
                            if st.button("🗑️", key="del_" + str(usr["id"])):
                                curr_id = u.get("id")
                                if curr_id == usr["id"]:
                                    st.error("Nao e possivel apagar a si mesmo.")
                                else:
                                    admin_delete_user(usr["id"])
                                    audit_log(u["username"], "admin_user_deleted", _get_client_ip(), _get_user_agent(),
                                              "target=" + usr["username"])
                                    st.rerun()
                st.divider()

        with tab_audit:
            st.markdown("**Ultimos eventos**")
            logs = audit_list(limit=50)
            if not logs:
                st.info("Nenhum evento registrado ainda.")
            else:
                for log in logs:
                    evt_time = log["created_at"][:19].replace("T", " ") if log["created_at"] else "?"
                    icon = _EVENT_ICONS.get(log["event"], "📋")
                    details = log.get("details", "") or ""
                    st.markdown(
                        "`" + evt_time + "` " + icon + " **" + log["event"] + "** — "
                        "`" + log["username"] + "` de `" + str(log.get("ip", "?")) + "` · " + details,
                    )
                    ua = (log.get("user_agent", "") or "")[:80]
                    if ua:
                        st.caption("UA: " + ua)


# ─────────────────────────────── Init ───────────────────────────────────

_ensure_admin()
