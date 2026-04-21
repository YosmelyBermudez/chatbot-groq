import streamlit as st
import os
import json
import sqlite3
import hashlib
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import PromptTemplate

st.set_page_config(page_title="Chatbot con Personalidad", page_icon="🤖", layout="wide")

# ============================================
# BASE DE DATOS
# ============================================
def init_database():
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS conversaciones
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  usuario_id TEXT,
                  session_id TEXT,
                  titulo TEXT,
                  fecha_creacion TEXT,
                  fecha_actualizacion TEXT,
                  mensajes TEXT,
                  modelo_usado TEXT,
                  ultimo_mensaje TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS preferencias_usuario
                 (usuario_id TEXT PRIMARY KEY,
                  avatar_style TEXT,
                  avatar_seed TEXT,
                  avatar_vibe TEXT,
                  bot_name TEXT,
                  tema TEXT,
                  color_acento TEXT,
                  color_fondo TEXT)''')
    conn.commit()
    conn.close()

def get_usuario_id():
    if "uid" in st.query_params and st.query_params["uid"]:
        return st.query_params["uid"]
    nuevo_id = hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:16]
    st.query_params["uid"] = nuevo_id
    return nuevo_id

def guardar_preferencias(usuario_id, prefs):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("""INSERT INTO preferencias_usuario 
                 (usuario_id, avatar_style, avatar_seed, avatar_vibe, bot_name, tema, color_acento, color_fondo)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                 ON CONFLICT(usuario_id) DO UPDATE SET
                 avatar_style=excluded.avatar_style,
                 avatar_seed=excluded.avatar_seed,
                 avatar_vibe=excluded.avatar_vibe,
                 bot_name=excluded.bot_name,
                 tema=excluded.tema,
                 color_acento=excluded.color_acento,
                 color_fondo=excluded.color_fondo""",
              (usuario_id, prefs['avatar_style'], prefs['avatar_seed'], prefs['avatar_vibe'],
               prefs['bot_name'], prefs['tema'], prefs['color_acento'], prefs['color_fondo']))
    conn.commit()
    conn.close()

def cargar_preferencias(usuario_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("SELECT * FROM preferencias_usuario WHERE usuario_id = ?", (usuario_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'avatar_style': row[1],
            'avatar_seed':  row[2],
            'avatar_vibe':  row[3],
            'bot_name':     row[4],
            'tema':         row[5],
            'color_acento': row[6],
            'color_fondo':  row[7],
        }
    return None

def guardar_conversacion(usuario_id, session_id, mensajes, modelo):
    if not mensajes:
        return
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    titulo = "Nueva conversación"
    for msg in mensajes:
        if isinstance(msg, HumanMessage):
            titulo = msg.content[:40].replace("?", "").strip()
            break
    mensajes_json = json.dumps([{
        'role': 'user' if isinstance(msg, HumanMessage) else 'assistant',
        'content': msg.content
    } for msg in mensajes])
    ultimo = mensajes[-1].content[:50] + "..." if len(mensajes[-1].content) > 50 else mensajes[-1].content
    c.execute("SELECT id FROM conversaciones WHERE usuario_id = ? AND session_id = ?", (usuario_id, session_id))
    existe = c.fetchone()
    if existe:
        c.execute("""UPDATE conversaciones 
                     SET fecha_actualizacion=?, mensajes=?, modelo_usado=?, ultimo_mensaje=?, titulo=?
                     WHERE usuario_id=? AND session_id=?""",
                  (ahora, mensajes_json, modelo, ultimo, titulo, usuario_id, session_id))
    else:
        c.execute("""INSERT INTO conversaciones 
                     (usuario_id, session_id, titulo, fecha_creacion, fecha_actualizacion, mensajes, modelo_usado, ultimo_mensaje) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (usuario_id, session_id, titulo, ahora, ahora, mensajes_json, modelo, ultimo))
    conn.commit()
    conn.close()

def cargar_conversacion(usuario_id, session_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("SELECT mensajes FROM conversaciones WHERE usuario_id=? AND session_id=?", (usuario_id, session_id))
    resultado = c.fetchone()
    conn.close()
    if resultado:
        mensajes_json = json.loads(resultado[0])
        return [HumanMessage(content=m['content']) if m['role'] == 'user'
                else AIMessage(content=m['content']) for m in mensajes_json]
    return []

def listar_conversaciones(usuario_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("""SELECT session_id, titulo, fecha_actualizacion, modelo_usado, ultimo_mensaje 
                 FROM conversaciones WHERE usuario_id=? ORDER BY fecha_actualizacion DESC""", (usuario_id,))
    conversaciones = c.fetchall()
    conn.close()
    return conversaciones

def eliminar_conversacion(usuario_id, session_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("DELETE FROM conversaciones WHERE usuario_id=? AND session_id=?", (usuario_id, session_id))
    conn.commit()
    conn.close()

def eliminar_todas(usuario_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("DELETE FROM conversaciones WHERE usuario_id=?", (usuario_id,))
    conn.commit()
    conn.close()

# ============================================
# PERSONAJES — organizados por inspiración
# ============================================
PERSONAJES = [
    # ── Bridgerton vibe ──────────────────────────────────────────
    {"style": "adventurer",  "seed": "daphne",    "nombre": "Daphne",    "vibe": "Bridgerton · romántica y brillante",      "categoria": "Bridgerton"},
    {"style": "adventurer",  "seed": "benedict",  "nombre": "Benedict",  "vibe": "Bridgerton · artista y soñador",          "categoria": "Bridgerton"},
    {"style": "adventurer",  "seed": "penelope",  "nombre": "Penelope",  "vibe": "Bridgerton · escritora y observadora",    "categoria": "Bridgerton"},
    {"style": "lorelei",     "seed": "eloise",    "nombre": "Eloise",    "vibe": "Bridgerton · rebelde e intelectual",      "categoria": "Bridgerton"},
    {"style": "lorelei",     "seed": "anthony",   "nombre": "Anthony",   "vibe": "Bridgerton · serio y apasionado",         "categoria": "Bridgerton"},
    {"style": "personas",    "seed": "kate",      "nombre": "Kate",      "vibe": "Bridgerton · fuerte y decidida",          "categoria": "Bridgerton"},

    # ── Mamma Mia / mediterráneo ──────────────────────────────────
    {"style": "lorelei",     "seed": "sophia",    "nombre": "Sophie",    "vibe": "Mamma Mia · alegre y soñadora",           "categoria": "Mamma Mia"},
    {"style": "adventurer",  "seed": "donna99",   "nombre": "Donna",     "vibe": "Mamma Mia · libre y vital",               "categoria": "Mamma Mia"},
    {"style": "open-peeps",  "seed": "sam77",     "nombre": "Sam",       "vibe": "Mamma Mia · romántico y nostálgico",      "categoria": "Mamma Mia"},
    {"style": "lorelei",     "seed": "rosie22",   "nombre": "Rosie",     "vibe": "Mamma Mia · divertida y leal",            "categoria": "Mamma Mia"},

    # ── One Piece vibe ────────────────────────────────────────────
    {"style": "pixel-art",   "seed": "zoro55",    "nombre": "Zoro",      "vibe": "One Piece · guerrero sin dirección",      "categoria": "One Piece"},
    {"style": "pixel-art",   "seed": "nami88",    "nombre": "Nami",      "vibe": "One Piece · navegante astuta",            "categoria": "One Piece"},
    {"style": "pixel-art",   "seed": "luffy11",   "nombre": "Luffy",     "vibe": "One Piece · capitán sin límites",         "categoria": "One Piece"},
    {"style": "pixel-art",   "seed": "robin44",   "nombre": "Robin",     "vibe": "One Piece · arqueóloga misteriosa",       "categoria": "One Piece"},
    {"style": "pixel-art",   "seed": "sanji66",   "nombre": "Sanji",     "vibe": "One Piece · cocinero caballero",          "categoria": "One Piece"},
    {"style": "pixel-art",   "seed": "chopper33", "nombre": "Chopper",   "vibe": "One Piece · doctor adorable",             "categoria": "One Piece"},

    # ── Los Simpsons vibe ─────────────────────────────────────────
    {"style": "fun-emoji",   "seed": "homer99",   "nombre": "Homer",     "vibe": "Simpsons · simple y entrañable",          "categoria": "Simpsons"},
    {"style": "fun-emoji",   "seed": "marge55",   "nombre": "Marge",     "vibe": "Simpsons · paciente y amorosa",           "categoria": "Simpsons"},
    {"style": "fun-emoji",   "seed": "bart77",    "nombre": "Bart",      "vibe": "Simpsons · rebelde y travieso",           "categoria": "Simpsons"},
    {"style": "fun-emoji",   "seed": "lisa22",    "nombre": "Lisa",      "vibe": "Simpsons · inteligente y sensible",       "categoria": "Simpsons"},
    {"style": "miniavs",     "seed": "burns11",   "nombre": "Burns",     "vibe": "Simpsons · excéntrico y poderoso",        "categoria": "Simpsons"},
    {"style": "miniavs",     "seed": "ned33",     "nombre": "Ned",       "vibe": "Simpsons · amable y formalito",           "categoria": "Simpsons"},

    # ── Futurama vibe ─────────────────────────────────────────────
    {"style": "bottts-neutral", "seed": "bender44", "nombre": "Bender",  "vibe": "Futurama · robot irreverente",            "categoria": "Futurama"},
    {"style": "bottts-neutral", "seed": "fry88",    "nombre": "Fry",     "vibe": "Futurama · despistado del futuro",        "categoria": "Futurama"},
    {"style": "bottts-neutral", "seed": "zoidberg", "nombre": "Zoidberg","vibe": "Futurama · médico caótico",               "categoria": "Futurama"},
    {"style": "rings",          "seed": "leela77",  "nombre": "Leela",   "vibe": "Futurama · piloto de élite",              "categoria": "Futurama"},
    {"style": "rings",          "seed": "amy66",    "nombre": "Amy",     "vibe": "Futurama · heredera despistada",          "categoria": "Futurama"},
    {"style": "bottts-neutral", "seed": "prof22",   "nombre": "Profesor","vibe": "Futurama · científico chiflado",          "categoria": "Futurama"},

    # ── The Gentlemen vibe ────────────────────────────────────────
    {"style": "notionists",  "seed": "mickey99",  "nombre": "Mickey",    "vibe": "The Gentlemen · rey del hampa elegante",  "categoria": "The Gentlemen"},
    {"style": "notionists",  "seed": "raymond11", "nombre": "Raymond",   "vibe": "The Gentlemen · mano derecha leal",       "categoria": "The Gentlemen"},
    {"style": "micah",       "seed": "coach44",   "nombre": "Coach",     "vibe": "The Gentlemen · mente criminal aguda",    "categoria": "The Gentlemen"},
    {"style": "micah",       "seed": "susie66",   "nombre": "Susie",     "vibe": "The Gentlemen · fría y calculadora",      "categoria": "The Gentlemen"},
    {"style": "notionists",  "seed": "stanley77", "nombre": "Stanley",   "vibe": "The Gentlemen · aristócrata corrompido",  "categoria": "The Gentlemen"},
]

# Paletas de color por categoría
TEMAS = {
    "Bridgerton":     {"acento": "#8B5E9B", "fondo": "#F5EEF8", "nombre": "Regencia púrpura"},
    "Mamma Mia":      {"acento": "#E8873A", "fondo": "#FEF9F0", "nombre": "Mediterráneo cálido"},
    "One Piece":      {"acento": "#D63031", "fondo": "#FFF5F5", "nombre": "Pirata rojo"},
    "Simpsons":       {"acento": "#F5A623", "fondo": "#FFFBF0", "nombre": "Springfield amarillo"},
    "Futurama":       {"acento": "#0984E3", "fondo": "#EBF5FB", "nombre": "Siglo XXXI azul"},
    "The Gentlemen":  {"acento": "#2D3436", "fondo": "#F2F3F4", "nombre": "Mayfair oscuro"},
}

# Estilos de avatar disponibles
AVATAR_STYLES = {
    "adventurer": "🧑 Aventurero",
    "lorelei": "👩 Lorelei",
    "personas": "😊 Personas",
    "open-peeps": "🎭 Open Peeps",
    "pixel-art": "🕹️ Pixel Art",
    "fun-emoji": "😄 Fun Emoji",
    "miniavs": "🎨 Mini Avatars",
    "bottts-neutral": "🤖 Bottts",
    "rings": "💍 Anillos",
    "notionists": "📝 Notionists",
    "micah": "👤 Micah",
}

# ============================================
# CONFIGURACIÓN
# ============================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    st.error("❌ Configura GROQ_API_KEY con: setx GROQ_API_KEY 'tu-key'")
    st.stop()

MODELOS_GROQ = {
    "🐪 Llama 3.3 70B":   {"id": "llama-3.3-70b-versatile",        "desc": "Muy potente"},
    "⚡ Llama 3.1 8B":    {"id": "llama-3.1-8b-instant",           "desc": "El más rápido"},
    "🔬 DeepSeek R1 70B": {"id": "deepseek-r1-distill-llama-70b",  "desc": "Razonamiento"},
    "🧠 Qwen QwQ 32B":    {"id": "qwen-qwq-32b",                   "desc": "Explicaciones"},
    "📝 Gemma 2 9B":      {"id": "gemma2-9b-it",                   "desc": "Equilibrado"},
    "🎯 Mixtral 8x7B":    {"id": "mixtral-8x7b-32768",             "desc": "Contexto enorme"},
    "💻 Qwen Coder 32B":  {"id": "qwen-2.5-coder-32b",             "desc": "Programación"},
}

# ============================================
# INICIALIZACIÓN
# ============================================
init_database()
USUARIO_ID = get_usuario_id()

# Cargar preferencias guardadas
if "preferencias" not in st.session_state:
    prefs_guardadas = cargar_preferencias(USUARIO_ID)
    if prefs_guardadas:
        st.session_state.preferencias = prefs_guardadas
    else:
        # Por defecto: primer personaje
        p = PERSONAJES[0]
        st.session_state.preferencias = {
            "avatar_style": p["style"],
            "avatar_seed":  p["seed"],
            "avatar_vibe":  p["vibe"],
            "bot_name":     p["nombre"],
            "tema":         p["categoria"],
            "color_acento": TEMAS[p["categoria"]]["acento"],
            "color_fondo":  TEMAS[p["categoria"]]["fondo"],
        }

# Cargar conversación
if "conv" not in st.query_params or not st.query_params["conv"]:
    nueva_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    st.query_params["conv"] = nueva_id
    st.session_state.session_actual = nueva_id
    st.session_state.mensajes = []
else:
    session_id = st.query_params["conv"]
    st.session_state.session_actual = session_id
    mensajes_cargados = cargar_conversacion(USUARIO_ID, session_id)
    st.session_state.mensajes = mensajes_cargados if mensajes_cargados else []

if "modelo_seleccionado" not in st.session_state:
    st.session_state.modelo_seleccionado = "🐪 Llama 3.3 70B"

# ============================================
# CSS DINÁMICO según preferencias
# ============================================
prefs = st.session_state.preferencias
acento  = prefs["color_acento"]
fondo   = prefs["color_fondo"]
bot_name = prefs["bot_name"]

st.markdown(f"""
<style>
    /* Fondo general */
    .stApp {{
        background-color: {fondo} !important;
    }}

    /* Título principal */
    h1 {{
        color: {acento} !important;
        font-family: 'Georgia', serif !important;
    }}

    /* Burbujas del asistente */
    [data-testid="stChatMessageContent"] {{
        border-left: 3px solid {acento} !important;
    }}

    /* Input del chat */
    .stChatInput textarea {{
        border: 1.5px solid {acento} !important;
        border-radius: 12px !important;
        background-color: white !important;
    }}
    .stChatInput textarea:focus {{
        box-shadow: 0 0 0 2px {acento}44 !important;
    }}

    /* Botones primarios */
    .stButton > button[kind="primary"] {{
        background-color: {acento} !important;
        border-color: {acento} !important;
        color: white !important;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: white !important;
        border-right: 2px solid {acento}33 !important;
    }}

    /* Avatar del bot en el chat — mostrar imagen DiceBear */
    [data-testid="stChatMessageAvatarAssistant"] {{
        background-image: url('https://api.dicebear.com/9.x/{prefs["avatar_style"]}/svg?seed={prefs["avatar_seed"]}') !important;
        background-size: cover !important;
        background-color: {fondo} !important;
        border: 2px solid {acento} !important;
        border-radius: 50% !important;
    }}
    [data-testid="stChatMessageAvatarAssistant"] > * {{
        display: none !important;
    }}

    /* Separadores */
    hr {{
        border-color: {acento}33 !important;
    }}

    /* Tabs y expanders */
    .stExpander summary {{
        color: {acento} !important;
    }}

    /* Caption y texto secundario */
    .stCaption {{
        color: {acento}99 !important;
    }}

    /* Scrollbar */
    ::-webkit-scrollbar-thumb {{
        background-color: {acento}66 !important;
        border-radius: 4px;
    }}
</style>
""", unsafe_allow_html=True)

# ============================================
# TÍTULO con avatar
# ============================================
avatar_url = f"https://api.dicebear.com/9.x/{prefs['avatar_style']}/svg?seed={prefs['avatar_seed']}&size=60"
st.markdown(f"""
<div style="display:flex; align-items:center; gap:16px; margin-bottom:8px;">
    <img src="{avatar_url}" style="width:56px;height:56px;border-radius:50%;border:2px solid {acento};background:{fondo}"/>
    <div>
        <h1 style="margin:0;font-size:26px;">Hola, soy {bot_name}</h1>
        <p style="margin:0;color:{acento}99;font-size:13px;">{prefs.get('avatar_vibe', prefs.get('vibe', ''))}</p>
    </div>
</div>
""", unsafe_allow_html=True)
st.markdown("💡 **Tus conversaciones se guardan automáticamente**")

# ============================================
# AUTO-GUARDADO
# ============================================
def auto_guardar():
    if st.session_state.mensajes:
        guardar_conversacion(USUARIO_ID, st.session_state.session_actual,
                             st.session_state.mensajes, st.session_state.modelo_seleccionado)

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.info(f"🔗 Tu ID: `{USUARIO_ID[:8]}...`")
    st.caption("💡 Comparte el enlace completo para mantener tus conversaciones")
    st.divider()

    if st.button("➕ Nueva conversación", use_container_width=True, type="primary"):
        auto_guardar()
        nueva_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        st.session_state.mensajes = []
        st.session_state.session_actual = nueva_id
        st.query_params["conv"] = nueva_id
        st.rerun()

    st.divider()

    # ── Selector de personaje y avatar ────────────────────────────
    with st.expander("🎭 Cambiar personaje y avatar"):
        categorias = list(TEMAS.keys())
        cat_sel = st.selectbox("Serie", categorias,
                               index=categorias.index(prefs["tema"]) if prefs["tema"] in categorias else 0)

        personajes_cat = [p for p in PERSONAJES if p["categoria"] == cat_sel]
        nombres = [p["nombre"] for p in personajes_cat]

        idx_actual = 0
        for i, p in enumerate(personajes_cat):
            if p["nombre"] == prefs["bot_name"]:
                idx_actual = i
                break

        per_sel = st.selectbox("Personaje", nombres, index=idx_actual)
        personaje = next(p for p in personajes_cat if p["nombre"] == per_sel)

        # Preview del personaje
        prev_url = f"https://api.dicebear.com/9.x/{personaje['style']}/svg?seed={personaje['seed']}&size=80"
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"""
            <img src="{prev_url}" style="width:64px;height:64px;border-radius:50%;
            border:2px solid {TEMAS[cat_sel]['acento']};background:{TEMAS[cat_sel]['fondo']}"/>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"**{personaje['nombre']}**")
            st.caption(personaje['vibe'])

        nombre_custom = st.text_input("Nombre personalizado (opcional)", value=personaje["nombre"])
        
        # ── SELECTOR DE AVATAR ────────────────────────────────────
        st.markdown("---")
        st.markdown("**🎨 Personaliza el avatar**")
        
        # Obtener el style actual (puede ser del personaje o personalizado)
        avatar_style_actual = st.session_state.get("avatar_style_temp", prefs.get("avatar_style", personaje["style"]))
        avatar_seed_actual = st.session_state.get("avatar_seed_temp", prefs.get("avatar_seed", personaje["seed"]))
        
        # Selector de estilo
        style_options = list(AVATAR_STYLES.keys())
        style_labels = list(AVATAR_STYLES.values())
        
        try:
            style_idx = style_options.index(avatar_style_actual)
        except:
            style_idx = 0
        
        avatar_style = st.selectbox(
            "Estilo de avatar",
            options=style_options,
            format_func=lambda x: AVATAR_STYLES[x],
            index=style_idx,
            key="avatar_style_selector"
        )
        
        # Input para el seed (permite personalización total)
        avatar_seed = st.text_input(
            "Identificador del avatar (cambia el diseño)",
            value=avatar_seed_actual,
            help="Escribe cualquier texto para generar un avatar único",
            key="avatar_seed_input"
        )
        
        # Guardar temporalmente en session_state
        st.session_state.avatar_style_temp = avatar_style
        st.session_state.avatar_seed_temp = avatar_seed
        
        # Preview del avatar personalizado
        preview_avatar_url = f"https://api.dicebear.com/9.x/{avatar_style}/svg?seed={avatar_seed}&size=100"
        st.markdown(f"""
        <div style="text-align:center;margin:16px 0;">
            <p style="margin:0 0 8px 0;color:{TEMAS[cat_sel]['acento']};font-size:12px;">Vista previa:</p>
            <img src="{preview_avatar_url}" 
                 style="width:80px;height:80px;border-radius:50%;
                 border:3px solid {TEMAS[cat_sel]['acento']};
                 background:{TEMAS[cat_sel]['fondo']};
                 box-shadow:0 4px 8px rgba(0,0,0,0.1);"/>
        </div>
        """, unsafe_allow_html=True)
        
        st.caption("💡 Prueba diferentes identificadores para encontrar el avatar perfecto")

        if st.button("✅ Aplicar personaje y avatar", use_container_width=True, type="primary"):
            nuevas_prefs = {
                "avatar_style": avatar_style,
                "avatar_seed":  avatar_seed,
                "avatar_vibe":  personaje["vibe"],
                "bot_name":     nombre_custom or personaje["nombre"],
                "tema":         cat_sel,
                "color_acento": TEMAS[cat_sel]["acento"],
                "color_fondo":  TEMAS[cat_sel]["fondo"],
            }
            st.session_state.preferencias = nuevas_prefs
            guardar_preferencias(USUARIO_ID, nuevas_prefs)
            # Limpiar temporales
            if "avatar_style_temp" in st.session_state:
                del st.session_state.avatar_style_temp
            if "avatar_seed_temp" in st.session_state:
                del st.session_state.avatar_seed_temp
            st.success("¡Guardado! Recargando...")
            st.rerun()

    # ── Conversaciones ────────────────────────────────────────────
    st.header("📚 Tus conversaciones")
    conversaciones = listar_conversaciones(USUARIO_ID)

    if conversaciones:
        for session_id, titulo, fecha, modelo, preview in conversaciones:
            is_current = (session_id == st.session_state.session_actual)
            emoji = "👉 " if is_current else "   "
            if st.button(f"{emoji}{titulo[:35]}", key=f"btn_{session_id}", use_container_width=True):
                if not is_current:
                    auto_guardar()
                    st.session_state.mensajes = cargar_conversacion(USUARIO_ID, session_id)
                    st.session_state.session_actual = session_id
                    st.query_params["conv"] = session_id
                    st.rerun()
            st.caption(f"📅 {fecha[:16]} | {preview[:30] if preview else 'Nueva'}")
    else:
        st.info("💬 Empieza a chatear")

    st.divider()

    # ── Modelo y configuración ────────────────────────────────────
    with st.expander("⚙️ Configuración del modelo"):
        modelo = st.selectbox("Modelo", list(MODELOS_GROQ.keys()), key="modelo_select")
        st.session_state.modelo_seleccionado = modelo
        temperature = st.slider("Creatividad", 0.0, 1.0, 0.7)

        try:
            chat_model = ChatGroq(
                api_key=GROQ_API_KEY,
                model=MODELOS_GROQ[modelo]["id"],
                temperature=temperature
            )
            st.success(f"✅ {modelo}")
        except Exception as e:
            st.error(f"Error: {e}")
            chat_model = None

    # ── Borrar ────────────────────────────────────────────────────
    with st.expander("🗑️ Borrar conversaciones"):
        if conversaciones:
            if st.button("🗑️ Eliminar TODAS", type="primary"):
                eliminar_todas(USUARIO_ID)
                st.session_state.mensajes = []
                st.rerun()
            st.markdown("---")
            borrar_id = st.selectbox("Seleccionar",
                                     options=[(s, t) for s, t, _, _, _ in conversaciones],
                                     format_func=lambda x: x[1][:40])
            if borrar_id and st.button("🗑️ Eliminar esta"):
                eliminar_conversacion(USUARIO_ID, borrar_id[0])
                if st.session_state.session_actual == borrar_id[0]:
                    st.session_state.mensajes = []
                st.rerun()

# ============================================
# PROMPT con personalidad del personaje
# ============================================
PROMPT_PERSONALIDAD = """Eres {bot_name}, un asistente con la personalidad de: {vibe}.
Habla de forma natural y coherente con ese personaje. No rompas el personaje.
Sé útil, entretenido y mantén tu esencia.

Historial:
{historial}

Mensaje del usuario: {mensaje}

Respuesta como {bot_name}:"""

prompt_template = PromptTemplate(
    input_variables=["bot_name", "vibe", "mensaje", "historial"],
    template=PROMPT_PERSONALIDAD
)

if 'chat_model' in locals() and chat_model:
    cadena = prompt_template | chat_model

# ============================================
# CHAT PRINCIPAL
# ============================================
for msg in st.session_state.mensajes:
    role = "assistant" if isinstance(msg, AIMessage) else "user"
    with st.chat_message(role):
        st.markdown(msg.content)

if not st.session_state.mensajes:
    with st.chat_message("assistant"):
        vibe_actual = prefs.get("avatar_vibe", prefs.get("vibe", ""))
        st.markdown(f"👋 ¡Hola! Soy **{bot_name}** — {vibe_actual}. ¿De qué quieres hablar?")

pregunta = st.chat_input(f"Escribe a {bot_name}...")

if pregunta and 'cadena' in locals():
    with st.chat_message("user"):
        st.markdown(pregunta)

    try:
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""

            historial = "\n".join([
                f"{'Usuario' if isinstance(msg, HumanMessage) else bot_name}: {msg.content}"
                for msg in st.session_state.mensajes[-10:]
            ])

            for chunk in cadena.stream({
                "bot_name": bot_name,
                "vibe": prefs.get("avatar_vibe", prefs.get("vibe", "")),
                "mensaje": pregunta,
                "historial": historial
            }):
                if chunk.content:
                    full_response += chunk.content
                    response_placeholder.markdown(full_response + "▌")

            response_placeholder.markdown(full_response)

        st.session_state.mensajes.append(HumanMessage(content=pregunta))
        st.session_state.mensajes.append(AIMessage(content=full_response))
        auto_guardar()

    except Exception as e:
        st.error(f"Error: {e}")

st.markdown("---")
st.caption(f"💾 Guardado automático · 🎭 Personaje: {bot_name} · 🎨 Tema: {prefs['tema']}")