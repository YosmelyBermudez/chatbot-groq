from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

chat = ChatOpenAI(model='gpt-4o-mini', temperature=0.7)

plantilla = PromptTemplate(
    input_variables=["nombre"],
    template="Saluda al usuario con su nombre.\n Nombre del usuario: {nombre}\nAsistente: "
)

# Nueva sintaxis con el operador |
chain = plantilla | chat

resultado = chain.invoke({"nombre": "Carlos"})
print(resultado.content)  # Para obtener solo el texto