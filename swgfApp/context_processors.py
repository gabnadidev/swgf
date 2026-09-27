from .models import Notificacao


def notificacoes_nao_lidas(request):
    """Injeta o contador de notificações não lidas em todos os templates."""
    if request.user.is_authenticated:
        total = Notificacao.objects.filter(usuario=request.user, visualizada=False).count()
        return {'notificacoes_nao_lidas': total}
    return {'notificacoes_nao_lidas': 0}