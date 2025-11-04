# app.py
import json
import re
import os  # <-- Importante para las variables de entorno
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template

# ------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------
# Leemos la API Key desde las variables de entorno de Render
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# El archivo FAQ debe estar en la misma carpeta que app.py
FAQ_ARCHIVO = "faq.json" 

# ------------------------------------------------------------
# LÓGICA "CEREBRO" (Tu Celda 3 - Lógica central intacta)
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
        return {} # Devuelve un dict vacío para evitar que todo falle
    except json.JSONDecodeError:
        print(f"Error fatal: El archivo '{FAQ_ARCHIVO}' no es un JSON válido.")
        return {}

def consultar_ia_gemini(pregunta_usuario, faq_dict):
    """Envía la pregunta + FAQ como contexto a Gemini. (Función 100% original)"""
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
    """Encuentra preguntas similares. (Lógica original, salida modificada para la API)"""
    palabras_usuario = set(re.findall(r'\w+', consulta_usuario.lower()))
    coincidencias = []
    for categoria, preguntas in faq.items():
        for pregunta, respuesta in preguntas.items():
            palabras_pregunta = set(re.findall(r'\w+', pregunta.lower()))
            comunes = len(palabras_usuario & palabras_pregunta)
            if comunes >= umbral:
                # Guardamos (comunes, categoria, pregunta, respuesta)
                coincidencias.append((comunes, categoria, pregunta, respuesta))
    
    coincidencias.sort(key=lambda x: x[0], reverse=True)
    
    # Devolvemos un formato útil para la API: una lista de diccionarios
    sugerencias_formateadas = []
    for _, cat, preg, resp in coincidencias[:max_sugerencias]:
        sugerencias_formateadas.append({"categoria": cat, "pregunta": preg, "respuesta": resp})
    
    return sugerencias_formateadas

# ------------------------------------------------------------
# LÓGICA DE SERVIDOR WEB (El reemplazo de 'main')
# ------------------------------------------------------------

app = Flask(__name__)

# Cargamos el FAQ una sola vez cuando el servidor se inicia
FAQ_GLOBAL = cargar_faq()

@app.route("/")
def index():
    """Sirve la página principal del chat (el archivo index.html)"""
    # Flask busca automáticamente en la carpeta 'templates'
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def manejar_chat():
    """
    Este es el "endpoint" de la API. Recibe un JSON con el mensaje del usuario
    y decide qué hacer, imitando tu lógica de 'procesar_sugerencias'.
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
        # 1. Imitamos 'procesar_sugerencias': Buscamos similares
        sugerencias = encontrar_preguntas_similares(FAQ_GLOBAL, consulta)
        
        if sugerencias:
            # Enviamos las sugerencias al frontend
            return jsonify({
                "tipo_respuesta": "sugerencias",
                "sugerencias": sugerencias,
                "consulta_original": consulta # Devolvemos la consulta por si la necesitamos
            })
        else:
            # Si no hay sugerencias, pasamos directo a la IA
            tipo = "ia" 
            
    if tipo == "ia":
        # 2. Imitamos la Opción 'C' o 'derivar_con_sugerencias'
        print(f"Enviando consulta a Gemini: {consulta}") # Log para el servidor
        respuesta_ia = consultar_ia_gemini(consulta, FAQ_GLOBAL)
        return jsonify({
            "tipo_respuesta": "ia",
            "respuesta": respuesta_ia
        })

# Esto permite que Flask se inicie (necesario para Render)
if __name__ == "__main__":
    # El puerto lo asignará Render automáticamente
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))