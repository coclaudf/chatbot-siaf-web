# app.py
import json
import re
import os
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template

# ------------------------------------------------------------
# CONFIGURACIÓN (EXISTENTE)
# ------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FAQ_ARCHIVO = "faq.json" 

# ------------------------------------------------------------
# LÓGICA "CEREBRO" (EXISTENTE)
# ------------------------------------------------------------

# Configurar la API una sola vez al iniciar el servidor
if not GEMINI_API_KEY:
    print("Error fatal: La variable de entorno GEMINI_API_KEY no está configurada.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        modelo_ia = genai.GenerativeModel('gemini-2.5-flash-lite')
        print("API de Gemini configurada exitosamente.")
    except Exception as e:
        print(f"Error fatal al configurar la API de Gemini: {e}")

def cargar_faq():
    """Carga el FAQ desde un archivo local."""
    try:
        with open(FAQ_ARCHIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error fatal: No se encontró el archivo '{FAQ_ARCHIVO}'")
        return {} 
    except json.JSONDecodeError:
        print(f"Error fatal: El archivo '{FAQ_ARCHIVO}' no es un JSON válido.")
        return {}

def consultar_ia_gemini(pregunta_usuario, faq_dict):
    """(Función 100% original)"""
    contexto_faq = ""
    for categoria, preguntas in faq_dict.items():
        contexto_faq += f"\n## {categoria}\n"
        for p, r in preguntas.items():
            contexto_faq += f"P: {p}\nR: {r}\n"

    prompt = (
        "Eres un asistente oficial del Sistema Integrado de Administración Financiera (SIAF) "
        "de la provincia, gestionado por la Contaduría General. "
        "Responde la siguiente consulta utilizando la información del contexto proporcionado. "
        "Si el contexto no contiene la respuesta, responde con precisión basada en buenas prácticas "
        "administrativas y normativa contable/financiera provincial. "
        "Mantén un tono formal, claro y útil.\n\n"
        "=== CONTEXTO DEL SISTEMA (FAQ OFICIAL) ===\n"
        f"{contexto_faq}\n"
        "=== FIN DEL CONTEXTO ===\n\n"
        f"Consulta del usuario:\n{pregunta_usuario}\n\n"
        "Respuesta:"
    )

    try:
        respuesta = modelo_ia.generate_content(prompt)
        return respuesta.text
    except Exception as e:
        return f"⚠️ No fue posible obtener una respuesta. Error: {str(e)}"

def encontrar_preguntas_similares(faq, consulta_usuario, umbral=1, max_sugerencias=5):
    """(Función 100% original en su LÓGICA)"""
    palabras_usuario = set(re.findall(r'\w+', consulta_usuario.lower()))
    coincidencias = []
    for categoria, preguntas in faq.items():
        for pregunta, respuesta in preguntas.items():
            palabras_pregunta = set(re.findall(r'\w+', pregunta.lower()))
            comunes = len(palabras_usuario & palabras_pregunta)
            if comunes >= umbral:
                coincidencias.append((comunes, categoria, pregunta, respuesta))
    
    coincidencias.sort(key=lambda x: x[0], reverse=True)
    
    sugerencias_formateadas = []
    for _, cat, preg, resp in coincidencias[:max_sugerencias]:
        sugerencias_formateadas.append({"categoria": cat, "pregunta": preg, "respuesta": resp})
    
    return sugerencias_formateadas

# ------------------------------------------------------------
# LÓGICA DE SERVIDOR WEB (EXISTENTE + NUEVAS RUTAS)
# ------------------------------------------------------------

app = Flask(__name__)

# Cargamos el FAQ una sola vez cuando el servidor se inicia
FAQ_GLOBAL = cargar_faq()

@app.route("/")
def index():
    """Sirve la página principal del chat (el archivo index.html)"""
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def manejar_chat():
    """
    Esta ruta (EXISTENTE) se usa para la BÚSQUEDA LIBRE (sugerencias) y
    la escalada a la IA.
    """
    if not FAQ_GLOBAL:
        return jsonify({"error": "El servidor no pudo cargar el archivo FAQ."}), 500
    if not GEMINI_API_KEY:
         return jsonify({"error": "El servidor no tiene configurada la API Key."}), 500

    datos = request.json
    consulta = datos.get("mensaje")
    tipo = datos.get("tipo", "sugerencias") # "sugerencias" o "ia"

    if not consulta:
        return jsonify({"error": "No se recibió ningún mensaje."}), 400

    if tipo == "sugerencias":
        sugerencias = encontrar_preguntas_similares(FAQ_GLOBAL, consulta)
        if sugerencias:
            return jsonify({
                "tipo_respuesta": "sugerencias",
                "sugerencias": sugerencias,
                "consulta_original": consulta
            })
        else:
            tipo = "ia" # Si no hay sugerencias, pasa directo a la IA
            
    if tipo == "ia":
        print(f"Enviando consulta a Gemini: {consulta}") 
        respuesta_ia = consultar_ia_gemini(consulta, FAQ_GLOBAL)
        return jsonify({
            "tipo_respuesta": "ia",
            "respuesta": respuesta_ia
        })

# ------------------------------------------------------------
# ¡NUEVAS RUTAS PARA EL FLUJO DE CATEGORÍAS!
# ------------------------------------------------------------

@app.route("/get_initial_data", methods=["GET"])
def get_initial_data():
    """
    Envía el saludo inicial y la lista de categorías principales
    para que el frontend las muestre como botones.
    """
    if not FAQ_GLOBAL:
        return jsonify({"error": "El servidor no pudo cargar el archivo FAQ."}), 500
        
    categorias = list(FAQ_GLOBAL.keys())
    return jsonify({
        "saludo": "¡Hola! 👋 Soy el asistente del SIAF. Puedes seleccionar una categoría o escribirme tu consulta directamente.",
        "categorias": categorias
    })

@app.route("/get_questions", methods=["POST"])
def get_questions():
    """
    Dado un nombre de categoría, devuelve la lista de preguntas
    para esa categoría.
    """
    datos = request.json
    categoria_nombre = datos.get("categoria")
    
    if not categoria_nombre or categoria_nombre not in FAQ_GLOBAL:
        return jsonify({"error": "Categoría no válida."}), 400
        
    preguntas = list(FAQ_GLOBAL[categoria_nombre].keys())
    return jsonify({
        "categoria": categoria_nombre,
        "preguntas": preguntas
    })

@app.route("/get_answer", methods=["POST"])
def get_answer():
    """
    Dada una categoría y una pregunta, devuelve la respuesta final.
    """
    datos = request.json
    categoria = datos.get("categoria")
    pregunta = datos.get("pregunta")
    
    if not categoria or not pregunta or categoria not in FAQ_GLOBAL or pregunta not in FAQ_GLOBAL[categoria]:
        return jsonify({"error": "Pregunta o categoría no válida."}), 400
        
    respuesta = FAQ_GLOBAL[categoria][pregunta]
    return jsonify({
        "respuesta": respuesta
    })

# ------------------------------------------------------------

# Esto permite que Flask se inicie
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)