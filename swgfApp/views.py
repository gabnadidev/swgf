from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import Cliente, Senha, Ticket
from .forms import RetirarSenhaForm


def home(request):
    return render(request, 'swgfApp/home.html')


def totem(request):
    """
    Tela do Totem: exibe o formulário para o cliente retirar a senha.
    Se for POST (envio), cria o Cliente, a Senha e o Ticket, e redireciona
    para a tela de confirmação.
    """
    if request.method == 'POST':
        form = RetirarSenhaForm(request.POST)
        if form.is_valid():
            # 1. Cria o cliente
            cliente = Cliente.objects.create(
                nome=form.cleaned_data['nome'],
                tipo_prioridade=form.cleaned_data['tipo_prioridade'],
            )

            # 2. Gera o código da senha (ex: A0001, A0002...)
            hoje = timezone.now().date()
            total_hoje = Ticket.objects.filter(data=hoje).count()
            codigo = f"A{total_hoje + 1:04d}"

            # 3. Cria a senha
            senha = Senha.objects.create(
                codigo=codigo,
                status='aguardando',
            )

            # 4. Cria o ticket (liga cliente + senha)
            ticket = Ticket.objects.create(
                cliente=cliente,
                senha=senha,
            )

            # 5. Redireciona para a tela de confirmação
            return redirect('swgfApp:senha_emitida', ticket_id=ticket.id)
    else:
        form = RetirarSenhaForm()

    return render(request, 'swgfApp/totem.html', {'form': form})


def senha_emitida(request, ticket_id):
    """
    Tela de confirmação: mostra a senha gerada e o horário.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return render(request, 'swgfApp/senha_emitida.html', {'ticket': ticket})