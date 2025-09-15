import subprocess
import time

while True:
    print("Iniciando o bot...")
    
    # O comando que inicia o seu bot.
    # Certifique-se de que o caminho para o python está correto.
    process = subprocess.Popen(['python', 'bot_clinica.py'])
    
    # Espera até o processo do bot terminar.
    process.wait()
    
    # Se o bot parou, espera 5 segundos antes de tentar reiniciá-lo.
    print("O bot parou. Reiniciando em 5 segundos...")
    time.sleep(5)