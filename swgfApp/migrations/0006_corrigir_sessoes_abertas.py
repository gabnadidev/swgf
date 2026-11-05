"""
Corrige dados antigos, gravados antes das regras de ocupação de mesas:
  - fecha sessões abertas cuja mesa já foi apagada;
  - fecha sessões a mais do mesmo usuário, mantendo só a mais recente;
  - quando várias pessoas estão na mesma mesa, mantém só a sessão mais recente.

Nenhum registro é apagado: apenas o campo data_fim é preenchido.
"""

from django.db import migrations
from django.utils import timezone


def fechar_sessoes_invalidas(apps, schema_editor):
    SessaoMesa = apps.get_model('swgfApp', 'SessaoMesa')
    agora = timezone.now()

    abertas = SessaoMesa.objects.filter(data_fim__isnull=True)
    abertas.filter(mesa__isnull=True).update(data_fim=agora)

    usuarios_vistos, mesas_vistas = set(), set()
    # Da sessão mais nova para a mais antiga: a primeira de cada um é mantida.
    for sessao in abertas.order_by('-data_inicio', '-id'):
        if sessao.usuario_id in usuarios_vistos or sessao.mesa_id in mesas_vistas:
            sessao.data_fim = agora
            sessao.save(update_fields=['data_fim'])
        else:
            usuarios_vistos.add(sessao.usuario_id)
            mesas_vistas.add(sessao.mesa_id)


class Migration(migrations.Migration):

    dependencies = [
        ('swgfApp', '0005_regras_b2'),
    ]

    operations = [
        # Não há como reverter: não se sabe quais sessões estavam abertas.
        migrations.RunPython(fechar_sessoes_invalidas, migrations.RunPython.noop),
    ]
