from django.shortcuts import render


def home(request):
    """
    Página inicial do sistema. Vai servir como um 'menu' para
    acessar as diferentes áreas: Totem, Painel TV e Workspace.
    """
    return render(request, 'swgfApp/home.html')
