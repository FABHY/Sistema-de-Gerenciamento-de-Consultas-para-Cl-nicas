from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import mysql.connector
from datetime import datetime, timedelta
from models import get_user, get_user_by_username
import locale
locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')

# Inicialização do Flask
app = Flask(__name__)
app.secret_key = 'uma_chave_super_secreta' # Precisa de uma chave secreta para as sessões

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return get_user(user_id)

# Configurações do Banco de Dados MySQL
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Fabio@4040',
    'database': 'clinica_bot'
}

def is_horario_disponivel(medico, data, horario, agendamento_id=None):
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 1. Validação do horário de trabalho do médico
        dia_da_semana = datetime.strptime(data, '%d/%m/%Y').strftime('%A')
        query_disponibilidade = """
            SELECT * FROM medico_disponibilidade
            WHERE medico_nome = %s AND dia_da_semana = %s AND horario_inicio <= %s AND horario_fim >= %s
        """
        cursor.execute(query_disponibilidade, (medico, dia_da_semana, horario, horario))
        if not cursor.fetchone():
            return False, f"Dr(a). {medico} não atende na {dia_da_semana} neste horário."

        # 2. Validação de agendamento duplicado
        query_check = "SELECT id FROM agendamentos WHERE data = %s AND horario = %s AND medico = %s"
        
        # Exclui o agendamento atual da validação de duplicidade
        if agendamento_id:
            query_check += " AND id != %s"
            cursor.execute(query_check, (data, horario, medico, agendamento_id))
        else:
            cursor.execute(query_check, (data, horario, medico))

        if cursor.fetchone():
            return False, f"O horário das {horario} com Dr(a). {medico} já está ocupado."

        return True, None

    except mysql.connector.Error as err:
        print(f"Erro ao verificar a disponibilidade: {err}")
        return False, "Ocorreu um erro no banco de dados. Tente novamente."
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def get_agendamentos(termo_busca=None):
    """Busca agendamentos no banco de dados com opção de filtro."""
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, nome, especialidade, data, horario, medico FROM agendamentos"
        
        if termo_busca:
            query += " WHERE nome LIKE %s OR especialidade LIKE %s OR medico LIKE %s"
            termo_busca = f"%{termo_busca}%"
            cursor.execute(query, (termo_busca, termo_busca, termo_busca))
        else:
            cursor.execute(query)
            
        agendamentos = cursor.fetchall()
        
        agendamentos.sort(key=lambda x: (
            datetime.strptime(x['data'], '%d/%m/%Y'),
            datetime.strptime(x['horario'], '%H:%M')
        ))
        
        return agendamentos
    except mysql.connector.Error as err:
        print(f"Erro no banco de dados: {err}")
        return []
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Rotas protegidas (agora exigem login)
@app.route('/')
@login_required
def dashboard():
    termo_busca = request.args.get('busca')
    agendamentos = get_agendamentos(termo_busca)
    return render_template('dashboard.html', agendamentos=agendamentos, termo_busca=termo_busca)

@app.route('/excluir/<int:id>')
@login_required
def excluir_agendamento(id):
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = "DELETE FROM agendamentos WHERE id = %s"
        cursor.execute(query, (id,))
        conn.commit()
        flash('Agendamento excluído com sucesso.', 'success')
    except mysql.connector.Error as err:
        print(f"Erro ao excluir agendamento: {err}")
        flash('Erro ao excluir agendamento. Tente novamente.', 'danger')
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
    
    return redirect(url_for('dashboard'))

@app.route('/editar/<int:id>', methods=['GET'])
@login_required
def editar_agendamento(id):
    conn = None
    agendamento = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, nome, especialidade, data, horario, medico FROM agendamentos WHERE id = %s"
        cursor.execute(query, (id,))
        agendamento = cursor.fetchone()
    except mysql.connector.Error as err:
        print(f"Erro ao buscar agendamento para edição: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
    
    if agendamento:
        return render_template('editar.html', agendamento=agendamento)
    else:
        flash('Agendamento não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/atualizar/<int:id>', methods=['POST'])
@login_required
def atualizar_agendamento(id):
    novo_nome = request.form['nome']
    nova_especialidade = request.form['especialidade']
    novo_medico = request.form['medico']
    nova_data = request.form['data']
    novo_horario = request.form['horario']
    
    # Validação em tempo real
    is_valid, error_msg = is_horario_disponivel(novo_medico, nova_data, novo_horario, agendamento_id=id)
    if not is_valid:
        flash(error_msg, 'danger')
        return redirect(url_for('editar_agendamento', id=id))

    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = "UPDATE agendamentos SET nome = %s, especialidade = %s, medico = %s, data = %s, horario = %s WHERE id = %s"
        values = (novo_nome, nova_especialidade, novo_medico, nova_data, novo_horario, id)
        cursor.execute(query, values)
        conn.commit()
        flash('Agendamento atualizado com sucesso!', 'success')
    except mysql.connector.Error as err:
        print(f"Erro ao atualizar agendamento: {err}")
        flash('Erro ao atualizar agendamento. Tente novamente.', 'danger')
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
    
    return redirect(url_for('dashboard'))

# Rotas de Login e Logout
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user_by_username(username)
        if user and user.password == password:
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Credenciais inválidas. Tente novamente.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)