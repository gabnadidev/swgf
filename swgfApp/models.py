"""
Modelos (tabelas do banco) do SWGF — Sistema de Gestão de Filas.

As regras de negócio ficam aqui, nos próprios modelos, e não nas views.
Assim a mesma regra vale para qualquer tela que a use, e os testes
conseguem verificá-la sem precisar abrir uma página.

Relacionamentos usados no sistema:
    1:1  Senha ── Ticket          (cada senha pertence a um único ticket)
    1:N  Cliente ── Ticket        (um cliente pode ter vários tickets)
    1:N  Usuario ── SessaoMesa    (um usuário abre várias sessões)
    1:N  Mesa ── SessaoMesa       (uma mesa recebe várias sessões)
    1:N  SessaoMesa ── Ticket     (uma sessão atende vários tickets)
    1:N  Usuario ── Mensagem/Data/Nota/Notificacao
    1:N  Mensagem ── Notificacao  e  Data ── Notificacao
"""

from django.contrib.auth.models import AbstractUser
from django.db import IntegrityError, models, transaction
from django.db.models import Case, Exists, IntegerField, Max, OuterRef, Value, When
from django.db.models.functions import Cast, Substr
from django.utils import timezone


class RegraDeNegocioError(Exception):
    """
    Erro levantado quando uma regra de negócio impede uma ação
    (ex.: entrar em uma mesa já ocupada). A view captura este erro e
    mostra o texto dele para o usuário como uma mensagem na tela.
    """


# =============================================================================
# BLOCO 1 — Usuário, Cliente, Senha e Mesa
# =============================================================================

class Usuario(AbstractUser):
    """
    Usuário personalizado do sistema. Herda do usuário padrão do Django
    (username, password, email...) e acrescenta o nível de acesso.

    Os dois níveis de acesso exigidos pelo sistema são:
        is_adm = True   -> administrador: gerencia mesas, senhas, mensagens,
                           datas e notas.
        is_adm = False  -> usuário comum (atendente): só atende a fila, vê o
                           histórico e lê as notificações.
    """
    is_adm = models.BooleanField(default=False, verbose_name="É administrador")
    status = models.CharField(max_length=50, default='ativo', verbose_name="Status")

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def __str__(self):
        return f"{self.username} ({'ADM' if self.is_adm else 'Atendente'})"

    def save(self, *args, **kwargs):
        # Quem é criado com "createsuperuser" já nasce administrador do sistema.
        # Sem isto, o superusuário entrava nas telas como um atendente comum.
        if self.is_superuser:
            self.is_adm = True
        super().save(*args, **kwargs)

    @property
    def sessao_ativa(self):
        """Sessão de mesa aberta agora (só conta se a mesa ainda existir)."""
        return self.sessaomesa_set.filter(
            data_fim__isnull=True, mesa__isnull=False
        ).select_related('mesa').first()

    def encerrar_sessoes(self):
        """Fecha toda sessão aberta do usuário, liberando a mesa dele."""
        self.sessaomesa_set.filter(data_fim__isnull=True).update(data_fim=timezone.now())


class Cliente(models.Model):
    """Pessoa que retirou uma senha no totem."""

    class Prioridade(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        IDOSO = 'idoso', 'Idoso (60+)'
        GESTANTE = 'gestante', 'Gestante'
        PCD = 'pcd', 'Pessoa com Deficiência'

    # Todos estes tipos passam na frente dos clientes normais na fila.
    PRIORITARIOS = [Prioridade.IDOSO, Prioridade.GESTANTE, Prioridade.PCD]

    nome = models.CharField(max_length=255, verbose_name="Nome")
    tipo_prioridade = models.CharField(
        max_length=50,
        choices=Prioridade.choices,
        default=Prioridade.NORMAL,
        blank=True,
        null=True,
        verbose_name="Tipo de prioridade",
    )

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return self.nome

    @property
    def eh_prioritario(self):
        return self.tipo_prioridade in self.PRIORITARIOS


class SenhaQuerySet(models.QuerySet):
    """Consultas prontas de senhas, usadas pelas telas da fila e pelo painel."""

    def fila_de_hoje(self):
        """
        Senhas de hoje que ainda aguardam, na ordem correta de atendimento:
        primeiro as prioritárias e, dentro de cada grupo, por ordem de chegada.

        O campo "peso" é calculado na consulta: 0 = prioritário, 1 = normal.
        Senhas de dias anteriores ficam de fora, pois o cliente já foi embora.
        """
        return self.filter(
            status=Senha.Status.AGUARDANDO,
            ticket__data=timezone.localdate(),
        ).annotate(
            peso=Case(
                When(ticket__cliente__tipo_prioridade__in=Cliente.PRIORITARIOS, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by('peso', 'id').select_related('ticket__cliente')

    def chamadas_de_hoje(self):
        """
        Senhas chamadas hoje, da chamada mais recente para a mais antiga.

        A ordem usa a hora da chamada, não o id: com a prioridade, uma senha
        emitida depois pode ser chamada antes.
        """
        return self.filter(
            status__in=[Senha.Status.CHAMADA, Senha.Status.ATENDIDA],
            ticket__data=timezone.localdate(),
            ticket__hora_atendimento__isnull=False,
        ).order_by('-ticket__hora_atendimento').select_related(
            'ticket__cliente', 'ticket__sessao_mesa__mesa'
        )


class Senha(models.Model):
    """Código que o cliente recebe no totem (A0001, A0002...)."""

    class Status(models.TextChoices):
        AGUARDANDO = 'aguardando', 'Aguardando'
        CHAMADA = 'chamada', 'Chamada'
        ATENDIDA = 'atendida', 'Atendida'

    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.AGUARDANDO,
        verbose_name="Status",
    )

    # Permite escrever Senha.objects.fila_de_hoje() nas views.
    objects = SenhaQuerySet.as_manager()

    class Meta:
        verbose_name = "Senha"
        verbose_name_plural = "Senhas"

    def __str__(self):
        return f"{self.codigo} ({self.status})"

    @classmethod
    def proximo_codigo(cls):
        """
        Gera o próximo código a partir do MAIOR número já emitido.

        Antes o número era calculado só com os tickets do dia. Como o código é
        único no banco inteiro, a contagem voltava a 1 e preenchia os buracos
        da sequência (por isso apareciam senhas como A0006 emitida depois de
        A0011). Agora a sequência sempre cresce.
        """
        maior = cls.objects.annotate(
            numero=Cast(Substr('codigo', 2), IntegerField())
        ).aggregate(maior=Max('numero'))['maior'] or 0
        return f"A{maior + 1:04d}"

    def ajustar_status(self, novo_status):
        """
        Muda o status mantendo o ticket coerente. É usado na edição feita pelo
        administrador: voltar uma senha para "aguardando" apaga o registro da
        chamada, e assim ela sai do histórico e do painel.
        """
        self.status = novo_status
        self.save(update_fields=['status'])

        ticket = getattr(self, 'ticket', None)
        if ticket is None:
            return
        if novo_status == self.Status.AGUARDANDO:
            ticket.hora_atendimento = None
            ticket.sessao_mesa = None
            ticket.save(update_fields=['hora_atendimento', 'sessao_mesa'])
        elif ticket.hora_atendimento is None:
            ticket.hora_atendimento = timezone.localtime().time()
            ticket.save(update_fields=['hora_atendimento'])


class MesaQuerySet(models.QuerySet):
    def com_ocupacao(self):
        """Acrescenta a cada mesa o campo "esta_ocupada", calculado na consulta."""
        sessao_aberta = SessaoMesa.objects.filter(mesa=OuterRef('pk'), data_fim__isnull=True)
        return self.annotate(esta_ocupada=Exists(sessao_aberta))


class Mesa(models.Model):
    """
    Ponto de atendimento. O status indica se a mesa está ativa ou não.
    "Ocupada" não é gravado no status: é deduzido de haver uma sessão aberta,
    para os dois dados nunca ficarem em conflito.
    """

    class Status(models.TextChoices):
        DISPONIVEL = 'disponivel', 'Ativa'
        INATIVA = 'inativa', 'Inativa'

    # unique=True impede duas mesas com o mesmo número.
    numero = models.PositiveIntegerField(unique=True, verbose_name="Número da mesa")
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.DISPONIVEL,
        verbose_name="Status",
    )

    objects = MesaQuerySet.as_manager()

    class Meta:
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"
        ordering = ['numero']

    def __str__(self):
        return f"Mesa {self.numero} ({self.get_status_display()})"

    @property
    def sessao_aberta(self):
        return self.sessaomesa_set.filter(data_fim__isnull=True).select_related('usuario').first()

    def alternar_status(self):
        """Ativa ou desativa a mesa. Uma mesa em uso não pode ser desativada."""
        if self.status == self.Status.DISPONIVEL:
            if self.sessao_aberta:
                raise RegraDeNegocioError(
                    f"A Mesa {self.numero} está em uso. Libere-a antes de desativar."
                )
            self.status = self.Status.INATIVA
        else:
            self.status = self.Status.DISPONIVEL
        self.save(update_fields=['status'])

    def liberar(self):
        """Encerra a sessão aberta da mesa (ex.: atendente saiu sem fazer logout)."""
        self.sessaomesa_set.filter(data_fim__isnull=True).update(data_fim=timezone.now())


# =============================================================================
# BLOCO 2 — Sessão de mesa e Ticket
# =============================================================================

class SessaoMesa(models.Model):
    """
    Registra o período em que um usuário ficou em uma mesa.
    data_fim vazia significa que a sessão ainda está aberta.
    """
    usuario = models.ForeignKey(  # 1:N — um usuário tem várias sessões
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuário",
    )
    mesa = models.ForeignKey(  # 1:N — uma mesa tem várias sessões
        Mesa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Mesa",
    )
    data_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Início da sessão")
    data_fim = models.DateTimeField(null=True, blank=True, verbose_name="Fim da sessão")

    class Meta:
        verbose_name = "Sessão de Mesa"
        verbose_name_plural = "Sessões de Mesa"

    def __str__(self):
        return f"{self.usuario} na {self.mesa} (início: {self.data_inicio:%d/%m/%Y %H:%M})"

    @classmethod
    def entrar(cls, usuario, mesa_id):
        """
        Coloca o usuário em uma mesa, encerrando a sessão anterior dele.
        Regras: a mesa precisa estar ativa e não pode estar com outra pessoa.
        """
        # atomic + select_for_update trava a linha da mesa até o fim do bloco:
        # dois atendentes clicando ao mesmo tempo não conseguem pegar a mesma mesa.
        with transaction.atomic():
            mesa = Mesa.objects.select_for_update().get(pk=mesa_id)
            if mesa.status != Mesa.Status.DISPONIVEL:
                raise RegraDeNegocioError(f"A Mesa {mesa.numero} está desativada.")

            ocupante = mesa.sessao_aberta
            if ocupante and ocupante.usuario_id != usuario.pk:
                raise RegraDeNegocioError(
                    f"A Mesa {mesa.numero} já está sendo usada por {ocupante.usuario.username}."
                )
            if ocupante:  # o próprio usuário já está nela: nada a fazer
                return ocupante

            usuario.encerrar_sessoes()
            return cls.objects.create(usuario=usuario, mesa=mesa)

    def senha_em_atendimento(self):
        """Senha que este atendente chamou e ainda não finalizou."""
        return Senha.objects.filter(
            status=Senha.Status.CHAMADA, ticket__sessao_mesa=self
        ).select_related('ticket__cliente').first()

    def finalizar_atendimento(self):
        """Marca como atendida a senha em andamento nesta sessão, se houver."""
        senha = self.senha_em_atendimento()
        if senha:
            senha.status = Senha.Status.ATENDIDA
            senha.save(update_fields=['status'])
        return senha

    def chamar_proxima(self):
        """
        Chama a próxima senha da fila para esta mesa e devolve essa senha
        (ou None, se a fila estiver vazia). A senha que estava em atendimento
        é finalizada automaticamente, pois só se chama o próximo depois de
        terminar o atual.
        """
        with transaction.atomic():
            for senha in Senha.objects.fila_de_hoje():
                # O update só altera a linha se ela ainda estiver "aguardando".
                # Se outro atendente chamou a mesma senha um instante antes,
                # o resultado é 0 e o laço tenta a próxima da fila.
                conseguiu = Senha.objects.filter(
                    pk=senha.pk, status=Senha.Status.AGUARDANDO
                ).update(status=Senha.Status.CHAMADA)
                if not conseguiu:
                    continue

                # O ticket da senha nova ainda não aponta para esta sessão,
                # então só a senha anterior é finalizada aqui.
                self.finalizar_atendimento()
                ticket = senha.ticket
                ticket.sessao_mesa = self
                ticket.hora_atendimento = timezone.localtime().time()
                ticket.save(update_fields=['sessao_mesa', 'hora_atendimento'])
                senha.status = Senha.Status.CHAMADA
                return senha
        return None


class Ticket(models.Model):
    """Liga o cliente, a senha e a sessão de mesa que fez o atendimento."""
    cliente = models.ForeignKey(  # 1:N — um cliente pode ter vários tickets
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Cliente",
    )
    # 1:1 — cada senha pertence a um único ticket, e vice-versa.
    # A partir de uma senha, o ticket é acessado com "senha.ticket".
    # CASCADE: apagar a senha apaga também o ticket dela.
    senha = models.OneToOneField(
        Senha,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Senha",
    )
    sessao_mesa = models.ForeignKey(  # 1:N — uma sessão atende vários tickets
        SessaoMesa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sessão de Mesa",
    )
    hora_emissao = models.DateTimeField(auto_now_add=True, verbose_name="Hora de emissão")
    hora_atendimento = models.TimeField(null=True, blank=True, verbose_name="Hora de atendimento")
    # localdate usa o fuso de settings.py, o mesmo das consultas de "hoje".
    data = models.DateField(default=timezone.localdate, editable=False, verbose_name="Data")

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"

    def __str__(self):
        return f"Ticket #{self.id} — Senha {self.senha}"

    @classmethod
    def emitir(cls, nome, tipo_prioridade):
        """
        Cria cliente, senha e ticket de uma só vez (ou nenhum, se algo falhar).
        Se dois totens gerarem o mesmo código ao mesmo tempo, o banco recusa o
        segundo (código é único) e a emissão tenta novamente com outro número.
        """
        for _tentativa in range(5):
            try:
                with transaction.atomic():
                    cliente = Cliente.objects.create(nome=nome, tipo_prioridade=tipo_prioridade)
                    senha = Senha.objects.create(codigo=Senha.proximo_codigo())
                    return cls.objects.create(cliente=cliente, senha=senha)
            except IntegrityError:
                continue
        raise RegraDeNegocioError("Não foi possível emitir a senha. Tente novamente.")


# =============================================================================
# BLOCO 3 — Mensagens, datas, notificações e notas
# =============================================================================

def notificar_atendentes(**referencia):
    """
    Cria uma notificação para cada atendente ativo.
    Recebe mensagem=... ou data=..., que é o assunto da notificação.
    """
    atendentes = Usuario.objects.filter(is_adm=False, is_active=True)
    Notificacao.objects.bulk_create(
        [Notificacao(usuario=atendente, **referencia) for atendente in atendentes]
    )


class Mensagem(models.Model):
    """Aviso enviado pelo administrador para os atendentes."""

    class Status(models.TextChoices):
        ENVIADA = 'enviada', 'Enviada'
        LIDA = 'lida', 'Lida por todos'

    usuario = models.ForeignKey(  # 1:N — um administrador envia várias mensagens
        Usuario,
        on_delete=models.CASCADE,
        verbose_name="Remetente (ADM)",
    )
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.ENVIADA,
        verbose_name="Status",
    )
    conteudo = models.TextField(verbose_name="Conteúdo da mensagem")

    class Meta:
        verbose_name = "Mensagem"
        verbose_name_plural = "Mensagens"

    def __str__(self):
        return f"Mensagem #{self.id} de {self.usuario}"

    def atualizar_status_leitura(self):
        """Passa para "lida" quando todos os destinatários já tiverem lido."""
        if not self.notificacao_set.filter(visualizada=False).exists():
            self.status = self.Status.LIDA
            self.save(update_fields=['status'])


class Data(models.Model):
    """
    Dia cadastrado pelo administrador. Se tiver nome de feriado e estiver
    ativo, o totem não emite senhas naquele dia.
    """

    class Status(models.TextChoices):
        ATIVO = 'ativo', 'Ativo'
        INATIVO = 'inativo', 'Inativo'

    usuario = models.ForeignKey(  # 1:N — um administrador cadastra várias datas
        Usuario,
        on_delete=models.CASCADE,
        verbose_name="Cadastrado por (ADM)",
    )
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.ATIVO,
        verbose_name="Status",
    )
    dia = models.DateField(unique=True, verbose_name="Dia")
    feriado = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Nome do feriado",
        help_text="Deixe vazio se for apenas um dia de funcionamento normal",
    )

    class Meta:
        verbose_name = "Data"
        verbose_name_plural = "Datas"

    def __str__(self):
        if self.feriado:
            return f"{self.dia:%d/%m/%Y} — {self.feriado}"
        return f"{self.dia:%d/%m/%Y}"

    @classmethod
    def feriado_de_hoje(cls):
        """Devolve o feriado ativo de hoje, ou None se hoje houver atendimento."""
        return cls.objects.filter(
            dia=timezone.localdate(), status=cls.Status.ATIVO, feriado__isnull=False
        ).exclude(feriado='').first()


class Notificacao(models.Model):
    """Aviso individual de um atendente, sobre uma mensagem ou uma data."""
    usuario = models.ForeignKey(  # 1:N — um usuário recebe várias notificações
        Usuario,
        on_delete=models.CASCADE,
        verbose_name="Destinatário",
    )
    mensagem = models.ForeignKey(  # 1:N — uma mensagem gera várias notificações
        Mensagem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Mensagem",
    )
    data = models.ForeignKey(  # 1:N — uma data gera várias notificações
        Data,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Data/Feriado",
    )
    visualizada = models.BooleanField(default=False, verbose_name="Já visualizada?")

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"

    def __str__(self):
        return f"Notificação para {self.usuario} (visualizada: {self.visualizada})"

    def marcar_como_lida(self):
        """Registra a leitura e atualiza o status da mensagem de origem."""
        self.visualizada = True
        self.save(update_fields=['visualizada'])
        if self.mensagem:
            self.mensagem.atualizar_status_leitura()


class Nota(models.Model):
    """Anotação interna do administrador."""
    usuario = models.ForeignKey(  # 1:N — um administrador escreve várias notas
        Usuario,
        on_delete=models.CASCADE,
        verbose_name="Autor (ADM)",
    )
    conteudo = models.TextField(verbose_name="Conteúdo da nota")

    class Meta:
        verbose_name = "Nota"
        verbose_name_plural = "Notas"

    def __str__(self):
        return f"Nota #{self.id} de {self.usuario}"
