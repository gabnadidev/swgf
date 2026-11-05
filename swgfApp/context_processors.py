"""
Context processors: acrescentam variáveis a todos os templates do sistema.
São registrados em TEMPLATES, no arquivo swgf/settings.py.
"""

from .models import Notificacao


def notificacoes_nao_lidas(request):
    """Disponibiliza o número de notificações não lidas para o sino do topo."""
    if request.user.is_authenticated:
        total = Notificacao.objects.filter(usuario=request.user, visualizada=False).count()
        return {'notificacoes_nao_lidas': total}
    return {'notificacoes_nao_lidas': 0}
