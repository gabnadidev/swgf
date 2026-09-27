from django.urls import path
from . import views

app_name = 'swgfApp'

urlpatterns = [
    path('', views.home, name='home'),
    path('totem/', views.totem, name='totem'),
    path('senha-emitida/<int:ticket_id>/', views.senha_emitida, name='senha_emitida'),
]