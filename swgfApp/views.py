"""
Views do SWGF, todas baseadas em classes.

Controle de acesso, feito pelos mixins de mixins.py:
    sem mixin            -> público (home, totem e painel TV)
    UsuarioLogadoMixin   -> nível USER: qualquer usuário logado
    AdministradorMixin   -> nível ADMIN: apenas is_adm = True

As regras de negócio ficam em models.py. As views só recebem o pedido,
chamam o modelo e devolvem a resposta.
"""

from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView,
)

from .forms import (
    DataForm, FiltroDataForm, FiltroFilaForm, FiltroHistoricoForm, FiltroMensagemForm,
    FiltroMesaForm, FiltroNotaForm, FiltroNotificacaoForm, MensagemForm, MesaForm, NotaForm,
    RetirarSenhaForm, SenhaForm,
)
from .mixins import (
    AdministradorMixin, ApenasPostMixin, FiltroMixin, MensagemSucessoDeleteMixin,
    UsuarioLogadoMixin,
)
from .models import (
    Data, Mensagem, Mesa, Nota, Notificacao, RegraDeNegocioError, Senha, SessaoMesa, Ticket,
    notificar_atendentes,
)


# =============================================================================
# Páginas públicas
# =============================================================================

class HomeView(TemplateView):
    """Página inicial com os atalhos do sistema."""
    template_name = 'swgfApp/home.html'


class LoginUsuarioView(LoginView):
    """Login. Quem já está logado é levado direto para a fila."""
    template_name = 'swgfApp/login.html'
    redirect_authenticated_user = True


class TotemView(FormView):
    """Tela onde o cliente retira a senha. Não emite senhas em feriado ativo."""
    template_name = 'swgfApp/totem.html'
    form_class = RetirarSenhaForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['feriado'] = Data.feriado_de_hoje()  # o template esconde o formulário
        return context

    def form_valid(self, form):
        # Confere de novo no servidor: o formulário pode ter sido aberto antes
        # de o feriado ser cadastrado.
        if Data.feriado_de_hoje():
            messages.error(self.request, "Hoje não há atendimento (feriado).")
            return redirect('swgfApp:totem')
        try:
            ticket = Ticket.emitir(
                nome=form.cleaned_data['nome'],
                tipo_prioridade=form.cleaned_data['tipo_prioridade'],
            )
        except RegraDeNegocioError as erro:
            messages.error(self.request, str(erro))
            return redirect('swgfApp:totem')
        return redirect('swgfApp:senha_emitida', pk=ticket.pk)


class SenhaEmitidaView(DetailView):
    """Confirmação com a senha gerada e o horário."""
    model = Ticket
    template_name = 'swgfApp/senha_emitida.html'
    context_object_name = 'ticket'


def dados_do_painel():
    """
    Reúne os dados do painel TV. A página e o JSON usam esta mesma função para
    nunca mostrarem informações diferentes.

    Senha atual: a chamada mais recente ainda em atendimento.
    Últimas senhas: as outras cinco chamadas mais recentes de hoje.
    """
    chamadas = Senha.objects.chamadas_de_hoje()
    atual = chamadas.filter(status=Senha.Status.CHAMADA).first()
    ultimas = chamadas.exclude(pk=atual.pk) if atual else chamadas
    return atual, ultimas[:5]


def numero_da_mesa(senha):
    """Número da mesa que chamou a senha, ou None se ela não existir mais."""
    sessao = senha.ticket.sessao_mesa
    return sessao.mesa.numero if sessao and sessao.mesa else None


class PainelTVView(TemplateView):
    """Painel público exibido na TV. A primeira carga vem pronta do servidor."""
    template_name = 'swgfApp/painel_tv.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['senha_atual'], context['ultimas_senhas'] = dados_do_painel()
        return context


class PainelTVJsonView(View):
    """Mesmos dados em JSON, lidos pelo JavaScript do painel a cada 3 segundos."""

    def get(self, request):
        atual, ultimas = dados_do_painel()
        return JsonResponse({
            'senha_atual': {
                'codigo': atual.codigo,
                'mesa': numero_da_mesa(atual),
            } if atual else None,
            'ultimas_senhas': [
                {'codigo': senha.codigo, 'mesa': numero_da_mesa(senha)}
                for senha in ultimas
            ],
        })


# =============================================================================
# Atendimento (nível USER)
# =============================================================================

class FilaView(UsuarioLogadoMixin, TemplateView):
    """Tela de trabalho: mesa atual, fila de espera, chamadas e filtros."""
    template_name = 'swgfApp/fila.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sessao = self.request.user.sessao_ativa

        # O filtro atinge apenas a lista de espera. O botão CHAMAR sempre
        # segue a fila completa, senão o filtro mudaria a ordem de atendimento.
        fila = Senha.objects.fila_de_hoje()
        filtro_form = FiltroFilaForm(self.request.GET or None)
        if filtro_form.is_bound and filtro_form.is_valid():
            fila = filtro_form.filtrar(fila)

        context.update({
            'filtro_form': filtro_form,
            'senhas_aguardando': fila,
            'senhas_chamadas': Senha.objects.chamadas_de_hoje()[:10],
            'mesa_atual': sessao.mesa if sessao else None,
            'senha_em_atendimento': sessao.senha_em_atendimento() if sessao else None,
            # Só aparecem as mesas ativas e sem ninguém usando.
            'mesas_disponiveis': Mesa.objects.com_ocupacao().filter(
                status=Mesa.Status.DISPONIVEL, esta_ocupada=False
            ),
        })
        return context


class ChamarSenhaView(UsuarioLogadoMixin, ApenasPostMixin, View):
    """Botão CHAMAR: chama a próxima senha da fila para a mesa do usuário."""

    def post(self, request):
        sessao = request.user.sessao_ativa
        if not sessao:
            messages.error(request, "Escolha uma mesa antes de chamar uma senha.")
            return redirect('swgfApp:fila')

        senha = sessao.chamar_proxima()
        if senha:
            messages.success(request, f"Senha {senha.codigo} chamada para a Mesa {sessao.mesa.numero}.")
        else:
            messages.info(request, "Não há senhas aguardando.")
        return redirect('swgfApp:fila')


class FinalizarAtendimentoView(UsuarioLogadoMixin, ApenasPostMixin, View):
    """Encerra o atendimento atual: a senha passa de "chamada" para "atendida"."""

    def post(self, request):
        sessao = request.user.sessao_ativa
        senha = sessao.finalizar_atendimento() if sessao else None
        if senha:
            messages.success(request, f"Atendimento da senha {senha.codigo} finalizado.")
        else:
            messages.info(request, "Nenhum atendimento em andamento.")
        return redirect('swgfApp:fila')


class TrocarMesaView(UsuarioLogadoMixin, ApenasPostMixin, View):
    """Coloca o usuário na mesa escolhida. A regra está em SessaoMesa.entrar."""

    def post(self, request, pk):
        get_object_or_404(Mesa, pk=pk)  # mesa inexistente devolve erro 404
        try:
            SessaoMesa.entrar(request.user, pk)
        except RegraDeNegocioError as erro:
            messages.error(request, str(erro))
        return redirect('swgfApp:fila')


class SairMesaView(UsuarioLogadoMixin, ApenasPostMixin, View):
    """Libera a mesa do usuário, finalizando antes o atendimento em andamento."""

    def post(self, request):
        sessao = request.user.sessao_ativa
        if sessao:
            sessao.finalizar_atendimento()
        request.user.encerrar_sessoes()
        return redirect('swgfApp:fila')


class HistoricoView(UsuarioLogadoMixin, FiltroMixin, ListView):
    """Atendimentos registrados, com filtros e paginação. Abre mostrando hoje."""
    # select_related traz as tabelas ligadas em uma só consulta ao banco.
    queryset = Ticket.objects.filter(hora_atendimento__isnull=False).select_related(
        'senha', 'cliente', 'sessao_mesa__mesa', 'sessao_mesa__usuario'
    ).order_by('-data', '-hora_atendimento')
    template_name = 'swgfApp/historico.html'
    context_object_name = 'tickets'
    paginate_by = 20
    filtro_form_class = FiltroHistoricoForm
    filtro_padrao = {'periodo': 'hoje'}


class NotificacaoListView(UsuarioLogadoMixin, FiltroMixin, ListView):
    """Notificações do usuário logado."""
    queryset = Notificacao.objects.select_related('mensagem', 'data').order_by('-id')
    template_name = 'swgfApp/notificacoes.html'
    context_object_name = 'notificacoes'
    filtro_form_class = FiltroNotificacaoForm

    def get_queryset(self):
        # Cada usuário só enxerga as próprias notificações.
        return super().get_queryset().filter(usuario=self.request.user)


class LerNotificacaoView(UsuarioLogadoMixin, DetailView):
    """Mostra a notificação e a marca como lida."""
    template_name = 'swgfApp/ler_notificacao.html'
    context_object_name = 'notificacao'

    def get_queryset(self):
        # Filtrar pelo usuário impede abrir a notificação de outra pessoa.
        return Notificacao.objects.filter(usuario=self.request.user)

    def get_object(self, queryset=None):
        notificacao = super().get_object(queryset)
        notificacao.marcar_como_lida()
        return notificacao


# =============================================================================
# Gestão de mesas (nível ADMIN)
# =============================================================================

class MesaListView(AdministradorMixin, FiltroMixin, ListView):
    """Lista as mesas com status, ocupante e filtros."""
    queryset = Mesa.objects.com_ocupacao()
    template_name = 'swgfApp/mesas.html'
    context_object_name = 'mesas'
    filtro_form_class = FiltroMesaForm


class CriarMesaView(AdministradorMixin, ApenasPostMixin, View):
    """Cria uma mesa com o próximo número livre."""

    def post(self, request):
        ultima = Mesa.objects.order_by('-numero').first()
        numero = ultima.numero + 1 if ultima else 1
        Mesa.objects.create(numero=numero)
        messages.success(request, f"Mesa {numero} criada.")
        return redirect('swgfApp:mesas')


class MesaUpdateView(AdministradorMixin, UpdateView):
    """Edita o número da mesa."""
    model = Mesa
    form_class = MesaForm
    template_name = 'swgfApp/editar_mesa.html'
    context_object_name = 'mesa'
    success_url = reverse_lazy('swgfApp:mesas')


class AlternarMesaView(AdministradorMixin, ApenasPostMixin, View):
    """Ativa ou desativa a mesa, respeitando a regra de Mesa.alternar_status."""

    def post(self, request, pk):
        mesa = get_object_or_404(Mesa, pk=pk)
        try:
            mesa.alternar_status()
        except RegraDeNegocioError as erro:
            messages.error(request, str(erro))
        return redirect('swgfApp:mesas')


class LiberarMesaView(AdministradorMixin, ApenasPostMixin, View):
    """Tira o ocupante da mesa, para quando alguém saiu sem fazer logout."""

    def post(self, request, pk):
        mesa = get_object_or_404(Mesa, pk=pk)
        mesa.liberar()
        messages.success(request, f"Mesa {mesa.numero} liberada.")
        return redirect('swgfApp:mesas')


class MesaDeleteView(AdministradorMixin, ApenasPostMixin, MensagemSucessoDeleteMixin, DeleteView):
    """Deleta a mesa, exceto se estiver em uso. Os tickets perdem apenas a referência."""
    model = Mesa
    success_url = reverse_lazy('swgfApp:mesas')
    mensagem_sucesso = "Mesa deletada."

    def form_valid(self, form):
        if self.object.sessao_aberta:
            messages.error(self.request, "Não é possível deletar uma mesa em uso. Libere-a antes.")
            return redirect('swgfApp:mesas')
        return super().form_valid(form)


# =============================================================================
# Gestão de senhas (nível ADMIN)
# =============================================================================

class SenhaUpdateView(AdministradorMixin, UpdateView):
    """Edita o status da senha e os dados do cliente (ver SenhaForm)."""
    model = Senha
    form_class = SenhaForm
    template_name = 'swgfApp/editar_senha.html'
    context_object_name = 'senha'
    success_url = reverse_lazy('swgfApp:fila')


class SenhaDeleteView(AdministradorMixin, ApenasPostMixin, MensagemSucessoDeleteMixin, DeleteView):
    """Deleta a senha e, em cascata (1:1), o ticket. O cliente permanece no banco."""
    model = Senha
    success_url = reverse_lazy('swgfApp:fila')
    mensagem_sucesso = "Senha deletada."


# =============================================================================
# Mensagens (nível ADMIN)
# =============================================================================

class MensagemListView(AdministradorMixin, FiltroMixin, ListView):
    model = Mensagem
    template_name = 'swgfApp/mensagens.html'
    context_object_name = 'mensagens'
    filtro_form_class = FiltroMensagemForm
    ordering = ['-id']


class MensagemCreateView(AdministradorMixin, CreateView):
    """Cria a mensagem e notifica cada atendente ativo."""
    model = Mensagem
    form_class = MensagemForm
    template_name = 'swgfApp/criar_mensagem.html'
    success_url = reverse_lazy('swgfApp:mensagens')

    def form_valid(self, form):
        form.instance.usuario = self.request.user  # o remetente é quem está logado
        resposta = super().form_valid(form)
        notificar_atendentes(mensagem=self.object)
        return resposta


class MensagemUpdateView(AdministradorMixin, UpdateView):
    model = Mensagem
    form_class = MensagemForm
    template_name = 'swgfApp/editar_mensagem.html'
    context_object_name = 'mensagem'
    success_url = reverse_lazy('swgfApp:mensagens')


class MensagemDeleteView(AdministradorMixin, ApenasPostMixin, MensagemSucessoDeleteMixin, DeleteView):
    """Deleta a mensagem e, em cascata, as notificações ligadas a ela."""
    model = Mensagem
    success_url = reverse_lazy('swgfApp:mensagens')
    mensagem_sucesso = "Mensagem deletada."


# =============================================================================
# Notas (nível ADMIN)
# =============================================================================

class NotaListView(AdministradorMixin, FiltroMixin, ListView):
    model = Nota
    template_name = 'swgfApp/notas.html'
    context_object_name = 'notas'
    filtro_form_class = FiltroNotaForm
    ordering = ['-id']


class NotaCreateView(AdministradorMixin, CreateView):
    model = Nota
    form_class = NotaForm
    template_name = 'swgfApp/criar_nota.html'
    success_url = reverse_lazy('swgfApp:notas')

    def form_valid(self, form):
        form.instance.usuario = self.request.user  # o autor é quem está logado
        return super().form_valid(form)


class NotaUpdateView(AdministradorMixin, UpdateView):
    model = Nota
    form_class = NotaForm
    template_name = 'swgfApp/editar_nota.html'
    context_object_name = 'nota'
    success_url = reverse_lazy('swgfApp:notas')


class NotaDeleteView(AdministradorMixin, ApenasPostMixin, MensagemSucessoDeleteMixin, DeleteView):
    model = Nota
    success_url = reverse_lazy('swgfApp:notas')
    mensagem_sucesso = "Nota deletada."


# =============================================================================
# Datas e feriados (nível ADMIN)
# =============================================================================

class DataListView(AdministradorMixin, FiltroMixin, ListView):
    model = Data
    template_name = 'swgfApp/datas.html'
    context_object_name = 'datas'
    filtro_form_class = FiltroDataForm
    ordering = ['-dia']


class DataCreateView(AdministradorMixin, CreateView):
    """Cadastra a data e notifica os atendentes (antes ninguém era avisado)."""
    model = Data
    form_class = DataForm
    template_name = 'swgfApp/criar_data.html'
    success_url = reverse_lazy('swgfApp:datas')

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        resposta = super().form_valid(form)
        notificar_atendentes(data=self.object)
        return resposta


class DataUpdateView(AdministradorMixin, UpdateView):
    model = Data
    form_class = DataForm
    template_name = 'swgfApp/editar_data.html'
    context_object_name = 'registro'
    success_url = reverse_lazy('swgfApp:datas')


class DataDeleteView(AdministradorMixin, ApenasPostMixin, MensagemSucessoDeleteMixin, DeleteView):
    model = Data
    success_url = reverse_lazy('swgfApp:datas')
    mensagem_sucesso = "Data deletada."
