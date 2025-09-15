import mysql.connector
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
import locale
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Configuração de logging para depuração
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configurações de Idioma ---
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    logger.warning("Locale 'pt_BR.UTF-8' não disponível. Usando o padrão do sistema.")

# --- Credenciais de Ambiente ---
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_RECEIVER = os.getenv('EMAIL_RECEIVER')

# --- Configurações do Banco de Dados MySQL ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_DATABASE', 'clinica_bot')
}

# --- Dicionários para Armazenar Dados (Temporário) ---
conversas_em_andamento = {}

# --- Funções de Validação ---
def validar_data(data_str):
    try:
        data_agendamento = datetime.strptime(data_str, '%d/%m/%Y').date()
        if data_agendamento < datetime.now().date():
            return False, "A data deve ser igual ou posterior à data de hoje."
        return True, None
    except ValueError:
        return False, "Formato de data inválido. Por favor, use o formato dd/mm/aaaa."

def validar_horario(horario_str):
    try:
        datetime.strptime(horario_str, '%H:%M')
        return True
    except ValueError:
        return False

# --- Funções do Chatbot ---
def enviar_email(assunto, corpo):
    try:
        msg = MIMEText(corpo)
        msg['Subject'] = assunto
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar o e-mail: {e}")
        return False

# --- Configuração do NLP ---
faq_data = [
    ("Qual o horário de funcionamento?", "horario"), ("A que horas vocês abrem?", "horario"),
    ("Qual o horário da clínica?", "horario"), ("Vocês funcionam de sábado?", "horario"),
    ("Que horas a clínica fecha?", "horario"), ("Quais especialidades vocês oferecem?", "especialidade"),
    ("Me diga as especialidades da clínica.", "especialidade"), ("Quais médicos estão disponíveis?", "especialidade"),
    ("Qual a especialidade de vocês?", "especialidade"), ("Vocês aceitam plano de saúde?", "plano_saude"),
    ("Aceitam convênio?", "plano_saude"), ("Quais convênios são aceitos?", "plano_saude"),
    ("A Unimed é aceita?", "plano_saude"), ("Vocês trabalham com a SulAmérica?", "plano_saude")
]

X_train = [item[0] for item in faq_data]
y_train = [item[1] for item in faq_data]

nlp_model = Pipeline([
    ('vectorizer', TfidfVectorizer(lowercase=True)),
    ('classifier', MultinomialNB())
])

nlp_model.fit(X_train, y_train)

# --- Funções de Gestão de Agendamentos ---
async def minhas_consultas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todas as consultas do usuário."""
    user_id = update.effective_user.id
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, especialidade, data, horario, medico FROM agendamentos WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        consultas = cursor.fetchall()
        cursor.close()
        conn.close()

        if not consultas:
            await update.message.reply_text('Você não tem nenhuma consulta agendada.')
            return

        response_text = "Suas consultas agendadas:\n\n"
        for consulta in consultas:
            response_text += (
                f"ID: `{consulta['id']}`\n"
                f"Especialidade: {consulta['especialidade']}\n"
                f"Médico: Dr(a). {consulta['medico']}\n"
                f"Data: {consulta['data']} às {consulta['horario']}\n\n"
            )
        response_text += "Use o comando `/cancelar [ID]` para cancelar uma consulta. Ex: `/cancelar 123`"
        await update.message.reply_text(response_text)
    except mysql.connector.Error as err:
        await update.message.reply_text(f"Ocorreu um erro ao buscar suas consultas. Erro: {err}")

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o fluxo para cancelar uma consulta."""
    user_id = update.effective_user.id
    
    if context.args:
        try:
            consulta_id = int(context.args[0])
            await processar_cancelamento(update, context, consulta_id, user_id)
        except (ValueError, IndexError):
            await update.message.reply_text("Por favor, use o formato correto. Ex: `/cancelar 123`")
    else:
        conversas_em_andamento[user_id] = {'etapa': 'cancelamento'}
        await update.message.reply_text(
            'Para cancelar uma consulta, por favor, informe o ID dela. '
            'Você pode ver o ID usando o comando `/minhas_consultas`.'
        )

async def processar_cancelamento(update: Update, context: ContextTypes.DEFAULT_TYPE, consulta_id, user_id):
    """Lida com a lógica de cancelamento no banco de dados."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        query_select = "SELECT * FROM agendamentos WHERE id = %s AND user_id = %s"
        cursor.execute(query_select, (consulta_id, user_id))
        consulta = cursor.fetchone()

        if not consulta:
            await update.message.reply_text(f"Nenhuma consulta encontrada com o ID `{consulta_id}`.")
            cursor.close()
            conn.close()
            return

        query_delete = "DELETE FROM agendamentos WHERE id = %s"
        cursor.execute(query_delete, (consulta_id,))
        conn.commit()

        assunto_email = f"Agendamento Cancelado: {consulta['nome']}"
        corpo_email = f"""
        Olá! Um agendamento foi cancelado através do bot:
        
        ID da Consulta: {consulta_id}
        Nome do Paciente: {consulta['nome']}
        Especialidade: {consulta['especialidade']}
        Médico: Dr(a). {consulta['medico']}
        Data: {consulta['data']}
        Horário: {consulta['horario']}
        
        Por favor, verifique a agenda e remova a consulta.
        """
        enviar_email(assunto_email, corpo_email)

        await update.message.reply_text(
            f"Sua consulta de {consulta['especialidade']} com Dr(a). {consulta['medico']} foi cancelada com sucesso."
        )

    except mysql.connector.Error as err:
        await update.message.reply_text(f"Ocorreu um erro ao cancelar a consulta. Erro: {err}")
    finally:
        if 'etapa' in conversas_em_andamento.get(user_id, {}):
            del conversas_em_andamento[user_id]
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# --- Funções do Chatbot (Resto do Código) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao comando /start com saudação personalizada e botões relevantes."""
    user_id = update.effective_user.id
    
    user_name = None
    has_appointments = False
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        query = "SELECT nome FROM agendamentos WHERE user_id = %s LIMIT 1"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        if result:
            user_name = result['nome'].split()[0]
            has_appointments = True
            
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        logger.error(f"Erro ao buscar usuário no banco de dados: {err}")

    if user_name:
        greeting_text = f"Olá, {user_name}! Bem-vindo(a) de volta. Como posso te ajudar hoje?"
        keyboard = [['Agendar Consulta'], ['Ver minhas consultas']]
    else:
        greeting_text = 'Olá! Bem-vindo(a) à nossa clínica. Como posso ajudar?'
        keyboard = [['Agendar Consulta']]
        
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(greeting_text, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao comando /help com a lista de comandos disponíveis."""
    help_text = (
        'Aqui estão os comandos que você pode usar:\n'
        '/agendar - Inicia o processo de agendamento de uma consulta.\n'
        '/minhas_consultas - Mostra a lista das suas consultas agendadas.\n'
        '/cancelar [ID] - Cancela uma consulta específica.\n'
        'Você também pode fazer perguntas sobre:\n'
        '- Horário de funcionamento\n'
        '- Nossas especialidades\n'
        '- Planos de saúde aceitos'
    )
    await update.message.reply_text(help_text)

async def agendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o fluxo de agendamento de uma consulta com botões."""
    user_id = update.effective_user.id
    conversas_em_andamento[user_id] = {'etapa': 'especialidade'}
    
    especialidades_keyboard = [['Cardiologia'], ['Dermatologia'], ['Ginecologia'], ['Pediatria']]
    reply_markup = ReplyKeyboardMarkup(especialidades_keyboard, one_time_keyboard=True)
    
    await update.message.reply_text(
        'Para agendar sua consulta, por favor, escolha a especialidade:',
        reply_markup=reply_markup
    )
        
async def handle_agendamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    etapa_atual = conversas_em_andamento[user_id]['etapa']
    
    if etapa_atual == 'especialidade':
        especialidade = update.message.text
        especialidades_validas = ['Cardiologia', 'Dermatologia', 'Ginecologia', 'Pediatria']
        if especialidade not in especialidades_validas:
            await update.message.reply_text('Por favor, escolha uma especialidade da lista ou digite o nome corretamente.')
            return
        conversas_em_andamento[user_id]['especialidade'] = especialidade
        conversas_em_andamento[user_id]['etapa'] = 'data'
        await update.message.reply_text(f'Você escolheu {especialidade}. Por favor, informe a data desejada (dd/mm/aaaa).', reply_markup=ReplyKeyboardRemove())
    
    elif etapa_atual == 'data':
        data = update.message.text
        is_valid, error_msg = validar_data(data)
        if not is_valid:
            await update.message.reply_text(error_msg)
            return
        conversas_em_andamento[user_id]['data'] = data
        conversas_em_andamento[user_id]['etapa'] = 'horario'
        await update.message.reply_text(f'Data registrada: {data}. Qual o horário desejado para a consulta? Exemplo: 14:30')
    
    elif etapa_atual == 'horario':
        horario = update.message.text
        if not validar_horario(horario):
            await update.message.reply_text('Formato de horário inválido. Por favor, use o formato hh:mm.')
            return
        conversas_em_andamento[user_id]['horario'] = horario
        conversas_em_andamento[user_id]['etapa'] = 'medico'
        await update.message.reply_text(f'Horário registrado: {horario}. Para qual médico você deseja agendar?')

    elif etapa_atual == 'medico':
        medico_completo = update.message.text
        # Remove os prefixos "Dr." e "Dra." e limpa espaços e caracteres de nova linha
        medico_limpo = medico_completo.replace("Dr.", "").replace("Dr.", "").replace("Dra.", "").replace("Dra.", "").strip().replace('\n', '').replace('\r', '')
        # Extrai apenas o primeiro nome para a consulta
        medico_limpo = medico_limpo.split()[0]
        conversas_em_andamento[user_id]['medico'] = medico_completo
        
        data = conversas_em_andamento[user_id]['data']
        horario = conversas_em_andamento[user_id]['horario']
        
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()

            # Mapeamento manual dos dias da semana para evitar erros de locale
            dias_da_semana = {
                0: 'Segunda-feira',
                1: 'Terça-feira',
                2: 'Quarta-feira',
                3: 'Quinta-feira',
                4: 'Sexta-feira',
                5: 'Sábado',
                6: 'Domingo'
            }
            dia_da_semana_num = datetime.strptime(data, '%d/%m/%Y').weekday()
            dia_da_semana_pt = dias_da_semana.get(dia_da_semana_num)

            # 1. Validação do horário de trabalho do médico (versão final e mais robusta)
            # A consulta usa a versão "limpa" do nome do médico para evitar conflitos de formatação
            query_disponibilidade = """
                SELECT * FROM medico_disponibilidade
                WHERE medico_nome = %s
                  AND dia_da_semana = %s
                  AND horario_inicio <= %s AND horario_fim >= %s
            """
            
            logger.info(f"Executando query com: Médico='{medico_limpo}', Dia='{dia_da_semana_pt}', Horário='{horario}'")
            
            cursor.execute(query_disponibilidade, (medico_limpo, dia_da_semana_pt, horario, horario))
            if not cursor.fetchone():
                await update.message.reply_text(
                    f"{medico_completo} não atende na {dia_da_semana_pt} neste horário. "
                    "Por favor, tente outro horário ou outro dia."
                )
                cursor.close()
                conn.close()
                conversas_em_andamento[user_id]['etapa'] = 'medico'
                return

            # 2. Validação de agendamento duplicado
            query_check = "SELECT * FROM agendamentos WHERE data = %s AND horario = %s AND medico = %s"
            cursor.execute(query_check, (data, horario, medico_completo))
            if cursor.fetchone():
                await update.message.reply_text(
                    f"O horário das {horario} com {medico_completo} já está ocupado. "
                    "Por favor, tente outro horário ou data."
                )
                cursor.close()
                conn.close()
                conversas_em_andamento[user_id]['etapa'] = 'medico'
                return
            
            cursor.close()
            conn.close()
            
        except mysql.connector.Error as err:
            await update.message.reply_text(
                f"Ocorreu um erro ao verificar a disponibilidade. Por favor, tente novamente. Erro: {err}"
            )
            del conversas_em_andamento[user_id]
            return

        # Se as duas validações passarem, avança para a próxima etapa
        conversas_em_andamento[user_id]['etapa'] = 'nome'
        await update.message.reply_text(f'Certo, {medico_completo}. Agora, por favor, informe seu nome completo para finalizar o agendamento.')

    elif etapa_atual == 'nome':
        nome = update.message.text
        especialidade = conversas_em_andamento[user_id]['especialidade']
        data = conversas_em_andamento[user_id]['data']
        horario = conversas_em_andamento[user_id]['horario']
        medico_completo = conversas_em_andamento[user_id]['medico']
        
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            query = "INSERT INTO agendamentos (nome, especialidade, data, horario, medico, user_id) VALUES (%s, %s, %s, %s, %s, %s)"
            values = (nome, especialidade, data, horario, medico_completo, user_id)
            cursor.execute(query, values)
            conn.commit()
            cursor.close()
            conn.close()

            assunto_email = f"Novo Agendamento: {nome}"
            corpo_email = f"""
            Olá! Um novo agendamento foi marcado através do bot:
            
            Nome do Paciente: {nome}
            Especialidade: {especialidade}
            Médico: {medico_completo}
            Data: {data}
            Horário: {horario}
            
            Por favor, verifique a agenda e confirme com o paciente.
            """
            enviar_email(assunto_email, corpo_email)

            await update.message.reply_text(
                f'Agendamento concluído com sucesso, {nome}! '
                f'Sua consulta com {medico_completo} ({especialidade}) está '
                f'marcada para o dia {data}, às {horario}.',
                reply_markup=ReplyKeyboardRemove()
            )
        except mysql.connector.Error as err:
            await update.message.reply_text(f"Ocorreu um erro ao agendar a consulta. Por favor, tente novamente mais tarde. Erro: {err}")
        
        del conversas_em_andamento[user_id]
        
    elif etapa_atual == 'cancelamento':
        try:
            consulta_id = int(update.message.text)
            await processar_cancelamento(update, context, consulta_id, user_id)
        except ValueError:
            await update.message.reply_text("Entrada inválida. Por favor, digite apenas o número de ID da consulta.")

async def faq_nlp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pergunta = update.message.text
    intencao = nlp_model.predict([pergunta])[0]
    
    if intencao == 'horario':
        await update.message.reply_text('Nosso horário de funcionamento é de segunda a sexta, das 8h às 18h.')
    elif intencao == 'especialidade':
        await update.message.reply_text('Oferecemos as seguintes especialidades: Cardiologia, Dermatologia, Ginecologia e Pediatria.')
    elif intencao == 'plano_saude':
        await update.message.reply_text('Aceitamos os planos de saúde Unimed, SulAmérica e Bradesco Saúde.')
    else:
        await update.message.reply_text(
            'Desculpe, não entendi a sua pergunta. Você pode tentar reformular '
            'ou usar o comando /help para ver o que posso fazer.'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in conversas_em_andamento and conversas_em_andamento[user_id]['etapa'] in ['especialidade', 'data', 'horario', 'medico', 'nome', 'cancelamento']:
        await handle_agendamento(update, context)
    else:
        if update.message.text == 'Agendar Consulta':
            await agendar(update, context)
        elif update.message.text == 'Ver minhas consultas':
            await minhas_consultas(update, context)
        else:
            await faq_nlp(update, context)

async def check_and_send_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Verifica e envia lembretes para consultas no dia seguinte."""
    logger.info("Executando a tarefa de verificação de lembretes.")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d/%m/%Y')
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = "SELECT user_id, especialidade, data, horario, medico FROM agendamentos WHERE data = %s"
        cursor.execute(query, (tomorrow,))
        consultas = cursor.fetchall()
        cursor.close()
        conn.close()

        if not consultas:
            logger.info("Nenhuma consulta encontrada para amanhã.")
            return

        for consulta in consultas:
            try:
                message_text = (
                    f"Olá! Lembrete de sua consulta para amanhã:\n\n"
                    f"Especialidade: {consulta['especialidade']}\n"
                    f"Médico: Dr(a). {consulta['medico']}\n"
                    f"Data: {consulta['data']} às {consulta['horario']}\n\n"
                    f"Agradecemos a preferência!"
                )
                await context.bot.send_message(chat_id=consulta['user_id'], text=message_text)
                logger.info(f"Lembrete enviado para o usuário {consulta['user_id']}.")
            except Exception as e:
                logger.error(f"Não foi possível enviar mensagem para o usuário {consulta['user_id']}: {e}")

    except mysql.connector.Error as err:
        logger.error(f"Erro no banco de dados durante a verificação de lembretes: {err}")

# --- Configuração e Inicialização do Bot ---
def start_and_register_commands(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("agendar", agendar))
    application.add_handler(CommandHandler("minhas_consultas", minhas_consultas))
    application.add_handler(CommandHandler("cancelar", cancelar))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

def main():
    if not TOKEN or not DB_CONFIG['password'] or not EMAIL_SENDER or not EMAIL_PASSWORD:
        logger.error("ERRO: Credenciais de ambiente não configuradas. Por favor, verifique o arquivo .env.")
        return
    
    application = ApplicationBuilder().token(TOKEN).build()
    start_and_register_commands(application)

    job_queue = application.job_queue
    job_queue.run_daily(check_and_send_reminders, time=datetime.strptime('00:00:00', '%H:%M:%S').time())

    logger.info("Bot rodando...")
    application.run_polling()

if __name__ == '__main__':
    main()