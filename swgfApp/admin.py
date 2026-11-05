"""
Configuração do painel /admin/ do Django, para cada modelo do sistema:
    list_display  -> colunas da listagem
    list_filter   -> filtros da barra lateral
    search_fields -> campos pesquisados pela caixa de busca
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Cliente, Data, Mensagem, Mesa, Nota, Notificacao, Senha, SessaoMesa, Ticket, Usuario,
)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Herda o admin padrão de usuários e acrescenta os campos do SWGF."""
    list_display = ('username', 'email', 'first_name', 'is_adm', 'status', 'is_active')
    list_filter = ('is_adm', 'status', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Informações SWGF', {'fields': ('is_adm', 'status')}),
    )


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'tipo_prioridade')
    search_fields = ('nome',)
    list_filter = ('tipo_prioridade',)


@admin.register(Senha)
class SenhaAdmin(admin.ModelAdmin):
    list_display = ('id', 'codigo', 'status')
    search_fields = ('codigo',)
    list_filter = ('status',)


@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero', 'status')
    list_filter = ('status',)


@admin.register(SessaoMesa)
class SessaoMesaAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'mesa', 'data_inicio', 'data_fim')
    list_filter = ('mesa', 'usuario')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'senha', 'sessao_mesa', 'hora_emissao', 'hora_atendimento', 'data')
    list_filter = ('data',)
    search_fields = ('cliente__nome', 'senha__codigo')


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'status', 'conteudo')
    list_filter = ('status',)


@admin.register(Data)
class DataAdmin(admin.ModelAdmin):
    list_display = ('id', 'dia', 'feriado', 'status', 'usuario')
    list_filter = ('status',)
    search_fields = ('feriado',)


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'mensagem', 'data', 'visualizada')
    list_filter = ('visualizada',)


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'conteudo')
