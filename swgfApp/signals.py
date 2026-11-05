"""
Sinais: funções que o Django executa automaticamente quando algo acontece.
"""

from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver


@receiver(user_logged_out)
def liberar_mesa_ao_sair(sender, request, user, **kwargs):
    """
    Ao fazer logout, finaliza o atendimento e libera a mesa do usuário.
    Antes, a sessão ficava aberta e a mesa continuava presa para sempre.
    """
    if user is None:
        return
    sessao = user.sessao_ativa
    if sessao:
        sessao.finalizar_atendimento()
    user.encerrar_sessoes()
