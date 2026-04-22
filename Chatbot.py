import streamlit as st
import os
import json
import sqlite3
import uuid
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import PromptTemplate

st.set_page_config(page_title="Chatbot Personal", page_icon="🤖", layout="wide")
st.title("🤖 Chatbot")
st.markdown("💡 **Tus conversaciones son privadas** - Cada dispositivo tiene su propio espacio")

# ============================================
# BASE DE DATOS CON MIGRACIÓN
# ============================================
def init_database():
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    
    # Crear tabla si no existe (estructura base)
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
    
    conn.commit()
    conn.close()

def migrar_base_datos():
    """Actualiza la base de datos de versión anterior a la nueva"""
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    
    # Verificar columnas existentes
    c.execute("PRAGMA table_info(conversaciones)")
    columnas = [columna[1] for columna in c.fetchall()]
    
    # Agregar columna dispositivo_id si no existe
    if 'dispositivo_id' not in columnas:
        try:
            # Si existe usuario_id, renombrarla
            if 'usuario_id' in columnas:
                c.execute("ALTER TABLE conversaciones RENAME COLUMN usuario_id TO dispositivo_id")
                st.info("📀 Base de datos actualizada: usuario_id → dispositivo_id")
            else:
                # Si no existe ninguna, crear nueva
                c.execute("ALTER TABLE conversaciones ADD COLUMN dispositivo_id TEXT")
                st.info("📀 Base de datos actualizada: columna dispositivo_id agregada")
        except Exception as e:
            st.warning(f"Nota: {e}")
    
    conn.commit()
    conn.close()

def get_dispositivo_id():
    """
    ID ÚNICO y PRIVADO por navegador/dispositivo.
    NO aparece en la URL.
    """
    if "dispositivo_id" in st.session_state and st.session_state.dispositivo_id:
        return st.session_state.dispositivo_id
    
    nuevo_id = str(uuid.uuid4())[:16]
    st.session_state.dispositivo_id = nuevo_id
    return nuevo_id

def guardar_conversacion(dispositivo_id, session_id, mensajes, modelo):
    if not mensajes:
        return
    
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Generar título
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
    
    # Usar dispositivo_id (nuevo nombre)
    c.execute("SELECT id FROM conversaciones WHERE dispositivo_id = ? AND session_id = ?", 
              (dispositivo_id, session_id))
    existe = c.fetchone()
    
    if existe:
        c.execute("""UPDATE conversaciones 
                     SET fecha_actualizacion = ?, mensajes = ?, modelo_usado = ?, 
                         ultimo_mensaje = ?, titulo = ?
                     WHERE dispositivo_id = ? AND session_id = ?""",
                  (ahora, mensajes_json, modelo, ultimo, titulo, dispositivo_id, session_id))
    else:
        c.execute("""INSERT INTO conversaciones 
                     (dispositivo_id, session_id, titulo, fecha_creacion, fecha_actualizacion, 
                      mensajes, modelo_usado, ultimo_mensaje) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (dispositivo_id, session_id, titulo, ahora, ahora, mensajes_json, modelo, ultimo))
    
    conn.commit()
    conn.close()

def cargar_conversacion(dispositivo_id, session_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("SELECT mensajes FROM conversaciones WHERE dispositivo_id = ? AND session_id = ?", 
              (dispositivo_id, session_id))
    resultado = c.fetchone()
    conn.close()
    
    if resultado:
        mensajes_json = json.loads(resultado[0])
        return [HumanMessage(content=m['content']) if m['role'] == 'user' 
                else AIMessage(content=m['content']) for m in mensajes_json]
    return []

def listar_conversaciones(dispositivo_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("""SELECT session_id, titulo, fecha_actualizacion, modelo_usado, ultimo_mensaje 
                 FROM conversaciones 
                 WHERE dispositivo_id = ? 
                 ORDER BY fecha_actualizacion DESC""", (dispositivo_id,))
    conversaciones = c.fetchall()
    conn.close()
    return conversaciones

def eliminar_conversacion(dispositivo_id, session_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("DELETE FROM conversaciones WHERE dispositivo_id = ? AND session_id = ?", 
              (dispositivo_id, session_id))
    conn.commit()
    conn.close()

def eliminar_todas(dispositivo_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("DELETE FROM conversaciones WHERE dispositivo_id = ?", (dispositivo_id,))
    conn.commit()
    conn.close()

# ============================================
# CONFIGURACIÓN
# ============================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    try:
        if "GROQ_API_KEY" in st.secrets:
            GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    except:
        pass

if not GROQ_API_KEY:
    st.error("""
    ❌ **No se encontró la API Key de Groq**
    
    **Configúrala con:**
    - `setx GROQ_API_KEY "tu-key"` (Windows)
    - O en Streamlit Cloud: Settings → Secrets
    """)
    st.stop()

MODELOS_GROQ = {
    "🐪 Llama 3.3 70B": {"id": "llama-3.3-70b-versatile", "desc": "Muy potente"},
    "⚡ Llama 3.1 8B": {"id": "llama-3.1-8b-instant", "desc": "El más rápido"},
    "🦙 Llama 4 Maverick 17B": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "desc": "Nuevo modelo"},
    "🚀 Llama 4 Scout 17B": {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "desc": "Contexto 131K"},
    "🧠 Qwen QwQ 32B": {"id": "qwen-qwq-32b", "desc": "Razonamiento"},
    "💻 Qwen Coder 32B": {"id": "qwen-2.5-coder-32b", "desc": "Programación"},
    "🎯 Mixtral 8x7B": {"id": "mixtral-8x7b-32768", "desc": "Contexto enorme"},
}

PROMPT_PERSONALIDAD = """Eres un asistente con personalidad. Elige tu nombre y preséntate.

Historial:
{historial}

Mensaje: {mensaje}

Respuesta natural:"""

# ============================================
# INICIALIZACIÓN
# ============================================
init_database()
migrar_base_datos()  # ← CRÍTICO: Actualiza la base de datos

DISPOSITIVO_ID = get_dispositivo_id()

# Gestión de conversación actual
if "session_actual" not in st.session_state:
    st.session_state.session_actual = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    st.session_state.mensajes = []
else:
    mensajes_cargados = cargar_conversacion(DISPOSITIVO_ID, st.session_state.session_actual)
    if mensajes_cargados:
        st.session_state.mensajes = mensajes_cargados
    else:
        st.session_state.mensajes = []

if "modelo_seleccionado" not in st.session_state:
    st.session_state.modelo_seleccionado = "🐪 Llama 3.3 70B"

# ============================================
# AUTO-GUARDADO
# ============================================
def auto_guardar():
    if st.session_state.mensajes:
        guardar_conversacion(
            DISPOSITIVO_ID, 
            st.session_state.session_actual, 
            st.session_state.mensajes, 
            st.session_state.modelo_seleccionado
        )

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.info("🔒 **Conversaciones 100% privadas**")
    st.caption("✅ Cada dispositivo tiene su propio espacio")
    st.caption("✅ Compartir el enlace NO da acceso a tus conversaciones")
    st.divider()
    
    if st.button("➕ Nueva conversación", use_container_width=True, type="primary"):
        auto_guardar()
        st.session_state.mensajes = []
        st.session_state.session_actual = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        st.rerun()
    
    st.divider()
    
    st.header("📚 Tus conversaciones")
    conversaciones = listar_conversaciones(DISPOSITIVO_ID)
    
    if conversaciones:
        for session_id, titulo, fecha, modelo, preview in conversaciones:
            is_current = (session_id == st.session_state.session_actual)
            emoji = "👉 " if is_current else "   "
            
            if st.button(f"{emoji}{titulo[:35]}", key=f"btn_{session_id}", use_container_width=True):
                if not is_current:
                    auto_guardar()
                    st.session_state.mensajes = cargar_conversacion(DISPOSITIVO_ID, session_id)
                    st.session_state.session_actual = session_id
                    st.rerun()
            st.caption(f"📅 {fecha[:16]} | {preview[:30] if preview else 'Nueva'}")
    else:
        st.info("💬 Empieza a chatear")
    
    st.divider()
    
    with st.expander("⚙️ Configuración"):
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
    
    with st.expander("🗑️ Borrar"):
        if conversaciones:
            if st.button("🗑️ Eliminar TODAS", type="primary"):
                eliminar_todas(DISPOSITIVO_ID)
                st.session_state.mensajes = []
                st.rerun()
            
            st.markdown("---")
            borrar_id = st.selectbox("Seleccionar", 
                                     options=[(s, t) for s, t, _, _, _ in conversaciones],
                                     format_func=lambda x: x[1][:40])
            if borrar_id and st.button("🗑️ Eliminar esta"):
                eliminar_conversacion(DISPOSITIVO_ID, borrar_id[0])
                if st.session_state.session_actual == borrar_id[0]:
                    st.session_state.mensajes = []
                st.rerun()

# ============================================
# CHAT PRINCIPAL
# ============================================
prompt_template = PromptTemplate(
    input_variables=["mensaje", "historial"],
    template=PROMPT_PERSONALIDAD
)

if 'chat_model' in locals() and chat_model:
    cadena = prompt_template | chat_model

for msg in st.session_state.mensajes:
    role = "assistant" if isinstance(msg, AIMessage) else "user"
    with st.chat_message(role):
        st.markdown(msg.content)

if not st.session_state.mensajes:
    with st.chat_message("assistant"):
        st.markdown("👋 ¡Hola! Cuéntame, ¿de qué quieres hablar?")

pregunta = st.chat_input("Escribe tu mensaje...")

if pregunta and 'cadena' in locals():
    with st.chat_message("user"):
        st.markdown(pregunta)
    
    try:
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            
            historial = "\n".join([
                f"{'Usuario' if isinstance(msg, HumanMessage) else 'Asistente'}: {msg.content}" 
                for msg in st.session_state.mensajes[-10:]
            ])
            
            for chunk in cadena.stream({"mensaje": pregunta, "historial": historial}):
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
st.caption("🔒 **Privacidad total** - Cada dispositivo tiene sus propias conversaciones")