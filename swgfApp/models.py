from django.contrib.auth.models import AbstractUser

from django.db import models

# BLOCO 1

# criando um usuario customizado(modelo)

class Usuario(AbstractUser):
    """
    CustomUser do sistema SWGF.
    Herda tudo do User padrão do Django (username, password, email, etc.)
    e adiciona campos específicos do nosso sistema.
    
    """
    is_adm = models.BooleanField(default=False, verbose_name="É administrador")
    status = models.CharField(max_length=50, default='ativo', verbose_name="Status")
    
class Meta:
    verbose_name = "Usuário"
    verbose_name_plural = "Usuários"
    
def __str__(self):
        return f"{self.username} ({'ADM' if self.is_adm else 'Atendente'})"
    
# criando a tabela cliente(modelo)
    
class Cliente(models.Model):
    nome = models.CharField(max_length=255, verbose_name="Nome")
    tipo_prioridade = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Tipo de prioridade",
        help_text="Ex: idoso, gestante, PCD, normal"
    )

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return self.nome

# criando a tabela senha(modelo)

class Senha(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    status = models.CharField(
        max_length=50,
        default='aguardando',
        verbose_name="Status",
        help_text="Ex: aguardando, chamada, atendida"
    )

    class Meta:
        verbose_name = "Senha"
        verbose_name_plural = "Senhas"

    def __str__(self):
        return f"{self.codigo} ({self.status})"

# criando a tabela mesa (modelo)

class Mesa(models.Model):
    numero = models.IntegerField(verbose_name="Número da mesa")
    status = models.CharField(
        max_length=50,
        default='disponivel',
        verbose_name="Status",
        help_text="Ex: disponivel, ocupada, inativa"
    )

    class Meta:
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"

    def __str__(self):
        return f"Mesa {self.numero} ({self.status})"
    
# BLOCO 2

# criando a tabela sessao mesa(modelo)

class SessaoMesa(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuário"
    )
    mesa = models.ForeignKey(
        Mesa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Mesa"
    )
    data_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Início da sessão")
    data_fim = models.DateTimeField(null=True, blank=True, verbose_name="Fim da sessão")

    class Meta:
        verbose_name = "Sessão de Mesa"
        verbose_name_plural = "Sessões de Mesa"

    def __str__(self):
        return f"{self.usuario} na {self.mesa} (início: {self.data_inicio:%d/%m/%Y %H:%M})"

# criando a tabela ticket(modelo)

class Ticket(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Cliente"
    )
    senha = models.ForeignKey(
        Senha,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Senha"
    )
    sessao_mesa = models.ForeignKey(
        SessaoMesa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sessão de Mesa"
    )
    hora_emissao = models.DateTimeField(auto_now_add=True, verbose_name="Hora de emissão")
    hora_atendimento = models.TimeField(null=True, blank=True, verbose_name="Hora de atendimento")
    data = models.DateField(auto_now_add=True, verbose_name="Data")

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"

    def __str__(self):
        return f"Ticket #{self.id} — Senha {self.senha}"
    
# BLOCO 3

# criando a tabela mensagem(modelo)

class Mensagem(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        verbose_name="Remetente (ADM)"
    )
    status = models.CharField(
        max_length=50,
        default='enviada',
        verbose_name="Status",
        help_text="Ex: enviada, lida"
    )
    conteudo = models.TextField(verbose_name="Conteúdo da mensagem")

    class Meta:
        verbose_name = "Mensagem"
        verbose_name_plural = "Mensagens"

    def __str__(self):
        return f"Mensagem #{self.id} de {self.usuario}"

# criando a tabela data(modelo)

class Data(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        verbose_name="Cadastrado por (ADM)"
    )
    status = models.CharField(
        max_length=50,
        default='ativo',
        verbose_name="Status"
    )
    dia = models.DateField(verbose_name="Dia")
    feriado = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Nome do feriado",
        help_text="Deixe vazio se for apenas um dia de funcionamento normal"
    )

    class Meta:
        verbose_name = "Data"
        verbose_name_plural = "Datas"

    def __str__(self):
        if self.feriado:
            return f"{self.dia:%d/%m/%Y} — {self.feriado}"
        return f"{self.dia:%d/%m/%Y}"

# criando a tabela notificação(modelo)

class Notificacao(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        verbose_name="Destinatário"
    )
    mensagem = models.ForeignKey(
        Mensagem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Mensagem"
    )
    data = models.ForeignKey(
        Data,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Data/Feriado"
    )
    visualizada = models.BooleanField(default=False, verbose_name="Já visualizada?")

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"

    def __str__(self):
        return f"Notificação para {self.usuario} (visualizada: {self.visualizada})"

# criando a tabela nota(modelo)

class Nota(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        verbose_name="Autor (ADM)"
    )
    conteudo = models.TextField(verbose_name="Conteúdo da nota")

    class Meta:
        verbose_name = "Nota"
        verbose_name_plural = "Notas"

    def __str__(self):
        return f"Nota #{self.id} de {self.usuario}"