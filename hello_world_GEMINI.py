from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model='gemini-2.5-flash',temperature=0.7)
pregunta = '¿ Qué año llegó el ser humano a la luna por primera vez?'
print('Pregunta: ',pregunta)

respuesta= llm.invoke(pregunta)
print('Respuesta del modelo: ',respuesta.content)
