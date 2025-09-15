import mysql.connector

# Configurações do Banco de Dados MySQL
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Fabio@4040',
    'database': 'clinica_bot'
}

def adicionar_medico(nome, dia, inicio, fim):
    """Adiciona um novo médico e sua disponibilidade no banco de dados."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = "INSERT INTO medico_disponibilidade (medico_nome, dia_da_semana, horario_inicio, horario_fim) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (nome, dia, inicio, fim))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Médico {nome} adicionado com sucesso para {dia}, das {inicio} às {fim}.")
    except mysql.connector.Error as err:
        print(f"Erro ao adicionar médico: {err}")

# Exemplo de uso: adicione os dados que estão faltando
adicionar_medico('Dr. Carlos', 'Quinta-feira', '08:00', '18:00')