# SWGF — Sistema de Gestão de Filas e Atendimento

Sistema web desenvolvido em Django para gerenciamento de filas de atendimento em estabelecimentos como restaurantes, clínicas e repartições públicas.

## 🎯 Sobre o Projeto

O SWGF resolve o problema de organização de filas presenciais, oferecendo:
- **Totem** para o cliente retirar sua senha (com prioridade para idosos, gestantes e PCDs)
- **Painel TV** que exibe a senha chamada em tempo real (atualização automática)
- **Workspace** para atendentes gerenciarem a fila e o atendimento
- **Painel ADM** para gerenciar mesas, mensagens, feriados e notas internas

## 🛠️ Tecnologias Utilizadas

- **Python 3.13**
- **Django 4.2 LTS**
- **MySQL 8.0**
- **HTML5 + CSS3 + JavaScript (Fetch API / AJAX)**
- **PyMySQL** (conector MySQL)
- **python-decouple** (gerenciamento de variáveis de ambiente)

## 📋 Funcionalidades

### Cliente (Totem)
- Retirada de senha com nome e prioridade
- Impressão/visualização da senha gerada

### Atendente (Workspace)
- Login autenticado
- Seleção e troca de mesa
- Chamada de próxima senha da fila
- Visualização do histórico de atendimentos
- Recebimento de notificações do ADM

### Administrador (ADM)
- CRUD de Mesas
- CRUD de Senhas (via Fila)
- CRUD de Mensagens (com notificações para atendentes)
- CRUD de Notas internas
- CRUD de Datas e Feriados

### Painel TV
- Exibição da senha atual e mesa
- Lista das últimas senhas chamadas
- Atualização automática a cada 3 segundos (AJAX)

## 🗄️ Modelagem de Dados

O sistema possui as seguintes tabelas:
- `Usuario` (CustomUser com flag `is_adm`)
- `Cliente`
- `Senha`
- `Mesa`
- `SessaoMesa`
- `Ticket`
- `Mensagem`
- `Data`
- `Notificacao`
- `Nota`

## 🚀 Como Executar

### Pré-requisitos
- Python 3.13+
- MySQL 8.0+
- Git

### Passo a passo

1. Clone o repositório:
   ```bash
   git clone https://github.com/gabnadidev/swgf.git
   cd swgf

2. Crie e ative o ambiente virtual:
    python -m venv venv
    # Windows:
    venv\Scripts\activate
    # Linux/Mac:
    source venv/bin/activate

3. Instale as dependências:
    pip install -r requirements.txt

4. Crie o banco no MySQL:
    CREATE DATABASE swgf CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

5. Copie o .env.example para .env e configure:
    SECRET_KEY=sua_chave_secreta
    DEBUG=True
    DB_NAME=swgf
    DB_USER=seu_usuario
    DB_PASSWORD=sua_senha
    DB_HOST=localhost
    DB_PORT=3306

6. Rode as migrações:
    python manage.py migrate

7. Crie um superusuério:
    python manage.py createsuperuser

8. Inicie o servidor:
    python manage.py runserver

9. Acesse:
    Totem: http://127.0.0.1:8000/totem/

    Painel TV: http://127.0.0.1:8000/painel/

    Login: http://127.0.0.1:8000/login/

    Admin: http://127.0.0.1:8000/admin/


Estrutura do Projeto:
    swgf/
├── swgf/               # Configurações do projeto (settings, urls)
├── swgfApp/            # App principal
│   ├── migrations/
│   ├── templates/
│   ├── admin.py
│   ├── context_processors.py
│   ├── decorators.py
│   ├── forms.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
├── static/             # Arquivos estáticos (CSS, JS)
├── venv/               # Ambiente virtual (não versionado)
├── .env                # Variáveis de ambiente (não versionado)
├── .env.example        # Exemplo de variáveis
├── .gitignore
├── manage.py
├── README.md
└── requirements.txt


Autor
Gabriel da Silva Nadi

Projeto desenvolvido para a disciplina de Programação 2

Professor: James Clauton

Data de entrega:
    Setembro de 2026