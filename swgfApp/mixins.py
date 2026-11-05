"""
Mixins: pequenas classes que acrescentam um comportamento às views.
Como as views são baseadas em classes, basta herdar destes mixins para
reaproveitar o controle de acesso e os filtros em várias telas.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect


class UsuarioLogadoMixin(LoginRequiredMixin):
    """Nível USER: basta estar logado. Quem não está vai para a tela de login."""


class AdministradorMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Nível ADMIN: além de logado, o usuário precisa ter is_adm = True."""

    def test_func(self):
        # O Django chama este método para decidir se o acesso é permitido.
        return self.request.user.is_adm

    def handle_no_permission(self):
        # Sem login: o comportamento padrão leva para a tela de login.
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        # Logado, mas sem permissão: explica o motivo e volta para a fila.
        messages.error(self.request, "Esta área é exclusiva para administradores.")
        return redirect('swgfApp:fila')


class ApenasPostMixin:
    """
    Aceita somente POST. Toda ação que altera o banco (deletar, ativar, chamar...)
    usa este mixin: um simples link (GET) não pode alterar dados, pois o navegador
    pode abrir links sozinho e não há proteção CSRF nesse caso.
    """
    http_method_names = ['post', 'options']


class FiltroMixin:
    """
    Aplica um formulário de filtro (forms.py) sobre a lista de uma ListView.

    Atributos que a view define:
        filtro_form_class: formulário com o método filtrar(queryset).
        filtro_padrao: filtro usado quando a URL não traz nenhum parâmetro.
    """
    filtro_form_class = None
    filtro_padrao = None

    def get_queryset(self):
        queryset = super().get_queryset()
        # Só o parâmetro de paginação não conta como filtro escolhido.
        parametros = self.request.GET.copy()
        parametros.pop('page', None)
        self.filtro_form = self.filtro_form_class(parametros or self.filtro_padrao)
        if self.filtro_form.is_bound and self.filtro_form.is_valid():
            queryset = self.filtro_form.filtrar(queryset)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtro_form'] = self.filtro_form
        # Mantém os filtros ao trocar de página na paginação.
        parametros = self.request.GET.copy()
        parametros.pop('page', None)
        context['parametros_filtro'] = parametros.urlencode()
        return context


class MensagemSucessoDeleteMixin:
    """Mostra um aviso depois de deletar um registro em uma DeleteView."""
    mensagem_sucesso = "Registro deletado."

    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(self.request, self.mensagem_sucesso)
        return resposta
