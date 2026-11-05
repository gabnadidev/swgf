"""
Rotas do app. Cada URL aponta para uma view baseada em classe, por isso o
".as_view()", que transforma a classe em algo que o Django consegue chamar.
"""

from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = 'swgfApp'  # permite usar nomes como 'swgfApp:fila' nos templates

urlpatterns = [
    # Páginas públicas
    path('', views.HomeView.as_view(), name='home'),
    path('totem/', views.TotemView.as_view(), name='totem'),
    path('senha-emitida/<int:pk>/', views.SenhaEmitidaView.as_view(), name='senha_emitida'),
    path('painel/', views.PainelTVView.as_view(), name='painel_tv'),
    path('painel/json/', views.PainelTVJsonView.as_view(), name='painel_tv_json'),

    # Autenticação (o logout usa a classe pronta do Django e é feito por POST)
    path('login/', views.LoginUsuarioView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # Atendimento (admin e user)
    path('fila/', views.FilaView.as_view(), name='fila'),
    path('chamar/', views.ChamarSenhaView.as_view(), name='chamar_senha'),
    path('finalizar/', views.FinalizarAtendimentoView.as_view(), name='finalizar_atendimento'),
    path('mesas/<int:pk>/trocar/', views.TrocarMesaView.as_view(), name='trocar_mesa'),
    path('mesas/sair/', views.SairMesaView.as_view(), name='sair_mesa'),
    path('historico/', views.HistoricoView.as_view(), name='historico'),
    path('notificacoes/', views.NotificacaoListView.as_view(), name='notificacoes'),
    path('notificacoes/<int:pk>/ler/', views.LerNotificacaoView.as_view(), name='ler_notificacao'),

    # Mesas (somente admin)
    path('mesas/', views.MesaListView.as_view(), name='mesas'),
    path('mesas/criar/', views.CriarMesaView.as_view(), name='criar_mesa'),
    path('mesas/<int:pk>/editar/', views.MesaUpdateView.as_view(), name='editar_mesa'),
    path('mesas/<int:pk>/alternar/', views.AlternarMesaView.as_view(), name='alternar_mesa'),
    path('mesas/<int:pk>/liberar/', views.LiberarMesaView.as_view(), name='liberar_mesa'),
    path('mesas/<int:pk>/deletar/', views.MesaDeleteView.as_view(), name='deletar_mesa'),

    # Senhas (somente admin)
    path('senhas/<int:pk>/editar/', views.SenhaUpdateView.as_view(), name='editar_senha'),
    path('senhas/<int:pk>/deletar/', views.SenhaDeleteView.as_view(), name='deletar_senha'),

    # Mensagens (somente admin)
    path('mensagens/', views.MensagemListView.as_view(), name='mensagens'),
    path('mensagens/criar/', views.MensagemCreateView.as_view(), name='criar_mensagem'),
    path('mensagens/<int:pk>/editar/', views.MensagemUpdateView.as_view(), name='editar_mensagem'),
    path('mensagens/<int:pk>/deletar/', views.MensagemDeleteView.as_view(), name='deletar_mensagem'),

    # Notas (somente admin)
    path('notas/', views.NotaListView.as_view(), name='notas'),
    path('notas/criar/', views.NotaCreateView.as_view(), name='criar_nota'),
    path('notas/<int:pk>/editar/', views.NotaUpdateView.as_view(), name='editar_nota'),
    path('notas/<int:pk>/deletar/', views.NotaDeleteView.as_view(), name='deletar_nota'),

    # Datas (somente admin)
    path('datas/', views.DataListView.as_view(), name='datas'),
    path('datas/criar/', views.DataCreateView.as_view(), name='criar_data'),
    path('datas/<int:pk>/editar/', views.DataUpdateView.as_view(), name='editar_data'),
    path('datas/<int:pk>/deletar/', views.DataDeleteView.as_view(), name='deletar_data'),
]
