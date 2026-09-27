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
]