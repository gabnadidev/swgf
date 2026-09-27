from django import forms


class RetirarSenhaForm(forms.Form):
    nome = forms.CharField(
        max_length=255,
        label="Nome",
        widget=forms.TextInput(attrs={
            'placeholder': 'Digite seu nome',
            'autofocus': True,
        })
    )

    tipo_prioridade = forms.ChoiceField(
        choices=[
            ('normal', 'Normal'),
            ('idoso', 'Idoso (60+)'),
            ('gestante', 'Gestante'),
            ('pcd', 'Pessoa com Deficiência'),
        ],
        label="Prioridade",
        initial='normal',
    )