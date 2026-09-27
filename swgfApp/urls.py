from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'swgfApp'

urlpatterns = [
    path('', views.home, name='home'),
    path('totem/', views.totem, name='totem'),
    path('senha-emitida/<int:ticket_id>/', views.senha_emitida, name='senha_emitida'),

    # Autenticação
    path('login/', auth_views.LoginView.as_view(
        template_name='swgfApp/login.html'
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Workspace
    path('fila/', views.fila, name='fila'),
    path('chamar/', views.chamar_senha, name='chamar_senha'),
    path('painel/', views.painel_tv, name='painel_tv'),
    path('painel/json/', views.painel_tv_json, name='painel_tv_json'),
    path('mesas/', views.mesas, name='mesas'),
    path('mesas/<int:mesa_id>/alternar/', views.alternar_mesa, name='alternar_mesa'),
    path('mesas/criar/', views.criar_mesa, name='criar_mesa'),
    path('mesas/<int:mesa_id>/editar/', views.editar_mesa, name='editar_mesa'),
    path('mesas/<int:mesa_id>/deletar/', views.deletar_mesa, name='deletar_mesa'),
    path('senhas/<int:senha_id>/editar/', views.editar_senha, name='editar_senha'),
    path('senhas/<int:senha_id>/deletar/', views.deletar_senha, name='deletar_senha'),
    
    # Mensagens (ADM)
    path('mensagens/', views.mensagens, name='mensagens'),
    path('mensagens/criar/', views.criar_mensagem, name='criar_mensagem'),
    path('mensagens/<int:mensagem_id>/editar/', views.editar_mensagem, name='editar_mensagem'),
    path('mensagens/<int:mensagem_id>/deletar/', views.deletar_mensagem, name='deletar_mensagem'),
    
    # Notas (ADM)
    path('notas/', views.notas, name='notas'),
    path('notas/criar/', views.criar_nota, name='criar_nota'),
    path('notas/<int:nota_id>/editar/', views.editar_nota, name='editar_nota'),
    path('notas/<int:nota_id>/deletar/', views.deletar_nota, name='deletar_nota'),

    # Datas (ADM)
    path('datas/', views.datas, name='datas'),
    path('datas/criar/', views.criar_data, name='criar_data'),
    path('datas/<int:data_id>/editar/', views.editar_data, name='editar_data'),
    path('datas/<int:data_id>/deletar/', views.deletar_data, name='deletar_data'),
]