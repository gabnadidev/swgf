"""
Formulários do sistema.

Cada formulário valida os dados no servidor. Antes, as views liam
request.POST direto, então só o HTML do navegador conferia os campos.

Os formulários de filtro têm o método filtrar(queryset), chamado pelo
FiltroMixin (mixins.py), e usam method="get": os filtros ficam na URL.
"""

from datetime import timedelta

from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import Cliente, Data, Mensagem, Mesa, Nota, Notificacao, Senha, Usuario

# Opção vazia nos filtros: significa "não filtrar por este campo".
TODOS = [('', 'Todos')]


def campo_data(label):
    """Campo de data opcional com o calendário do navegador."""
    return forms.DateField(
        label=label,
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )


# =============================================================================
# Formulários de cadastro e edição
# =============================================================================

class RetirarSenhaForm(forms.Form):
    """Formulário do totem, onde o cliente informa nome e prioridade."""
    nome = forms.CharField(
        max_length=255,
        label="Nome",
        widget=forms.TextInput(attrs={'placeholder': 'Digite seu nome', 'autofocus': True}),
    )
    tipo_prioridade = forms.ChoiceField(
        choices=Cliente.Prioridade.choices,
        label="Prioridade",
        initial=Cliente.Prioridade.NORMAL,
    )


class MesaForm(forms.ModelForm):
    """Edição do número da mesa. O unique do modelo já barra número repetido."""

    class Meta:
        model = Mesa
        fields = ['numero']

    def clean_numero(self):
        numero = self.cleaned_data['numero']
        if numero < 1:
            raise forms.ValidationError("O número da mesa deve ser maior que zero.")
        return numero


class SenhaForm(forms.ModelForm):
    """Edição da senha pelo administrador: status e dados do cliente ligado a ela."""
    nome = forms.CharField(max_length=255, label="Nome do cliente", required=False)
    tipo_prioridade = forms.ChoiceField(
        choices=Cliente.Prioridade.choices, label="Prioridade", required=False
    )

    class Meta:
        model = Senha
        fields = ['status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A partir da senha chega-se ao ticket (1:1) e dele ao cliente.
        ticket = getattr(self.instance, 'ticket', None)
        self.cliente = ticket.cliente if ticket else None

        if self.cliente:
            self.fields['nome'].required = True
            self.fields['nome'].initial = self.cliente.nome
            self.fields['tipo_prioridade'].initial = (
                self.cliente.tipo_prioridade or Cliente.Prioridade.NORMAL
            )
        else:
            # Senha sem cliente: os campos do cliente não fazem sentido.
            del self.fields['nome']
            del self.fields['tipo_prioridade']

    def save(self, commit=True):
        # ajustar_status mantém o ticket coerente com o novo status.
        self.instance.ajustar_status(self.cleaned_data['status'])
        if self.cliente:
            self.cliente.nome = self.cleaned_data['nome']
            self.cliente.tipo_prioridade = self.cleaned_data['tipo_prioridade']
            self.cliente.save()
        return self.instance


class MensagemForm(forms.ModelForm):
    class Meta:
        model = Mensagem
        fields = ['conteudo']
        widgets = {'conteudo': forms.Textarea(attrs={'rows': 6})}


class NotaForm(forms.ModelForm):
    class Meta:
        model = Nota
        fields = ['conteudo']
        widgets = {'conteudo': forms.Textarea(attrs={'rows': 8})}


class DataForm(forms.ModelForm):
    class Meta:
        model = Data
        fields = ['dia', 'feriado', 'status']
        widgets = {
            'dia': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'feriado': forms.TextInput(attrs={'placeholder': 'Ex: Natal, Ano Novo...'}),
        }
        # O unique do campo "dia" barra data repetida com esta mensagem.
        error_messages = {'dia': {'unique': 'Esta data já está cadastrada.'}}

    def clean_feriado(self):
        # Guarda vazio como NULL, para o valor ser sempre "tem nome" ou "não tem".
        return self.cleaned_data['feriado'] or None


# =============================================================================
# Formulários de filtro
# =============================================================================

class FiltroFilaForm(forms.Form):
    """Filtro da tela da fila: busca por senha ou cliente, e por prioridade."""
    busca = forms.CharField(label="Senha ou cliente", required=False)
    prioridade = forms.ChoiceField(label="Prioridade", required=False,
                                   choices=TODOS + Cliente.Prioridade.choices)

    def filtrar(self, queryset):
        dados = self.cleaned_data
        if dados['busca']:
            queryset = queryset.filter(
                Q(codigo__icontains=dados['busca'])
                | Q(ticket__cliente__nome__icontains=dados['busca'])
            )
        if dados['prioridade']:
            queryset = queryset.filter(ticket__cliente__tipo_prioridade=dados['prioridade'])
        return queryset


class FiltroHistoricoForm(forms.Form):
    """Filtro principal do sistema, com período, mesa, atendente, prioridade e status."""
    PERIODOS = [
        ('', 'Todo o período'),
        ('hoje', 'Hoje'),
        ('7dias', 'Últimos 7 dias'),
        ('30dias', 'Últimos 30 dias'),
    ]

    busca = forms.CharField(label="Senha ou cliente", required=False)
    periodo = forms.ChoiceField(label="Período", required=False, choices=PERIODOS)
    data_inicio = campo_data("De")
    data_fim = campo_data("Até")
    mesa = forms.ModelChoiceField(label="Mesa", required=False, queryset=Mesa.objects.all(),
                                  empty_label="Todas")
    atendente = forms.ModelChoiceField(label="Atendente", required=False, empty_label="Todos",
                                       queryset=Usuario.objects.order_by('username'))
    prioridade = forms.ChoiceField(label="Prioridade", required=False,
                                   choices=TODOS + Cliente.Prioridade.choices)
    status = forms.ChoiceField(label="Status", required=False, choices=TODOS + [
        (Senha.Status.CHAMADA, Senha.Status.CHAMADA.label),
        (Senha.Status.ATENDIDA, Senha.Status.ATENDIDA.label),
    ])

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get('data_inicio'), dados.get('data_fim')
        if inicio and fim and inicio > fim:
            raise forms.ValidationError("A data inicial não pode ser depois da data final.")
        return dados

    def filtrar(self, queryset):
        dados = self.cleaned_data
        hoje = timezone.localdate()

        # Datas preenchidas à mão têm preferência sobre o período pronto.
        if dados['data_inicio'] or dados['data_fim']:
            if dados['data_inicio']:
                queryset = queryset.filter(data__gte=dados['data_inicio'])
            if dados['data_fim']:
                queryset = queryset.filter(data__lte=dados['data_fim'])
        elif dados['periodo'] == 'hoje':
            queryset = queryset.filter(data=hoje)
        elif dados['periodo'] == '7dias':
            queryset = queryset.filter(data__gte=hoje - timedelta(days=6))
        elif dados['periodo'] == '30dias':
            queryset = queryset.filter(data__gte=hoje - timedelta(days=29))

        if dados['busca']:
            queryset = queryset.filter(
                Q(senha__codigo__icontains=dados['busca'])
                | Q(cliente__nome__icontains=dados['busca'])
            )
        if dados['mesa']:
            queryset = queryset.filter(sessao_mesa__mesa=dados['mesa'])
        if dados['atendente']:
            queryset = queryset.filter(sessao_mesa__usuario=dados['atendente'])
        if dados['prioridade']:
            queryset = queryset.filter(cliente__tipo_prioridade=dados['prioridade'])
        if dados['status']:
            queryset = queryset.filter(senha__status=dados['status'])
        return queryset


class FiltroMesaForm(forms.Form):
    status = forms.ChoiceField(label="Status", required=False, choices=TODOS + Mesa.Status.choices)
    ocupacao = forms.ChoiceField(label="Ocupação", required=False, choices=TODOS + [
        ('livre', 'Livre'),
        ('ocupada', 'Ocupada'),
    ])

    def filtrar(self, queryset):
        dados = self.cleaned_data
        if dados['status']:
            queryset = queryset.filter(status=dados['status'])
        # "esta_ocupada" é calculado em Mesa.objects.com_ocupacao() (models.py).
        if dados['ocupacao']:
            queryset = queryset.filter(esta_ocupada=dados['ocupacao'] == 'ocupada')
        return queryset


class FiltroMensagemForm(forms.Form):
    busca = forms.CharField(label="Conteúdo", required=False)
    status = forms.ChoiceField(label="Status", required=False,
                               choices=TODOS + Mensagem.Status.choices)

    def filtrar(self, queryset):
        dados = self.cleaned_data
        if dados['busca']:
            queryset = queryset.filter(conteudo__icontains=dados['busca'])
        if dados['status']:
            queryset = queryset.filter(status=dados['status'])
        return queryset


class FiltroNotaForm(forms.Form):
    busca = forms.CharField(label="Conteúdo", required=False)

    def filtrar(self, queryset):
        if self.cleaned_data['busca']:
            queryset = queryset.filter(conteudo__icontains=self.cleaned_data['busca'])
        return queryset


class FiltroDataForm(forms.Form):
    busca = forms.CharField(label="Feriado", required=False)
    status = forms.ChoiceField(label="Status", required=False, choices=TODOS + Data.Status.choices)
    data_inicio = campo_data("De")
    data_fim = campo_data("Até")

    def filtrar(self, queryset):
        dados = self.cleaned_data
        if dados['busca']:
            queryset = queryset.filter(feriado__icontains=dados['busca'])
        if dados['status']:
            queryset = queryset.filter(status=dados['status'])
        if dados['data_inicio']:
            queryset = queryset.filter(dia__gte=dados['data_inicio'])
        if dados['data_fim']:
            queryset = queryset.filter(dia__lte=dados['data_fim'])
        return queryset


class FiltroNotificacaoForm(forms.Form):
    situacao = forms.ChoiceField(label="Situação", required=False, choices=TODOS + [
        ('nao_lidas', 'Não lidas'),
        ('lidas', 'Lidas'),
    ])

    def filtrar(self, queryset):
        situacao = self.cleaned_data['situacao']
        if situacao:
            queryset = queryset.filter(visualizada=situacao == 'lidas')
        return queryset
