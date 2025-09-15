from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector

# Adiciona o parâmetro static_folder para que o servidor consiga encontrar os arquivos estáticos
app = Flask(__name__, static_folder='.', static_url_path='')

# Habilita o CORS para todas as rotas da API
CORS(app)

# --- Configurações do Banco de Dados MySQL ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Fabio@4040',
    'database': 'clinica_bot'
}

# --- Rota para obter todos os agendamentos ---
@app.route('/agendamentos', methods=['GET'])
def get_agendamentos():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, nome, especialidade, medico, data, horario FROM agendamentos"
        cursor.execute(query)
        agendamentos = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(agendamentos)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500

# --- Rota para agendar uma nova consulta ---
@app.route('/agendar', methods=['POST'])
def agendar_consulta():
    try:
        # Recebe os dados JSON enviados pelo frontend
        dados = request.get_json()

        # Garante que todos os dados necessários foram enviados
        if not dados or 'nome' not in dados or 'especialidade' not in dados or 'medico' not in dados or 'data' not in dados or 'horario' not in dados:
            return jsonify({'error': 'Dados incompletos para o agendamento.'}), 400

        # Conecta ao banco de dados
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Insere o novo agendamento no banco de dados
        query = "INSERT INTO agendamentos (nome, especialidade, medico, data, horario) VALUES (%s, %s, %s, %s, %s)"
        values = (dados['nome'], dados['especialidade'], dados['medico'], dados['data'], dados['horario'])
        cursor.execute(query, values)
        conn.commit()
        
        # Fecha a conexão
        cursor.close()
        conn.close()

        return jsonify({"message": "Agendamento realizado com sucesso!", "dados": dados}), 201

    except mysql.connector.Error as err:
        # Retorna o erro específico do banco de dados
        print(f"Erro no agendamento: {err}")
        return jsonify({"error": str(err)}), 500
    except Exception as e:
        # Lida com outros erros inesperados
        print(f"Erro inesperado: {e}")
        return jsonify({"error": "Ocorreu um erro interno. Tente novamente mais tarde."}), 500

# --- Rota para cancelar um agendamento por ID ---
@app.route('/cancelar/<int:id>', methods=['DELETE'])
def cancelar_agendamento(id):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = "DELETE FROM agendamentos WHERE id = %s"
        cursor.execute(query, (id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Agendamento cancelado com sucesso."})
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500

# --- Rota principal para servir o painel (index.html) ---
@app.route('/')
def index():
    return app.send_static_file('templates/index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)