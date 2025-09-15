 Sistema-de-Gerenciamento-de-Consultas-para-Clinicas
Este projeto é uma solução completa para automação de clínicas médicas, facilitando o agendamento de consultas tanto para pacientes quanto para a equipe administrativa. Ele é composto por um bot de Telegram, uma API de agendamento e um painel web de gerenciamento, todos interligados a um banco de dados central.

Funcionalidades Principais
Bot do Telegram (bot_clinica.py): Pacientes podem agendar, visualizar e cancelar consultas de forma interativa diretamente pelo Telegram. O bot também envia lembretes automáticos por e-mail das consultas agendadas.

API de Agendamento (api_clinica.py): Uma API RESTful em Flask que gerencia as operações de agendamento, como criação, busca e cancelamento de consultas, servindo como a ponte de comunicação entre o bot, o painel e o banco de dados.

Painel de Gerenciamento (painel.py): Um painel web com login protegido para a equipe da clínica. Permite visualizar, adicionar, editar e excluir agendamentos, além de gerenciar a disponibilidade dos médicos.

Gestão de Médicos (adicionar_medico.py): Um script simples para adicionar novos médicos e suas disponibilidades ao banco de dados.

Automação e Monitoramento (run.py): Um script que garante que o bot do Telegram esteja sempre em execução, reiniciando-o automaticamente em caso de falha.
