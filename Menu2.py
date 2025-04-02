import logging
import os
import requests
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Obtén las credenciales de las variables de entorno
username = os.environ.get('DASH_USERNAME')
password = os.environ.get('DASH_PASSWORD')

# Configurar el registro de eventos
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Definir estados de la conversación
MENU, IP_ADDRESS = range(2)

# Función para obtener datos desde la API de SolarWinds
def get_solarwinds_data(query):
    url = f"https://10.78.80.131:17774/SolarWinds/InformationService/v3/Json/Query?query={query}"
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.get(url, auth=(username, password), headers=headers, verify=False)
        if response.status_code == 200:
            return response.json().get('results', [])
        else:
            logger.error(f"Error en la API: {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"Excepción en la petición: {e}")
        return None

# Función para obtener los nodos con mayor uso de CPU
def get_top_cpu():
    query = "SELECT TOP 5 n.NodeID, n.Caption, n.CPULoad FROM Orion.Nodes n  WHERE n.CustomProperties.Ambiente='Produccion' ORDER BY CPULoad DESC"
    return get_solarwinds_data(query)

# Función para obtener los nodos con mayor uso de Memoria
def get_top_memory():
    query = "SELECT TOP 5 n.NodeID, n.Caption, n.PercentMemoryUsed FROM Orion.Nodes n WHERE n.CustomProperties.Ambiente='Produccion'  ORDER BY PercentMemoryUsed DESC"
    return get_solarwinds_data(query)

# Función para obtener información del nodo por IP
def get_node_by_ip(ip_address):
    query = f"""
    SELECT n.NodeId, n.Caption, n.Ip_Address, n.CPULoad, n.PercentMemoryUsed, n.Vendor,n.Customproperties.Servicio,
           ISNULL(CNT, 0) AS ActiveAlertsCount 
    FROM Orion.Nodes n 
    LEFT JOIN (
        SELECT COUNT(AlertActiveID) as CNT, t1.AlertObjects.RelatedNodeId 
        FROM Orion.AlertActive t1 
        GROUP BY t1.AlertObjects.RelatedNodeId
    ) aa ON n.NodeID = aa.RelatedNodeId 
    WHERE n.IP_Address='{ip_address}'"""
    return get_solarwinds_data(query)

# Función para manejar el comando /start

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_message = update.message.text.lower()
    await update.message.reply_text("¡Hola! ¿Qué información necesitas?")
    keyboard = [["Top CPU", "Top Memoria"], ["Buscar Nodo por IP"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Selecciona una opción:", reply_markup=reply_markup)
    return MENU



# Función para manejar la selección del usuario
async def menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_choice = update.message.text
    
    if user_choice == "Top CPU":
        nodes = get_top_cpu()
        if nodes:
            response = "\n".join([f"{node['Caption']} - {node['CPULoad']}%" for node in nodes])
            await update.message.reply_text(f"Top 5 Uso de CPU:\n{response}")
        else:
            await update.message.reply_text("No se pudo obtener la información de CPU.")
    
    elif user_choice == "Top Memoria":
        nodes = get_top_memory()
        if nodes:
            response = "\n".join([f"{node['Caption']} - {node['PercentMemoryUsed']}%" for node in nodes])
            await update.message.reply_text(f"Top 5 Uso de Memoria:\n{response}")
        else:
            await update.message.reply_text("No se pudo obtener la información de Memoria.")
    
    elif user_choice == "Buscar Nodo por IP":
        await update.message.reply_text("Por favor, ingresa la dirección IP del nodo:", reply_markup=ReplyKeyboardRemove())
        return IP_ADDRESS
    
    return ConversationHandler.END

# Función para manejar la entrada de la IP Address
async def ip_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_ip = update.message.text.strip()
    node_info = get_node_by_ip(user_ip)
    if node_info:
        for node in node_info:
            response_text = (f"Servicio: {node.get('Servicio', 'N/A')}\n"
                             f"Caption: {node.get('Caption', 'N/A')}\n"
                             f"IP Address: {node.get('IP_Address', 'N/A')}\n"
                             f"CPU Load: {node.get('CPULoad', 'N/A')} %\n"
                             f"Memory Usage: {node.get('PercentMemoryUsed', 'N/A')} %\n"
                             f"Active Alerts: {node.get('ActiveAlertsCount', 'N/A')}")
                             
            await update.message.reply_text(response_text)
    else:
        await update.message.reply_text("No se encontró información para la IP proporcionada.")
    return ConversationHandler.END

# Función para cancelar la conversación
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Conversación cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Función principal
def main() -> None:
    application = Application.builder().token("6810695007:AAFHlWEdV8M6_5OGEbHAtuJy2Gi_YXWrOPY").build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
        states={
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_selection)],
            IP_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ip_address)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
