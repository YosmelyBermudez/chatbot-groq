import streamlit as st
import os
import json
import sqlite3
import hashlib
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import PromptTemplate

st.set_page_config(page_title="Chatbot Personal", page_icon="🤖", layout="wide")
st.title("🤖 Chatbot")
st.markdown("💡 **Tus conversaciones se guardan automáticamente**")

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
    conn.commit()
    conn.close()

def get_usuario_id():
    """ID persistente en la URL"""
    if "uid" in st.query_params and st.query_params["uid"]:
        return st.query_params["uid"]
    
    nuevo_id = hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:16]
    st.query_params["uid"] = nuevo_id
    return nuevo_id

def guardar_conversacion(usuario_id, session_id, mensajes, modelo):
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
    
    c.execute("SELECT id FROM conversaciones WHERE usuario_id = ? AND session_id = ?", 
              (usuario_id, session_id))
    existe = c.fetchone()
    
    if existe:
        c.execute("""UPDATE conversaciones 
                     SET fecha_actualizacion = ?, mensajes = ?, modelo_usado = ?, 
                         ultimo_mensaje = ?, titulo = ?
                     WHERE usuario_id = ? AND session_id = ?""",
                  (ahora, mensajes_json, modelo, ultimo, titulo, usuario_id, session_id))
    else:
        c.execute("""INSERT INTO conversaciones 
                     (usuario_id, session_id, titulo, fecha_creacion, fecha_actualizacion, 
                      mensajes, modelo_usado, ultimo_mensaje) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (usuario_id, session_id, titulo, ahora, ahora, mensajes_json, modelo, ultimo))
    
    conn.commit()
    conn.close()

def cargar_conversacion(usuario_id, session_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("SELECT mensajes FROM conversaciones WHERE usuario_id = ? AND session_id = ?", 
              (usuario_id, session_id))
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
                 FROM conversaciones 
                 WHERE usuario_id = ? 
                 ORDER BY fecha_actualizacion DESC""", (usuario_id,))
    conversaciones = c.fetchall()
    conn.close()
    return conversaciones

def eliminar_conversacion(usuario_id, session_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("DELETE FROM conversaciones WHERE usuario_id = ? AND session_id = ?", 
              (usuario_id, session_id))
    conn.commit()
    conn.close()

def eliminar_todas(usuario_id):
    conn = sqlite3.connect('conversaciones.db')
    c = conn.cursor()
    c.execute("DELETE FROM conversaciones WHERE usuario_id = ?", (usuario_id,))
    conn.commit()
    conn.close()

# ============================================
# CONFIGURACIÓN
# ============================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    st.error("❌ Configura GROQ_API_KEY con: setx GROQ_API_KEY 'tu-key'")
    st.stop()

MODELOS_GROQ = {
    "🐪 Llama 3.3 70B": {
        "id": "llama-3.3-70b-versatile", 
        "desc": "Muy potente, ideal para tareas complejas"
    },
    "⚡ Llama 3.1 8B": {
        "id": "llama-3.1-8b-instant", 
        "desc": "El más rápido, perfecto para chat"
    },
    "🦙 Llama 4 Maverick 17B": {
        "id": "meta-llama/llama-4-maverick-17b-128e-instruct", 
        "desc": "Nuevo modelo de Meta, 600 tokens/seg"
    },
    "🚀 Llama 4 Scout 17B": {
        "id": "meta-llama/llama-4-scout-17b-16e-instruct", 
        "desc": "Contexto 131K tokens, 750 tokens/seg"
    },
    "🧠 Qwen QwQ 32B": {
        "id": "qwen-qwq-32b", 
        "desc": "Explicaciones paso a paso, razonamiento"
    },
    "💻 Qwen Coder 32B": {
        "id": "qwen-2.5-coder-32b", 
        "desc": "Especializado en programación"
    },
    "🎯 Mixtral 8x7B": {
        "id": "mixtral-8x7b-32768", 
        "desc": "Contexto enorme (32K tokens)"
    },
}

PROMPT_PERSONALIDAD = """Eres un asistente con personalidad. Elige tu nombre y preséntate.

Historial:
{historial}

Mensaje: {mensaje}

Respuesta natural:"""

# ============================================
# INICIALIZACIÓN - CRÍTICO: CARGAR CONVERSACIÓN
# ============================================
init_database()
USUARIO_ID = get_usuario_id()

# --- IMPORTANTE: Cargar la conversación correcta al iniciar ---
# Primero, obtener la conversación actual desde la URL o crear una nueva
if "conv" not in st.query_params or not st.query_params["conv"]:
    # No hay conversación en la URL, crear nueva
    nueva_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    st.query_params["conv"] = nueva_id
    st.session_state.session_actual = nueva_id
    st.session_state.mensajes = []
else:
    # Hay una conversación en la URL
    session_id = st.query_params["conv"]
    st.session_state.session_actual = session_id
    
    # Cargar los mensajes desde la base de datos
    mensajes_cargados = cargar_conversacion(USUARIO_ID, session_id)
    if mensajes_cargados:
        st.session_state.mensajes = mensajes_cargados
    else:
        st.session_state.mensajes = []

# Asegurar que modelo_seleccionado existe en session_state
if "modelo_seleccionado" not in st.session_state:
    st.session_state.modelo_seleccionado = "🐪 Llama 3.3 70B"

# ============================================
# AUTO-GUARDADO
# ============================================
def auto_guardar():
    if st.session_state.mensajes:
        guardar_conversacion(
            USUARIO_ID, 
            st.session_state.session_actual, 
            st.session_state.mensajes, 
            st.session_state.modelo_seleccionado
        )

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.info(f"🔗 Tu ID: `{USUARIO_ID[:8]}...`")
    st.caption("💡 Comparte el enlace completo para mantener tus conversaciones")
    st.divider()
    
    # Nueva conversación
    if st.button("➕ Nueva conversación", use_container_width=True, type="primary"):
        auto_guardar()
        nueva_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        st.session_state.mensajes = []
        st.session_state.session_actual = nueva_id
        st.query_params["conv"] = nueva_id
        st.rerun()
    
    st.divider()
    
    # Lista de conversaciones
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
    
    # Configuración
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
    
    # Borrar
    with st.expander("🗑️ Borrar"):
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
# CHAT PRINCIPAL
# ============================================
prompt_template = PromptTemplate(
    input_variables=["mensaje", "historial"],
    template=PROMPT_PERSONALIDAD
)

if 'chat_model' in locals() and chat_model:
    cadena = prompt_template | chat_model

# Mostrar mensajes
for msg in st.session_state.mensajes:
    role = "assistant" if isinstance(msg, AIMessage) else "user"
    with st.chat_message(role):
        st.markdown(msg.content)

if not st.session_state.mensajes:
    with st.chat_message("assistant"):
        st.markdown("👋 ¡Hola! Cuéntame, ¿de qué quieres hablar?")

# Input
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
st.caption("💾 **Guardado automático** | 🔄 **Recarga la página y tus conversaciones siguen aquí**")