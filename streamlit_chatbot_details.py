from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import streamlit as st
from langchain_core.prompts import PromptTemplate

# Configurar la pagina de la app.
st.set_page_config(page_title="Chatbot Básico", page_icon="🤖")
st.title("Chatbot Básico con LangChain")
st.markdown("Este es un chatbot de ejemplo construido con Langchain + streamlit. Escribe tu mensaje abajo para configurar")

with st.sidebar:
    st.header("Configuración")
    temperature = st.slider("Temperatura", 0.0, 1.0, 0.5, 0.1)
    model_name = st.selectbox("Modelo", ["gpt-3.5-turbo", "gpt-4", "gpt-4o-mini"])
    
    # Crear el modelo con los parámetros seleccionados
    try:
        chat_model = ChatOpenAI(model=model_name, temperature=temperature)
    except Exception as e:
        st.error(f"Error al inicializar el modelo: {str(e)}")
        st.info("Verifica que tu API KEY de OpenAI esté configurada correctamente.")
        st.stop()

# Inicializar el historial de mensajes
if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

# Mostrar mensajes previos en la interfaz
for msg in st.session_state.mensajes:
    if isinstance(msg, SystemMessage):
        continue
    role = "assistant" if isinstance(msg, AIMessage) else "user"
    with st.chat_message(role):
        st.markdown(msg.content)

# Cuadro de entrada de texto de usuario
pregunta = st.chat_input("Escribe tu mensaje: ")

if pregunta:
    # Mostrar inmediatamente el mensaje del usuario en la interfaz
    with st.chat_message("user"):
        st.markdown(pregunta)
    
    # Guardar el mensaje del usuario en el historial
    st.session_state.mensajes.append(HumanMessage(content=pregunta))
    
    # Convertir el historial a formato texto para el prompt
    historial_texto = ""
    for msg in st.session_state.mensajes[:-1]:  # Excluir el mensaje actual
        if isinstance(msg, HumanMessage):
            historial_texto += f"Usuario: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            historial_texto += f"Asistente: {msg.content}\n"
    
    prompt_template = PromptTemplate(
        input_variables=["historial", "mensaje"],
        template="""Eres un asistente útil y amigable llamado ChatBot Pro. 
        
        Historial de conversación:
        {historial}
        
        Responde de manera clara y concisa a la siguiente pregunta: {mensaje}"""
    )
    
    cadena = prompt_template | chat_model
    
    # Generar respuesta usando el modelo de lenguaje con manejo de errores
    try:
        # Mostrar indicador de carga mientras se genera la respuesta
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            response_placeholder.markdown("🤔 Pensando...")
        
        # Generar la respuesta
        respuesta = cadena.invoke({"mensaje": pregunta, "historial": historial_texto})
        
        # Mostrar la respuesta en la interfaz
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = respuesta.content  # ✅ Acceder directamente al contenido
            response_placeholder.markdown(full_response)
        
        # Guardar la respuesta en el historial
        st.session_state.mensajes.append(AIMessage(content=full_response))
    
    except Exception as e:
        # Manejo específico de errores comunes
        error_msg = str(e)
        if "API key" in error_msg or "authentication" in error_msg.lower():
            st.error("❌ Error de autenticación: Verifica que tu API KEY de OpenAI esté configurada correctamente.")
            st.info("Puedes configurar tu API KEY como variable de entorno OPENAI_API_KEY o en el código.")
        elif "rate limit" in error_msg.lower():
            st.error("⚠️ Límite de tasa excedido. Espera unos momentos y vuelve a intentar.")
        elif "insufficient_quota" in error_msg.lower():
            st.error("💸 Cuota insuficiente. Verifica tu plan de pago en OpenAI.")
        else:
            st.error(f"❌ Error al generar respuesta: {error_msg}")
            st.info("Verifica tu conexión a internet y que la API KEY sea válida.")
        
        # Eliminar el mensaje del usuario del historial si falló la respuesta
        # para evitar inconsistencias
        if st.session_state.mensajes and isinstance(st.session_state.mensajes[-1], HumanMessage):
            st.session_state.mensajes.pop()
        
