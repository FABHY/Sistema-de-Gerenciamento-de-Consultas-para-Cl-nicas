from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password
        
    def get_id(self):
        return str(self.id)

# Simulação de um banco de dados de usuários.
# Em um ambiente real, você buscaria isso de um banco de dados.
# Vamos criar um usuário de exemplo: "admin" com a senha "123456"
users = [
    User(id=1, username='admin', password='123456')
]

def get_user(user_id):
    for user in users:
        if user.id == int(user_id):
            return user
    return None

def get_user_by_username(username):
    for user in users:
        if user.username == username:
            return user
    return None