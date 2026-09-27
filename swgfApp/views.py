from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import Cliente, Senha, Ticket
from .forms import RetirarSenhaForm
from django.contrib.auth.decorators import login_required
from .models import Cliente, Senha, Ticket, SessaoMesa, Mesa
from django.http import JsonResponse



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


@login_required
def fila(request):
    senhas_aguardando = Senha.objects.filter(status='aguardando').order_by('id')
    senhas_atendidas = Senha.objects.filter(status__in=['chamada', 'atendida']).order_by('-id')[:10]

    context = {
        'senhas_aguardando': senhas_aguardando,
        'senhas_atendidas': senhas_atendidas,
    }
    return render(request, 'swgfApp/fila.html', context)


@login_required
def chamar_senha(request):
    """
    Chama a próxima senha da fila (a mais antiga com status 'aguardando').
    Cria uma SessaoMesa se o atendente ainda não tiver uma ativa.
    """
    # 1. Pega a próxima senha da fila
    proxima_senha = Senha.objects.filter(status='aguardando').order_by('id').first()

    if not proxima_senha:
        # Se não houver senha, volta para a fila com uma mensagem
        return redirect('swgfApp:fila')

    # 2. Verifica se o atendente tem uma sessão de mesa ativa
    sessao = SessaoMesa.objects.filter(usuario=request.user, data_fim__isnull=True).first()

    if not sessao:
        # Se não tiver, cria uma para a Mesa 1 (temporário)
        mesa = Mesa.objects.first()
        if not mesa:
            # Se não existir nenhuma mesa, cria a Mesa 1
            mesa = Mesa.objects.create(numero=1, status='disponivel')
        sessao = SessaoMesa.objects.create(usuario=request.user, mesa=mesa)

    # 3. Atualiza o status da senha
    proxima_senha.status = 'chamada'
    proxima_senha.save()

    # 4. Atualiza o ticket correspondente
    ticket = Ticket.objects.filter(senha=proxima_senha).first()
    if ticket:
        ticket.hora_atendimento = timezone.now().time()
        ticket.sessao_mesa = sessao
        ticket.save()

    # 5. Redireciona de volta para a fila
    return redirect('swgfApp:fila')

def painel_tv(request):
    """
    Painel público (TV) que mostra a senha atual e as últimas chamadas.
    Não requer login.
    """
    # Pega a última senha chamada (status 'chamada')
    senha_atual = Senha.objects.filter(status='chamada').order_by('-id').first()

    # Pega as 5 últimas senhas chamadas (excluindo a atual)
    ultimas_senhas = Senha.objects.filter(status='chamada').order_by('-id')[1:6]

    context = {
        'senha_atual': senha_atual,
        'ultimas_senhas': ultimas_senhas,
    }
    return render(request, 'swgfApp/painel_tv.html', context)


def painel_tv_json(request):
    """
    Retorna os dados do painel TV em formato JSON.
    Usado pelo JavaScript para atualizar a tela sem recarregar.
    """
    senha_atual = Senha.objects.filter(status='chamada').order_by('-id').first()

    # Função auxiliar para pegar o número da mesa de uma senha
    def get_mesa(senha):
        ticket = senha.ticket_set.first()
        if ticket and ticket.sessao_mesa and ticket.sessao_mesa.mesa:
            return ticket.sessao_mesa.mesa.numero
        return None

    # Monta o JSON
    data = {
        'senha_atual': {
            'codigo': senha_atual.codigo,
            'mesa': get_mesa(senha_atual),
        } if senha_atual else None,
        'ultimas_senhas': [
            {
                'codigo': s.codigo,
                'mesa': get_mesa(s),
            }
            for s in Senha.objects.filter(status='chamada').order_by('-id')[1:6]
        ]
    }

    return JsonResponse(data)


@login_required
def mesas(request):
    """
    Lista todas as mesas com seus status.
    Permite ativar/desativar e criar novas mesas.
    """
    lista_mesas = Mesa.objects.all().order_by('numero')
    return render(request, 'swgfApp/mesas.html', {'mesas': lista_mesas})


@login_required
def alternar_mesa(request, mesa_id):
    """
    Ativa ou desativa uma mesa (inverte o status).
    """
    mesa = get_object_or_404(Mesa, id=mesa_id)
    if mesa.status == 'disponivel':
        mesa.status = 'inativa'
    else:
        mesa.status = 'disponivel'
    mesa.save()
    return redirect('swgfApp:mesas')


@login_required
def criar_mesa(request):
    """
    Cria uma nova mesa com o próximo número disponível.
    """
    ultimo_numero = Mesa.objects.order_by('-numero').first()
    proximo_numero = (ultimo_numero.numero + 1) if ultimo_numero else 1

    Mesa.objects.create(numero=proximo_numero, status='disponivel')
    return redirect('swgfApp:mesas')

@login_required
def editar_mesa(request, mesa_id):
    """Edita o número de uma mesa."""
    mesa = get_object_or_404(Mesa, id=mesa_id)

    if request.method == 'POST':
        novo_numero = request.POST.get('numero')
        if novo_numero:
            mesa.numero = novo_numero
            mesa.save()
        return redirect('swgfApp:mesas')

    return render(request, 'swgfApp/editar_mesa.html', {'mesa': mesa})


@login_required
def deletar_mesa(request, mesa_id):
    """Deleta uma mesa (os tickets perdem a referência, mas não são deletados)."""
    mesa = get_object_or_404(Mesa, id=mesa_id)
    mesa.delete()
    return redirect('swgfApp:mesas')


@login_required
def editar_senha(request, senha_id):
    """
    Permite editar o status da senha e os dados do cliente associado.
    """
    senha = get_object_or_404(Senha, id=senha_id)
    ticket = Ticket.objects.filter(senha=senha).first()

    if request.method == 'POST':
        # Atualiza o status da senha
        novo_status = request.POST.get('status')
        if novo_status:
            senha.status = novo_status
            senha.save()

        # Atualiza os dados do cliente (se houver ticket com cliente)
        if ticket and ticket.cliente:
            cliente = ticket.cliente
            cliente.nome = request.POST.get('nome', cliente.nome)
            cliente.tipo_prioridade = request.POST.get('tipo_prioridade', cliente.tipo_prioridade)
            cliente.save()

        return redirect('swgfApp:fila')

    context = {
        'senha': senha,
        'ticket': ticket,
        'cliente': ticket.cliente if ticket else None,
    }
    return render(request, 'swgfApp/editar_senha.html', context)


@login_required
def deletar_senha(request, senha_id):
    """
    Deleta a senha e o ticket associado. O cliente permanece no banco.
    """
    senha = get_object_or_404(Senha, id=senha_id)
    senha.delete()  # O ticket é deletado em cascata (não configuramos SET_NULL aqui, é CASCADE por padrão)
    return redirect('swgfApp:fila')