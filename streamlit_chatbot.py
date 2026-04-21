from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import streamlit as st

# Configurar la pagina de la app.
st.set_page_config(page_title="Chatbot Básico",page_icon="🤖")
st.title("Chatbot Básico con LangChain")
st.markdown("Este es un chatbot de ejemplo construido con Langchain + streamlit. Escribe tu mensaje abajo para configurar")

chat_model= ChatOpenAI(model="gpt-4o-mini",temperature=0.5)

#Inicializar el historial de mensajes
if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

# Mostrar mensajes previos en la interfaz
for msg in st.session_state.mensajes:
    if isinstance(msg, SystemMessage):
        #No muestro el mensaje por pantalla
        continue
    role = "assistant" if isinstance(msg,AIMessage) else "user"

    with st.chat_message(role):
        st.markdown(msg.content)

# Cuadro de entrada de texto de usuario
pregunta = st.chat_input("Escribe tu mensaje: ")

if pregunta:
    #Mostrar inmediatamente el mensaje del usuario en la interfaz
    with st.chat_message("user"):
        st.markdown(pregunta)
    # Almacenamos el mensaje en la memoria de streamlit
    st.session_state.mensajes.append(HumanMessage(content=pregunta))
    #Generar respuesta usando el modelo de lenguaje

    respuesta= chat_model.invoke(st.session_state.mensajes)

    #Mostrar la respuesta en la interfaz
    with st.chat_message("assistant"):
        st.markdown(respuesta.content)

    st.session_state.mensajes.append(respuesta)
